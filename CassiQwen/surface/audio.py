"""Opt-in, session-scoped audio mechanics for Cassi Surface.

The PulseAudio protocol client can target a named dedicated sink/monitor,
including a PipeWire-Pulse server. This module never creates routes, selects a
default device, captures a microphone/system mix, or grants authority. Every
capture/playback is bounded and requires a broker-provided grant validator.
"""

from __future__ import annotations

import hashlib
import os
import re
import select
import shutil
import stat
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Mapping


_AUDIO_UNAVAILABLE_REASON = (
    "no explicitly provisioned session-scoped audio provider is available; "
    "unrelated system-mix capture is not supported"
)
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SURFACE_MAX_AUDIO_BYTES = 4 << 20
_DEFAULT_CAPTURE_DURATION_MS = 1_000
_DEFAULT_CAPTURE_BYTES = 1 << 20
_DEFAULT_PLAYBACK_DURATION_MS = 5_000
_DEFAULT_PLAYBACK_BYTES = 1 << 20


def _identifier(value: Any, name: str) -> str:
    if (
        not isinstance(value, str)
        or not _IDENTIFIER_RE.fullmatch(value)
        or value.casefold().startswith(
            ("secret.", "credential.", "vault.", "keyring.", "wincred.", "dpapi.", "token.")
        )
    ):
        raise ValueError(f"{name} must be a bounded opaque identifier")
    return value


def _bounded_positive_int(value: Any, name: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > maximum:
        raise ValueError(f"{name} must be an integer in [1, {maximum}]")
    return value


class AudioCapabilityError(RuntimeError):
    """Base class for an unavailable or rejected audio operation."""


class AudioCapabilityUnavailable(AudioCapabilityError):
    """No supported session-scoped audio provider is installed."""


class AudioAuthorizationError(AudioCapabilityError):
    """The broker did not authorize this exact audio operation."""


class AudioPayloadError(AudioCapabilityError):
    """A playback payload violates its bound media or resource contract."""


class UnavailableAudioCapability:
    """Describe audio as unavailable and deny capture/playback by default.

    This object contains no platform audio implementation. The explicit
    methods exist so callers receive a typed, observable refusal instead of
    falling back to an unrelated microphone, output device, or system mix.
    """

    backend_id = "audio-unavailable"

    def describe(self) -> dict[str, Any]:
        operations = {
            name: {
                "supported": False,
                "status": "unavailable",
                "reason": _AUDIO_UNAVAILABLE_REASON,
                "default_authorized": False,
                "acknowledgment": "none",
            }
            for name in ("capture", "playback")
        }
        return {
            "backend_id": self.backend_id,
            "operations": operations,
            "limits": {
                "routing": "explicit session route required",
                "system_mix_capture": False,
                "microphone_capture": False,
                "playback": False,
            },
        }

    def sources(self) -> list[dict[str, Any]]:
        return []

    def capture(self, *, source_id: str, source_scope: str) -> Mapping[str, Any]:
        raise AudioCapabilityUnavailable(
            f"audio capture is unavailable for the requested scoped source: {_AUDIO_UNAVAILABLE_REASON}"
        )

    def playback(
        self,
        *,
        route_id: str,
        destination_scope: str,
        payload: bytes,
    ) -> Mapping[str, Any]:
        raise AudioCapabilityUnavailable(
            f"audio playback is unavailable for the requested scoped route: {_AUDIO_UNAVAILABLE_REASON}"
        )

    def close(self) -> None:
        return None


class PipeWirePulseAudioBackend:
    """Duck-protocol backend for one explicitly named PulseAudio-compatible route.

    ``session_endpoint_id`` must be an already provisioned sink named
    ``cassi.surface.<session_id>.output``; its only accepted capture source is
    that sink's ``.monitor``. The backend only connects to the supplied private
    UNIX socket and never creates/configures devices. It works with native
    PulseAudio or PipeWire-Pulse; native PipeWire tools are not used.

    Capture and playback are mechanics only. ``capture`` requires the broker's
    ephemeral ``_surface_capture_authorization`` context. ``dispatch`` accepts
    only the broker-injected ``_audio_payload`` and
    ``_surface_audio_authorization`` fields; a public ``artifact_ref`` is never
    resolved by this backend.
    """

    backend_id = "pulse-session-audio"

    def __init__(
        self,
        *,
        session_id: str,
        runtime_dir: str | os.PathLike[str],
        server_socket: str | os.PathLike[str],
        session_endpoint_id: str,
        monitor_source_id: str,
        sample_rate_hz: int = 48_000,
        channels: int = 2,
        capture_duration_ms: int = _DEFAULT_CAPTURE_DURATION_MS,
        max_capture_bytes: int = _DEFAULT_CAPTURE_BYTES,
        max_playback_duration_ms: int = _DEFAULT_PLAYBACK_DURATION_MS,
        max_playback_bytes: int = _DEFAULT_PLAYBACK_BYTES,
        probe_timeout_s: float = 1.5,
        playback_timeout_s: float = 8.0,
    ) -> None:
        self.session_id = _identifier(session_id, "session_id")
        self.session_endpoint_id = _identifier(session_endpoint_id, "session_endpoint_id")
        self.monitor_source_id = _identifier(monitor_source_id, "monitor_source_id")
        prefix = f"cassi.surface.{self.session_id}."
        if not self.session_endpoint_id.startswith(prefix) or self.session_endpoint_id != prefix + "output":
            raise ValueError("session_endpoint_id must be the session's dedicated cassi.surface output sink")
        if self.monitor_source_id != self.session_endpoint_id + ".monitor":
            raise ValueError("monitor_source_id must be the exact monitor of the session output sink")
        self.sample_rate_hz = _bounded_positive_int(sample_rate_hz, "sample_rate_hz", 192_000)
        if self.sample_rate_hz < 8_000:
            raise ValueError("sample_rate_hz must be at least 8000")
        self.channels = _bounded_positive_int(channels, "channels", 8)
        self.capture_duration_ms = _bounded_positive_int(capture_duration_ms, "capture_duration_ms", 5_000)
        self.max_capture_bytes = _bounded_positive_int(
            max_capture_bytes, "max_capture_bytes", _SURFACE_MAX_AUDIO_BYTES
        )
        self.max_playback_duration_ms = _bounded_positive_int(
            max_playback_duration_ms, "max_playback_duration_ms", 10_000
        )
        self.max_playback_bytes = _bounded_positive_int(
            max_playback_bytes, "max_playback_bytes", _SURFACE_MAX_AUDIO_BYTES
        )
        if (
            not isinstance(probe_timeout_s, (int, float))
            or isinstance(probe_timeout_s, bool)
            or not 0.05 <= probe_timeout_s <= 5.0
        ):
            raise ValueError("probe_timeout_s must be between 0.05 and 5 seconds")
        if (
            not isinstance(playback_timeout_s, (int, float))
            or isinstance(playback_timeout_s, bool)
            or not 0.1 <= playback_timeout_s <= 15.0
        ):
            raise ValueError("playback_timeout_s must be between 0.1 and 15 seconds")
        self.probe_timeout_s = float(probe_timeout_s)
        self.playback_timeout_s = float(playback_timeout_s)
        self.runtime_dir = Path(runtime_dir)
        self.server_socket = Path(server_socket)
        if not self.runtime_dir.is_absolute() or not self.server_socket.is_absolute():
            raise ValueError("runtime_dir and server_socket must be explicit absolute paths")
        if any(part == ".." for part in self.runtime_dir.parts + self.server_socket.parts):
            raise ValueError("audio route paths cannot contain parent traversal")
        try:
            self._socket_relative = self.server_socket.relative_to(self.runtime_dir)
        except ValueError:
            raise ValueError("server_socket must be inside the explicit runtime_dir") from None
        if not self._socket_relative.parts:
            raise ValueError("server_socket must name a socket below runtime_dir")

        self._lock = threading.RLock()
        self._closed = False
        self._route_fingerprint: str | None = None
        self._source_instance: str | None = None
        self._environment_incarnation: str | None = None
        self._source_epoch = 0
        self._sequence = 0
        self._active_playbacks: set[subprocess.Popen] = set()
        self._active_captures: set[subprocess.Popen] = set()

    def _child_env(self) -> dict[str, str]:
        # Do not inherit ambient Pulse/PipeWire route selectors or startup
        # hooks. Every client also receives explicit --server/--device.
        return {
            "PATH": os.environ.get("PATH", ""),
            "LANG": "C",
            "LC_ALL": "C",
        }

    def _socket_info(self) -> os.stat_result:
        if os.name != "posix":
            raise AudioCapabilityUnavailable("session-scoped PulseAudio routing requires a POSIX UNIX socket")
        current = Path(self.runtime_dir.anchor)
        runtime_info: os.stat_result | None = None
        for part in self.runtime_dir.parts[1:]:
            current = current / part
            try:
                component = current.lstat()
            except OSError:
                raise AudioCapabilityUnavailable("the configured audio runtime directory is unavailable") from None
            if stat.S_ISLNK(component.st_mode) or not stat.S_ISDIR(component.st_mode):
                raise AudioCapabilityUnavailable("the audio runtime path crosses a non-directory")
            if current == self.runtime_dir:
                runtime_info = component
        if runtime_info is None or runtime_info.st_uid != os.getuid() or runtime_info.st_mode & 0o002:
            raise AudioCapabilityUnavailable("the audio runtime directory is not private to the current user")
        current = self.runtime_dir
        for part in self._socket_relative.parts[:-1]:
            current = current / part
            try:
                component = current.lstat()
            except OSError:
                raise AudioCapabilityUnavailable("the configured audio server socket path is unavailable") from None
            if stat.S_ISLNK(component.st_mode) or not stat.S_ISDIR(component.st_mode):
                raise AudioCapabilityUnavailable("the configured audio server socket path crosses a non-directory")
        try:
            info = self.server_socket.lstat()
        except OSError:
            raise AudioCapabilityUnavailable("the configured audio server socket is unavailable") from None
        if (
            stat.S_ISLNK(info.st_mode)
            or not stat.S_ISSOCK(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_mode & 0o002
        ):
            raise AudioCapabilityUnavailable("the configured audio server socket is not private to this session")
        return info

    def _server_uri(self) -> str:
        return "unix:" + os.fspath(self.server_socket)

    def _run_text(self, command: list[str], *, limit: int = 64 << 10) -> str:
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                start_new_session=True,
                env=self._child_env(),
            )
        except OSError:
            raise AudioCapabilityUnavailable("the explicit PulseAudio-compatible client could not start") from None
        assert process.stdout is not None
        output = bytearray()
        deadline = time.monotonic() + self.probe_timeout_s
        try:
            descriptor = process.stdout.fileno()
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise AudioCapabilityUnavailable("the explicit audio server probe timed out")
                ready, _, _ = select.select([descriptor], [], [], min(remaining, 0.1))
                if ready:
                    chunk = os.read(descriptor, min(8192, limit + 1 - len(output)))
                    if not chunk:
                        break
                    output.extend(chunk)
                    if len(output) > limit:
                        raise AudioCapabilityUnavailable("audio server discovery exceeded its response budget")
                if process.poll() is not None and not ready:
                    continue
        except Exception:
            self._stop_process(process)
            raise
        finally:
            process.stdout.close()
        try:
            exit_code = process.wait(timeout=0.2)
        except subprocess.TimeoutExpired:
            self._stop_process(process)
            raise AudioCapabilityUnavailable("the explicit audio server probe did not exit") from None
        if exit_code != 0:
            raise AudioCapabilityUnavailable("the explicit audio server or named route is unavailable")
        return output.decode("utf-8", errors="replace")

    @staticmethod
    def _stop_process(process: subprocess.Popen, *, timeout_s: float = 0.25) -> bool:
        if process.poll() is None:
            try:
                process.terminate()
            except OSError:
                pass
            try:
                process.wait(timeout=timeout_s)
            except subprocess.TimeoutExpired:
                try:
                    process.kill()
                except OSError:
                    pass
                try:
                    process.wait(timeout=timeout_s)
                except subprocess.TimeoutExpired:
                    return False
        return process.poll() is not None

    @staticmethod
    def _listed_index(output: str, expected: str) -> str | None:
        for line in output.splitlines():
            columns = line.split("\t")
            if len(columns) >= 2 and columns[1] == expected and columns[0].isdigit():
                return columns[0]
        return None

    def _route_snapshot(self) -> dict[str, Any]:
        if self._closed:
            raise AudioCapabilityUnavailable("audio backend is closed")
        socket_info = self._socket_info()
        pactl = shutil.which("pactl")
        if pactl is None:
            raise AudioCapabilityUnavailable("pactl is not installed; no audio server discovery is available")
        server_arg = "--server=" + self._server_uri()
        self._run_text([pactl, server_arg, "info"])
        sinks = self._run_text([pactl, server_arg, "list", "short", "sinks"])
        sources = self._run_text([pactl, server_arg, "list", "short", "sources"])
        sink_index = self._listed_index(sinks, self.session_endpoint_id)
        monitor_index = self._listed_index(sources, self.monitor_source_id)
        if sink_index is None:
            raise AudioCapabilityUnavailable("the explicitly named session output sink is not present")
        if monitor_index is None:
            raise AudioCapabilityUnavailable("the exact monitor for the session output sink is not present")
        identity = (
            f"{socket_info.st_dev}:{socket_info.st_ino}:{socket_info.st_ctime_ns}:"
            f"{socket_info.st_uid}:{sink_index}:{monitor_index}:"
            f"{self.session_endpoint_id}:{self.monitor_source_id}"
        )
        fingerprint = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]
        with self._lock:
            if fingerprint != self._route_fingerprint:
                self._route_fingerprint = fingerprint
                self._source_epoch += 1
                self._source_instance = hashlib.sha256(
                    f"{self.session_id}:{socket_info.st_dev}:{socket_info.st_ino}:{sink_index}:{monitor_index}".encode("utf-8")
                ).hexdigest()[:32]
                self._environment_incarnation = fingerprint
            parec = shutil.which("parec")
            paplay = shutil.which("paplay")
            capture_modalities = ["audio"] if parec is not None else []
            operations = []
            if parec is not None:
                operations.append("audio.capture")
            if paplay is not None:
                operations.append("audio.playback")
            return {
                "source_id": self.monitor_source_id,
                "source_instance": self._source_instance,
                "source_epoch": self._source_epoch,
                "environment_incarnation": self._environment_incarnation,
                "geometry_revision": 0,
                "width": 0,
                "height": 0,
                "operations": operations,
                "modalities": list(capture_modalities),
                "capture_modalities": capture_modalities,
                "capture_state": "available" if parec is not None else "unavailable",
                "input_state": "available" if paplay is not None else "unavailable",
                "backend_version": "PulseAudio protocol (PulseAudio or PipeWire-Pulse)",
                "input_domain": f"audio-session:{self.session_id}",
                "input_domain_epoch": self._source_epoch,
                "focus_epoch": 0,
                "audio_session_endpoint_id": self.session_endpoint_id,
            }


    @staticmethod
    def _authorized(context: Any, operation: str) -> bool:
        if not isinstance(context, Mapping):
            return False
        operations = context.get("operations")
        if not isinstance(operations, (list, tuple, set, frozenset)) or operation not in operations:
            return False
        validator = context.get("validate")
        if not callable(validator):
            return False
        try:
            result = validator()
        except Exception:
            return False
        return result is True or (isinstance(result, Mapping) and result.get("approved") is True)

    def _check_bound_source(self, binding: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(binding, Mapping):
            raise AudioCapabilityUnavailable("audio binding is unavailable")
        route = self._route_snapshot()
        for key in (
            "backend_id",
            "source_id",
            "source_instance",
            "source_epoch",
            "environment_incarnation",
            "audio_session_endpoint_id",
        ):
            if binding.get(key) != (self.backend_id if key == "backend_id" else route.get(key)):
                raise AudioCapabilityUnavailable("the audio source binding is stale")
        return route

    def revalidate(self, binding: Mapping[str, Any]) -> dict[str, Any]:
        """Read current endpoint identity without binding or changing the route."""
        if (
            not isinstance(binding, Mapping)
            or binding.get("source_id") != self.monitor_source_id
            or binding.get("audio_session_endpoint_id") != self.session_endpoint_id
        ):
            return {"supported": True, "valid": False, "reason": "audio binding does not name this session route"}
        try:
            route = self._route_snapshot()
        except AudioCapabilityError as exc:
            return {"supported": True, "valid": False, "reason": str(exc)[:256]}
        return {"supported": True, "valid": True, "backend_id": self.backend_id, **route}

    def describe(self) -> dict[str, Any]:
        try:
            route = self._route_snapshot()
        except AudioCapabilityError as exc:
            reason = str(exc)
            return {
                "backend_id": self.backend_id,
                "status": "unavailable",
                "operations": {
                    "audio.capture": {
                        "supported": False,
                        "status": "unavailable",
                        "reason": reason,
                        "default_authorized": False,
                    },
                    "audio.playback": {
                        "supported": False,
                        "status": "unavailable",
                        "reason": reason,
                        "default_authorized": False,
                    },
                },
                "limits": {
                    "provider": "PulseAudio protocol (PulseAudio or PipeWire-Pulse)",
                    "explicit_session_route": True,
                    "system_mix_capture": False,
                    "microphone_capture": False,
                    "default_device_fallback": False,
                    "capture_max_bytes": self.max_capture_bytes,
                    "capture_max_duration_ms": self.capture_duration_ms,
                    "playback_max_bytes": self.max_playback_bytes,
                    "playback_max_duration_ms": self.max_playback_duration_ms,
                },
            }
        operations = {}
        for operation, executable, supported, reason in (
            ("audio.capture", "parec", "audio.capture" in route["operations"], "parec is not installed"),
            ("audio.playback", "paplay", "audio.playback" in route["operations"], "paplay is not installed"),
        ):
            operations[operation] = {
                "supported": supported,
                "status": "available" if supported else "unavailable",
                "reason": None if supported else reason,
                "client": executable,
                "default_authorized": False,
            }
        return {
            "backend_id": self.backend_id,
            "status": "available" if any(item["supported"] for item in operations.values()) else "unavailable",
            "operations": operations,
            "limits": {
                "provider": "PulseAudio protocol (PulseAudio or PipeWire-Pulse)",
                "audio_session_endpoint_id": self.session_endpoint_id,
                "monitor_source_id": self.monitor_source_id,
                "explicit_session_route": True,
                "system_mix_capture": False,
                "microphone_capture": False,
                "default_device_fallback": False,
                "sample_rate_hz": self.sample_rate_hz,
                "channels": self.channels,
                "capture_max_bytes": self.max_capture_bytes,
                "capture_max_duration_ms": self.capture_duration_ms,
                "playback_max_bytes": self.max_playback_bytes,
                "playback_max_duration_ms": self.max_playback_duration_ms,
            },
        }

    def sources(self) -> list[dict[str, Any]]:
        try:
            route = self._route_snapshot()
        except AudioCapabilityError:
            return []
        if not route["operations"]:
            return []
        return [{
            "source_id": route["source_id"],
            "source_instance": route["source_instance"],
            "source_epoch": route["source_epoch"],
            "environment_incarnation": route["environment_incarnation"],
            "geometry_revision": route["geometry_revision"],
            "width": 0,
            "height": 0,
            "operations": list(route["operations"]),
            "modalities": list(route["modalities"]),
            "capture_modalities": list(route["capture_modalities"]),
            "capture_state": route["capture_state"],
            "input_state": route["input_state"],
            "backend_version": route["backend_version"],
            "input_domain": route["input_domain"],
            "input_domain_epoch": route["input_domain_epoch"],
            "focus_epoch": route["focus_epoch"],
            "audio_session_endpoint_id": self.session_endpoint_id,
        }]

    def bind(self, source_id: str) -> dict[str, Any]:
        source_id = _identifier(source_id, "source_id")
        route = self._route_snapshot()
        if source_id != self.monitor_source_id:
            raise AudioCapabilityUnavailable("only the configured session sink monitor can be bound")
        if not route["operations"]:
            raise AudioCapabilityUnavailable("no session-scoped audio operation is available")
        return {"backend_id": self.backend_id, **route}

    def capture(self, binding: Mapping[str, Any]) -> Mapping[str, Any]:
        if not isinstance(binding, Mapping) or binding.get("_surface_audio_enabled") is not True:
            raise AudioAuthorizationError("the broker did not enable audio capture for this request")
        authorization = binding.get("_surface_capture_authorization")
        if not self._authorized(authorization, "audio.capture"):
            raise AudioAuthorizationError("audio capture requires a current core audio.capture grant")
        route = self._check_bound_source(binding)
        executable = shutil.which("parec")
        if executable is None or "audio.capture" not in route["operations"]:
            raise AudioCapabilityUnavailable("parec is unavailable for the configured session monitor")
        frame_bytes = self.channels * 2
        requested_frames = (self.sample_rate_hz * self.capture_duration_ms) // 1_000
        requested_bytes = requested_frames * frame_bytes
        if requested_bytes < frame_bytes or requested_bytes > self.max_capture_bytes:
            raise AudioCapabilityUnavailable("the configured capture exceeds its PCM byte budget")
        with self._lock:
            self._sequence += 1
            sequence = self._sequence
        # Revalidate at the last point before starting the audio client.
        if not self._authorized(authorization, "audio.capture"):
            raise AudioAuthorizationError("the core audio.capture grant expired before capture")
        command = [
            executable,
            "--server=" + self._server_uri(),
            "--device=" + self.monitor_source_id,
            "--raw",
            "--format=s16le",
            f"--rate={self.sample_rate_hz}",
            f"--channels={self.channels}",
        ]
        started_ns = time.monotonic_ns()
        samples = self._capture_pcm(command, requested_bytes)
        receipt_time_ns = time.monotonic_ns()
        raw_sample_bytes = len(samples)
        trailing_partial_bytes = raw_sample_bytes % frame_bytes
        if trailing_partial_bytes:
            samples = samples[:-trailing_partial_bytes]
        captured_frames = len(samples) // frame_bytes
        if captured_frames <= 0:
            raise AudioCapabilityUnavailable("the named session monitor produced no complete PCM frames")
        coverage_complete = captured_frames == requested_frames and trailing_partial_bytes == 0
        return {
            "source_id": self.monitor_source_id,
            "source_instance": route["source_instance"],
            "source_epoch": route["source_epoch"],
            "environment_incarnation": route["environment_incarnation"],
            "geometry_revision": 0,
            "width": 0,
            "height": 0,
            "pixel_format": "none",
            "pixels": None,
            "sequence": sequence,
            "sample_time_ns": None,
            "receipt_time_ns": receipt_time_ns,
            "receipt_clock_domain": "python.time.monotonic_ns",
            "provenance": f"pulse-monitor:{self.session_id}",
            "coverage": {
                "kind": "audio-frames",
                "status": "complete" if coverage_complete else "partial",
                "complete": coverage_complete,
                "requested_frames": requested_frames,
                "captured_frames": captured_frames,
                "missing_frames": requested_frames - captured_frames,
                "sample_time_available": False,
            },
            "audio": {
                "samples": samples,
                "audio_format": "pcm-i16le",
                "sample_rate_hz": self.sample_rate_hz,
                "channel_count": self.channels,
                "sample_count": captured_frames,
                "sequence": sequence,
                "sample_time_ns": None,
                "sample_clock_domain": None,
                "sample_time_uncertainty_ns": None,
                "receipt_time_ns": receipt_time_ns,
                "receipt_clock_domain": "python.time.monotonic_ns",
                "capture_started_ns": started_ns,
                "coverage": {
                    "complete": coverage_complete,
                    "coordinate": "capture-local-frame-index",
                    "sample_rate_hz": self.sample_rate_hz,
                    "requested_interval": {
                        "start_frame": 0,
                        "end_frame_exclusive": requested_frames,
                    },
                    "captured_intervals": [
                        {"start_frame": 0, "end_frame_exclusive": captured_frames}
                    ],
                    "missing_intervals": (
                        [{"start_frame": captured_frames, "end_frame_exclusive": requested_frames}]
                        if captured_frames < requested_frames
                        else []
                    ),
                    "discarded_trailing_bytes": trailing_partial_bytes,
                    "source_sample_time_available": False,
                },
            },
        }

    def _capture_pcm(self, command: list[str], target_bytes: int) -> bytes:
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                start_new_session=True,
                env=self._child_env(),
            )
        except OSError:
            raise AudioCapabilityUnavailable("the named session audio monitor could not start") from None
        assert process.stdout is not None
        with self._lock:
            self._active_captures.add(process)
        output = bytearray()
        deadline = time.monotonic() + (self.capture_duration_ms / 1_000.0) + self.probe_timeout_s
        try:
            descriptor = process.stdout.fileno()
            while len(output) < target_bytes:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                ready, _, _ = select.select([descriptor], [], [], min(remaining, 0.1))
                if not ready:
                    if process.poll() is not None:
                        continue
                    continue
                chunk = os.read(descriptor, min(64 << 10, target_bytes - len(output)))
                if not chunk:
                    break
                output.extend(chunk)
        except Exception:
            self._stop_process(process)
            raise
        finally:
            self._stop_process(process)
            process.stdout.close()
            with self._lock:
                self._active_captures.discard(process)
        if process.returncode not in (0, -15, -9):
            if not output:
                raise AudioCapabilityUnavailable("the explicit session monitor ended without audio")
        if process.returncode is None:
            raise AudioCapabilityUnavailable("the session audio monitor did not stop within its bounded grace period")
        return bytes(output)

    def dispatch(self, binding: Mapping[str, Any], action: Mapping[str, Any]) -> Mapping[str, Any]:
        if not isinstance(action, Mapping) or action.get("operation") != "audio.playback":
            return {
                "disposition": "rejected",
                "delivered_count": 0,
                "ack_strength": "none",
                "detail": {"reason": "only the explicitly granted audio.playback operation is supported"},
            }
        arguments = action.get("arguments")
        if not isinstance(arguments, Mapping):
            return self._not_started("playback arguments are unavailable")
        authorization = action.get("_surface_audio_authorization")
        if not self._authorized(authorization, "audio.playback"):
            return {
                "disposition": "rejected",
                "delivered_count": 0,
                "ack_strength": "none",
                "detail": {"reason": "audio playback requires a current core audio.playback grant"},
            }
        payload = action.get("_audio_payload", arguments.get("_audio_payload"))
        try:
            samples, frames = self._validate_playback_payload(payload)
        except AudioPayloadError as exc:
            return {
                "disposition": "rejected",
                "delivered_count": 0,
                "ack_strength": "none",
                "detail": {"reason": str(exc)[:256]},
            }
        try:
            route = self._check_bound_source(binding)
        except AudioCapabilityError as exc:
            return self._not_started(str(exc))
        executable = shutil.which("paplay")
        if executable is None or "audio.playback" not in route["operations"]:
            return self._not_started("paplay is unavailable for the configured session output")
        # The public artifact_ref stays in the JSON intent; only the core may
        # resolve it and attach bounded, scope-checked bytes here.
        command = [
            executable,
            "--server=" + self._server_uri(),
            "--device=" + self.session_endpoint_id,
            "--raw",
            "--format=s16le",
            f"--rate={self.sample_rate_hz}",
            f"--channels={self.channels}",
        ]
        if not self._authorized(authorization, "audio.playback"):
            return {
                "disposition": "rejected",
                "delivered_count": 0,
                "ack_strength": "none",
                "detail": {"reason": "the core audio.playback grant expired before dispatch"},
            }
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                start_new_session=True,
                env=self._child_env(),
            )
        except OSError:
            return self._not_started("the named session output could not start")
        with self._lock:
            self._active_playbacks.add(process)
        timed_out = False
        try:
            process.communicate(input=samples, timeout=self.playback_timeout_s)
        except subprocess.TimeoutExpired:
            timed_out = True
            self._stop_process(process)
            try:
                process.communicate(timeout=0.25)
            except subprocess.TimeoutExpired:
                self._stop_process(process)
        finally:
            with self._lock:
                self._active_playbacks.discard(process)
        if not timed_out and process.returncode == 0:
            return {
                "disposition": "delivered",
                "delivered_count": 1,
                "ack_strength": "server-accepted",
                "detail": {
                    "route": self.session_endpoint_id,
                    "sample_rate_hz": self.sample_rate_hz,
                    "channels": self.channels,
                    "frames": frames,
                    "acknowledgment": "PulseAudio-compatible server accepted the bounded stream",
                    "application_observation": False,
                },
            }
        return {
            "disposition": "unknown",
            "delivered_count": 0,
            "ack_strength": "unknown",
            "detail": {
                "reason": (
                    "playback timed out after stream start"
                    if timed_out
                    else "audio server did not acknowledge complete stream delivery"
                ),
                "route": self.session_endpoint_id,
                "application_observation": False,
            },
        }

    def _validate_playback_payload(self, value: Any) -> tuple[bytes, int]:
        if not isinstance(value, Mapping):
            raise AudioPayloadError("core-resolved audio payload is unavailable")
        samples = value.get("samples")
        if not isinstance(samples, bytes) or not samples:
            raise AudioPayloadError("resolved audio payload must contain immutable PCM bytes")
        if len(samples) > self.max_playback_bytes or len(samples) > _SURFACE_MAX_AUDIO_BYTES:
            raise AudioPayloadError("resolved audio payload exceeds the playback byte budget")
        audio_format = value.get("format")
        if not isinstance(audio_format, str) or audio_format not in {"pcm-i16le", "s16le"}:
            raise AudioPayloadError("only signed 16-bit little-endian PCM is supported")
        sample_rate = value.get("sample_rate")
        channels = value.get("channels")
        if (
            isinstance(sample_rate, bool)
            or not isinstance(sample_rate, int)
            or isinstance(channels, bool)
            or not isinstance(channels, int)
            or sample_rate != self.sample_rate_hz
            or channels != self.channels
        ):
            raise AudioPayloadError("audio payload sample rate or channel count does not match the route")
        if value.get("recipient_scope") != self.session_endpoint_id:
            raise AudioPayloadError("audio payload recipient does not match the dedicated session sink")
        declared_length = value.get("byte_length")
        if isinstance(declared_length, bool) or not isinstance(declared_length, int) or declared_length != len(samples):
            raise AudioPayloadError("audio payload byte length does not match its resolved bytes")
        digest = value.get("sha256")
        if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
            raise AudioPayloadError("audio payload requires a lowercase SHA-256 digest")
        if hashlib.sha256(samples).hexdigest() != digest:
            raise AudioPayloadError("audio payload digest does not match the resolved bytes")
        frame_bytes = 2 * self.channels
        if len(samples) % frame_bytes:
            raise AudioPayloadError("audio payload does not contain whole PCM frames")
        frames = len(samples) // frame_bytes
        if frames <= 0:
            raise AudioPayloadError("audio payload contains no PCM frames")
        duration_ms = value.get("duration_ms")
        if isinstance(duration_ms, bool) or not isinstance(duration_ms, int):
            raise AudioPayloadError("audio payload duration_ms must be an integer")
        duration_numerator = frames * 1_000
        actual_duration_ms = (duration_numerator + self.sample_rate_hz // 2) // self.sample_rate_hz
        if abs(duration_ms - actual_duration_ms) > 1:
            raise AudioPayloadError("audio payload duration does not match its sample count")
        if duration_numerator > self.max_playback_duration_ms * self.sample_rate_hz:
            raise AudioPayloadError("audio payload exceeds the playback duration budget")
        return samples, frames

    @staticmethod
    def _not_started(reason: str) -> dict[str, Any]:
        return {
            "disposition": "not-started",
            "delivered_count": 0,
            "ack_strength": "none",
            "detail": {"reason": reason[:256]},
        }

    def neutralize(self, binding: Mapping[str, Any]) -> Mapping[str, Any]:
        with self._lock:
            processes = tuple(self._active_playbacks)
        confirmed = True
        for process in processes:
            confirmed = self._stop_process(process) and confirmed
        with self._lock:
            self._active_playbacks = {process for process in self._active_playbacks if process.poll() is None}
            confirmed = confirmed and not self._active_playbacks
            active_count = len(self._active_playbacks)
        return {
            "confirmed": confirmed,
            "detail": {
                "scope": "backend-owned playback processes only",
                "route": self.session_endpoint_id,
                "active_processes": active_count,
            },
        }

    def close(self) -> None:
        with self._lock:
            self._closed = True
            processes = tuple(self._active_playbacks | self._active_captures)
        for process in processes:
            self._stop_process(process)
        with self._lock:
            self._active_playbacks = {process for process in self._active_playbacks if process.poll() is None}
            self._active_captures = {process for process in self._active_captures if process.poll() is None}

__all__ = [
    "AudioAuthorizationError",
    "AudioCapabilityError",
    "AudioCapabilityUnavailable",
    "AudioPayloadError",
    "PipeWirePulseAudioBackend",
    "UnavailableAudioCapability",
]


