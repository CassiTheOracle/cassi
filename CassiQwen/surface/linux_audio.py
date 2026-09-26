"""Host-to-guest audio route for a dedicated WSL Surface session.

The Windows entity owns grants and starts a fixed guest client as the restricted
account. The guest opens only its named private PulseAudio socket and sink.
No ambient Windows or WSLg audio device is selected.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
import threading
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from . import audio as _audio
from .audio import AudioAuthorizationError, AudioCapabilityUnavailable, PipeWirePulseAudioBackend

_MAX_REQUEST_BYTES = 2 << 20
_MAX_RESPONSE_BYTES = 2 << 20
_MAX_PCM_BYTES = 1 << 20

_SOURCE_FILE_NAMES = ("linux_audio.py", "audio.py")


def _active_source_digests() -> dict[str, str]:
    audio_path = getattr(_audio, "__file__", None)
    if not isinstance(audio_path, str) or not audio_path:
        raise OSError("audio module source path is unavailable")
    paths = {
        "linux_audio.py": Path(__file__),
        "audio.py": Path(audio_path),
    }
    return {
        name: hashlib.sha256(paths[name].read_bytes()).hexdigest()
        for name in _SOURCE_FILE_NAMES
    }


def _valid_source_digests(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == set(_SOURCE_FILE_NAMES)
        and all(
            isinstance(value[name], str)
            and len(value[name]) == 64
            and all(char in "0123456789abcdef" for char in value[name])
            for name in _SOURCE_FILE_NAMES
        )
    )


class WslPulseAudioBackend:
    """Surface backend that carries scoped PCM through one owned WSL process."""

    backend_id = "wsl-pulse-session-audio"

    def __init__(self, *, distribution: str, user: str, home: str, session_id: str,
                 runtime_dir: str, server_socket: str, session_endpoint_id: str,
                 monitor_source_id: str) -> None:
        if os.name != "nt" or not distribution or not user or user in {"root", "0"}:
            raise ValueError("WSL audio requires a configured restricted Windows-side account")
        lib = PurePosixPath(home) / ".local/lib"
        if (not lib.is_absolute() or ".." in lib.parts
                or not PurePosixPath(runtime_dir).is_absolute()
                or PurePosixPath(server_socket).parent != PurePosixPath(runtime_dir) / "pulse"):
            raise ValueError("WSL audio requires the dedicated guest package and runtime socket")
        self._command = [
            "wsl.exe", "--distribution", distribution, "--user", user, "--exec",
            "/usr/bin/env", "-i", f"HOME={home}", f"PYTHONPATH={lib}", "PATH=/usr/local/bin:/usr/bin:/bin",
            "/usr/bin/python3", "-m", "surface.linux_audio", "--bridge",
            json.dumps({
                "session_id": session_id, "runtime_dir": runtime_dir,
                "server_socket": server_socket, "session_endpoint_id": session_endpoint_id,
                "monitor_source_id": monitor_source_id,
            }, separators=(",", ":")),
        ]
        self._lock = threading.RLock()
        self._active: set[subprocess.Popen[bytes]] = set()
        self._closed = False

    def _rpc(self, request: Mapping[str, Any], *, timeout_s: float = 9.0) -> Any:
        try:
            verified_request = {
                "operation": "verified-call",
                "source_digests": _active_source_digests(),
                "request": dict(request),
            }
        except OSError as exc:
            raise AudioCapabilityUnavailable(
                "host audio helper source digest is unavailable"
            ) from exc
        payload = json.dumps(
            verified_request, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        if len(payload) > _MAX_REQUEST_BYTES:
            raise AudioCapabilityUnavailable("guest audio request exceeds its byte budget")
        with self._lock:
            if self._closed:
                raise AudioCapabilityUnavailable("guest audio backend is closed")
            process = subprocess.Popen(
                self._command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, close_fds=True,
            )
            self._active.add(process)
        try:
            try:
                output, _ = process.communicate(input=payload, timeout=timeout_s)
            except subprocess.TimeoutExpired as exc:
                process.terminate()
                try:
                    process.communicate(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate()
                raise AudioCapabilityUnavailable("named guest audio client exceeded its time budget") from exc
            if process.returncode != 0 or len(output) > _MAX_RESPONSE_BYTES:
                raise AudioCapabilityUnavailable("named guest audio client failed or exceeded its reply budget")
            response = json.loads(output)
            if not isinstance(response, dict) or set(response) not in ({"result"}, {"error", "detail"}):
                raise AudioCapabilityUnavailable("named guest audio client returned an invalid reply")
            if "error" in response:
                if response["error"] == "AudioAuthorizationError":
                    raise AudioAuthorizationError(str(response["detail"])[:256])
                raise AudioCapabilityUnavailable(str(response["detail"])[:256])
            return response["result"]
        finally:
            with self._lock:
                self._active.discard(process)

    @staticmethod
    def _guest_binding(binding: Mapping[str, Any]) -> dict[str, Any]:
        return {**{key: value for key, value in binding.items() if not key.startswith("_")},
                "backend_id": "pulse-session-audio"}

    def describe(self) -> dict[str, Any]:
        result = self._rpc({"operation": "describe"})
        result["backend_id"] = self.backend_id
        result["limits"]["transport"] = "restricted-wsl-guest-process"
        return result

    def sources(self) -> list[dict[str, Any]]:
        return self._rpc({"operation": "sources"})

    def bind(self, source_id: str) -> dict[str, Any]:
        result = self._rpc({"operation": "bind", "source_id": source_id})
        result["backend_id"] = self.backend_id
        return result

    def revalidate(self, binding: Mapping[str, Any]) -> dict[str, Any]:
        try:
            result = self._rpc({"operation": "revalidate", "binding": self._guest_binding(binding)})
        except AudioCapabilityUnavailable as exc:
            return {"supported": True, "valid": False, "reason": str(exc)[:256]}
        result["backend_id"] = self.backend_id
        return result

    def capture(self, binding: Mapping[str, Any]) -> dict[str, Any]:
        authorization = binding.get("_surface_capture_authorization")
        if binding.get("_surface_audio_enabled") is not True or not PipeWirePulseAudioBackend._authorized(
            authorization, "audio.capture"
        ):
            raise AudioAuthorizationError("guest audio capture requires a current core grant")
        frame = self._rpc({"operation": "capture", "binding": self._guest_binding(binding)})
        encoded = frame["audio"].pop("samples_b64")
        samples = base64.b64decode(encoded, validate=True)
        if len(samples) > _MAX_PCM_BYTES:
            raise AudioCapabilityUnavailable("guest audio capture exceeded its PCM byte budget")
        if not PipeWirePulseAudioBackend._authorized(authorization, "audio.capture"):
            raise AudioAuthorizationError("guest audio capture grant expired before publication")
        frame["audio"]["samples"] = samples
        return frame

    def dispatch(self, binding: Mapping[str, Any], action: Mapping[str, Any]) -> dict[str, Any]:
        authorization = action.get("_surface_audio_authorization")
        if action.get("operation") != "audio.playback" or not PipeWirePulseAudioBackend._authorized(
            authorization, "audio.playback"
        ):
            return {"disposition": "rejected", "delivered_count": 0, "ack_strength": "none",
                    "detail": {"reason": "guest audio playback requires a current core grant"}}
        audio = action.get("_audio_payload")
        if not isinstance(audio, Mapping) or not isinstance(audio.get("samples"), bytes):
            return {"disposition": "rejected", "delivered_count": 0, "ack_strength": "none",
                    "detail": {"reason": "core-resolved PCM audio is unavailable"}}
        samples = audio["samples"]
        if not samples or len(samples) > _MAX_PCM_BYTES:
            return {"disposition": "rejected", "delivered_count": 0, "ack_strength": "none",
                    "detail": {"reason": "PCM audio exceeds the session budget"}}
        prepared = {**audio, "samples_b64": base64.b64encode(samples).decode("ascii")}
        del prepared["samples"]
        # From this point an interrupted guest call has an unknown outcome; it is
        # never retried under the same effect identity by the broker.
        return self._rpc({"operation": "dispatch", "binding": self._guest_binding(binding),
                          "arguments": action.get("arguments"), "audio_payload": prepared,
                          "recipient_scope": authorization.get("recipient_scope") if isinstance(authorization, Mapping) else None}, timeout_s=12.0)

    def neutralize(self, binding: Mapping[str, Any]) -> dict[str, Any]:
        with self._lock:
            active = tuple(self._active)
        for process in active:
            if process.poll() is None:
                process.terminate()
        return {"confirmed": not active, "detail": {
            "scope": "only backend-owned WSL audio clients", "active_processes": len(active),
        }}

    def close(self) -> None:
        with self._lock:
            self._closed = True
            active = tuple(self._active)
        for process in active:
            if process.poll() is None:
                process.terminate()


def _serve_guest() -> None:
    if len(sys.argv) != 3 or sys.argv[1] != "--bridge":
        raise ValueError("expected the dedicated audio bridge invocation")
    config = json.loads(sys.argv[2])
    raw = sys.stdin.buffer.read(_MAX_REQUEST_BYTES + 1)
    if len(raw) > _MAX_REQUEST_BYTES:
        raise ValueError("audio request exceeds the byte budget")
    request = json.loads(raw)
    if (
        not isinstance(request, dict)
        or set(request) != {"operation", "source_digests", "request"}
        or request.get("operation") != "verified-call"
    ):
        raise ValueError("audio request is missing its source-version handshake")
    expected_digests = request["source_digests"]
    if not _valid_source_digests(expected_digests):
        raise ValueError("audio request source digests are invalid")
    try:
        guest_digests = _active_source_digests()
    except OSError as exc:
        raise AudioCapabilityUnavailable(
            "guest audio helper source digest is unavailable"
        ) from exc
    mismatches = [
        name for name in _SOURCE_FILE_NAMES
        if guest_digests[name] != expected_digests[name]
    ]
    if mismatches:
        print(json.dumps({
            "error": "AudioSourceMismatch",
            "detail": "guest audio helper source SHA-256 mismatch: " + ", ".join(mismatches),
        }, separators=(",", ":"), allow_nan=False))
        return

    call = request["request"]
    if not isinstance(call, dict):
        raise ValueError("audio bridge operation is invalid")
    backend = _audio.PipeWirePulseAudioBackend(
        **config, sample_rate_hz=8000, channels=1,
        capture_duration_ms=100, probe_timeout_s=3.0,
    )
    try:
        operation = call.get("operation")
        if operation == "describe":
            result = backend.describe()
        elif operation == "sources":
            result = backend.sources()
        elif operation == "bind":
            result = backend.bind(call["source_id"])
        elif operation == "revalidate":
            result = backend.revalidate(call["binding"])
        elif operation == "capture":
            binding = {**call["binding"], "_surface_audio_enabled": True,
                       "_surface_capture_authorization": {
                           "operations": ["audio.capture"], "validate": lambda: True,
                       }}
            result = dict(backend.capture(binding))
            audio = dict(result["audio"])
            audio["samples_b64"] = base64.b64encode(audio.pop("samples")).decode("ascii")
            result["audio"] = audio
        elif operation == "dispatch":
            audio = dict(call["audio_payload"])
            audio["samples"] = base64.b64decode(audio.pop("samples_b64"), validate=True)
            action = {"operation": "audio.playback", "arguments": call["arguments"],
                      "_audio_payload": audio, "_surface_audio_authorization": {
                          "operations": ["audio.playback"],
                          "recipient_scope": call["recipient_scope"], "validate": lambda: True,
                      }}
            result = backend.dispatch(call["binding"], action)
        else:
            raise ValueError("audio bridge operation is unavailable")
        print(json.dumps({"result": result}, separators=(",", ":"), allow_nan=False))
    finally:
        backend.close()


if __name__ == "__main__":
    try:
        _serve_guest()
    except Exception as exc:
        print(json.dumps({"error": type(exc).__name__, "detail": str(exc)[:256]},
                         separators=(",", ":")))
