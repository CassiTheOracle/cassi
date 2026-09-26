"""The level memory: what the player knows of a level, kept in a field.

The player sees the game through a keyhole and forgets everything it walked past;
this module gives it a memory that is a field rather than a dictionary of cells.
The memory is the Cassi two-fluid scalar sector running on the level's own grid,
one Yang/Yin pair per remembered channel.  Perception writes a cell's polarity:
the field then lets the polarity decay toward the Yang equilibrium, so a memory
fades unless the player looks at it again.  Nothing is stored beside the field,
and what the player is told is read back out of the field.

Three fields live on the same grid, with the law each one needs:

* the **memory** (terrain, goal, blocked, trail) is two-fluid conversion only:
  the canonical solver's `conv = -lam*(ey - PHI*ei)`, `d(ey)/dt = conv`,
  `d(ei)/dt = -conv`, RK2 with `dt` = one game turn.  The sum `ey + ei` is
  conserved, so what fades is the content, with half-life `ln2/(lam*(1+PHI))`
  turns.  A place does not move, so this sector has no flow term.
* the **route** is a distance field: the shortest walk from every remembered
  cell to what the player is heading for, relaxed to its fixed point on the same
  grid.  A cell the player cannot stand on holds no distance and passes none on,
  and a cell that refused the player holds none either, so the route goes around
  it.  This is the law a route needs: it settles rather than fades.
* the **dungeon** is one memory per level, plus the turns the player has spent
  elsewhere: a level left behind keeps fading by the same law while the player
  is away, and is still there (what remains of it) on the way back.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

import numpy as np

PHI = (1.0 + math.sqrt(5.0)) / 2.0
EQUILIBRIUM = (PHI - 1.0) / (PHI + 1.0)
CHANNELS = ("terrain", "goal", "value", "blocked", "trail")
DEFAULT_ROWS = 21
DEFAULT_COLS = 80
DEFAULT_HALF_LIFE = 120.0
DEFAULT_THRESHOLD = 0.25
DEFAULT_WRITE = 1.0
RELAX_SWEEPS = 400
STRAIGHT = 1.0
DIAGONAL = math.sqrt(2.0)
WALKED_COST = 1.6
NEIGHBOURS = (
    (-1, -1, DIAGONAL), (-1, 0, STRAIGHT), (-1, 1, DIAGONAL),
    (0, -1, STRAIGHT), (0, 1, STRAIGHT),
    (1, -1, DIAGONAL), (1, 0, STRAIGHT), (1, 1, DIAGONAL),
)

# What a cell of the world's reading means to the memory: the channel it is
# written into, and with which polarity (Yang is +1, Yin is -1).
CELL_WRITES: Mapping[str, tuple[str, float]] = {
    "open": ("terrain", 1.0),
    "solid": ("terrain", -1.0),
    "door": ("terrain", 1.0),
    "down": ("goal", 1.0),
    "up": ("goal", -1.0),
    "gold": ("value", 1.0),
    "goods": ("value", -1.0),
    "blocked": ("blocked", -1.0),
    "refused-door": ("blocked", 1.0),
    "trail": ("trail", 1.0),
}

# How the field's own readout is drawn when the player is told what it holds.
MARKERS: Mapping[str, str] = {
    "open": ".",
    "solid": "#",
    "down": ">",
    "up": "<",
    "gold": "$",
    "goods": "?",
    "door-blocked": "+",
    "blocked": "x",
    "trail": "·",
    "player": "@",
}

# The player's own intentions, which the route field turns into a step.
INTENTS: Mapping[str, str] = {
    "head-down": "head for the way down you remember",
    "head-up": "head for the way up you remember",
    "head-unseen": "head for ground you have not seen yet",
    "head-value": "head for the gold or goods you remember",
    "wander": "stop heading anywhere and explore",
}
INTENT_KINDS = {
    "head-down": "down",
    "head-up": "up",
    "head-unseen": "unseen",
    "head-value": "value",
}


def aim_words(kind: str | None) -> str:
    """What an aim is called in the player's sentences."""
    if kind is None:
        return "nowhere in particular"
    return {
        "down": "way down",
        "up": "way up",
        "unseen": "ground you have not seen",
        "value": "gold or goods",
    }.get(kind, f"way {kind}")


def step_direction(down: int, right: int) -> str:
    """Name a step between two cells the way the game's own keys are named."""
    vertical = "south" if down > 0 else "north"
    horizontal = "east" if right > 0 else "west"
    if down and right:
        return vertical + horizontal
    return vertical if down else horizontal


DIRECTION_STEPS: Mapping[str, tuple[int, int]] = {
    "north": (-1, 0), "south": (1, 0), "east": (0, 1), "west": (0, -1),
    "northwest": (-1, -1), "northeast": (-1, 1), "southwest": (1, -1), "southeast": (1, 1),
}


def _shifted(field: np.ndarray, down: int, right: int) -> np.ndarray:
    """`field` read as if stepped by (down, right): a step off the grid is no step."""
    out = np.full_like(field, np.inf)
    rows, cols = field.shape
    src_rows = slice(max(0, -down), rows - max(0, down))
    dst_rows = slice(max(0, down), rows - max(0, -down))
    src_cols = slice(max(0, -right), cols - max(0, right))
    dst_cols = slice(max(0, right), cols - max(0, -right))
    out[dst_rows, dst_cols] = field[src_rows, src_cols]
    return out


def _shifted_bool(field: np.ndarray, down: int, right: int) -> np.ndarray:
    """`field` read as if stepped by (down, right), with a false border."""
    out = np.zeros_like(field, dtype=bool)
    rows, cols = field.shape
    src_rows = slice(max(0, -down), rows - max(0, down))
    dst_rows = slice(max(0, down), rows - max(0, -down))
    src_cols = slice(max(0, -right), cols - max(0, right))
    dst_cols = slice(max(0, right), cols - max(0, -right))
    out[dst_rows, dst_cols] = field[src_rows, src_cols]
    return out


@dataclass(frozen=True, slots=True)
class Route:
    """What the route field holds from where the player stands."""

    aim: str | None = None
    target: tuple[int, int] | None = None
    reachable: bool = False
    moves: int = 0
    length: float = 0.0
    directions: tuple[str, ...] = ()

    @property
    def arrived(self) -> bool:
        return self.target is not None and self.reachable and self.moves == 0

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "aim": self.aim,
            "target": list(self.target) if self.target else None,
            "reachable": self.reachable,
            "moves": self.moves,
            "length": round(self.length, 3),
            "directions": list(self.directions),
        }

    def step_reason(self) -> str:
        """The route taking its next step, in the player's terms."""
        if not self.directions:
            return "the route has no step to take"
        step = self.directions[0]
        if self.aim == "unseen":
            if self.moves == 0:
                return f"the route field steps {step} into ground it has not seen"
            return f"the route field steps {step} ({self.moves} moves to the edge of what is known)"
        return f"the route field steps {step} ({self.moves} moves to the {aim_words(self.aim)})"

    def sentence(self) -> str:
        """The route in the player's terms, as a sentence."""
        if self.aim is None:
            return "You are not heading anywhere in particular."
        if self.aim == "unseen":
            if self.target is None:
                return "You have seen everything you can reach from here."
            where = f"column {self.target[1]}, row {self.target[0]}"
            if self.arrived:
                into = ", ".join(self.directions) or "nowhere you can step"
                return f"You are at the edge of what you know ({where}); ground you have not seen lies {into}."
            return (
                f"You are heading for the edge of what you know at {where}: the route from "
                f"where you stand runs {', '.join(self.directions)} ({self.moves} moves)."
            )
        if self.target is None:
            return f"You remember no {aim_words(self.aim)} on this level."
        where = f"column {self.target[1]}, row {self.target[0]}"
        article = "some" if self.aim == "value" else "a"
        if not self.reachable:
            return (
                f"You remember {article} {aim_words(self.aim)} at {where}, "
                "but not a way to reach it any more."
            )
        if self.arrived:
            return f"You are standing on the {aim_words(self.aim)} at {where}."
        return (
            f"You are heading for the {aim_words(self.aim)} at {where}: the route from where "
            f"you stand runs {', '.join(self.directions)} ({self.moves} moves)."
        )


class LevelField:
    """The two-fluid memory of one level, and the route laid over it."""

    def __init__(
        self,
        *,
        rows: int = DEFAULT_ROWS,
        cols: int = DEFAULT_COLS,
        half_life: float = DEFAULT_HALF_LIFE,
        threshold: float = DEFAULT_THRESHOLD,
        write: float = DEFAULT_WRITE,
    ) -> None:
        if rows < 1 or cols < 1:
            raise ValueError("a level field needs a grid")
        if half_life <= 0.0:
            raise ValueError("half_life must be positive turns")
        if threshold <= 0.0 or write <= 0.0:
            raise ValueError("threshold and write must be positive")
        self.rows = int(rows)
        self.cols = int(cols)
        self.half_life = float(half_life)
        self.lam = math.log(2.0) / ((1.0 + PHI) * self.half_life)
        self.threshold = float(threshold)
        self.write = float(write)
        self.ey = {name: np.zeros((self.rows, self.cols)) for name in CHANNELS}
        self.ei = {name: np.zeros((self.rows, self.cols)) for name in CHANNELS}
        self.turns = 0
        self.aim: str | None = None
        self.distance: np.ndarray | None = None

    # -- the field's own dynamics ----------------------------------------
    def _rhs(self, ey: np.ndarray, ei: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        conversion = -self.lam * (ey - PHI * ei)
        return conversion, -conversion

    def step(self, ticks: int = 1) -> None:
        """Advance the conversion the canonical solver uses (RK2, dt = 1 turn)."""
        for _ in range(int(ticks)):
            for name in CHANNELS:
                ey, ei = self.ey[name], self.ei[name]
                k1y, k1i = self._rhs(ey, ei)
                k2y, k2i = self._rhs(ey + k1y, ei + k1i)
                ey += 0.5 * (k1y + k2y)
                ei += 0.5 * (k1i + k2i)
            self.turns += 1

    # -- perception ------------------------------------------------------
    def _write(self, channel: str, polarity: float, cells: Iterable[tuple[int, int]]) -> None:
        ey, ei = self.ey[channel], self.ei[channel]
        for row, col in cells:
            if 0 <= row < self.rows and 0 <= col < self.cols:
                if polarity > 0:
                    ey[row, col] = self.write
                    ei[row, col] = 0.0
                else:
                    ey[row, col] = 0.0
                    ei[row, col] = self.write

    def observe(
        self,
        cells: Mapping[tuple[int, int], str] | None = None,
        *,
        position: tuple[int, int] | None = None,
        blocked: tuple[int, int, str] | None = None,
    ) -> None:
        """One turn of memory: forget a little, then write what was just seen.

        ``cells`` is the world's reading of the screen (cell -> class, where the
        class is one of :data:`CELL_WRITES`), ``position`` is where the player
        is now, and ``blocked`` is the cell that just refused it, with the kind
        of refusal.
        """
        self.step()
        if cells:
            grouped: dict[tuple[str, float], list[tuple[int, int]]] = {}
            for cell, kind in cells.items():
                meaning = CELL_WRITES.get(str(kind))
                if meaning is None:
                    continue
                grouped.setdefault(meaning, []).append((int(cell[0]), int(cell[1])))
            for (channel, polarity), members in grouped.items():
                self._write(channel, polarity, members)
        if position is not None:
            self._write("trail", 1.0, [position])
        if blocked is not None and blocked[2] != "creature":
            row, col, kind = blocked
            self._write("blocked", 1.0 if kind == "door" else -1.0, [(int(row), int(col))])
        if self.aim is not None:
            self.settle()

    # -- readout ---------------------------------------------------------
    def content(self, channel: str) -> np.ndarray:
        """``pi - pi*``: what the field holds of a channel, cell by cell."""
        ey, ei = self.ey[channel], self.ei[channel]
        return (ey - ei) - EQUILIBRIUM * (ey + ei)

    def held(self, channel: str) -> tuple[np.ndarray, np.ndarray]:
        """Cells whose content is above the readout threshold, and its sign."""
        content = self.content(channel)
        return np.abs(content) > self.threshold, content

    def read(self) -> Mapping[str, Any]:
        """The whole memory as the field holds it right now."""
        terrain, terrain_sign = self.held("terrain")
        goal, goal_sign = self.held("goal")
        value, value_sign = self.held("value")
        blocked, blocked_sign = self.held("blocked")
        trail, _ = self.held("trail")
        return {
            "terrain": terrain,
            "terrain_sign": terrain_sign,
            "goal": goal,
            "goal_sign": goal_sign,
            "value": value,
            "value_sign": value_sign,
            "blocked": blocked,
            "blocked_sign": blocked_sign,
            "trail": trail,
        }

    def render(self) -> str:
        """The remembered map, drawn from the readout only."""
        reading = self.read()
        here = self.here()
        rows = []
        for row in range(self.rows):
            line = []
            for col in range(self.cols):
                if reading["goal"][row, col]:
                    mark = MARKERS["down"] if reading["goal_sign"][row, col] > 0 else MARKERS["up"]
                elif reading["value"][row, col]:
                    mark = MARKERS["gold"] if reading["value_sign"][row, col] > 0 else MARKERS["goods"]
                elif reading["blocked"][row, col]:
                    mark = (
                        MARKERS["door-blocked"]
                        if reading["blocked_sign"][row, col] > 0
                        else MARKERS["blocked"]
                    )
                elif reading["terrain"][row, col]:
                    mark = MARKERS["open"] if reading["terrain_sign"][row, col] > 0 else MARKERS["solid"]
                elif reading["trail"][row, col]:
                    mark = MARKERS["trail"]
                else:
                    mark = " "
                if here is not None and (row, col) == here:
                    mark = MARKERS["player"]
                line.append(mark)
            rows.append("".join(line))
        return "\n".join(rows)

    def goals(self) -> list[tuple[int, int, str]]:
        """Where the field holds a way down or up: (row, col, kind)."""
        reading = self.read()
        found = []
        for row, col in np.argwhere(reading["goal"]):
            kind = "down" if reading["goal_sign"][row, col] > 0 else "up"
            found.append((int(row), int(col), kind))
        return sorted(found, key=lambda item: (item[2] != "down", item[0], item[1]))

    def valuable_cells(self) -> list[tuple[int, int, str]]:
        """Where the field holds something worth walking to: (row, col, kind).

        Gold is the score; goods are the food and items a crawl runs on.  The
        field keeps what it saw, not which scroll it was -- a place worth
        taking is the memory, and the screen says what lies there now.
        """
        reading = self.read()
        found = [
            (int(row), int(col), "gold" if reading["value_sign"][row, col] > 0 else "goods")
            for row, col in np.argwhere(reading["value"])
        ]
        return sorted(found)

    def here(self) -> tuple[int, int] | None:
        """Where the player last stood, as the field holds it.

        Every trail write has the same strength and decays at the same rate, so
        the strongest trail cell is the most recent one: the player's own cell,
        read back out of the field rather than remembered beside it.
        """
        trail = self.content("trail")
        if not np.any(np.abs(trail) > self.threshold):
            return None
        row, col = np.unravel_index(int(np.argmax(trail)), trail.shape)
        return (int(row), int(col))

    def blocked_cells(self) -> list[tuple[int, int, str]]:
        reading = self.read()
        found = []
        for row, col in np.argwhere(reading["blocked"]):
            kind = "door" if reading["blocked_sign"][row, col] > 0 else "blocked"
            found.append((int(row), int(col), kind))
        return sorted(found)

    def bearing(self, cell: tuple[int, int]) -> str:
        """How a remembered cell lies from where the player stands."""
        here = self.here()
        if here is None:
            return ""
        if here == cell:
            return "you are standing on it"
        down, right = cell[0] - here[0], cell[1] - here[1]
        said = []
        if down:
            said.append(f"{abs(down)} row{'s' if abs(down) != 1 else ''} {'south' if down > 0 else 'north'}")
        if right:
            said.append(f"{abs(right)} column{'s' if abs(right) != 1 else ''} {'east' if right > 0 else 'west'}")
        return " and ".join(said) + " of you"

    # -- the route -------------------------------------------------------
    def cost_map(self) -> np.ndarray:
        """What a step onto each cell costs the route (nothing where it cannot go).

        Only what the memory holds as somewhere the player can stand is passable:
        remembered floor, a stairs, a door, or the trail the player has walked.
        A refusal is read for what refused: rock keeps its cost at nothing, and
        a door does not, because the field records the two apart precisely so a
        door stays something the player can open by walking in — counting every
        refusal as rock seals a room the moment its door has been tried.
        Ground the player has already walked costs a little more than ground it
        has not, so a route across a known room prefers the part of it that is
        still new.
        """
        reading = self.read()
        solid = reading["terrain"] & (reading["terrain_sign"] < 0)
        rock = reading["blocked"] & (reading["blocked_sign"] < 0)
        door = reading["blocked"] & (reading["blocked_sign"] > 0)
        walkable = (
            (reading["terrain"] & ~solid)
            | reading["goal"]
            | reading["value"]
            | reading["trail"]
            | door
        ) & ~rock
        cost = np.full((self.rows, self.cols), np.inf)
        cost[walkable] = 1.0
        cost[walkable & reading["trail"]] = WALKED_COST
        here = self.here()
        if here is not None:
            # The player is standing there, so that cell is somewhere it can
            # stand, whatever the rest of the memory says about it.
            cost[here] = min(cost[here], WALKED_COST)
        return cost

    def frontier(self) -> list[tuple[int, int]]:
        """Where knowledge ends: remembered-walkable cells next to unseen ground.

        A player that has run out of anywhere to go needs to know which way the
        level continues, and that is the edge of what the field holds: a cell it
        can stand on whose neighbour it has never seen.
        """
        reading = self.read()
        known = reading["terrain"] | reading["goal"] | reading["value"] | reading["trail"] | reading["blocked"]
        cost = self.cost_map()
        unseen = ~known
        edge = np.zeros_like(known)
        for down, right, _length in NEIGHBOURS:
            edge |= _shifted_bool(unseen, down, right)
        edge &= np.isfinite(cost)
        return [(int(row), int(col)) for row, col in np.argwhere(edge)]

    def _sources(self, kind: str) -> list[tuple[int, int]]:
        if kind == "unseen":
            return self.frontier()
        if kind == "value":
            return [(row, col) for row, col, _found in self.valuable_cells()]
        return [(row, col) for row, col, found in self.goals() if found == kind]

    def _relax(self, sources: Iterable[tuple[int, int]]) -> np.ndarray | None:
        """Settle the distance field from those cells to everywhere reachable.

        Every sweep lets each cell take the cheapest step it knows; the field
        stops changing when every cell holds the true shortest walk, so the same
        map always gives the same route.
        """
        cost = self.cost_map()
        distance = np.full((self.rows, self.cols), np.inf)
        seeded = False
        for row, col in sources:
            if np.isfinite(cost[row, col]):
                distance[row, col] = 0.0
                seeded = True
        if not seeded:
            return None
        for _ in range(RELAX_SWEEPS):
            best = np.full_like(distance, np.inf)
            for down, right, length in NEIGHBOURS:
                # Stepping onto a cell pays that cell's cost, so the cost map is
                # read at the neighbour, not at the cell being reached from.
                np.minimum(
                    best,
                    _shifted(distance, down, right) + _shifted(cost, down, right) * length,
                    out=best,
                )
            updated = np.where(np.isfinite(cost), np.minimum(distance, best), np.inf)
            if not np.any(updated < distance - 1e-12):
                return updated
            distance = updated
        return distance

    def head(self, kind: str | None) -> None:
        """Aim the route at the nearest remembered way down or up (None clears)."""
        if kind is None:
            self.aim = None
            self.distance = None
            return
        self.aim = str(kind)
        self.distance = self._relax(self._sources(self.aim))

    def settle(self) -> None:
        """Lay the route again, now that the memory has changed."""
        self.head(self.aim)

    def can_reach(self, kind: str) -> bool:
        """Whether the route can reach a remembered way down or up at all."""
        distance = self._relax(self._sources(kind))
        here = self.here()
        return distance is not None and here is not None and bool(np.isfinite(distance[here]))

    def _descent(
        self, cell: tuple[int, int], cost: np.ndarray, distance: np.ndarray
    ) -> tuple[int, int] | None:
        """The neighbour the route steps to next, read off the settled field.

        At the field's fixed point the best neighbour satisfies the relaxation
        with equality, so the step taken is the one that holds the distance
        rather than one that beats it.
        """
        row, col = cell
        here = float(distance[row, col])
        if not np.isfinite(here):
            return None
        best: tuple[int, int] | None = None
        best_value = here + 1e-9
        for down, right, length in NEIGHBOURS:
            r, c = row + down, col + right
            if not (0 <= r < self.rows and 0 <= c < self.cols):
                continue
            if not np.isfinite(cost[r, c]):
                continue
            value = float(distance[r, c]) + float(cost[r, c]) * length
            if value < best_value - 1e-12:
                best_value = value
                best = (r, c)
        return best

    def unseen_directions(self, cell: tuple[int, int] | None = None) -> list[str]:
        """Which way the ground the player has not seen lies from a cell."""
        here = cell or self.here()
        if here is None:
            return []
        reading = self.read()
        known = reading["terrain"] | reading["goal"] | reading["value"] | reading["trail"] | reading["blocked"]
        row, col = here
        found: list[tuple[int, str]] = []
        for down, right, _length in NEIGHBOURS:
            r, c = row + down, col + right
            if not (0 <= r < self.rows and 0 <= c < self.cols):
                continue
            if not known[r, c]:
                # Straight ground first: a diagonal step into the unknown is
                # likelier to meet a wall corner, and there is no need for it
                # when a straight step is on offer.
                found.append((0 if (down == 0 or right == 0) else 1, step_direction(down, right)))
        return [name for _rank, name in sorted(found)]

    def route(self, steps: int = 4, aim: str | None = None) -> Route:
        """What the route field holds from where the player stands.

        Naming an `aim` reads the route to that kind of place without changing
        what the player is heading for.
        """
        kind = self.aim if aim is None else aim
        if kind is None:
            return Route()
        distance = self.distance if kind == self.aim else self._relax(self._sources(kind))
        sources = {(int(row), int(col)) for row, col in self._sources(kind)}
        here = self.here()
        if distance is None or here is None:
            return Route(aim=kind)
        if not sources:
            return Route(aim=kind, target=None)
        if not np.isfinite(distance[here]):
            nearest = min(sources, key=lambda cell: abs(cell[0] - here[0]) + abs(cell[1] - here[1]))
            return Route(aim=kind, target=nearest)
        cost = self.cost_map()
        cell = here
        directions: list[str] = []
        moves = 0
        while moves < 1000:
            nxt = self._descent(cell, cost, distance)
            if nxt is None:
                break
            directions.append(step_direction(nxt[0] - cell[0], nxt[1] - cell[1]))
            cell = nxt
            moves += 1
            if cell in sources:
                break
        if kind == "unseen" and moves == 0:
            directions = self.unseen_directions(here)
        return Route(
            aim=kind,
            target=(int(cell[0]), int(cell[1])),
            reachable=True,
            moves=moves,
            length=float(distance[here]),
            directions=tuple(directions[:steps]),
        )

    def next_step(self) -> tuple[int, int] | None:
        """The step the route takes from where the player stands, as a delta."""
        here = self.here()
        if here is None or self.aim is None:
            return None
        if self.distance is not None and np.isfinite(self.distance[here]):
            nxt = self._descent(here, self.cost_map(), self.distance)
            if nxt is not None:
                return (nxt[0] - here[0], nxt[1] - here[1])
        if self.aim == "unseen":
            # Standing at the edge of what is known, the step is into it.
            found = self.unseen_directions(here)
            if found:
                return DIRECTION_STEPS[found[0]]
        return None

    # -- what the player is told -----------------------------------------
    def summary(self) -> str:
        """One line of what the field holds, in the player's terms."""
        reading = self.read()
        known = int(reading["terrain"].sum())
        solid = int((reading["terrain"] & (reading["terrain_sign"] < 0)).sum())
        walked = int(reading["trail"].sum())
        goals = self.goals()
        blocked = self.blocked_cells()
        here = self.here()
        parts = [
            f"you have walked {walked} cells and know {known} of the level's cells ({solid} solid)"
        ]
        if here is not None:
            parts.append(f"you are at column {here[1]}, row {here[0]}")
        downs = [item for item in goals if item[2] == "down"]
        ups = [item for item in goals if item[2] == "up"]
        if downs:
            row, col, _ = downs[0]
            parts.append(
                f"you found a way down at column {col}, row {row} ({self.bearing((row, col))})"
            )
            if len(downs) > 1:
                parts.append(f"({len(downs)} ways down in all)")
        if ups:
            row, col, _ = ups[0]
            parts.append(f"a way up at column {col}, row {row} ({self.bearing((row, col))})")
        valuables = self.valuable_cells()
        if valuables:
            row, col, _ = valuables[0]
            parts.append(
                f"gold or goods worth taking at column {col}, row {row} ({self.bearing((row, col))})"
            )
            if len(valuables) > 1:
                parts.append(f"({len(valuables)} such places in all)")
        if blocked:
            doors = sum(1 for item in blocked if item[2] == "door")
            other = len(blocked) - doors
            said = []
            if doors:
                said.append(f"{doors} door{'s' if doors != 1 else ''} that would not open")
            if other:
                said.append(f"{other} cell{'s' if other != 1 else ''} that refused you")
            parts.append("you remember " + " and ".join(said))
        return "; ".join(parts) + "."

    def block(self, *, heading: str = "") -> str:
        """What the player is told: the memory, its legend, and what it means."""
        legend = (
            f"'{MARKERS['open']}' open, '{MARKERS['solid']}' solid, "
            f"'{MARKERS['down']}' stairs down, '{MARKERS['up']}' stairs up, "
            f"'{MARKERS['gold']}' gold, '{MARKERS['goods']}' goods worth taking "
            "(food or an item, the field keeps what it saw), "
            f"'{MARKERS['door-blocked']}' a door that would not open, "
            f"'{MARKERS['blocked']}' a way that refused you, "
            f"'{MARKERS['trail']}' where you have been, "
            f"'{MARKERS['player']}' you, right now"
        )
        ruler = "".join(str((col // 10) % 10) if col % 10 == 0 else " " for col in range(self.cols))
        route = self.route()
        return (
            (f"{heading}\n" if heading else "")
            + "What you remember of this level, read back out of your own field "
            "(a memory fades unless you look at it again; columns and rows count "
            "from 0 at the top-left of the map):\n"
            f"   {ruler}\n"
            + "\n".join(f"{row:2d} {line}" for row, line in enumerate(self.render().splitlines()))
            + f"\n({legend})\n{self.summary()}\n{route.sentence()}{self.no_aim_sentence()}"
        )

    def no_aim_sentence(self) -> str:
        """What a player heading nowhere is told about the edge of its knowledge."""
        if self.aim is not None or self.here() is None:
            return ""
        ahead = self.route(steps=2, aim="unseen")
        if not ahead.directions:
            return " Nothing is being headed for, and every cell you can reach has been seen."
        if ahead.moves == 0:
            return (
                " Nothing is being headed for; ground you have not seen lies "
                f"{', '.join(self.unseen_directions() or ahead.directions)} of you."
            )
        return (
            f" Nothing is being headed for; the edge of what you know is {ahead.moves} moves "
            f"away, and the first step is {ahead.directions[0]}."
        )

    # -- receipts --------------------------------------------------------
    def state(self) -> Mapping[str, Any]:
        """A small, stable description of the field for a receipt."""
        reading = self.read()
        digest = hashlib.sha256()
        for name in CHANNELS:
            digest.update(np.round(self.ey[name], 6).astype("<f8").tobytes())
            digest.update(np.round(self.ei[name], 6).astype("<f8").tobytes())
        route = self.route()
        return {
            "turns": self.turns,
            "grid": [self.rows, self.cols],
            "half_life": self.half_life,
            "lam": round(self.lam, 8),
            "threshold": self.threshold,
            "known_cells": int(reading["terrain"].sum()),
            "solid_cells": int((reading["terrain"] & (reading["terrain_sign"] < 0)).sum()),
            "walked_cells": int(reading["trail"].sum()),
            "goals": [[row, col, kind] for row, col, kind in self.goals()],
            "blocked_cells": [[row, col, kind] for row, col, kind in self.blocked_cells()],
            "route": route.as_dict(),
            "digest": digest.hexdigest(),
        }


class DungeonField:
    """One memory per level, and how the levels are joined.

    The player carries a memory of wherever it stands; the dungeon keeps them
    all.  A level left behind keeps fading by the same law while the player is
    elsewhere, so coming back finds what remains of it rather than a frozen copy.
    """

    def __init__(
        self,
        *,
        rows: int = DEFAULT_ROWS,
        cols: int = DEFAULT_COLS,
        half_life: float = DEFAULT_HALF_LIFE,
        threshold: float = DEFAULT_THRESHOLD,
        write: float = DEFAULT_WRITE,
    ) -> None:
        self.rows = int(rows)
        self.cols = int(cols)
        self.half_life = float(half_life)
        self.threshold = float(threshold)
        self.write = float(write)
        self.levels: dict[int, LevelField] = {}
        self.depth = 1
        self.came_from: int | None = None
        self.visited: list[int] = []

    # -- moving between levels -------------------------------------------
    def visit(self, depth: int) -> LevelField:
        """Take the field of the level the player is standing on."""
        depth = int(depth)
        if depth not in self.levels:
            self.levels[depth] = LevelField(
                rows=self.rows,
                cols=self.cols,
                half_life=self.half_life,
                threshold=self.threshold,
                write=self.write,
            )
            self.visited.append(depth)
            self.came_from = self.depth if self.visited[:-1] else None
        elif depth != self.depth:
            self.came_from = self.depth
        self.depth = depth
        return self.levels[depth]

    def field(self) -> LevelField:
        return self.visit(self.depth)

    def observe(
        self,
        cells: Mapping[tuple[int, int], str] | None = None,
        *,
        position: tuple[int, int] | None = None,
        blocked: tuple[int, int, str] | None = None,
    ) -> None:
        """Write what the player sees on this level; the others fade a turn."""
        self.field().observe(cells, position=position, blocked=blocked)
        for depth, other in self.levels.items():
            if depth != self.depth:
                other.step()

    # -- what the player is told -----------------------------------------
    def heading(self) -> str:
        """Where the player is in the dungeon, in its own terms."""
        if len(self.visited) == 1:
            if self.depth == 1:
                return (
                    "You are on level 1, the top of the dungeon, and have been nowhere "
                    "else; the way up from here leaves the dungeon, so the way on is down."
                )
            return f"You are on level {self.depth} of the dungeon, and have been nowhere else."
        if self.came_from is None:
            return (
                f"You are on level {self.depth} of the dungeon; you have been on "
                f"level{'s' if len(self.visited) > 2 else ''} "
                + ", ".join(str(level) for level in sorted(self.visited) if level != self.depth)
                + " as well."
            )
        move = "down" if self.depth > self.came_from else "up"
        return (
            f"You are on level {self.depth} of the dungeon, and came {move} here from "
            f"level {self.came_from}; you remember "
            + ", ".join(
                f"level {level} ({int(self.levels[level].read()['terrain'].sum())} cells)"
                for level in sorted(self.visited)
                if level != self.depth
            )
            + "."
        )

    def block(self) -> str:
        return self.field().block(heading=self.heading())

    # -- the player's intentions -----------------------------------------
    def aim(self, kind: str) -> None:
        self.field().head(kind)

    def can_reach(self, kind: str) -> bool:
        """Whether the route on this level can reach a remembered place."""
        return self.field().can_reach(kind)

    def next_step(self) -> tuple[int, int] | None:
        return self.field().next_step()

    def route(self, steps: int = 4) -> Route:
        """What the route field on this level holds from where the player stands."""
        return self.field().route(steps=steps)

    def retire_aim(self) -> None:
        """Give up an intention that has nothing left to do.

        Called once the player has chosen a step of its own: an aim that has
        arrived, or that cannot act at all, would otherwise keep waking the
        brain to be told the same thing.
        """
        field = self.field()
        if field.aim is None:
            return
        if field.next_step() is None or field.route().arrived:
            field.head(None)

    def intent_actions(self) -> tuple[tuple[str, str], ...]:
        """The intentions worth offering right now, as (key, label).

        An intention is offered only when it would do something: there is a
        remembered way there and the route can reach it.  Heading for a stairs
        is not offered while the player stands on it (the stairs themselves are
        the action then); heading for unseen ground is, because that is exactly
        when the step into it is available.
        """
        field = self.field()
        aim = field.aim
        offered: list[tuple[str, str]] = []
        for key, kind in INTENT_KINDS.items():
            if kind == "up" and self.depth <= 1:
                # The way up from the top level leaves the dungeon; there is
                # nothing to head for there.
                continue
            if not field.can_reach(kind):
                continue
            field.head(kind)
            route = field.route(steps=1)
            field.head(None)
            if not route.reachable:
                continue
            if route.arrived and kind != "unseen":
                continue
            offered.append((key, INTENTS[key]))
        if aim is not None:
            field.head(aim)
            offered.append(("wander", INTENTS["wander"]))
        return tuple(offered)

    # -- receipts --------------------------------------------------------
    def state(self) -> Mapping[str, Any]:
        return {
            "depth": self.depth,
            "came_from": self.came_from,
            "visited": list(self.visited),
            "levels": {str(depth): field.state() for depth, field in sorted(self.levels.items())},
        }

    def turn_state(self) -> Mapping[str, Any]:
        """The small part of the dungeon a receipt needs for one turn."""
        field = self.field()
        state = field.state()
        return {
            "depth": self.depth,
            "came_from": self.came_from,
            "visited": list(self.visited),
            "known_cells": state["known_cells"],
            "solid_cells": state["solid_cells"],
            "walked_cells": state["walked_cells"],
            "goals": state["goals"],
            "blocked_cells": state["blocked_cells"],
            "route": state["route"],
            "digest": state["digest"],
        }


def field_parameters() -> Mapping[str, Any]:
    """The physics this memory runs on, for a receipt header."""
    return {
        "physics": "cassi two-fluid scalar sector (conversion only, RK2, dt = 1 turn)",
        "source": "CassiTheory/two-fluid/cassi_two_fluid_3d_gpu.py",
        "route": "distance field relaxed to its fixed point on the same grid",
        "phi": round(PHI, 10),
        "equilibrium": round(EQUILIBRIUM, 10),
        "channels": list(CHANNELS),
        "cell_writes": {kind: [channel, polarity] for kind, (channel, polarity) in CELL_WRITES.items()},
    }
