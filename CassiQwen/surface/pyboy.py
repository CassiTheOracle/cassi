"""PyBoy-backed, field-native Game Boy Surface producer.

PyBoy is imported only when this backend is constructed. Install it with
``pip install PyBoy`` to use this module.

Example::

    from pathlib import Path
    from surface.pyboy import PyBoySurfaceBackend

    world = PyBoySurfaceBackend(
        Path("pokemon_yellow.gb"),
        source_id="pokemon-yellow",
        save_home=Path("field-home/game-save"),
    )
    world.advance(1)  # Directly step one frame; world.frame is immutable BGRA8.
    binding = world.describe()["source"]
    world.dispatch(binding, {
        "operation": "keyboard.key",
        "arguments": {"key": "ArrowRight", "state": "down"},
    })
    world.advance(8)
    # A queued-input acknowledgement means only that the event was queued.
    # Inspect the captured Surface/frame to observe what the game actually did.
    world.dispatch(world.describe()["source"], {
        "operation": "keyboard.key",
        "arguments": {"key": "ArrowRight", "state": "up"},
    })
    world.close()
"""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
import io
import os
from pathlib import Path
import tempfile
from threading import RLock
from time import monotonic_ns
from typing import BinaryIO, TypeAlias

from .field_native import FieldNativeBackend


RomSource: TypeAlias = str | os.PathLike[str] | bytes | bytearray | memoryview | BinaryIO

_MAX_ADVANCE_FRAMES = 600
_KEY_TO_BUTTON = {
    "up": "up",
    "arrowup": "up",
    "dpadup": "up",
    "down": "down",
    "arrowdown": "down",
    "dpaddown": "down",
    "left": "left",
    "arrowleft": "left",
    "dpadleft": "left",
    "right": "right",
    "arrowright": "right",
    "dpadright": "right",
    "a": "a",
    "b": "b",
    "start": "start",
    "select": "select",
}
_SUPPORTED_OPERATIONS = frozenset({"keyboard.key"})


def _normalized_key(key: str) -> str:
    return key.casefold().replace("_", "").replace("-", "").replace(" ", "")


def _make_rom_argument(rom: RomSource) -> tuple[BinaryIO, BinaryIO]:
    """Prepare a read-only PyBoy ROM stream with no adjacent save paths."""
    if isinstance(rom, (str, os.PathLike)):
        path = os.fspath(rom)
        if not isinstance(path, str):
            raise TypeError("ROM paths must be text paths")
        stream = Path(path).open("rb")
        return stream, stream
    if isinstance(rom, (bytes, bytearray, memoryview)):
        stream = io.BytesIO(bytes(rom))
        return stream, stream

    read = getattr(rom, "read", None)
    if not callable(read):
        raise TypeError("rom must be a Path, ROM bytes, or a binary file-like object")
    seek = getattr(rom, "seek", None)
    tell = getattr(rom, "tell", None)
    position: int | None = None
    if callable(seek) and callable(tell):
        try:
            position = tell()
            seek(0)
        except (OSError, ValueError):
            position = None
    try:
        payload = read()
    finally:
        if position is not None:
            try:
                seek(position)
            except (OSError, ValueError):
                pass
    if not isinstance(payload, (bytes, bytearray, memoryview)):
        raise TypeError("ROM file-like objects must return bytes")
    stream = io.BytesIO(bytes(payload))
    return stream, stream


def _rom_digest(stream: BinaryIO) -> str:
    digest = sha256()
    stream.seek(0)
    try:
        while chunk := stream.read(1 << 20):
            digest.update(chunk)
    finally:
        stream.seek(0)
    return digest.hexdigest()


def _load_save_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return b""


def _atomic_write(path: Path, payload: bytes) -> None:
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


class PyBoySurfaceBackend(FieldNativeBackend):
    """Run a real Game Boy ROM and publish its rendered screen to Cassi.

    Args:
        rom: A ROM path, ROM bytes, or a binary file-like object.
        source_id: Field-native identity exposed to Surface consumers.
        window: PyBoy window backend; defaults to headless ``"null"``.
        save_home: Optional directory for persistent ``.ram``/``.rtc`` saves.
            It must not be the ROM file or its parent directory; a dedicated
            subdirectory is safe. Without it, each instance starts fresh and
            discards cartridge saves on close.

    ``advance(frames)`` consumes queued ``keyboard.key`` events, advances the
    emulator, then publishes the actual 160x144 screen as BGRA8. Input is
    limited to the D-pad arrows and A/B/Start/Select; text and pointer events
    are not emulator controls. Queued delivery is not evidence of a semantic
    result: inspect a captured frame to observe the game. ROM paths are opened
    read-only as file-like objects, so PyBoy never creates saves beside them.
    """
    width = 160
    height = 144


    def __init__(
        self,
        rom: RomSource,
        source_id: str = "pyboy-world",
        *,
        window: str = "null",
        save_home: str | os.PathLike[str] | None = None,
    ) -> None:
        try:
            from pyboy import PyBoy
        except ImportError as exc:
            raise RuntimeError(
                "PyBoy support is optional; install it with `pip install PyBoy` "
                "(PyBoy 2.7.0 or newer)."
            ) from exc

        super().__init__(source_id)
        self._emulator_lock = RLock()
        self._frame: bytes | None = None
        self._running = False
        self._pressed_buttons: set[str] = set()
        self._rom_path = (
            Path(os.fspath(rom)).expanduser().resolve()
            if isinstance(rom, (str, os.PathLike))
            else None
        )
        self._save_home = (
            Path(save_home).expanduser().resolve() if save_home is not None else None
        )
        if self._rom_path is not None and self._save_home is not None:
            if self._save_home == self._rom_path or self._save_home == self._rom_path.parent:
                raise ValueError("save_home must not collide with the ROM file or its directory")
        self._save_stem: str | None = None
        self._ram_file = io.BytesIO()
        self._rtc_file = io.BytesIO()
        self._rom_stream: BinaryIO | None = None

        try:
            rom_argument, self._rom_stream = _make_rom_argument(rom)
            if self._save_home is not None:
                self._save_home.mkdir(parents=True, exist_ok=True)
                self._save_stem = f"pyboy-{_rom_digest(rom_argument)}"
                ram_data = _load_save_bytes(self._save_home / f"{self._save_stem}.ram")
                rtc_data = _load_save_bytes(self._save_home / f"{self._save_stem}.rtc")
                self._ram_file = io.BytesIO(ram_data)
                self._rtc_file = io.BytesIO(rtc_data)
            else:
                ram_data = rtc_data = b""
            self._pyboy = PyBoy(
                rom_argument,
                window=window,
                sound_emulated=False,
                ram_file=self._ram_file if ram_data else None,
                rtc_file=self._rtc_file if rtc_data else None,
            )
        except Exception:
            if self._rom_stream is not None:
                self._rom_stream.close()
            raise
        self._running = True

    def _binding(self) -> dict[str, object]:
        binding = super()._binding()
        binding["operations"] = ["keyboard.key"]
        return binding

    def describe(self) -> dict[str, object]:
        description = super().describe()
        unavailable = {
            "status": "unavailable",
            "reason": "PyBoy Surface maps only keyboard.key events to Game Boy controls",
        }
        for operation in ("keyboard.text", "pointer.absolute", "pointer.relative", "pointer.button", "pointer.wheel"):
            description["capabilities"][operation] = dict(unavailable)
        return description

    def dispatch(self, binding: Mapping[str, object], action: Mapping[str, object]) -> dict[str, object]:
        operation = action.get("operation") if isinstance(action, Mapping) else None
        if isinstance(operation, str) and operation not in _SUPPORTED_OPERATIONS:
            return {
                "disposition": "rejected",
                "delivered_count": 0,
                "ack_strength": "none",
                "detail": "PyBoy Surface supports keyboard.key only",
            }
        if operation == "keyboard.key":
            arguments = action.get("arguments")
            key = arguments.get("key") if isinstance(arguments, Mapping) else None
            if isinstance(key, str) and _normalized_key(key) not in _KEY_TO_BUTTON:
                return {
                    "disposition": "rejected",
                    "delivered_count": 0,
                    "ack_strength": "none",
                    "detail": "key is not a Game Boy D-pad or A/B/Start/Select control",
                }
        return super().dispatch(binding, action)

    @property
    def pyboy(self):
        """Underlying PyBoy instance for manual probing; ``advance`` publishes frames."""
        return self._pyboy

    @property
    def frame(self) -> bytes | None:
        """The latest immutable BGRA8 framebuffer, or None before first advance."""
        return self._frame

    @property
    def running(self) -> bool:
        """Whether PyBoy is still available for stepping."""
        return self._running and not self._closed

    def advance(self, frames: int = 1) -> bytes:
        """Apply queued input, step 1..600 frames, and publish the latest image."""
        if isinstance(frames, bool) or not isinstance(frames, int) or not 1 <= frames <= _MAX_ADVANCE_FRAMES:
            raise ValueError(f"frames must be an integer in 1..{_MAX_ADVANCE_FRAMES}")
        with self._emulator_lock:
            if self._closed:
                raise RuntimeError("PyBoy Surface is closed")
            if not self._running:
                raise RuntimeError("PyBoy emulation has stopped")
            self._consume_input()
            still_running = self._pyboy.tick(count=frames)
            if still_running is False:
                self._running = False
            image = self._pyboy.screen.image
            if image.size != (self.width, self.height):
                raise RuntimeError(f"PyBoy returned an unexpected framebuffer size: {image.size!r}")
            pixels = image.convert("RGBA").tobytes("raw", "BGRA")
            self.publish(
                pixels,
                width=self.width,
                height=self.height,
                pixel_format="BGRA8",
                sample_time_ns=monotonic_ns(),
                sample_clock_domain="host-monotonic",
            )
            self._frame = pixels
            return pixels

    def tick(self, frames: int = 1) -> bytes:
        """Alias for :meth:`advance`, convenient for emulator-oriented callers."""
        return self.advance(frames)

    def _consume_input(self) -> None:
        while (event := self.next_input()) is not None:
            if event["operation"] == "keyboard.key":
                arguments = event["arguments"]
                button = _KEY_TO_BUTTON.get(_normalized_key(arguments["key"]))
                if button is not None:
                    if arguments["state"] == "down":
                        if button not in self._pressed_buttons:
                            self._pyboy.button_press(button)
                        self._pressed_buttons.add(button)
                    else:
                        self._pyboy.button_release(button)
                        self._pressed_buttons.discard(button)
            # This confirms only that this producer processed the queued event;
            # the published framebuffer remains the source of observed outcome.
            self.acknowledge_input(event["sequence"])

    def _release_controls(self) -> None:
        failures: list[Exception] = []
        for button in tuple(self._pressed_buttons):
            try:
                self._pyboy.button_release(button)
            except Exception as exc:
                failures.append(exc)
            finally:
                self._pressed_buttons.discard(button)
        if failures:
            raise RuntimeError("one or more held PyBoy controls could not be released") from failures[0]

    def neutralize(self, binding: Mapping[str, object]) -> dict[str, object]:
        """Release emulator buttons synchronously when Surface neutralizes input."""
        with self._emulator_lock:
            result = super().neutralize(binding)
            if binding.get("source_instance") != self._instance or binding.get("source_epoch") != self._epoch:
                return result
            self._consume_input()
            self._release_controls()
            if self._neutralization_pending is not None:
                self.acknowledge_input(self._neutralization_pending)
            confirmed = self._neutralization_pending is None
            return {
                "confirmed": confirmed,
                "detail": "PyBoy controls released" if confirmed else result["detail"],
            }

    def save_state(self, path: str | os.PathLike[str]) -> None:
        """Write the emulator machine state so a later run resumes in place."""
        target = Path(os.fspath(path)).expanduser()
        with self._emulator_lock:
            if self._closed or not self._running:
                raise RuntimeError("PyBoy Surface is closed")
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("wb") as handle:
                self._pyboy.save_state(handle)

    def load_state(self, path: str | os.PathLike[str]) -> None:
        """Restore a machine state written by :meth:`save_state` and publish its screen."""
        source = Path(os.fspath(path)).expanduser()
        with self._emulator_lock:
            if self._closed or not self._running:
                raise RuntimeError("PyBoy Surface is closed")
            with source.open("rb") as handle:
                self._pyboy.load_state(handle)
        self.advance(1)

    def state_bytes(self) -> bytes:
        """The emulator machine state as bytes, for resumable place snapshots."""
        with self._emulator_lock:
            if self._closed or not self._running:
                raise RuntimeError("PyBoy Surface is closed")
            buffer = io.BytesIO()
            self._pyboy.save_state(buffer)
            return buffer.getvalue()

    def restore_bytes(self, state: bytes) -> None:
        """Restore a machine state from :meth:`state_bytes` and publish its screen."""
        with self._emulator_lock:
            if self._closed or not self._running:
                raise RuntimeError("PyBoy Surface is closed")
            self._release_controls()
            self._pyboy.load_state(io.BytesIO(state))
        self.advance(1)

    def set_speed(self, multiplier: int) -> None:
        """Emulation pace: 0 runs unthrottled, N runs at N times real time."""
        with self._emulator_lock:
            self._pyboy.set_emulation_speed(int(multiplier))

    def close(self) -> None:
        """Release controls and persist saves only under the configured save_home."""
        with self._emulator_lock:
            if self._closed:
                return
            try:
                self._release_controls()
            finally:
                try:
                    if self._save_home is None:
                        self._pyboy.stop(save=False)
                    else:
                        self._ram_file.seek(0)
                        self._ram_file.truncate(0)
                        self._rtc_file.seek(0)
                        self._rtc_file.truncate(0)
                        self._pyboy.stop(
                            save=True,
                            ram_file=self._ram_file,
                            rtc_file=self._rtc_file,
                        )
                        self._save_home.mkdir(parents=True, exist_ok=True)
                        assert self._save_stem is not None
                        _atomic_write(
                            self._save_home / f"{self._save_stem}.ram",
                            self._ram_file.getvalue(),
                        )
                        _atomic_write(
                            self._save_home / f"{self._save_stem}.rtc",
                            self._rtc_file.getvalue(),
                        )
                finally:
                    self._running = False
                    try:
                        super().close()
                    finally:
                        if self._rom_stream is not None:
                            self._rom_stream.close()
