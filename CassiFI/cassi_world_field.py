"""A world held as a field: one sheet per area, stitched together at the doors.

Every spot the body has stood on is a cell of its area's sheet. A walk that
moved the body opens the edge between two cells; a walk that went nowhere is
a wall, and nothing flows across it. A walk that changed the scene is a door:
its edge leads onto another area's sheet, so all sheets form one field.

Remembered things release their promise into the cell where they sit, and
every cell the body could still step onto for the first time releases
novelty. The field settles by relaxation: each cell holds its own source plus
a decayed share of what the cells it can walk to hold, so promise spreads over
walkable ground like warmth through a house and fades with every step it has
to travel. The body's next step goes where the flow pulls hardest.

The field dreams. From the scenery an area's background shows, it learns
which patterns of ground carry the body and which stop it, and it extends
each sheet into scenery it has seen but never walked, weighting every
imagined cell by how likely it is to carry a step. Walking into an imagined
cell checks the dream, and the patch statistics it teaches sharpen the next
one.

Doors are dreamt the same way. The spot a walk stepped into when the scene
changed to another area is a threshold, and its scenery pattern is a door
pattern. Seen scenery with a door pattern that the body has never walked
through becomes an imagined door, holding the promise of an unseen area.
Promise from imagined doors crosses known doors into neighbouring areas, so
the settled field plans routes from area to area toward unentered doors.

What each promise is worth is learned. Every pull target has a kind: a
scenery pattern of imagined ground, a door pattern, unknown ground, or a
remembered thing. When the body goes where the field drew it, that kind
collects the discoveries that follow, discounted by how many steps later
they came. Its worth is the mean of those returns, and it scales the
promise every target of that kind releases. Kinds that lead to discovery
pull harder, are followed more, and are judged again; kinds whose promise
stays empty fade. Novelty is spent as it is found, so the feedback feeds
on what is still unknown.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np

SCHEMA = "cassi.world-field.v1"
WALKS: dict[str, tuple[int, int]] = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
DIRECTIONS = tuple(WALKS)
Cell = tuple[int, int, int]  # (area, x, y)

DECAY = 0.96          # share of a neighbour's pull that survives one step
NOVELTY = 0.5         # pull of a spot never stood on at prior worth, scaled by the chance it carries a step
IMAGINE = 0.6         # walkability at which seen scenery becomes imagined ground
DOOR_IMAGINE = 0.5    # door chance at which seen scenery becomes an imagined door
WORTH_PRIOR = 2.0     # discounted discoveries a kind is expected to lead to before it has been followed
WORTH_WEIGHT = 1.0    # how many followings the prior counts as
RETURN_DISCOUNT = 0.9 # share of a discovery credited to a draw one step further back
_TRACE_FLOOR = 0.01
_QUIET = 1e-12
_TOLERANCE = 1e-9


def _step(cell: Cell, direction: str) -> Cell:
    dx, dy = WALKS[direction]
    return cell[0], cell[1] + dx, cell[2] + dy


class WorldField:
    """Area sheets, their walls and doors, what the scenery predicts, and the settled pull."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.ground: dict[Cell, int] = {}
        self.edges: dict[tuple[Cell, str], list[int]] = {}
        self.leads: dict[tuple[Cell, str], Cell] = {}
        self.patches: dict[str, list[int]] = {}
        self.scenery: dict[int, dict[tuple[int, int], str]] = {}
        self.dreams = {"dreamt": 0, "checked": 0, "right": 0}
        self.door_dreams = {"checked": 0, "right": 0}
        self.door_patches: dict[str, int] = {}
        self._thresholds: set[Cell] = set()
        self.worth: dict[str, list[float]] = {}  # kind -> [discounted discoveries that followed, draws]
        self._traces: dict[str, float] = {}
        self.sources: dict[Cell, float] = {}
        self._keys: list[Cell] = []
        self._index: dict[Cell, int] = {}
        self._kinds: list[str] = []
        self._targets = np.zeros((0, 4), dtype=np.int64)
        self._weights = np.zeros((0, 4), dtype=np.float64)
        self._degree = np.ones(0, dtype=np.float64)
        self._novelty = np.zeros(0, dtype=np.float64)
        self._u = np.zeros(0, dtype=np.float64)
        self._dirty = True
        self._load()

    # -- persistence ---------------------------------------------------------
    def _load(self) -> None:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        if payload.get("schema") != SCHEMA:
            raise RuntimeError("persisted world field has an incompatible schema")
        self.ground = {(int(z), int(x), int(y)): int(v) for z, x, y, v in payload["ground"]}
        self.edges = {((int(z), int(x), int(y)), str(d)): [int(m), int(b)]
                      for z, x, y, d, m, b in payload["edges"]}
        self.leads = {((int(z), int(x), int(y)), str(d)): (int(z2), int(x2), int(y2))
                      for z, x, y, d, z2, x2, y2 in payload["leads"]}
        self.dreams.update({str(key): int(value) for key, value in payload.get("dreams", {}).items()})
        self.door_dreams.update({str(key): int(value) for key, value in payload.get("door_dreams", {}).items()})
        self.worth = {str(key): [float(credit), float(draws)]
                      for key, (credit, draws) in payload.get("worth", {}).items()}

    @property
    def exists(self) -> bool:
        return self.path.is_file()

    def save(self) -> None:
        payload = {
            "schema": SCHEMA,
            "ground": [[*cell, visits] for cell, visits in self.ground.items()],
            "edges": [[*cell, direction, *row] for (cell, direction), row in self.edges.items()],
            "leads": [[*cell, direction, *target] for (cell, direction), target in self.leads.items()],
            "dreams": self.dreams,
            "door_dreams": self.door_dreams,
            "worth": self.worth,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".world-field.", suffix=".tmp", dir=self.path.parent)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, separators=(",", ":"))
        os.replace(temporary, self.path)

    # -- what the body does --------------------------------------------------
    def stand(self, cell: Cell) -> None:
        if cell not in self.ground:
            self._dirty = True
        self.ground[cell] = self.ground.get(cell, 0) + 1

    def walkable(self, cell: Cell) -> float | None:
        """Chance the scenery at ``cell`` carries a step; None where the background is unknown."""
        patch = self.scenery.get(cell[0], {}).get((cell[1], cell[2]))
        if patch is None:
            return None
        walked, blocked = self.patches.get(patch, (0, 0))
        return (walked + 1) / (walked + blocked + 2)

    def door_chance(self, cell: Cell) -> float | None:
        """Chance stepping into ``cell`` leads to another area; None where its scenery was never a threshold."""
        patch = self.scenery.get(cell[0], {}).get((cell[1], cell[2]))
        doors = self.door_patches.get(patch, 0) if patch is not None else 0
        if not doors:
            return None
        walked, blocked = self.patches.get(patch, (0, 0))
        return (doors + 0.5) / (doors + walked + blocked + 1)

    def _imagined_door(self, cell: Cell) -> float | None:
        """The door chance of a seen spot never stood on or walked through; None when it is no imagined door."""
        if cell in self.ground or cell in self._thresholds:
            return None
        chance = self.door_chance(cell)
        return chance if chance is not None and chance >= DOOR_IMAGINE else None

    def _tally(self) -> None:
        """What each scenery pattern has done under the body: every spot stood on carried a step, every wall stopped one."""
        patches: dict[str, list[int]] = {}
        for cell in self.ground:
            patch = self.scenery.get(cell[0], {}).get((cell[1], cell[2]))
            if patch is not None:
                patches.setdefault(patch, [0, 0])[0] += 1
        for (cell, direction), row in self.edges.items():
            if row[1] > row[0]:
                wall = _step(cell, direction)
                patch = self.scenery.get(wall[0], {}).get((wall[1], wall[2]))
                if patch is not None and wall not in self.ground:
                    patches.setdefault(patch, [0, 0])[1] += 1
        self.patches = patches
        # Every walk that changed the area stepped into a threshold; its scenery is a door pattern.
        doors: dict[str, int] = {}
        thresholds: set[Cell] = set()
        for (cell, direction), result in self.leads.items():
            if result[0] == cell[0]:
                continue
            threshold = _step(cell, direction)
            thresholds.add(threshold)
            patch = self.scenery.get(threshold[0], {}).get((threshold[1], threshold[2]))
            if patch is not None:
                doors[patch] = doors.get(patch, 0) + 1
        self.door_patches, self._thresholds = doors, thresholds

    def walked(self, origin: Cell, direction: str, result: Cell | None) -> None:
        """A walk from ``origin``: ``result`` is where the body ended up, None when it went nowhere."""
        fresh = (origin, direction) not in self.edges
        row = self.edges.setdefault((origin, direction), [0, 0])
        was_open = row[0] >= row[1]
        unit = _step(origin, direction)
        stepped = result == unit
        if fresh and self._imagined_door(unit) is not None:
            # A first walk into an imagined door checks whether it opens onto another area.
            self.door_dreams["checked"] += 1
            self.door_dreams["right"] += result is not None and result[0] != origin[0]
        if unit not in self.ground and (result is None or stepped):
            # A first try at an unwalked spot checks what the dream predicted there.
            patch = self.scenery.get(unit[0], {}).get((unit[1], unit[2]))
            if patch is not None and sum(self.patches.get(patch, (0, 0))):
                self.dreams["checked"] += 1
                self.dreams["right"] += ((self.walkable(unit) or 0) >= 0.5) == stepped
        if result is None:
            row[1] += 1
        else:
            if not stepped:
                self.leads[(origin, direction)] = result
            row[0] += 1
            self.stand(result)
        if (row[0] >= row[1]) != was_open or result is not None and not stepped:
            self._dirty = True
        if self._dirty:
            self._tally()

    def seed(self, ground: Iterable[Cell], tried: Iterable[tuple[Cell, str, str]]) -> None:
        """Start a sheet from a map drawn before the field held it: standing places and walk outcomes."""
        for cell in ground:
            self.ground.setdefault(cell, 1)
        for cell, direction, outcome in tried:
            target = _step(cell, direction)
            if outcome.startswith("moved") and target in self.ground:
                self.edges.setdefault((cell, direction), [0, 0])[0] += 1
            elif outcome == "still":
                self.edges.setdefault((cell, direction), [0, 0])[1] += 1
        self._dirty = True

    # -- dreaming ------------------------------------------------------------
    def dream(self, area: int, scenery: Mapping[tuple[int, int], str]) -> int:
        """Take in an area's scenery and imagine its unwalked ground; returns the imagined cells."""
        self.scenery[area] = {(int(x), int(y)): patch for (x, y), patch in scenery.items()}
        self._tally()
        self._dirty = True
        imagined = sum(1 for (x, y) in self.scenery[area]
                       if (area, x, y) not in self.ground and (self.walkable((area, x, y)) or 0) >= IMAGINE)
        self.dreams["dreamt"] += 1
        return imagined

    # -- the field -----------------------------------------------------------
    def set_sources(self, sources: Mapping[Cell, float]) -> None:
        if any(cell not in self._index for cell in sources):
            self._dirty = True
        self.sources = {cell: float(value) for cell, value in sources.items() if value > 0}

    # -- what matters --------------------------------------------------------
    def value(self, kind: str) -> float:
        """The learned worth of a kind of pull target: mean discounted discoveries after the body followed it."""
        credit, draws = self.worth.get(kind, (0.0, 0.0))
        return (credit + WORTH_PRIOR * WORTH_WEIGHT) / (draws + WORTH_WEIGHT)

    def kind_at(self, cell: Cell) -> str | None:
        """The kind of pull target ``cell`` is, or None for ground already stood on."""
        position = self._index.get(cell)
        return None if position is None else self._cell_kinds[position]

    def feel(self, drawn: str | None, discovered: bool) -> None:
        """One step of feedback: the kind the body followed this step, if any, and whether the step discovered."""
        if drawn is not None:
            self.worth.setdefault(drawn, [0.0, 0.0])[1] += 1.0
            self._traces[drawn] = self._traces.get(drawn, 0.0) + 1.0
        if discovered:
            for kind, trace in self._traces.items():
                self.worth.setdefault(kind, [0.0, 0.0])[0] += trace
        self._traces = {kind: trace * RETURN_DISCOUNT for kind, trace in self._traces.items()
                        if trace * RETURN_DISCOUNT >= _TRACE_FLOOR}

    def _blocked(self, cell: Cell, direction: str) -> bool:
        row = self.edges.get((cell, direction))
        return row is not None and row[1] > row[0]

    def _compile(self) -> None:
        kinds: dict[Cell, str] = {cell: "ground" for cell in self.ground}
        doors: dict[Cell, float] = {}
        patch_of = self._patch
        for area, cells in self.scenery.items():
            for (x, y) in cells:
                cell = (area, x, y)
                if cell in kinds:
                    continue
                door = self._imagined_door(cell)
                if door is not None:
                    kinds[cell] = "door"
                    doors[cell] = door
                elif (self.walkable(cell) or 0) >= IMAGINE:
                    kinds[cell] = "imagined"
        for cell in self.sources:
            kinds.setdefault(cell, "thing")
        for cell in self.ground:
            for direction in DIRECTIONS:
                if not self._blocked(cell, direction):
                    kinds.setdefault(self.leads.get((cell, direction), _step(cell, direction)), "unknown")
        keys = list(kinds)
        index = {cell: position for position, cell in enumerate(keys)}
        count = len(keys)
        targets = np.full((count, 4), count, dtype=np.int64)
        weights = np.zeros((count, 4), dtype=np.float64)
        novelty = np.zeros(count, dtype=np.float64)
        cell_kinds: list[str | None] = [None] * count
        for position, cell in enumerate(keys):
            kind = kinds[cell]
            if kind in ("imagined", "unknown"):
                chance = self.walkable(cell)
                novelty[position] = 0.5 if chance is None else chance
                cell_kinds[position] = f"ground:{patch_of(cell)}" if kind == "imagined" else "unknown"
            elif kind == "door":
                novelty[position] = doors[cell]
                cell_kinds[position] = f"door:{patch_of(cell)}"
            elif kind == "thing":
                cell_kinds[position] = "thing"
            if kind not in ("ground", "imagined"):
                continue
            for slot, direction in enumerate(DIRECTIONS):
                if kind == "ground":
                    if self._blocked(cell, direction):
                        continue
                    target = self.leads.get((cell, direction), _step(cell, direction))
                    row = self.edges.get((cell, direction))
                    known = row is not None and row[0] > 0
                else:
                    target = _step(cell, direction)
                    if target not in index or kinds[target] == "unknown":
                        continue
                    known = False
                where = index[target]
                if kinds[target] == "door":
                    weight = doors[target]
                elif known or kinds[target] in ("ground", "thing"):
                    weight = 1.0
                else:
                    chance = self.walkable(target)
                    weight = 0.5 if chance is None else chance
                targets[position, slot] = where
                weights[position, slot] = weight
        old = dict(zip(self._keys, self._u))
        self._keys, self._index, self._kinds = keys, index, [kinds[cell] for cell in keys]
        self._targets, self._weights, self._novelty = targets, weights, novelty
        self._cell_kinds = cell_kinds
        names = sorted({kind for kind in cell_kinds if kind is not None})
        slot_of = {kind: slot for slot, kind in enumerate(names)}
        self._worth_names = names
        self._worth_slots = np.array([slot_of.get(kind, len(names)) if kind is not None else len(names)
                                      for kind in cell_kinds], dtype=np.int64)
        self._degree = np.maximum((weights > 0).sum(axis=1), 1).astype(np.float64)
        self._u = np.array([old.get(cell, 0.0) for cell in keys], dtype=np.float64)
        self._dirty = False

    def settle(self, iterations: int = 256) -> int:
        """Relax the field toward its settled pull; returns the iterations spent."""
        if self._dirty:
            self._compile()
        scale = np.append([self.value(kind) / WORTH_PRIOR for kind in self._worth_names], 0.0)
        source = NOVELTY * self._novelty * scale[self._worth_slots]
        thing = self.value("thing") / WORTH_PRIOR
        for cell, value in self.sources.items():
            source[self._index[cell]] += value * thing
        u = np.append(self._u, 0.0)
        spent = 0
        for spent in range(1, iterations + 1):
            fresh = source + DECAY * (self._weights * u[self._targets]).sum(axis=1) / self._degree
            change = float(np.abs(fresh - u[:-1]).max(initial=0.0))
            u[:-1] = fresh
            if change < _TOLERANCE:
                break
        self._u = u[:-1]
        return spent

    def pull(self, cell: Cell) -> float:
        position = self._index.get(cell)
        return 0.0 if position is None else float(self._u[position])

    def flow(self, cell: Cell) -> tuple[str, float, Cell, str] | None:
        """The walk the settled field pulls the body into from ``cell``: (direction, pull, target, target kind)."""
        position = self._index.get(cell)
        if position is None or self._kinds[position] != "ground":
            return None
        best: tuple[str, float, Cell, str] | None = None
        for slot, direction in enumerate(DIRECTIONS):
            target = int(self._targets[position, slot])
            if target >= len(self._keys):
                continue
            value = float(self._weights[position, slot] * self._u[target])
            if value > _QUIET and (best is None or value > best[1]):
                best = (direction, value, self._keys[target], self._kinds[target])
        return best

    def summary(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for kind in self._kinds:
            counts[kind] = counts.get(kind, 0) + 1
        return {
            "areas": len({cell[0] for cell in self.ground}),
            "ground": len(self.ground),
            "walls": sum(1 for row in self.edges.values() if row[1] > row[0]),
            "doors": sum(1 for (cell, _), result in self.leads.items() if result[0] != cell[0]),
            "cells": counts,
            "sources": len(self.sources),
            "scenery_patterns": len(self.patches),
            "door_patterns": len(self.door_patches),
            "dreams": dict(self.dreams),
            "door_dreams": dict(self.door_dreams),
        }
