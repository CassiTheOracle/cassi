"""Terminal sessions: a live text-mode program we can see and touch.

A `TerminalSession` owns one child process attached to a Windows pseudoconsole
(ConPTY), a background reader that decodes the VT stream into a screen model,
and the clock that says when the screen has settled.  Everything a text game
needs to be watchable and playable passes through here: the game repaints the
screen, we read the screen, and we type into it.

The screen model is authoritative: a text game's screen *is* its world state as
far as any player can tell, so nothing above this layer scrapes the raw stream.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, Sequence

import pyte
import winpty

DEFAULT_COLS = 80
DEFAULT_ROWS = 24
RAW_TAIL_LIMIT = 256 * 1024


class TerminalError(RuntimeError):
    """A terminal session could not be started, addressed, or read."""


@dataclass(frozen=True, slots=True)
class ScreenFrame:
    """One settled screen: what a human sitting at this terminal would see."""

    lines: tuple[str, ...]
    cursor: tuple[int, int]
    revision: int
    quiet: float

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    def row(self, index: int) -> str:
        if not 0 <= index < len(self.lines):
            raise TerminalError(f"screen row {index} is outside the frame")
        return self.lines[index]

    def find(self, needle: str) -> tuple[int, int] | None:
        """First (row, column) whose text starts `needle` (case-sensitive)."""
        for index, line in enumerate(self.lines):
            column = line.find(needle)
            if column >= 0:
                return index, column
        return None


class TerminalSession:
    """One live terminal program: spawn, read the screen, type into it."""

    def __init__(
        self,
        argv: Sequence[str],
        *,
        cols: int = DEFAULT_COLS,
        rows: int = DEFAULT_ROWS,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        if not argv:
            raise TerminalError("terminal session requires a program to run")
        self.argv = tuple(str(item) for item in argv)
        self.cols = int(cols)
        self.rows = int(rows)
        self.cwd = cwd
        self.env = dict(env) if env else None
        self._screen = pyte.Screen(self.cols, self.rows)
        self._stream = pyte.Stream(self._screen)
        self._lock = threading.RLock()
        self._process: winpty.PtyProcess | None = None
        self._reader: threading.Thread | None = None
        self._stop = threading.Event()
        self._eof = threading.Event()
        self._revision = 0
        self._last_output_at = 0.0
        self._started_at = 0.0
        self._raw = ""
        self._sent: list[str] = []
        self._closing = False
        self._surface_send_token: object | None = None
        self._surface_sender: Callable[..., ScreenFrame] | None = None
        self._surface_close_hook: Callable[[], None] | None = None

    # -- lifecycle -------------------------------------------------------
    def start(self) -> "TerminalSession":
        if self._process is not None:
            raise TerminalError("terminal session is already started")
        self._closing = False
        self._process = winpty.PtyProcess.spawn(
            list(self.argv),
            dimensions=(self.rows, self.cols),
            cwd=self.cwd,
            env=self.env,
        )
        self._started_at = time.time()
        self._last_output_at = self._started_at
        self._reader = threading.Thread(
            target=self._read_loop,
            name="cassiterm-reader",
            daemon=True,
        )
        self._reader.start()
        return self

    def close(self, *, timeout: float = 5.0) -> None:
        with self._lock:
            if self._closing:
                return
            self._closing = True
            close_hook = self._surface_close_hook
        self._stop.set()
        if close_hook is not None:
            try:
                close_hook()
            except Exception:  # broker may already be closed; process still must be reaped
                pass
        with self._lock:
            self._surface_send_token = None
            self._surface_sender = None
            self._surface_close_hook = None
        process = self._process
        if process is not None:
            try:
                if process.isalive():
                    process.terminate(force=True)
            except Exception:  # pragma: no cover - terminal already gone
                pass
            try:
                process.wait(timeout=timeout)
            except Exception:  # pragma: no cover - best effort reap
                pass
        reader = self._reader
        if reader is not None and reader.is_alive():
            reader.join(timeout=timeout)

    @property
    def accepting_input(self) -> bool:
        return not self._closing and self._process is not None and not self.exited()

    def enable_surface_transport(
        self,
        sender: Callable[..., ScreenFrame],
        close_hook: Callable[[], None],
    ) -> object:
        """Route every `send()` through the broker until this session closes."""
        if not callable(sender) or not callable(close_hook):
            raise TerminalError("Surface transport requires callable send and close hooks")
        with self._lock:
            if self._surface_send_token is not None:
                raise TerminalError("Surface transport is already installed")
            token = object()
            self._surface_send_token = token
            self._surface_sender = sender
            self._surface_close_hook = close_hook
            return token

    def _send_from_surface(
        self,
        token: object,
        keys: str,
        *,
        quiet: float,
        idle: float,
        timeout: float,
    ) -> ScreenFrame:
        with self._lock:
            if token is not self._surface_send_token:
                raise TerminalError("Surface transport token is stale")
            if self._closing:
                raise TerminalError("terminal session is closing")
        return self._send_direct(keys, quiet=quiet, idle=idle, timeout=timeout)

    def _send_direct(
        self,
        keys: str,
        *,
        quiet: float,
        idle: float,
        timeout: float,
    ) -> ScreenFrame:
        if self._closing:
            raise TerminalError("terminal session is closing")
        if self._process is None:
            raise TerminalError("terminal session is not started")
        if self.exited():
            raise TerminalError("terminal session has exited; no keys can be sent")
        stamp = time.time()
        with self._lock:
            self._sent.append(keys)
            self._sent = self._sent[-64:]
        self._process.write(keys)
        self.wait_quiet(
            quiet=quiet,
            timeout=min(timeout, idle + quiet),
            since=stamp,
        )
        return self.frame()

    def __enter__(self) -> "TerminalSession":
        return self.start()

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- reading ---------------------------------------------------------
    def _read_loop(self) -> None:
        process = self._process
        assert process is not None
        while not self._stop.is_set():
            try:
                chunk = process.read(65536)
            except EOFError:
                break
            except Exception as exc:  # pragma: no cover - pty torn down
                self._error = f"{type(exc).__name__}: {exc}"
                break
            if not chunk:
                break
            with self._lock:
                self._stream.feed(chunk)
                self._raw = (self._raw + chunk)[-RAW_TAIL_LIMIT:]
                self._revision += 1
                self._last_output_at = time.time()
        self._eof.set()

    def busy(self) -> bool:
        return self._process is not None and self._process.isalive()

    def exited(self) -> bool:
        return self._eof.is_set() or not self.busy()

    def quiet_for(self) -> float:
        if self._last_output_at == 0.0:
            return 0.0
        return time.time() - self._last_output_at

    def wait_quiet(
        self,
        *,
        quiet: float = 0.35,
        timeout: float = 15.0,
        since: float | None = None,
    ) -> bool:
        """Wait until the screen has not changed for `quiet` seconds.

        `since` is a wall-clock stamp to wait past first (the moment a command
        was sent), so a fast screen repaint cannot be mistaken for a settled one.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                changed_at = self._last_output_at
                quiet_now = time.time() - changed_at
            if since is not None and changed_at < since:
                time.sleep(0.01)
                continue
            if quiet_now >= quiet:
                return True
            if self.exited():
                return True
            time.sleep(0.02)
        return False

    def wait_change(
        self,
        revision: int,
        *,
        timeout: float = 15.0,
        poll: float = 0.02,
    ) -> bool:
        """Wait until the program writes something new after `revision`.

        A slow program is silent for seconds at a time; waiting for quiet would
        return at once on a screen that has simply not been drawn yet.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                changed = self._revision != revision
            if changed:
                return True
            if self.exited():
                return True
            time.sleep(poll)
        return False

    def wait_for(
        self,
        needle: str,
        *,
        timeout: float = 15.0,
        quiet: float = 0.25,
    ) -> bool:
        """Wait until `needle` appears on the settled screen."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.frame().find(needle) is not None:
                if self.wait_quiet(quiet=quiet, timeout=max(0.1, deadline - time.time())):
                    if self.frame().find(needle) is not None:
                        return True
            if self.exited():
                return self.frame().find(needle) is not None
            time.sleep(0.05)
        return self.frame().find(needle) is not None

    def frame(self) -> ScreenFrame:
        with self._lock:
            lines = tuple(line.rstrip() for line in self._screen.display)
            cursor = (self._screen.cursor.x, self._screen.cursor.y)
            revision = self._revision
        return ScreenFrame(
            lines=lines,
            cursor=cursor,
            revision=revision,
            quiet=self.quiet_for(),
        )

    def raw_tail(self) -> str:
        with self._lock:
            return self._raw

    def error(self) -> str | None:
        return self._error

    # -- writing ---------------------------------------------------------
    def send(
        self,
        keys: str,
        *,
        quiet: float = 0.35,
        idle: float = 3.0,
        timeout: float = 20.0,
    ) -> ScreenFrame:
        """Type `keys` and return the screen once it has settled.

        When Surface transport is installed, every write is routed through the
        broker callback.  The backend uses `_send_from_surface` with its private
        session token to reach the actual ConPTY writer without recursion.
        """
        with self._lock:
            sender = self._surface_sender
        if sender is not None:
            return sender(keys, quiet=quiet, idle=idle, timeout=timeout)
        return self._send_direct(keys, quiet=quiet, idle=idle, timeout=timeout)

    def sent_keys(self, limit: int = 12) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._sent[-limit:])
