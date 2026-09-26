"""Explicit, non-provisioning supervisor for one dedicated Linux desktop session.

The supervisor starts and stops only the configured foreground session and its
session-scoped control command.  It never installs software, changes WSL or
host settings, or invokes distro-wide/global shutdown operations.
"""
from __future__ import annotations

import getpass
import os
import posixpath
import re
import shutil
import subprocess
import threading
import time
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any


_ALLOWED_AUDIO_ENV = {
    "PIPEWIRE_REMOTE",
    "PIPEWIRE_LATENCY",
    "PULSE_SERVER",
    "PULSE_SINK",
    "PULSE_SOURCE",
    "PULSE_LATENCY_MSEC",
}
_BASE_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
_SESSION_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}\Z")
_DISPLAY_RE = re.compile(r":[1-9][0-9]*(?:\.[0-9]+)?\Z")


class LinuxSessionError(RuntimeError):
    """An explicit Linux session configuration or lifecycle operation failed."""


class LinuxSessionUnavailable(LinuxSessionError):
    """The configured host/session prerequisite is not available."""


def _required_text(value: Any, name: str, limit: int = 4096) -> str:
    if not isinstance(value, str) or not value or len(value) > limit or "\x00" in value or "\n" in value or "\r" in value:
        raise ValueError(f"{name} must be a non-empty bounded string")
    return value


def _linux_path(value: Any, name: str) -> str:
    value = _required_text(value, name)
    path = PurePosixPath(value)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{name} must be an absolute Linux path without parent traversal")
    return str(path)


def _argv(value: Any, name: str, *, required: bool = True) -> tuple[str, ...] | None:
    if value is None and not required:
        return None
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or not value:
        raise ValueError(f"{name} must be a non-empty argument array")
    result = tuple(_required_text(item, f"{name} item", 4096) for item in value)
    if len(result) > 128 or sum(len(item) for item in result) > 16_384:
        raise ValueError(f"{name} exceeds the configured argument limits")
    return result


def _within(path: str, directory: str) -> bool:
    try:
        return posixpath.commonpath((path, directory)) == directory
    except ValueError:
        return False


def _audio_config(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("audio must explicitly declare disabled or a supported session endpoint")
    kind = value.get("kind")
    if kind == "disabled":
        if set(value) != {"kind"}:
            raise ValueError("disabled audio may not carry endpoint or environment settings")
        return {"kind": "disabled", "environment": {}}
    if kind not in ("pipewire", "pulseaudio"):
        raise ValueError("audio.kind must be disabled, pipewire, or pulseaudio")
    environment = value.get("environment")
    if not isinstance(environment, Mapping) or not environment:
        raise ValueError("enabled audio requires an explicit endpoint environment mapping")
    copied: dict[str, str] = {}
    for name, endpoint in environment.items():
        if name not in _ALLOWED_AUDIO_ENV:
            raise ValueError(f"audio environment variable {name!r} is not allowed")
        copied[name] = _required_text(endpoint, f"audio.{name}", 2048)
    required = "PIPEWIRE_REMOTE" if kind == "pipewire" else "PULSE_SERVER"
    if required not in copied:
        raise ValueError(f"audio.{required} is required for the declared backend")
    if any("/mnt/wslg" in endpoint.lower() or endpoint.lower().startswith("wslg:") for endpoint in copied.values()):
        raise ValueError("WSLg audio endpoints are not inherited or accepted for the isolated desktop")
    return {"kind": kind, "environment": copied}


@dataclass(frozen=True)
class LinuxSessionSpec:
    """Validated, explicit session identity, channels and lifetime policy."""

    target: str
    distribution: str | None
    user: str
    home: str
    display: str
    xauthority: str
    runtime_dir: str
    session_bus_address: str
    audio: Mapping[str, Any]
    session_id: str
    session_argv: tuple[str, ...]
    stop_argv: tuple[str, ...]
    readiness_argv: tuple[str, ...] | None
    restart_policy: str
    max_restarts: int
    startup_timeout_s: float
    stop_timeout_s: float
    probe_timeout_s: float
    probe_interval_s: float
    restart_delay_s: float

    @classmethod
    def from_mapping(cls, config: Mapping[str, Any]) -> "LinuxSessionSpec":
        if not isinstance(config, Mapping):
            raise ValueError("Linux session config must be a mapping")
        target = config.get("target")
        if target not in ("wsl", "linux-host"):
            raise ValueError("target must be explicitly wsl or linux-host")
        distribution = config.get("distribution")
        if target == "wsl":
            distribution = _required_text(distribution, "distribution", 128)
        elif distribution is not None:
            raise ValueError("distribution is valid only for a WSL target")
        user = _required_text(config.get("user"), "user", 128)
        if user.lower() in ("root", "administrator") or user == "0":
            raise ValueError("the Linux desktop must run as an explicitly restricted non-root user")
        home = _linux_path(config.get("home"), "home")
        display = _required_text(config.get("display"), "display", 32)
        if not _DISPLAY_RE.fullmatch(display):
            raise ValueError("display must be a dedicated X11 display such as :1, not :0/WSLg")
        xauthority = _linux_path(config.get("xauthority"), "xauthority")
        runtime_dir = _linux_path(config.get("runtime_dir"), "runtime_dir")
        if runtime_dir == "/" or runtime_dir == "/tmp":
            raise ValueError("runtime_dir must be a dedicated private directory, not a shared temporary root")
        if not (_within(xauthority, home) or _within(xauthority, runtime_dir)):
            raise ValueError("Xauthority must belong to the dedicated home or runtime directory")
        bus_address = _required_text(config.get("session_bus_address"), "session_bus_address", 2048)
        prefix = "unix:path="
        if not bus_address.startswith(prefix):
            raise ValueError("session_bus_address must be an explicit filesystem Unix socket")
        bus_path = _linux_path(bus_address[len(prefix):], "session bus path")
        if not _within(bus_path, runtime_dir):
            raise ValueError("session bus socket must be within the dedicated runtime directory")
        audio = _audio_config(config.get("audio"))
        lifetime = config.get("lifetime")
        if not isinstance(lifetime, Mapping):
            raise ValueError("lifetime must explicitly declare the supervised process and stop policy")
        session_id = _required_text(lifetime.get("session_id"), "lifetime.session_id", 96)
        if not _SESSION_ID_RE.fullmatch(session_id):
            raise ValueError("session_id must use bounded alphanumeric, dot, underscore or hyphen characters")
        session_argv = _argv(lifetime.get("session_argv"), "lifetime.session_argv")
        stop_argv = _argv(lifetime.get("stop_argv"), "lifetime.stop_argv")
        assert session_argv is not None and stop_argv is not None
        if session_id not in session_argv and lifetime.get("session_scope") != session_id:
            raise ValueError("session_argv must declare the configured session id in its arguments or session_scope")
        if session_id not in stop_argv:
            raise ValueError("stop_argv must target this exact session_id")
        session_name = posixpath.basename(session_argv[0]).lower()
        if session_name in {"shutdown", "poweroff", "halt", "reboot", "killall", "pkill", "wsl", "wsl.exe"}:
            raise ValueError("session_argv may not invoke global shutdown or process-wide control")
        if any(item in ("--shutdown", "--terminate") for item in session_argv):
            raise ValueError("session_argv may not request WSL or distribution-wide termination")
        stop_name = posixpath.basename(stop_argv[0]).lower()
        if stop_name in {"shutdown", "poweroff", "halt", "reboot", "killall", "pkill", "wsl", "wsl.exe"}:
            raise ValueError("stop_argv may not invoke a host/distro-wide shutdown or process-wide killer")
        if any(item in ("--shutdown", "--terminate", "-t", "--all") for item in stop_argv):
            raise ValueError("stop_argv may not request global or distribution-wide termination")
        readiness_argv = _argv(lifetime.get("readiness_argv"), "lifetime.readiness_argv", required=False)
        restart_policy = lifetime.get("restart_policy", "never")
        if restart_policy not in ("never", "on-failure"):
            raise ValueError("restart_policy must be never or on-failure")
        max_restarts = lifetime.get("max_restarts", 0)
        if isinstance(max_restarts, bool) or not isinstance(max_restarts, int) or not 0 <= max_restarts <= 3:
            raise ValueError("max_restarts must be an integer from 0 through 3")
        if restart_policy == "never" and max_restarts != 0:
            raise ValueError("never restart policy must use max_restarts=0")
        if restart_policy == "on-failure" and max_restarts == 0:
            raise ValueError("on-failure requires a positive bounded max_restarts")
        timeouts: dict[str, float] = {}
        for name, default, low, high in (
            ("startup_timeout_s", 30.0, 0.5, 120.0),
            ("stop_timeout_s", 15.0, 0.5, 60.0),
            ("probe_timeout_s", 2.0, 0.1, 15.0),
            ("probe_interval_s", 0.25, 0.05, 5.0),
            ("restart_delay_s", 1.0, 0.1, 30.0),
        ):
            raw = lifetime.get(name, default)
            if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not low <= raw <= high:
                raise ValueError(f"lifetime.{name} must be between {low} and {high}")
            timeouts[name] = float(raw)
        return cls(
            target=target,
            distribution=distribution,
            user=user,
            home=home,
            display=display,
            xauthority=xauthority,
            runtime_dir=runtime_dir,
            session_bus_address=bus_address,
            audio=audio,
            session_id=session_id,
            session_argv=session_argv,
            stop_argv=stop_argv,
            readiness_argv=readiness_argv,
            restart_policy=restart_policy,
            max_restarts=max_restarts,
            startup_timeout_s=timeouts["startup_timeout_s"],
            stop_timeout_s=timeouts["stop_timeout_s"],
            probe_timeout_s=timeouts["probe_timeout_s"],
            probe_interval_s=timeouts["probe_interval_s"],
            restart_delay_s=timeouts["restart_delay_s"],
        )

    def environment(self, incarnation: str) -> dict[str, str]:
        env = {
            "HOME": self.home,
            "USER": self.user,
            "LOGNAME": self.user,
            "PATH": _BASE_PATH,
            "LANG": "C.UTF-8",
            "DISPLAY": self.display,
            "XAUTHORITY": self.xauthority,
            "XDG_RUNTIME_DIR": self.runtime_dir,
            "DBUS_SESSION_BUS_ADDRESS": self.session_bus_address,
            "XDG_SESSION_TYPE": "x11",
            "CASSI_SURFACE_SESSION_ID": self.session_id,
            "CASSI_SURFACE_ENVIRONMENT_INCARNATION": incarnation,
        }
        env.update(self.audio["environment"])
        # No caller environment is merged. WSLg display, Wayland, bus, audio and
        # WSLENV variables therefore cannot leak into the dedicated session.
        return env


class LinuxSessionSupervisor:
    """Run one explicitly configured, foreground Linux session without global shutdown."""

    backend_id = "linux-session-supervisor"

    def __init__(self, config: Mapping[str, Any] | None = None) -> None:
        self._spec = LinuxSessionSpec.from_mapping(config) if config is not None else None
        self._process: subprocess.Popen[bytes] | None = None
        self._incarnation: str | None = None
        self._source_instance: str | None = None
        self._state = "not-configured" if self._spec is None else "stopped"
        self._reason: str | None = None
        self._last_exit_code: int | None = None
        self._restart_count = 0
        self._lock = threading.RLock()

    def describe(self) -> dict[str, Any]:
        spec = self._spec
        executable, availability_reason = self._resolve_executable(spec)
        available = executable is not None
        audio_kind = spec.audio["kind"] if spec is not None else "unconfigured"
        operations = {
            "start": {"status": "supported" if available else "unavailable", "reason": availability_reason},
            "stop": {
                "status": "supported" if available and spec is not None else "unavailable",
                "reason": None if available and spec is not None else availability_reason,
            },
            "status": {"status": "supported", "reason": None},
            "wait_ready": {
                "status": "supported" if available and spec is not None and spec.readiness_argv else "unavailable",
                "reason": None if available and spec is not None and spec.readiness_argv else "explicit readiness_argv is required; process creation alone is not readiness",
            },
            "audio": {
                "status": "unavailable",
                "configured_endpoint": audio_kind in ("pipewire", "pulseaudio"),
                "reason": "session environment only; audio capture/playback requires a separately supported channel and explicit grant",
            },
        }
        status = "available" if available else "unavailable"
        return {
            "backend_id": self.backend_id,
            "status": status,
            "reason": availability_reason,
            "operations": operations,
            "limits": {
                "target": spec.target if spec is not None else None,
                "display": spec.display if spec is not None else None,
                "audio_profile": audio_kind,
                "inherited_wslg_environment": False,
                "global_shutdown": "never invoked",
                "installation_or_provisioning": "not performed",
                "session_process": "configured foreground command only",
            },
            "lifecycle": self.status(),
        }

    def _resolve_executable(self, spec: LinuxSessionSpec | None) -> tuple[str | None, str | None]:
        if spec is None:
            return None, "session is not configured"
        if spec.target == "wsl":
            if os.name != "nt":
                return None, "WSL target requires a Windows host; no WSL command was run"
            executable = shutil.which("wsl.exe")
            if executable is None:
                return None, "wsl.exe is not installed or not on PATH; no installation or configuration change was attempted"
            return executable, None
        if os.name != "posix":
            return None, "linux-host target requires an existing POSIX host"
        try:
            current_user = getpass.getuser()
        except Exception:
            current_user = ""
        if current_user != spec.user:
            return None, "linux-host target must run as the explicitly configured current user; no privilege change is attempted"
        return "", None

    def sources(self) -> list[dict[str, Any]]:
        spec = self._spec
        if spec is None:
            return []
        executable, reason = self._resolve_executable(spec)
        return [
            {
                "source_id": spec.session_id,
                "source_instance": self._source_instance,
                "environment_incarnation": self._incarnation,
                "display": spec.display,
                "transport": "session-supervisor",
                "status": self.status()["state"],
                "available": executable is not None,
                "reason": reason,
                "operations": ["start", "stop", "status"],
            }
        ]

    def start(self) -> dict[str, Any]:
        spec = self._require_spec()
        executable, reason = self._resolve_executable(spec)
        if executable is None:
            self._state = "unavailable"
            self._reason = reason
            raise LinuxSessionUnavailable(reason or "Linux session target is unavailable")
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                return self.status()
            self._launch(spec, executable)
            return self.status()

    def _launch(self, spec: LinuxSessionSpec, executable: str) -> None:
        source_instance = uuid.uuid4().hex
        incarnation = uuid.uuid4().hex
        environment = spec.environment(incarnation)
        if spec.target == "wsl":
            assert spec.distribution is not None
            command = [executable, "--distribution", spec.distribution, "--user", spec.user, "--exec", "/usr/bin/env", "-i"]
            command.extend(f"{name}={value}" for name, value in environment.items())
            command.extend(spec.session_argv)
        else:
            command = list(spec.session_argv)
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=environment if spec.target == "linux-host" else None,
                close_fds=True,
                creationflags=creationflags,
            )
        except OSError as exc:
            self._source_instance = None
            self._incarnation = None
            self._process = None
            self._state = "failed"
            self._reason = f"foreground session launch failed: {type(exc).__name__}"
            raise LinuxSessionUnavailable(self._reason) from exc
        self._process = process
        self._incarnation = incarnation
        self._source_instance = source_instance
        self._last_exit_code = None
        self._reason = None
        self._state = "starting"

    def status(self) -> dict[str, Any]:
        with self._lock:
            code = self._process.poll() if self._process is not None else None
            if self._process is not None and code is not None and self._state in ("starting", "running", "ready"):
                self._last_exit_code = code
                self._state = "stopped" if code == 0 else "failed"
                if code != 0:
                    self._reason = f"owned foreground session exited with status {code}"
            spec = self._spec
            return {
                "state": self._state,
                "session_id": spec.session_id if spec else None,
                "source_instance": self._source_instance,
                "environment_incarnation": self._incarnation,
                "supervisor_pid": self._process.pid if self._process is not None and code is None else None,
                "process_id_scope": (
                    None if spec is None else
                    "host-side WSL client only" if spec.target == "wsl" else
                    "linux-host foreground command"
                ),
                "exit_code": self._last_exit_code,
                "restart_count": self._restart_count,
                "reason": self._reason,
                "ready": self._state == "ready",
                "readiness_scope": "configured environment probe only; RFB full-baseline readiness is separate",
            }

    def wait_ready(self, timeout_s: float | None = None) -> dict[str, Any]:
        spec = self._require_spec()
        if spec.readiness_argv is None:
            raise LinuxSessionUnavailable("readiness cannot be attested without an explicit readiness_argv")
        timeout = spec.startup_timeout_s if timeout_s is None else timeout_s
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0.1 <= timeout <= 120.0:
            raise ValueError("timeout_s must be between 0.1 and 120 seconds")
        deadline = time.monotonic() + float(timeout)
        last_reason = "readiness probe has not succeeded"
        while time.monotonic() < deadline:
            with self._lock:
                process = self._process
                if process is None:
                    raise LinuxSessionUnavailable("session is not started")
                code = process.poll()
                if code is not None:
                    self._last_exit_code = code
                    self._state = "failed" if code else "stopped"
                    raise LinuxSessionUnavailable(f"session exited before readiness with status {code}")
            try:
                result = self._run_guest_command(spec.readiness_argv, spec.probe_timeout_s)
                if result.returncode == 0:
                    with self._lock:
                        self._state = "ready"
                        self._reason = None
                    return self.status()
                last_reason = f"readiness probe returned status {result.returncode}"
            except (OSError, subprocess.TimeoutExpired, LinuxSessionError) as exc:
                last_reason = f"readiness probe failed: {type(exc).__name__}"
            time.sleep(min(spec.probe_interval_s, max(0.0, deadline - time.monotonic())))
        with self._lock:
            self._state = "starting"
            self._reason = last_reason
        return self.status()

    def poll(self) -> dict[str, Any]:
        """Observe lifetime and apply only a bounded, explicitly configured restart policy."""
        status = self.status()
        spec = self._spec
        if spec is None or status["state"] != "failed" or spec.restart_policy != "on-failure" or self._source_instance is None:
            return status
        with self._lock:
            if self._restart_count >= spec.max_restarts:
                self._reason = "configured restart limit reached"
                return self.status()
        try:
            stopped = self._run_guest_command(spec.stop_argv, spec.stop_timeout_s)
        except (OSError, subprocess.TimeoutExpired, LinuxSessionError) as exc:
            with self._lock:
                self._state = "degraded"
                self._reason = f"scoped cleanup before restart was not confirmed: {type(exc).__name__}"
                return self.status()
        if stopped.returncode != 0:
            with self._lock:
                self._state = "degraded"
                self._reason = f"scoped cleanup before restart returned status {stopped.returncode}"
                return self.status()
        time.sleep(spec.restart_delay_s)
        executable, reason = self._resolve_executable(spec)
        if executable is None:
            with self._lock:
                self._state = "unavailable"
                self._reason = reason
                return self.status()
        with self._lock:
            self._restart_count += 1
            self._launch(spec, executable)
            return self.status()

    def stop(self) -> dict[str, Any]:
        spec = self._require_spec()
        with self._lock:
            if self._source_instance is None:
                return self.status()
        executable, reason = self._resolve_executable(spec)
        if executable is None:
            with self._lock:
                self._state = "degraded"
                self._reason = reason
                return self.status()
        try:
            result = self._run_guest_command(spec.stop_argv, spec.stop_timeout_s)
        except (OSError, subprocess.TimeoutExpired, LinuxSessionError) as exc:
            with self._lock:
                self._state = "degraded"
                self._reason = f"session-scoped graceful stop was not confirmed: {type(exc).__name__}"
                return self.status()
        if result.returncode != 0:
            with self._lock:
                self._state = "degraded"
                self._reason = f"session-scoped stop command returned status {result.returncode}; no global shutdown was attempted"
                return self.status()
        with self._lock:
            process = self._process
        if process is not None:
            try:
                process.wait(timeout=spec.stop_timeout_s)
            except subprocess.TimeoutExpired:
                with self._lock:
                    self._state = "degraded"
                    self._reason = "scoped stop command succeeded but foreground WSL/client process did not exit; it was not force-killed"
                    return self.status()
        with self._lock:
            self._state = "stopped"
            self._source_instance = None
            self._incarnation = None
            self._reason = None
            self._last_exit_code = process.returncode if process is not None else None
            return self.status()

    def close(self) -> dict[str, Any]:
        if self._spec is None:
            return self.status()
        return self.stop()

    def _run_guest_command(self, argv: Sequence[str] | None, timeout_s: float) -> subprocess.CompletedProcess[bytes]:
        spec = self._require_spec()
        if argv is None:
            raise LinuxSessionUnavailable("no explicit command is configured")
        executable, reason = self._resolve_executable(spec)
        if executable is None:
            raise LinuxSessionUnavailable(reason or "Linux target is unavailable")
        environment = spec.environment(self._incarnation or uuid.uuid4().hex)
        if spec.target == "wsl":
            assert spec.distribution is not None
            command = [executable, "--distribution", spec.distribution, "--user", spec.user, "--exec", "/usr/bin/env", "-i"]
            command.extend(f"{name}={value}" for name, value in environment.items())
            command.extend(argv)
            # The env -i inside Linux, not Python's or WSLg's inherited environment,
            # defines the session bus, display, authority and audio endpoint.
            return subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout_s, check=False)
        return subprocess.run(
            list(argv),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=environment,
            timeout=timeout_s,
            check=False,
        )

    def _require_spec(self) -> LinuxSessionSpec:
        if self._spec is None:
            raise LinuxSessionUnavailable("an explicit Linux session config is required")
        return self._spec
