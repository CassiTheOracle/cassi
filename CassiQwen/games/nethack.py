"""NetHack: the first world.

The game is the console build of NetHack 5.0.  Its interface is a screen and a
keyboard, so this module is NetHack's *perception and vocabulary*: what the
screen means (message line, map, status lines, menus, questions) and what Cassi
may do (the game's own verbs, spelled the way the game spells them).

Two facts about this build shape everything here:

* the character, the tutorial prompt, and the keypad all come from the game's
  own config file, which this world writes and owns;
* a life's files live per player name, and a stale file from a killed run makes
  the next start ask to recover an old game — so a fresh life begins by clearing
  the name.
"""
from __future__ import annotations

import os
import re
import shutil
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from games.screen import ScreenWorld
from games.terminal import ScreenFrame, TerminalSession
from games.world import Action, Observation, WorldError, register_world

NETHACK_HOME = Path("C:/Users/Carina/NetHack")
NETHACK_RC = NETHACK_HOME / ".nethackrc"
NETHACK_RC_BACKUP = NETHACK_HOME / ".nethackrc.original"
PLAYER_HOME = Path("C:/Users/Carina/AppData/Local/NetHack/5.0")
SHARED_HOME = Path("C:/ProgramData/NetHack/5.0")
DEFAULT_PROGRAM = Path(
    "C:/Users/Carina/AppData/Local/Microsoft/WinGet/Packages"
    "/Nethack.Nethack_Microsoft.Winget.Source_8wekyb3d8bbwe/NetHack.exe"
)

RC_MARKER = "# Cassi's NetHack configuration"
RC_TEXT = f"""\
{RC_MARKER}.  Written by CassiQwen/games/nethack.py; edits are overwritten.
OPTIONS=name:Cassi,role:Valkyrie,race:dwarf,gender:female,align:lawful
OPTIONS=!tutorial
OPTIONS=!splash_screen
OPTIONS=symset:IBMGraphics_2
OPTIONS=showexp
"""

MOVE_KEYS = {
    "k": "north",
    "j": "south",
    "h": "west",
    "l": "east",
    "y": "northwest",
    "u": "northeast",
    "b": "southwest",
    "n": "southeast",
}

# The same moves as map-cell steps (rows grow downward, columns to the right).
_STEP_OF_MOVE = {
    "north": (-1, 0),
    "south": (1, 0),
    "west": (0, -1),
    "east": (0, 1),
    "northwest": (-1, -1),
    "northeast": (-1, 1),
    "southwest": (1, -1),
    "southeast": (1, 1),
}

PLAY_ACTIONS: tuple[tuple[str, str], ...] = (
    *((key, f"move {name}") for key, name in MOVE_KEYS.items()),
    (".", "wait one turn, letting the world act"),
    ("s", "search the ground and walls for hidden things"),
    (",", "pick up what is lying here"),
    (">", "go down the stairs (only works standing on '>')"),
    ("<", "go up the stairs (only works standing on '<')"),
    ("o", "open a door or a container next to you"),
    ("c", "close a door next to you"),
    ("i", "review your inventory"),
    ("e", "eat something you carry"),
    ("q", "quaff a potion you carry"),
    ("r", "read a scroll you carry"),
    ("w", "wield a weapon you carry"),
    ("W", "wear armor you carry"),
    ("T", "take off something you are wearing"),
    ("P", "put on an accessory you carry"),
    ("R", "remove an accessory you wear"),
    ("d", "drop something you carry"),
    ("a", "apply a tool you carry"),
    ("z", "zap a wand you carry"),
    ("t", "throw something you carry"),
    ("p", "pay a shopkeeper"),
    ("#pray", "pray to your deity for help"),
    ("#sit", "sit down on what is here"),
    ("#loot", "loot a container or a grave here"),
    ("#force", "force a lock with a weapon"),
    ("#enhance", "advance your weapon and spell skills"),
    ("#conduct", "review the conduct of this life"),
    ("S", "save the game and stop for now"),
)

# A life in a campaign is bounded by its turns and its death, and stopping is
# the human's file to create.  Offering the mind "save and stop" gave it a
# give-up action it reached for whenever it had no plan: in one measured life it
# proposed saving 45 times in 341 turns, each proposal costing a turn to open
# the prompt and another to decline it.
NO_SAVE_ACTIONS = tuple(item for item in PLAY_ACTIONS if item[0] != "S")

_QUESTION = re.compile(r"\[[^\]]*[yn][^\]]*\]")
_MENU_ROW = re.compile(r"^\s*([a-zA-Z0-9])\s*[-+*]?\s+-\s+(.{2,})$")
_STAT_FIELD = re.compile(r"\b(St|Dx|Co|In|Wi|Ch):(\d+)(?:/(\d+))?")
_STATUS_FIELD = {
    "depth": re.compile(r"Dlvl:(-?\d+)"),
    "gold": re.compile(r"\$:(-?\d+)"),
    "hp": re.compile(r"HP:(\d+)\((\d+)\)"),
    "power": re.compile(r"Pw:(\d+)\((\d+)\)"),
    "armor": re.compile(r"AC:(-?\d+)"),
    "experience": re.compile(r"Xp:(\d+)(?:/(\d+))?"),
    "turns": re.compile(r"T:(\d+)"),
}
_ALIGNMENT = re.compile(r"\b(Lawful|Neutral|Chaotic|unaligned)\b")
# What a map cell of NetHack means, as the seam's own vocabulary: the classes a
# memory can hold.  Anything not listed is a thing standing on a floor tile
# (monsters, items, features), so it reads as open ground.
SOLID_GLYPHS = frozenset("|-S\u2500\u2502\u250c\u2510\u2514\u2518\u251c\u2524\u252c\u2534\u253c")
DOOR_GLYPHS = frozenset("+")
GOAL_GLYPHS = {">": "down", "<": "up"}
# What the field remembers as worth walking to: the score itself, and the food
# and items a crawl runs on.  The classes match CELL_WRITES in fieldmemory; '+'
# is not here because a closed door is read as a door before any item class.
VALUE_GLYPHS = {"$": "gold"}
VALUE_GLYPHS.update({glyph: "goods" for glyph in '%?!)[="(/*'})
_DEATH = (
    "Do you want your possessions identified?",
    "DYWYPI",
    "You die",
    "Goodbye ",
)
_STORY = (
    "It is written in the Book of",
    "Shall I pick",
    "Is this ok?",
    "Who are you?",
)


class NetHackError(WorldError):
    """The NetHack world cannot be prepared or addressed."""


@register_world("nethack")
class NetHackWorld(ScreenWorld):
    """One life in NetHack, driven through the screen."""

    name = "nethack"
    PROSE_ROWS = (0, 22, 23)
    # NetHack levels are exactly 80 columns by 21 rows, drawn under the message
    # line, so a screen cell is a level cell and no scrolling has to be undone.
    map_top = 1
    map_rows = 21
    map_cols = 80
    goal = (
        "Descend into the dungeon, stay alive, and grow strong enough to find "
        "the Amulet of Yendor and bring it back up."
    )

    def __init__(
        self,
        *,
        program: str | Path | None = None,
        player: str = "Cassi",
        strategy: str = "standard",
        quiet: float = 0.35,
        write_config: bool = True,
        cols: int = 80,
        rows: int = 24,
        allow_save: bool = True,
    ) -> None:
        super().__init__(cols=cols, rows=rows, quiet=quiet)
        if strategy != "standard":
            raise NetHackError(f"unknown NetHack strategy {strategy!r}")
        self.allow_save = bool(allow_save)
        self.program = Path(program or _discover_program())
        self.player = player
        self.character = _character_line(RC_TEXT)
        self.write_config = write_config
        self.cleared: tuple[str, ...] = ()
        self.menu: tuple[Action, ...] = ()
        self.message = ""

    # -- preparation -----------------------------------------------------
    def prepare(self) -> Mapping[str, Any]:
        """Write the game's config and clear the player's stale files."""
        if not self.program.exists():
            raise NetHackError(f"NetHack program is missing: {self.program}")
        if self.write_config:
            install_config()
        self.cleared = clear_player_state(self.player)
        return {
            "program": str(self.program),
            "player": self.player,
            "character": self.character,
            "cleared": list(self.cleared),
        }

    def argv(self) -> Sequence[str]:
        return [str(self.program)]

    def reset(self) -> Observation:
        self.prepare()
        return super().reset()

    # -- startup ---------------------------------------------------------
    STARTUP_TIMEOUT = 90.0

    def handshake(self, session: TerminalSession) -> None:
        """Answer the opening questions until the dungeon is on screen.

        The game is slow to draw its first screen and then waits for a key:
        each step either reads something new, sends the one key the screen is
        waiting for, or waits for the game to say something else.
        """
        deadline = time.time() + self.STARTUP_TIMEOUT
        seen = -1
        while time.time() < deadline:
            frame = session.frame()
            if frame.quiet < self.quiet or frame.revision == seen:
                # the screen is still being drawn, or has not changed: wait.
                session.wait_change(frame.revision, timeout=0.5)
                continue
            seen = frame.revision
            if self._playable(frame):
                return
            key = self._answer(frame)
            if key is None:
                continue
            session.send(key, quiet=self.quiet, timeout=30.0)
        last = " / ".join(line for line in session.frame().lines if line.strip())
        raise NetHackError(
            f"NetHack never reached a playable screen in {self.STARTUP_TIMEOUT:.0f}s; "
            f"last screen was: {last[:400]!r}"
        )

    @staticmethod
    def _playable(frame: ScreenFrame) -> bool:
        text = frame.text
        return (
            "@" in text
            and "Dlvl:" in text
            and "--More--" not in text
            and "Hit <Enter> to continue" not in text
            and not any(story in text for story in _STORY)
        )

    def _answer(self, frame: ScreenFrame) -> str | None:
        """The key this screen is waiting for, or None to wait longer."""
        text = frame.text
        if "Hit <Enter> to continue" in text:
            return "\r"
        if "Recover?" in text:
            return "n"
        if "Shall I pick character" in text:
            return "y"
        if "Is this ok?" in text:
            return "y"
        if "Who are you?" in text:
            return f"{self.player}\r"
        if "--More--" in text:
            return " "
        return None

    # -- perception ------------------------------------------------------
    def read(self, frame: ScreenFrame) -> Mapping[str, Any]:
        reading: dict[str, Any] = {}
        message = self.message_line(frame)
        self.message = message
        reading["message"] = message
        reading["summary"] = self._status(frame)
        self.menu = self._menu(frame)
        prompt = self._prompt(frame, message)
        if prompt:
            reading["prompt"] = prompt
        if any(marker in frame.text for marker in _DEATH):
            reading["done"] = True
        reading["score"] = float(reading["summary"].get("gold", self.score))
        return reading

    def level_cells(self, frame: ScreenFrame) -> Mapping[tuple[int, int], str]:
        """The map as the seam's cell classes: what a memory can keep.

        Rows are numbered from 0 at the top of the map area (the screen's row 1),
        so a cell here is the cell the player sees on the same screen column.
        Blank cells are unlit or unexplored, which is not knowledge.
        """
        cells: dict[tuple[int, int], str] = {}
        for row in range(self.map_rows):
            line = frame.row(self.map_top + row)
            for col, glyph in enumerate(line[: self.map_cols]):
                if glyph in GOAL_GLYPHS:
                    cells[(row, col)] = GOAL_GLYPHS[glyph]
                elif glyph in SOLID_GLYPHS:
                    cells[(row, col)] = "solid"
                elif glyph in DOOR_GLYPHS:
                    cells[(row, col)] = "door"
                elif glyph in VALUE_GLYPHS:
                    cells[(row, col)] = VALUE_GLYPHS[glyph]
                elif glyph.strip():
                    # A feature (the shade glyph ░, the square ■), a monster, an
                    # item: things that stand on a floor tile, so the ground
                    # under them is ground.  Only a blank cell -- unlit or
                    # unexplored -- is not knowledge.
                    cells[(row, col)] = "open"
        return cells

    def map_cell(self, position: tuple[int, int] | None) -> tuple[int, int] | None:
        """A screen position as a map cell (the map starts one row down)."""
        if position is None:
            return None
        return (position[0] - self.map_top, position[1])

    def move_action(self, step: tuple[int, int]) -> Action | None:
        """The action that moves the player by (down, right) map cells."""
        down, right = int(step[0]), int(step[1])
        for key, name in MOVE_KEYS.items():
            row, col = _STEP_OF_MOVE[name]
            if (row, col) == (down, right):
                return Action(key=key, keys=key, label=f"move {name}")
        return None

    @staticmethod
    def _status(frame: ScreenFrame) -> dict[str, Any]:
        block = "\n".join(frame.lines[-4:])
        summary: dict[str, Any] = {}
        for field, pattern in _STATUS_FIELD.items():
            match = pattern.search(block)
            if not match:
                continue
            if field in {"hp", "power"}:
                summary[field] = int(match.group(1))
                summary[f"{field}_max"] = int(match.group(2))
            elif field == "experience":
                summary["experience"] = int(match.group(1))
                if match.group(2) is not None:
                    summary["experience_next"] = int(match.group(2))
            else:
                summary[field] = int(match.group(1))
        stats: dict[str, int] = {}
        for short, value, _partial in _STAT_FIELD.findall(block):
            stats[short] = int(value)
        if stats:
            summary["stats"] = stats
        alignment = _ALIGNMENT.search(block)
        if alignment:
            summary["alignment"] = alignment.group(1)
        for line in frame.lines[-3:]:
            rank = re.match(r"\s*(.+?)\s{2,}\S+:", line)
            if rank and ":" not in rank.group(1):
                summary["character"] = rank.group(1).strip()
                break
        if "Hallu" in block:
            summary["hallucinating"] = True
        for condition in ("Blind", "Conf", "Stun", "FoodPois", "Ill", "Burdened", "Satiated"):
            if condition in block:
                summary[condition.lower()] = True
        return summary

    @staticmethod
    def _menu(frame: ScreenFrame) -> tuple[Action, ...]:
        options: list[Action] = []
        for line in frame.lines:
            match = _MENU_ROW.match(line)
            if not match:
                continue
            key, label = match.group(1), match.group(2).strip()
            if len(options) >= 26:
                break
            options.append(Action(key=key, keys=key, label=label[:80]))
        return tuple(options)

    @staticmethod
    def _prompt(frame: ScreenFrame, message: str) -> str | None:
        if "--More--" in message:
            return message
        if _QUESTION.search(message):
            return message
        if message.strip().endswith("?"):
            return message.strip()
        if "Hit <Enter> to continue" in frame.text:
            return "press Enter to continue"
        if "Recover?" in frame.text:
            return "recover an interrupted game?"
        asked = _QUESTION.search(frame.text)
        if asked:
            return asked.group(0)
        if frame.lines and frame.lines[-1].strip().endswith("?"):
            return frame.lines[-1].strip()
        return None

    # -- vocabulary ------------------------------------------------------
    def vocabulary(self, frame: ScreenFrame) -> tuple[Action, ...]:
        text = frame.text
        if "--More--" in text or "Hit <Enter> to continue" in text:
            return (
                Action(key="continue", keys=" ", label="read on"),
                Action(key="stop-reading", keys="\x1b", label="stop reading"),
            )
        if "Recover?" in text or "[yn" in frame.row(0):
            return (
                Action(key="yes", keys="y", label="answer yes"),
                Action(key="no", keys="n", label="answer no"),
            )
        if "In what direction" in frame.row(0):
            return tuple(
                Action(key=key, keys=key, label=f"point {name}")
                for key, name in MOVE_KEYS.items()
            )
        if self.menu:
            return self.menu
        offered = PLAY_ACTIONS if self.allow_save else NO_SAVE_ACTIONS
        return tuple(Action(key=key, keys=key, label=label) for key, label in offered)

    # -- lifecycle -------------------------------------------------------
    def close(self) -> None:
        session, self.session = self.session, None
        if session is not None:
            session.close()


def _discover_program() -> Path:
    override = os.environ.get("CASSI_NETHACK_EXE")
    if override:
        return Path(override)
    if DEFAULT_PROGRAM.exists():
        return DEFAULT_PROGRAM
    which = shutil.which("nethackcmd") or shutil.which("nethack") or shutil.which("NetHack")
    if which:
        return Path(which)
    raise NetHackError(
        "NetHack was not found; set CASSI_NETHACK_EXE or install it (winget install Nethack.Nethack)"
    )


def _character_line(rc_text: str) -> str:
    for line in rc_text.splitlines():
        if "role:" in line:
            fields = dict(
                part.split(":", 1) for part in line.split("=", 1)[1].split(",") if ":" in part
            )
            return (
                f"{fields.get('name', 'Cassi')} the "
                f"{fields.get('align', 'lawful')} {fields.get('gender', 'female')} "
                f"{fields.get('race', 'dwarf')} {fields.get('role', 'Valkyrie')}"
            )
    return "Cassi"


def install_config() -> Path:
    """Write Cassi's NetHack options, keeping one backup of the original."""
    NETHACK_HOME.mkdir(parents=True, exist_ok=True)
    if NETHACK_RC.exists():
        current = NETHACK_RC.read_text(encoding="utf-8", errors="replace")
        if RC_MARKER not in current and not NETHACK_RC_BACKUP.exists():
            shutil.copy2(NETHACK_RC, NETHACK_RC_BACKUP)
    NETHACK_RC.write_text(RC_TEXT, encoding="utf-8")
    return NETHACK_RC


def clear_player_state(player: str) -> tuple[str, ...]:
    """Remove this player's stale level/save/lock files so a life starts clean."""
    prefix = player.lower() + "."
    removed: list[str] = []
    if PLAYER_HOME.is_dir():
        for path in sorted(PLAYER_HOME.iterdir()):
            if path.is_file() and path.name.lower().startswith(prefix):
                removed.append(str(path))
                path.unlink()
    if SHARED_HOME.is_dir():
        for path in sorted(SHARED_HOME.glob("*lock*")):
            removed.append(str(path))
            path.unlink()
    return tuple(removed)


