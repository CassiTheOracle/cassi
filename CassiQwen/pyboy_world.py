"""What Cassi sees and remembers of a Game Boy world, from the pixels alone.

Cassi perceives the 160x144 frame the console shows a player. Comparing two
frames gives the whole-screen displacement that best carries one onto the
other (phase correlation) and how much of the screen that displacement
explains. From that single measurement three kinds of change follow: the
world slid as a whole (Cassi walked), the view broke into a different scene
(a door, stairs, a battle, a full-screen menu), or a part of the screen changed
while the rest held still (a box opened, a cursor moved, a sprite turned).

Objects are what the stable scene does not explain. Each area keeps a
background learned by majority vote over views from distinct standing places,
so walls, floors, and anything that never moved win the vote, while a sprite
that walks away, the player's own body, and animated water lose it. A settled
view minus its background leaves figures; each figure's shape and shading is
matched against a growing library of kinds, so a character seen again in any
room is recognized and a never-seen kind is a discovery. The figure that stays
on the same spot of the screen wherever Cassi stands is Cassi itself. Changes
too large to be an object are panels (boxes and menus); where they happen is
learned online as a small set of screen regions, and whether their content was
seen before gives novelty.

Things are what Cassi can act on. The screen is a grid of 16-pixel cells: a
figure of a known kind is a thing, and so is a patch of scenery rare on its
screen (a sign, a door, a lone rock), named by its pixels so the same kind of
thing is known again anywhere. Walking into the cell beside Cassi, or pressing
a button while facing it, uses a verb on the thing there, and the answer is a
set of effects: nothing, a step, a scene change, a box, a stirring figure, the
thing gone or changed. What each kind of thing does to each verb is kept, so
curiosity points at things with untried verbs and at things known to do
something, and a verb that answers the same whatever it touches stops being
aimed at things.

Positions come from path integration: every whole-screen slide of 16 pixels is
one step. A scene break relocalizes against remembered keyframes and opens a
new area when nothing remembered matches. The place map stores those places,
their keyframes, backgrounds, object kinds, and emulator snapshots that let
exploration resume from any place Cassi has reached.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import random
import tempfile
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from scipy import ndimage

HEIGHT, WIDTH = 144, 160
TILE = 8
ROWS, COLUMNS = HEIGHT // TILE, WIDTH // TILE
STEP_PIXELS = 16

REGION_SLOTS = 16
KINDS = ("still", "moved", "cut", "self", "object", "panel")
OUTCOMES = ("still", "moved-new", "moved-seen", "cut-new", "cut-seen", "self", "object-new", "object-seen") + tuple(
    f"panel-{slot:02d}-{novelty}" for slot in range(REGION_SLOTS) for novelty in ("new", "seen")) + (
    "use-new", "facing-thing")
DISCOVERIES = ("moved-new", "cut-new", "object-new") + tuple(
    f"panel-{slot:02d}-new" for slot in range(REGION_SLOTS)) + ("use-new", "facing-thing")
WALK_BUTTONS = ("up", "down", "left", "right")

# What things do: Cassi uses a verb on the thing in a 16-pixel cell beside it
# and reads the answer as a set of effects.
CELL = 16
CELL_ROWS, CELL_COLUMNS = HEIGHT // CELL, WIDTH // CELL
HEADINGS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
VERBS = ("walk", "a", "b", "start", "select")
EFFECTS = ("still", "moved", "cut", "panel", "stirred", "gone", "changed")
_PLAIN_EFFECTS = frozenset(("still", "moved"))
_SALIENT_REPEATS = 2        # a scenery patch shown more often than this on one screen is ground
_RETIRE_THINGS = 8          # a verb is judged once it has been used on this many things
_RETIRE_SHARE = 0.75        # one answer on this share of them means the thing does not matter to the verb
_USE_WORTH = 0.5            # a verb that did something stays worth repeating while (fresh+1)/(uses+2) holds this

CUT_AGREEMENT = 0.5        # below this, no displacement explains the new frame
MOVE_AGREEMENT = 0.85      # a slide must explain this much of the overlap
_RELOCATE_AGREEMENT = 0.85  # a keyframe must explain this much to place a scene
_MIN_OVERLAP = 0.5
_REGION_MATCH = 0.5
_REGION_INSIDE = 0.8
_KEYFRAMES_PER_AREA = 32
_KEYFRAME_SPACING = 3
_GLOBAL_TRIES = 32
_MAP_SCHEMA = "cassi.pyboy-pixel-map.v2"
_MAX_EVENTS = 65536
_MAX_CONTEXTS = 16384

FIGURE_SPAN = 32            # an object is at most this many pixels across; larger figures are panels
_GROUND_VOTES = 2           # a background shade needs this many views and a majority of them
_GROUND_AGREEMENT = 0.8     # a view must match its background this well to be read or learned from
_KIND_MATCH = 0.7           # shared shape and shading that makes two figures one kind
_KIND_SHIFT = 2             # pixels of slack when aligning a figure with a kind
_MAX_KINDS = 4096
_SELF_VIEWS = 8             # views before the screen-fixed figure is trusted as Cassi's own body
_SELF_PRESENCE = 0.6        # share of views in which a pixel must be figure to belong to it
_JOIN = np.ones((13, 13), dtype=bool)  # figure pixels up to 12 apart are one figure: a word line joins, two sprites a tile apart do not
_EIGHT = np.ones((3, 3), dtype=bool)


# -- the retina ---------------------------------------------------------------

def view_of(frame: bytes) -> np.ndarray:
    """A BGRA framebuffer as four luminance shades, the Game Boy's own palette depth."""
    pixels = np.frombuffer(frame, dtype=np.uint8).reshape(HEIGHT, WIDTH, 4)
    luminance = (pixels[..., 2].astype(np.uint16) * 77 + pixels[..., 1].astype(np.uint16) * 150
                 + pixels[..., 0].astype(np.uint16) * 29) >> 8
    return (luminance >> 6).astype(np.uint8)


def blank(view: np.ndarray) -> bool:
    """One flat shade: the fade between scenes."""
    return int(view.min()) == int(view.max())


def agreement(before: np.ndarray, after: np.ndarray, dx: int, dy: int) -> float:
    """Fraction of the overlap where ``after`` equals ``before`` displaced by (dx, dy)."""
    height, width = before.shape
    if abs(dx) >= width or abs(dy) >= height:
        return 0.0
    old = before[max(0, -dy):height - max(0, dy), max(0, -dx):width - max(0, dx)]
    new = after[max(0, dy):height - max(0, -dy), max(0, dx):width - max(0, -dx)]
    if old.size < _MIN_OVERLAP * before.size:
        return 0.0
    return float(np.count_nonzero(old == new)) / old.size


def displacement(before: np.ndarray, after: np.ndarray) -> tuple[int, int]:
    """The whole-screen displacement carrying ``before`` onto ``after`` (phase correlation)."""
    a = before.astype(np.float32)
    b = after.astype(np.float32)
    cross = np.fft.rfft2(b - b.mean()) * np.conj(np.fft.rfft2(a - a.mean()))
    cross /= np.abs(cross) + 1e-9
    surface = np.fft.irfft2(cross, s=a.shape)
    y, x = np.unravel_index(int(np.argmax(surface)), surface.shape)
    height, width = a.shape
    return (int(x) - width if x > width // 2 else int(x), int(y) - height if y > height // 2 else int(y))


def changed_tiles(before: np.ndarray, after: np.ndarray) -> np.ndarray:
    """ROWS x COLUMNS mask of 8x8 tiles whose pixels differ."""
    diff = (before != after).reshape(ROWS, TILE, COLUMNS, TILE)
    return diff.any(axis=(1, 3))


def sight(view: np.ndarray, tiles: np.ndarray) -> str:
    """Identity of what ``view`` shows inside ``tiles``: the content that makes an event new."""
    digest = hashlib.sha256(np.packbits(tiles).tobytes())
    blocks = view.reshape(ROWS, TILE, COLUMNS, TILE).transpose(0, 2, 1, 3)
    digest.update(np.ascontiguousarray(blocks[tiles]).tobytes())
    return digest.hexdigest()[:20]


def boxes(view: np.ndarray) -> np.ndarray:
    """ROWS x COLUMNS mask of the framed windows on screen: messages, menus, and cards.

    A window is a rectangle of tiles drawn over the world with a frame: a
    straight line of its darkest shade runs through every tile of its top
    and bottom edges and down every tile of its left and right sides, and
    the rectangle holds at least one row and two columns of tiles inside.
    Scenery with a line along one tile, or lines on only some sides, is no
    window. A window whose edges another window covers stays partly unread.
    """
    blocks = view.reshape(ROWS, TILE, COLUMNS, TILE).transpose(0, 2, 1, 3)
    low = blocks.min(axis=(2, 3))
    dark = blocks == low[:, :, None, None]
    drawn = blocks.max(axis=(2, 3)) > low
    across = dark.all(axis=3).any(axis=2) & drawn
    down = dark.all(axis=2).any(axis=2) & drawn
    mask = np.zeros((ROWS, COLUMNS), dtype=bool)
    for top in range(ROWS - 2):
        column = 1
        while column < COLUMNS - 1:
            if not across[top, column]:
                column += 1
                continue
            first = column
            while column < COLUMNS - 1 and across[top, column]:
                column += 1
            last = column - 1
            if last - first < 1:
                continue
            left, right = first - 1, last + 1
            for bottom in range(top + 2, ROWS):
                if across[bottom, first:last + 1].all():
                    if down[top + 1:bottom, left].all() and down[top + 1:bottom, right].all():
                        mask[top:bottom + 1, left:right + 1] = True
                        break
    return mask


def compare(before: np.ndarray, after: np.ndarray) -> tuple[tuple[int, int], float, float]:
    """Best whole-screen displacement, how much of the screen it explains, and how much holding still explains."""
    dx, dy = displacement(before, after)
    return (dx, dy), agreement(before, after, dx, dy), agreement(before, after, 0, 0)


def scene_broke(before: np.ndarray, after: np.ndarray) -> bool:
    """No displacement, including none, explains the new frame: a different scene."""
    _, slide, still = compare(before, after)
    return max(slide, still) < CUT_AGREEMENT


def bounds(tiles: np.ndarray) -> tuple[int, int, int, int]:
    rows = np.flatnonzero(tiles.any(axis=1))
    columns = np.flatnonzero(tiles.any(axis=0))
    return int(rows[0]), int(columns[0]), int(rows[-1]) + 1, int(columns[-1]) + 1


def _area(box: Sequence[int]) -> int:
    return (box[2] - box[0]) * (box[3] - box[1])


def _shared(a: Sequence[int], b: Sequence[int]) -> int:
    return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))


def _overlap(a: Sequence[int], b: Sequence[int]) -> float:
    shared = _shared(a, b)
    union = _area(a) + _area(b) - shared
    return shared / union if union else 0.0


def futile(outcome: str, *, at_place: bool) -> bool:
    """A press that changed nothing new: still anywhere; standing in the world, also a turn or a known sight."""
    return outcome == "still" or (at_place and (outcome in ("self", "object-seen") or (
        outcome.startswith("panel-") and outcome.endswith("-seen"))))


@dataclass
class Figure:
    """A connected part of a view that its background does not explain."""

    top: int
    left: int
    mask: np.ndarray
    shades: np.ndarray
    kind: int = -1
    new: bool = False
    own: bool = False

    @property
    def height(self) -> int:
        return int(self.mask.shape[0])

    @property
    def width(self) -> int:
        return int(self.mask.shape[1])

    @property
    def large(self) -> bool:
        return self.height > FIGURE_SPAN or self.width > FIGURE_SPAN

    @property
    def clipped(self) -> bool:
        """Cut off by the screen edge, so its whole shape is unknown."""
        return (self.top == 0 or self.left == 0 or self.top + self.height == HEIGHT
                or self.left + self.width == WIDTH)

    def touches(self, pixels: np.ndarray) -> bool:
        window = pixels[self.top:self.top + self.height, self.left:self.left + self.width]
        return bool((window & self.mask).any())

    def record(self) -> list[Any]:
        label = "self" if self.own else ("edge" if self.clipped and self.kind < 0 else self.kind)
        return [self.left, self.top, self.width, self.height, label]


def figures_in(mask: np.ndarray, view: np.ndarray) -> list[Figure]:
    """Figures of ``mask`` (pixels up to 12 apart join), with their shading in ``view``."""
    labels, _ = ndimage.label(ndimage.binary_dilation(mask, structure=_JOIN), structure=_EIGHT)
    figures: list[Figure] = []
    for index, box in enumerate(ndimage.find_objects(labels), start=1):
        if box is None:
            continue
        part = (labels[box] == index) & mask[box]
        rows = np.flatnonzero(part.any(axis=1))
        columns = np.flatnonzero(part.any(axis=0))
        if rows.size == 0:
            continue
        top, left = box[0].start + int(rows[0]), box[1].start + int(columns[0])
        bottom, right = box[0].start + int(rows[-1]) + 1, box[1].start + int(columns[-1]) + 1
        figures.append(Figure(top, left, part[rows[0]:rows[-1] + 1, columns[0]:columns[-1] + 1].copy(),
                              view[top:bottom, left:right].copy()))
    return figures


# -- things -------------------------------------------------------------------

def own_cell(own_box: Sequence[int] | None) -> tuple[int, int] | None:
    """The screen cell (column, row) Cassi stands in: the cell holding the middle of its body."""
    if own_box is None:
        return None
    return (int((own_box[1] + own_box[3]) / 2) // CELL, int((own_box[0] + own_box[2]) / 2) // CELL)


def scene(view: np.ndarray, figures: Sequence[Figure],
          own_box: Sequence[int] | None) -> dict[tuple[int, int], str]:
    """The salient things of a settled world view by screen cell (column, row).

    A figure of a known kind is a thing in the cell holding its middle. Every
    other cell is a patch of scenery, named by its content with Cassi's body
    and the figures masked out. A patch repeated more than twice on one screen
    is ground; a rarer one (a sign, a door, a lone rock) is a thing, and the
    same name finds the same kind of thing anywhere in the world. Cells a
    figure partly covers stay unread.
    """
    shown = view.copy()
    if own_box is not None:
        shown[own_box[0]:own_box[2], own_box[1]:own_box[3]] = 4
    covered = np.zeros((CELL_ROWS, CELL_COLUMNS), dtype=bool)
    things: dict[tuple[int, int], str] = {}
    for figure in figures:
        if figure.own:
            continue
        shown[figure.top:figure.top + figure.height, figure.left:figure.left + figure.width][figure.mask] = 4
        covered[figure.top // CELL:(figure.top + figure.height - 1) // CELL + 1,
                figure.left // CELL:(figure.left + figure.width - 1) // CELL + 1] = True
        if figure.kind >= 0 and not figure.clipped and not figure.large:
            cell = (int(figure.left + figure.width / 2) // CELL, int(figure.top + figure.height / 2) // CELL)
            things[cell] = f"k{figure.kind}"
    blocks = shown.reshape(CELL_ROWS, CELL, CELL_COLUMNS, CELL).transpose(0, 2, 1, 3)
    patches: dict[bytes, list[tuple[int, int]]] = {}
    for row in range(CELL_ROWS):
        for column in range(CELL_COLUMNS):
            block = blocks[row, column]
            if covered[row, column] or bool((block == 4).all()):
                continue
            patches.setdefault(np.ascontiguousarray(block).tobytes(), []).append((column, row))
    for content, cells in patches.items():
        if len(cells) <= _SALIENT_REPEATS:
            name = "p" + hashlib.sha256(content).hexdigest()[:12]
            for cell in cells:
                things.setdefault(cell, name)
    things.pop(own_cell(own_box), None)
    return things


# -- the place map ------------------------------------------------------------

def place_key(zone: int, position: Sequence[int]) -> str:
    return f"a{zone}x{int(position[0])}y{int(position[1])}"


def _cell_of(key: str) -> tuple[int, int, int]:
    """(zone, x, y) of a place key."""
    zone, rest = key[1:].split("x", 1)
    x, y = rest.split("y", 1)
    return int(zone), int(x), int(y)


class PlaceMap:
    """Places, areas, backgrounds, object kinds, panel regions, keyframes, and resumable snapshots."""

    def __init__(self, home: Path, *, max_snapshots: int = 4096) -> None:
        self.home = home
        self._states = home / "states"
        self._grounds = home / "ground"
        self.max_snapshots = max_snapshots
        self.cells: dict[str, dict[str, Any]] = {}
        self.zones: list[dict[str, Any]] = []
        self.regions: list[list[int]] = []
        self.events: dict[str, int] = {}
        self.tries: dict[str, dict[str, list[Any]]] = {}
        self.action_totals: dict[str, list[int]] = {}
        self.returns = 0
        # What each thing did to each verb: effect counts, [uses, uses that taught something],
        # and the verbs already used at each world cell.
        self.uses: dict[str, dict[str, dict[str, int]]] = {}
        self.use_stats: dict[str, list[int]] = {}
        self.engaged: dict[str, list[str]] = {}
        self._retired: set[str] | None = None
        # The thing last seen at each world cell, so Cassi can travel back to it.
        self.sightings: dict[str, str] = {}
        self.keyframes: list[tuple[int, int, int, np.ndarray]] = []
        # Background votes per area: counts of each shade at every world pixel.
        self.grounds: dict[int, dict[str, Any]] = {}
        # Areas whose background learned something since the world field last dreamt of them.
        self.ground_changed: set[int] = set()
        self.kind_count = 0
        self.kind_masks = np.zeros((64, FIGURE_SPAN, FIGURE_SPAN), dtype=bool)
        self.kind_shades = np.zeros((64, FIGURE_SPAN, FIGURE_SPAN), dtype=np.uint8)
        self.kind_sizes = np.zeros((64, 2), dtype=np.int16)
        self.kind_seen = np.zeros(64, dtype=np.int64)
        self.presence = np.zeros((HEIGHT, WIDTH), dtype=np.int32)
        self.presence_views = 0
        self._objects_dirty = False
        self._load()

    # -- persistence ---------------------------------------------------------
    def _load(self) -> None:
        path = self.home / "map.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        if payload.get("schema") != _MAP_SCHEMA:
            raise RuntimeError("persisted PyBoy place map has an incompatible schema")
        self.cells = {str(key): dict(value) for key, value in payload["cells"].items()}
        self.zones = [dict(zone) for zone in payload["zones"]]
        self.regions = [list(map(int, region)) for region in payload["regions"]]
        self.events = {str(key): int(value) for key, value in payload["events"].items()}
        self.tries = {str(key): {str(a): list(v) for a, v in value.items()}
                      for key, value in payload.get("tries", {}).items()}
        self.action_totals = {str(key): [int(v) for v in value]
                              for key, value in payload.get("action_totals", {}).items()}
        self.returns = int(payload.get("returns", 0))
        self.uses = {str(thing): {str(verb): {str(effect): int(count) for effect, count in effects.items()}
                                  for verb, effects in verbs.items()}
                     for thing, verbs in payload.get("uses", {}).items()}
        self.use_stats = {str(key): [int(v) for v in value] for key, value in payload.get("use_stats", {}).items()}
        self.engaged = {str(key): [str(v) for v in value] for key, value in payload.get("engaged", {}).items()}
        self.sightings = {str(key): str(value) for key, value in payload.get("sightings", {}).items()}
        keyframes = self.home / "keyframes.npz"
        if keyframes.is_file():
            with np.load(keyframes) as stored:
                self.keyframes = [(int(z), int(x), int(y), view) for (z, x, y), view
                                  in zip(stored["where"], stored["views"])]
        objects = self.home / "objects.npz"
        if objects.is_file():
            with np.load(objects) as stored:
                self.kind_count = int(stored["sizes"].shape[0])
                self._reserve(self.kind_count)
                self.kind_masks[:self.kind_count] = stored["masks"]
                self.kind_shades[:self.kind_count] = stored["shades"]
                self.kind_sizes[:self.kind_count] = stored["sizes"]
                self.kind_seen[:self.kind_count] = stored["seen"]
                self.presence = stored["presence"].astype(np.int32)
                self.presence_views = int(stored["presence_views"])
        if self._grounds.is_dir():
            for path in self._grounds.glob("a*.npz"):
                with np.load(path) as stored:
                    self.grounds[int(path.stem[1:])] = {
                        "votes": stored["votes"].copy(), "y": int(stored["origin"][0]),
                        "x": int(stored["origin"][1]), "dirty": False}

    @staticmethod
    def _write_npz(path: Path, **arrays: np.ndarray) -> None:
        descriptor, temporary = tempfile.mkstemp(prefix=f".{path.stem}.", suffix=".npz", dir=path.parent)
        with os.fdopen(descriptor, "wb") as handle:
            np.savez_compressed(handle, **arrays)
        os.replace(temporary, path)

    def save(self) -> None:
        self.home.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": _MAP_SCHEMA,
            "cells": self.cells,
            "zones": self.zones,
            "regions": self.regions,
            "events": self.events,
            "tries": self.tries,
            "action_totals": self.action_totals,
            "returns": self.returns,
            "uses": self.uses,
            "use_stats": self.use_stats,
            "engaged": self.engaged,
            "sightings": self.sightings,
        }
        descriptor, temporary = tempfile.mkstemp(prefix=".map.", suffix=".tmp", dir=self.home)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
        os.replace(temporary, self.home / "map.json")
        if self.keyframes:
            self._write_npz(self.home / "keyframes.npz",
                            where=np.array([(z, x, y) for z, x, y, _ in self.keyframes], dtype=np.int32),
                            views=np.stack([view for *_, view in self.keyframes]))
        if self._objects_dirty:
            count = self.kind_count
            self._write_npz(self.home / "objects.npz", masks=self.kind_masks[:count],
                            shades=self.kind_shades[:count], sizes=self.kind_sizes[:count],
                            seen=self.kind_seen[:count], presence=self.presence,
                            presence_views=np.array(self.presence_views))
            self._objects_dirty = False
        for zone, ground in self.grounds.items():
            if ground["dirty"]:
                self._grounds.mkdir(parents=True, exist_ok=True)
                self._write_npz(self._grounds / f"a{zone}.npz", votes=ground["votes"],
                                origin=np.array([ground["y"], ground["x"]], dtype=np.int64))
                ground["dirty"] = False

    # -- objects -------------------------------------------------------------
    def _reserve(self, count: int) -> None:
        capacity = self.kind_sizes.shape[0]
        if count <= capacity:
            return
        while capacity < count:
            capacity *= 2
        for name in ("kind_masks", "kind_shades", "kind_sizes", "kind_seen"):
            old = getattr(self, name)
            grown = np.zeros((capacity, *old.shape[1:]), dtype=old.dtype)
            grown[:old.shape[0]] = old
            setattr(self, name, grown)

    def ground_window(self, zone: int, position: Sequence[int]) -> tuple[np.ndarray, np.ndarray] | None:
        """The background an area shows from ``position``: (shade, sure) screens, or None before any view."""
        ground = self.grounds.get(zone)
        if ground is None:
            return None
        votes = ground["votes"]
        y0 = STEP_PIXELS * int(position[1]) - ground["y"]
        x0 = STEP_PIXELS * int(position[0]) - ground["x"]
        window = np.zeros((HEIGHT, WIDTH, 4), dtype=np.uint8)
        top, bottom = max(0, y0), min(votes.shape[0], y0 + HEIGHT)
        left, right = max(0, x0), min(votes.shape[1], x0 + WIDTH)
        if top < bottom and left < right:
            window[top - y0:bottom - y0, left - x0:right - x0] = votes[top:bottom, left:right]
        best = window.max(axis=2).astype(np.int32)
        sure = (best >= _GROUND_VOTES) & (2 * best > window.sum(axis=2, dtype=np.int32))
        return window.argmax(axis=2).astype(np.uint8), sure

    def _learn_ground(self, zone: int, position: Sequence[int], view: np.ndarray) -> None:
        y0, x0 = STEP_PIXELS * int(position[1]), STEP_PIXELS * int(position[0])
        ground = self.grounds.get(zone)
        if ground is None:
            ground = self.grounds[zone] = {"votes": np.zeros((HEIGHT, WIDTH, 4), dtype=np.uint8),
                                           "y": y0, "x": x0, "dirty": True}
        votes = ground["votes"]
        top, left = min(ground["y"], y0), min(ground["x"], x0)
        bottom = max(ground["y"] + votes.shape[0], y0 + HEIGHT)
        right = max(ground["x"] + votes.shape[1], x0 + WIDTH)
        if (top, left, bottom - top, right - left) != (ground["y"], ground["x"], *votes.shape[:2]):
            grown = np.zeros((bottom - top, right - left, 4), dtype=np.uint8)
            grown[ground["y"] - top:ground["y"] - top + votes.shape[0],
                  ground["x"] - left:ground["x"] - left + votes.shape[1]] = votes
            votes = ground["votes"] = grown
            ground["y"], ground["x"] = top, left
        window = votes[y0 - top:y0 - top + HEIGHT, x0 - left:x0 - left + WIDTH]
        rows, columns = np.indices((HEIGHT, WIDTH))
        # One vote per standing place, and a pixel is covered from at most 90 places.
        window[rows, columns, view] += 1
        ground["dirty"] = True
        self.ground_changed.add(zone)

    def ground_patches(self, zone: int, own: Sequence[int]) -> dict[tuple[int, int], str]:
        """The scenery of an area by world cell: a name for each 16-pixel patch its background knows fully.

        ``own`` is the screen cell Cassi's body occupies, which ties world
        cells to background pixels: world cell w sits at area pixel 16(w + own).
        """
        ground = self.grounds.get(zone)
        if ground is None:
            return {}
        votes = ground["votes"]
        best = votes.max(axis=2).astype(np.int32)
        sure = (best >= _GROUND_VOTES) & (2 * best > votes.sum(axis=2, dtype=np.int32))
        shade = votes.argmax(axis=2).astype(np.uint8)
        rows, columns = votes.shape[0] // CELL, votes.shape[1] // CELL
        span = (slice(0, rows * CELL), slice(0, columns * CELL))
        full = sure[span].reshape(rows, CELL, columns, CELL).all(axis=(1, 3))
        blocks = shade[span].reshape(rows, CELL, columns, CELL).transpose(0, 2, 1, 3)
        left, top = ground["x"] // CELL - int(own[0]), ground["y"] // CELL - int(own[1])
        return {(left + column, top + row): hashlib.sha256(np.ascontiguousarray(blocks[row, column]).tobytes()
                                                            ).hexdigest()[:12]
                for row, column in zip(*np.nonzero(full))}

    def self_box(self) -> tuple[int, int, int, int] | None:
        """Screen box of the figure present wherever Cassi stands: (top, left, bottom, right)."""
        if self.presence_views < _SELF_VIEWS:
            return None
        steady = self.presence >= _SELF_PRESENCE * self.presence_views
        if not steady.any():
            return None
        rows, columns = np.flatnonzero(steady.any(axis=1)), np.flatnonzero(steady.any(axis=0))
        return int(rows[0]), int(columns[0]), int(rows[-1]) + 1, int(columns[-1]) + 1

    def _kind(self, figure: Figure) -> tuple[int, bool]:
        """The library kind ``figure`` is, adding a new kind when none shares its shape and shading."""
        span, slack = FIGURE_SPAN, _KIND_SHIFT
        height, width = figure.mask.shape
        count = self.kind_count
        if count:
            sizes = self.kind_sizes[:count]
            near = np.flatnonzero((np.abs(sizes[:, 0] - height) <= 2 * slack)
                                  & (np.abs(sizes[:, 1] - width) <= 2 * slack))
            if near.size:
                mask = np.zeros((span + 2 * slack, span + 2 * slack), dtype=bool)
                shades = np.zeros(mask.shape, dtype=np.uint8)
                mask[slack:slack + height, slack:slack + width] = figure.mask
                shades[slack:slack + height, slack:slack + width] = figure.shades
                masks, kinds = self.kind_masks[near], self.kind_shades[near]
                best = np.zeros(near.size)
                for dy in range(2 * slack + 1):
                    for dx in range(2 * slack + 1):
                        m = mask[dy:dy + span, dx:dx + span]
                        s = shades[dy:dy + span, dx:dx + span]
                        union = (m | masks).sum(axis=(1, 2))
                        same = (m & masks & (s == kinds)).sum(axis=(1, 2))
                        best = np.maximum(best, same / np.maximum(union, 1))
                pick = int(best.argmax())
                if best[pick] >= _KIND_MATCH or count >= _MAX_KINDS:
                    self.kind_seen[near[pick]] += 1
                    self._objects_dirty = True
                    return int(near[pick]), False
        if count >= _MAX_KINDS:
            return -1, False
        self._reserve(count + 1)
        self.kind_masks[count] = False
        self.kind_shades[count] = 0
        self.kind_masks[count, :height, :width] = figure.mask
        self.kind_shades[count, :height, :width] = figure.shades
        self.kind_sizes[count] = (height, width)
        self.kind_seen[count] = 1
        self.kind_count += 1
        self._objects_dirty = True
        return count, True

    def judge(self, figures: Sequence[Figure], *, in_world: bool) -> None:
        """Mark Cassi's own figure, name each whole figure's kind, and flag the first sightings.

        A figure larger than an object is recognized by its exact content, as
        panels are.
        """
        own = self.self_box() if in_world else None
        for figure in figures:
            if own is not None:
                middle_y, middle_x = figure.top + figure.height / 2, figure.left + figure.width / 2
                figure.own = (own[0] - 4 <= middle_y <= own[2] + 4 and own[1] - 4 <= middle_x <= own[3] + 4
                              and not figure.large)
            if figure.own or figure.clipped:
                continue
            if figure.large:
                digest = hashlib.sha256(np.packbits(figure.mask).tobytes() + figure.shades.tobytes())
                figure.new = self.notice(f"figure:{figure.height}x{figure.width}:{digest.hexdigest()[:20]}")
            else:
                figure.kind, figure.new = self._kind(figure)

    def observe(self, zone: int, position: Sequence[int], view: np.ndarray, place: str) -> list[Figure] | None:
        """Read a settled world view as figures against its area's background, then learn from it.

        Returns None when the background is still unknown here or the view
        does not fit it (a misplaced position is never learned). The first
        fitting view from each standing place votes into the background, and
        views with most of the screen known feed Cassi's sense of its own body.
        """
        figures: list[Figure] | None = None
        loose: np.ndarray | None = None
        known = self.ground_window(zone, position)
        fits = True
        covered = 0
        if known is not None:
            shade, sure = known
            covered = int(sure.sum())
            if covered >= HEIGHT * WIDTH // 8:
                fits = float((shade[sure] == view[sure]).mean()) >= _GROUND_AGREEMENT
                if fits:
                    loose = sure & (shade != view)
                    figures = figures_in(loose, view)
        cell = self.cells.get(place)
        if fits and cell is not None and not cell.get("ground"):
            # Only the first view from each place counts, so what is present
            # wherever Cassi stands is its own body, whoever stands beside it.
            if loose is not None and covered >= HEIGHT * WIDTH // 2:
                self.presence += loose
                self.presence_views += 1
                self._objects_dirty = True
            self._learn_ground(zone, position, view)
            cell["ground"] = True
        if figures is not None:
            self.judge(figures, in_world=True)
        return figures

    # -- perception memory ---------------------------------------------------
    def region(self, tiles: np.ndarray) -> int:
        """The learned screen region a partial change belongs to; grows until the slots are full.

        A change matches a region of the same extent, or else falls inside the
        smallest known region that holds it (a cursor inside a menu).
        """
        box = bounds(tiles)
        scored = [(_overlap(box, known), index) for index, known in enumerate(self.regions)]
        best = max(scored, default=(0.0, -1))
        if best[0] >= _REGION_MATCH:
            return best[1]
        full = len(self.regions) >= REGION_SLOTS
        holders = [(_area(known), index) for index, known in enumerate(self.regions)
                   if _shared(box, known) >= _REGION_INSIDE * _area(box)
                   and (full or 2 * _area(known) <= ROWS * COLUMNS)]
        if holders:
            return min(holders)[1]
        if full:
            return best[1] if best[1] >= 0 else 0
        self.regions.append(list(box))
        return len(self.regions) - 1

    def notice(self, key: str) -> bool:
        """Record a sight; True the first time it is seen."""
        if key in self.events:
            self.events[key] += 1
            return False
        if len(self.events) < _MAX_EVENTS:
            self.events[key] = 1
        return True

    @property
    def progress(self) -> int:
        """How much Cassi has witnessed: distinct sights so far."""
        return len(self.events)

    def locate(self, view: np.ndarray) -> tuple[int, tuple[int, int]] | None:
        """Place a new scene against remembered keyframes: (area, position) or None."""
        small = view[::2, ::2]
        best: tuple[float, int, tuple[int, int]] | None = None
        for zone, x, y, key in self.keyframes:
            dx, dy = displacement(key[::2, ::2], small)
            dx, dy = dx * 2, dy * 2
            score = agreement(key, view, dx, dy)
            if best is None or score > best[0]:
                best = (score, zone, (x - round(dx / STEP_PIXELS), y - round(dy / STEP_PIXELS)))
        if best is None or best[0] < _RELOCATE_AGREEMENT:
            return None
        return best[1], best[2]

    def remember_view(self, zone: int, position: tuple[int, int], view: np.ndarray) -> None:
        """Keep a keyframe of this area, spread out so relocalization covers its ground."""
        near = [(x, y) for z, x, y, _ in self.keyframes if z == zone]
        if len(near) >= _KEYFRAMES_PER_AREA:
            return
        if any(max(abs(x - position[0]), abs(y - position[1])) < _KEYFRAME_SPACING for x, y in near):
            return
        self.keyframes.append((zone, int(position[0]), int(position[1]), view.copy()))

    # -- recording -----------------------------------------------------------
    @property
    def snapshots(self) -> int:
        return sum(1 for cell in self.cells.values() if cell.get("snapshot"))

    def visit(self, zone: int | None, position: tuple[int, int], *, step: int) -> tuple[str, bool, bool, int]:
        """Stand at ``position`` in ``zone`` (None opens a new area at its origin).

        Returns (place, new place, new area, area).
        """
        new_zone = zone is None
        if new_zone:
            zone = len(self.zones)
            self.zones.append({"first_step": step, "cells": 0})
            position = (0, 0)
        place = place_key(zone, position)
        cell = self.cells.get(place)
        if cell is not None:
            cell["visits"] += 1
            return place, False, new_zone, zone
        self.cells[place] = {"zone": zone, "visits": 1, "returns": 0, "step": step,
                             "snapshot": False, "pos": [int(position[0]), int(position[1])]}
        self.zones[zone]["cells"] += 1
        return place, True, new_zone, zone

    def note_try(self, context: str, action: str, outcome: str) -> None:
        """Remember what ``action`` did from ``context`` (a place or an open event)."""
        row = self.tries.get(context)
        if row is None:
            if len(self.tries) >= _MAX_CONTEXTS:
                self.tries.pop(next(iter(self.tries)))
            row = self.tries[context] = {}
        entry = row.setdefault(action, [outcome, 0])
        entry[0] = outcome
        entry[1] += 1
        totals = self.action_totals.setdefault(action, [0, 0])
        totals[0] += 1
        totals[1] += outcome == "still"

    def spent(self, context: str, *, at_place: bool, actions: Sequence[str]) -> set[str]:
        """Presses known to do nothing new from ``context``; never every action.

        Standing in the world, a press that left the screen still, only turned
        Cassi, or repeated a known object or panel is spent. Inside an open
        panel only a press that changed nothing is.
        """
        row = self.tries.get(context, {})
        spent = {action for action, (outcome, _) in row.items() if futile(outcome, at_place=at_place)}
        spent.update(action for action, (tries, still) in self.action_totals.items()
                     if tries >= _GLOBAL_TRIES and still == tries)
        spent.intersection_update(actions)
        return set() if len(spent) >= len(actions) else spent

    def stale(self, place: str) -> bool:
        """True when ``place`` has no save taken at the story's current point."""
        cell = self.cells.get(place)
        return cell is not None and (not cell.get("snapshot") or cell.get("progress", -1) < self.progress)

    def store_snapshot(self, place: str, state: bytes) -> bool:
        """Save the game at ``place``, replacing a save from earlier in the story."""
        cell = self.cells.get(place)
        if cell is None or not self.stale(place):
            return False
        if not cell.get("snapshot") and self.snapshots >= self.max_snapshots:
            return False
        self._states.mkdir(parents=True, exist_ok=True)
        target = self._states / f"{place}.gbs.z"
        descriptor, temporary = tempfile.mkstemp(prefix=f".{place}.", suffix=".tmp", dir=self._states)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(zlib.compress(state, 6))
        os.replace(temporary, target)
        cell["snapshot"] = True
        cell["progress"] = self.progress
        return True

    def snapshot(self, place: str) -> bytes:
        return zlib.decompress((self._states / f"{place}.gbs.z").read_bytes())

    # -- what things do ------------------------------------------------------
    def learn_use(self, thing: str, verb: str, effects: Sequence[str], where: str, *, taught: bool) -> bool:
        """Record what ``verb`` did to ``thing`` at world cell ``where``; True when an effect is new for it.

        ``taught`` says the use brought any discovery (a new sign's words, a
        new room), which keeps a verb worth repeating on things of this kind.
        """
        row = self.uses.setdefault(thing, {}).setdefault(verb, {})
        fresh = any(effect not in row for effect in effects)
        for effect in effects:
            row[effect] = row.get(effect, 0) + 1
        stats = self.use_stats.setdefault(f"{thing}|{verb}", [0, 0])
        stats[0] += 1
        stats[1] += fresh or taught
        verbs = self.engaged.setdefault(where, [])
        if verb not in verbs:
            verbs.append(verb)
        self._retired = None
        return fresh

    def retired(self) -> set[str]:
        """Verbs whose answer does not depend on the thing: one effect set on most of many things."""
        if self._retired is None:
            answers: dict[str, dict[frozenset[str], int]] = {}
            for verbs in self.uses.values():
                for verb, effects in verbs.items():
                    row = answers.setdefault(verb, {})
                    row[frozenset(effects)] = row.get(frozenset(effects), 0) + 1
            self._retired = {verb for verb, row in answers.items()
                             if sum(row.values()) >= _RETIRE_THINGS
                             and max(row.values()) >= _RETIRE_SHARE * sum(row.values())}
        return self._retired

    def curious(self, thing: str, where: str) -> list[str]:
        """Verbs worth using on ``thing`` standing at world cell ``where``.

        A verb never used on this kind of thing is worth one use. A verb that
        did more than stand still or walk on it is worth using once at each
        new spot while such uses keep teaching something.
        """
        retired = self.retired()
        done = self.engaged.get(where, ())
        known = self.uses.get(thing, {})
        verbs: list[str] = []
        for verb in VERBS:
            if verb in retired:
                continue
            effects = known.get(verb)
            if effects is None:
                verbs.append(verb)
                continue
            if verb in done or not set(effects) - _PLAIN_EFFECTS:
                continue
            uses, taught = self.use_stats.get(f"{thing}|{verb}", [0, 0])
            if (taught + 1) / (uses + 2) >= _USE_WORTH:
                verbs.append(verb)
        return verbs

    def promise(self, thing: str, where: str) -> float:
        """How much using ``thing`` at world cell ``where`` is expected to teach.

        Each curious verb counts its share of uses that taught something, and
        an untried verb counts half. Doors that lead somewhere new and people
        with new words keep their promise; a thing that answers the same way
        everywhere loses it.
        """
        total = 0.0
        known = self.uses.get(thing, {})
        for verb in self.curious(thing, where):
            if verb not in known:
                total += 0.5
            else:
                uses, taught = self.use_stats.get(f"{thing}|{verb}", [0, 0])
                total += (taught + 1) / (uses + 2)
        return total

    def see(self, zone: int, origin: Sequence[int], things: Mapping[tuple[int, int], str]) -> None:
        """Remember the things of a settled view; ``origin`` is the world cell of screen cell (0, 0)."""
        for row in range(CELL_ROWS):
            for column in range(CELL_COLUMNS):
                key = place_key(zone, (origin[0] + column, origin[1] + row))
                thing = things.get((column, row))
                if thing is None:
                    self.sightings.pop(key, None)
                else:
                    self.sightings[key] = thing

    def prospects(self) -> list[tuple[str, tuple[int, int, int], float]]:
        """Remembered things still worth using, in every area: (world cell, (area, x, y), promise)."""
        rows = []
        for key, thing in self.sightings.items():
            worth = self.promise(thing, key)
            if worth > 0:
                rows.append((key, _cell_of(key), worth))
        return rows

    def doings(self, limit: int = 12) -> list[list[Any]]:
        """The things that do something, most used first: [thing, verb, effects, uses]."""
        rows = [[thing, verb, sorted(effects), sum(effects.values())]
                for thing, verbs in self.uses.items() for verb, effects in verbs.items()
                if set(effects) - _PLAIN_EFFECTS]
        rows.sort(key=lambda row: -row[3])
        return rows[:limit]

    # -- going back ----------------------------------------------------------
    def resumable(self, exclude: str | None) -> dict[str, dict[str, Any]]:
        """Places with a save taken at the story's current point."""
        return {key: cell for key, cell in self.cells.items()
                if cell.get("snapshot") and key != exclude and not self.stale(key)}

    def choose_return(self, rng: random.Random, *, exclude: str | None,
                      pull: Mapping[str, float]) -> str | None:
        """Pick a place to resume from without rewinding the story.

        ``pull`` is what the world field holds at each resumable place. Cassi
        resumes where the pull is strongest, discounted by how often it has
        already come back there; with no pull anywhere, it picks at random,
        favouring newer areas and places visited less.
        """
        current = self.resumable(exclude)
        pulled = [(pull.get(key, 0.0) / math.sqrt(1 + cell["returns"]), key)
                  for key, cell in current.items() if pull.get(key, 0.0) > 0]
        if pulled:
            key = max(pulled)[1]
        else:
            newest_zone = len(self.zones) - 1
            candidates = [(key, (2.0 if int(cell["zone"]) == newest_zone else 1.0)
                           / math.sqrt(1 + cell["returns"]) / math.sqrt(cell["visits"]))
                          for key, cell in current.items()]
            if not candidates:
                return None
            pick = rng.random() * sum(weight for _, weight in candidates)
            for key, weight in candidates:
                pick -= weight
                if pick <= 0:
                    break
        self.cells[key]["returns"] += 1
        self.returns += 1
        return key

    def summary(self) -> dict[str, Any]:
        return {
            "places": len(self.cells),
            "areas": len(self.zones),
            "snapshots": self.snapshots,
            "sights": len(self.events),
            "regions": len(self.regions),
            "keyframes": len(self.keyframes),
            "objects": self.kind_count,
            "self": self.self_box(),
            "returns": self.returns,
            "things": len(self.uses),
            "remembered_things": len(self.sightings),
            "retired_verbs": sorted(self.retired()),
            "doings": self.doings(),
        }
