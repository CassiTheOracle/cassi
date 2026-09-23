"""Bounded lifecycle supervision for externally provisioned surface helpers.

This module owns only the direct helper process it launches. It never installs
software or WSL distributions, discovers/kills processes by name or PID, or
issues WSL-wide shutdown commands. A Linux Xvnc helper may be launched through
an explicitly configured per-command WSL invocation, but its distribution,
display server and session must already be provisioned. Host effect ledgers
must remain outside disposable guests.

The helper reports one bounded JSON status record per stdout line::

    {"protocol":"cassi.surface.helper.v1","event":"ready",
     "sensing_ready":true,"input_eligible":false,"reason":"display attached"}

``event`` is ``ready``, ``degraded`` or ``heartbeat``. These readiness fields
describe mechanics only. ``input_eligible`` is not an authorization grant; the
host broker remains the only effect and control-authority route.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field, replace
import math
import json
import os
from pathlib import Path
import subprocess
import threading
import time
from typing import Any, Mapping
import uuid


_STATUS_PROTOCOL = "cassi.surface.helper.v1"
_SUPPORTED_KINDS = frozenset({"windows_session", "linux_xvnc_session"})
_FORBIDDEN_WSL_FLAGS = frozenset({
    "--shutdown", "--install", "--update", "--import", "--import-in-place",
    "--unregister", "--terminate", "--set-version", "--set-default-version",
    "--set-default",
})


@dataclass(frozen=True)
class RestartPolicy:
    """Bounded relaunch policy shared by automatic and explicit restarts."""

    enabled: bool = True
    max_restarts: int = 3
    window_s: float = 60.0
    initial_backoff_s: float = 0.25
    max_backoff_s: float = 5.0
    restart_on_unhealthy: bool = False

    def __post_init__(self) -> None:
        if (not isinstance(self.max_restarts, int) or isinstance(self.max_restarts, bool)
                or self.max_restarts < 0 or self.max_restarts > 10000
                or not math.isfinite(self.window_s) or not 0 < self.window_s <= 86400):
            raise ValueError("restart count/window is outside finite bounds")
        if (not math.isfinite(self.initial_backoff_s)
                or not math.isfinite(self.max_backoff_s)
                or not 0 < self.initial_backoff_s <= self.max_backoff_s <= 86400):
            raise ValueError("restart backoff must be finite, positive, and bounded")


@dataclass(frozen=True)
class ProcessBudget:
    """Lifecycle, watchdog and protocol bounds for one direct helper child."""

    startup_timeout_s: float = 15.0
    shutdown_timeout_s: float = 3.0
    watchdog_interval_s: float = 0.2
    heartbeat_timeout_s: float | None = None
    max_runtime_s: float | None = None
    max_stdout_line_bytes: int = 4096
    max_stdout_bytes_per_second: int = 262144

    def __post_init__(self) -> None:
        times = (self.startup_timeout_s, self.shutdown_timeout_s, self.watchdog_interval_s)
        if any(not math.isfinite(value) or not 0 < value <= 86400 for value in times):
            raise ValueError("startup, shutdown, and watchdog bounds must be finite and positive")
        if (not isinstance(self.max_stdout_line_bytes, int)
                or isinstance(self.max_stdout_line_bytes, bool)
                or not 128 <= self.max_stdout_line_bytes <= 1_048_576
                or not isinstance(self.max_stdout_bytes_per_second, int)
                or isinstance(self.max_stdout_bytes_per_second, bool)
                or not 128 <= self.max_stdout_bytes_per_second <= 104_857_600):
            raise ValueError("stdout resource bounds must be positive bounded integers")
        if (self.heartbeat_timeout_s is not None
                and (not math.isfinite(self.heartbeat_timeout_s)
                     or not 0 < self.heartbeat_timeout_s <= 86400)):
            raise ValueError("heartbeat timeout must be finite and positive")
        if (self.max_runtime_s is not None
                and (not math.isfinite(self.max_runtime_s)
                     or not 0 < self.max_runtime_s <= 86400)):
            raise ValueError("maximum runtime must be finite and positive")


@dataclass(frozen=True)
class HelperConfig:
    """Description of a helper already installed/configured by its operator.

    ``argv`` is passed directly to ``Popen`` with ``shell=False``. A Linux
    helper on Windows can use an explicit command such as
    ``wsl.exe -d <existing-distro> --exec <existing-helper>``. This supervisor
    does not install, import, update, terminate or shut down WSL distributions.
    The helper/wrapper must treat supervisor stdin EOF as graceful quiescence
    and clean up only its own session resources. The host does not discover or
    kill descendants/guest PIDs; an unconfirmed direct-child stop is degraded.


    A ``windows_session`` helper must be supervised from its target interactive
    session. This class does not impersonate users or move processes between
    Windows sessions; in particular, it refuses to start that helper from
    Session 0.
    """

    name: str
    kind: str
    argv: tuple[str, ...]
    working_directory: Path | None = None
    environment: Mapping[str, str] = field(default_factory=dict)
    inherit_environment: bool = True
    expected_session_id: int | None = None
    restart_policy: RestartPolicy = field(default_factory=RestartPolicy)
    budget: ProcessBudget = field(default_factory=ProcessBudget)

    def __post_init__(self) -> None:
        if not self.name or len(self.name) > 128 or "\x00" in self.name:
            raise ValueError("helper name must contain 1..128 non-NUL characters")
        if self.kind not in _SUPPORTED_KINDS:
            raise ValueError(f"unsupported helper kind: {self.kind!r}")
        if not self.argv or any(not isinstance(arg, str) or not arg or "\x00" in arg
                                for arg in self.argv):
            raise ValueError("argv must contain non-empty NUL-free strings")
        if any(not isinstance(key, str) or not isinstance(value, str)
               or "\x00" in key + value for key, value in self.environment.items()):
            raise ValueError("environment keys and values must be NUL-free strings")
        if self.expected_session_id is not None and os.name != "nt":
            raise ValueError("expected_session_id is only supported on Windows hosts")
        if self.expected_session_id is not None and self.expected_session_id < 0:
            raise ValueError("expected session id must be nonnegative")
        exe_name = Path(self.argv[0].replace("\\", "/")).name.casefold()
        if exe_name in {"wsl", "wsl.exe"}:
            flags = {arg.casefold() for arg in self.argv[1:]}
            if flags & _FORBIDDEN_WSL_FLAGS:
                raise ValueError("WSL management/global lifecycle flags are not helper commands")


@dataclass(frozen=True)
class EnvironmentState:
    """Immutable, serializable status for one environment incarnation."""

    name: str
    kind: str
    phase: str
    environment_incarnation: str | None
    generation: int
    process_id: int | None
    process_returncode: int | None
    session_id: int | None
    sensing_ready: bool
    input_eligible: bool
    readiness_reason: str
    last_heartbeat_ns: int | None
    started_at_ns: int | None
    updated_at_ns: int
    restarts_in_window: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "phase": self.phase,
            "environment_incarnation": self.environment_incarnation,
            "generation": self.generation,
            "process_id": self.process_id,
            "process_returncode": self.process_returncode,
            "session_id": self.session_id,
            "sensing_ready": self.sensing_ready,
            "input_eligible": self.input_eligible,
            "readiness_reason": self.readiness_reason,
            "last_heartbeat_ns": self.last_heartbeat_ns,
            "started_at_ns": self.started_at_ns,
            "updated_at_ns": self.updated_at_ns,
            "restarts_in_window": self.restarts_in_window,
        }


class BoundedProcessSupervisor:
    """Supervise one named helper, with bounded restarts and responsive stop.

    ``start`` returns immediately. ``wait_for_ready`` waits no longer than the
    startup budget by default. Every spawn gets a fresh incarnation UUID. Stop
    first makes control ineligible, closes the helper's stdin, then terminates
    and if necessary kills only the ``Popen`` child object owned here. No
    process-tree or global OS lifecycle operation is used.
    """

    def __init__(self, config: HelperConfig):
        self.config = config
        self._condition = threading.Condition(threading.RLock())
        self._stop_event = threading.Event()
        self._controller: threading.Thread | None = None
        self._process: subprocess.Popen[bytes] | None = None
        self._reader: threading.Thread | None = None
        self._closed = False
        self._restart_times: deque[float] = deque()
        self._generation = 0
        self._state = EnvironmentState(
            name=config.name,
            kind=config.kind,
            phase="configured",
            environment_incarnation=None,
            generation=0,
            process_id=None,
            process_returncode=None,
            session_id=None,
            sensing_ready=False,
            input_eligible=False,
            readiness_reason="configured_not_started",
            last_heartbeat_ns=None,
            started_at_ns=None,
            updated_at_ns=time.time_ns(),
            restarts_in_window=0,
        )

    def state(self) -> EnvironmentState:
        with self._condition:
            self._refresh_restart_count_locked()
            return self._state

    def describe(self) -> dict[str, Any]:
        """Report actual lifecycle state and the supervisor's explicit bounds."""
        state = self.state()
        return {
            "name": self.config.name,
            "availability": (
                "unavailable" if self.config.kind == "windows_session" and os.name != "nt"
                else "not_probed" if state.phase == "configured"
                else "ready" if state.phase == "ready"
                else "degraded" if state.phase == "degraded"
                else state.phase
            ),
            "availability_reason": (
                "windows_session_requires_windows_host"
                if self.config.kind == "windows_session" and os.name != "nt"
                else state.readiness_reason
            ),
            "kind": self.config.kind,
            "configured": True,
            "lifecycle_supported": True,
            "state": state.as_dict(),
            "limits": {
                "max_direct_children": 1,
                "automatic_restart": self.config.restart_policy.enabled,
                "max_restarts_per_window": self.config.restart_policy.max_restarts,
                "restart_window_s": self.config.restart_policy.window_s,
                "startup_timeout_s": self.config.budget.startup_timeout_s,
                "shutdown_timeout_s": self.config.budget.shutdown_timeout_s,
                "watchdog_interval_s": self.config.budget.watchdog_interval_s,
                "heartbeat_timeout_s": self.config.budget.heartbeat_timeout_s,
                "max_runtime_s_per_child": self.config.budget.max_runtime_s,
                "max_stdout_line_bytes": self.config.budget.max_stdout_line_bytes,
                "max_stdout_bytes_per_second": self.config.budget.max_stdout_bytes_per_second,
                "os_memory_cpu_quota": "not_enforced_by_this_supervisor",
            },
        }

    def start(self) -> EnvironmentState:
        """Begin the configured child lifecycle and return immediately."""
        with self._condition:
            if self._closed:
                raise RuntimeError("supervisor is closed")
            if self._controller is not None and self._controller.is_alive():
                raise RuntimeError("helper supervisor is already running")
            if self._process is not None:
                if self._process.poll() is None:
                    raise RuntimeError("previous helper child is still active")
                self._process = None
            self._stop_event.clear()
            self._set_state_locked(
                phase="starting",
                environment_incarnation=None,
                process_id=None,
                process_returncode=None,
                session_id=None,
                sensing_ready=False,
                input_eligible=False,
                readiness_reason="launch_pending",
                last_heartbeat_ns=None,
                started_at_ns=None,
            )
            # Reusing the supervisor is a restart and consumes the same bounded
            # retry budget as an automatic or explicit restart.
            charge_restart = self._generation > 0
            self._controller = threading.Thread(
                target=self._control_loop,
                args=(charge_restart,),
                name=f"surface-helper-{self.config.name}",
                daemon=True,
            )
            self._controller.start()
            return self._state

    def restart(self, reason: str = "operator_restart") -> EnvironmentState:
        """Quiesce any current child and relaunch as a fresh incarnation."""
        stopped = self.stop()
        if stopped.phase != "stopped":
            return stopped
        with self._condition:
            if self._closed:
                raise RuntimeError("supervisor is closed")
            if not self._reserve_restart_locked():
                self._set_state_locked(
                    phase="degraded",
                    readiness_reason="restart_budget_exhausted",
                    sensing_ready=False,
                    input_eligible=False,
                )
                return self._state
            self._stop_event.clear()
            self._set_state_locked(
                phase="starting",
                environment_incarnation=None,
                process_id=None,
                process_returncode=None,
                session_id=None,
                sensing_ready=False,
                input_eligible=False,
                readiness_reason=(reason or "operator_restart")[:512],
                last_heartbeat_ns=None,
                started_at_ns=None,
            )
            # The explicit restart slot was reserved above.
            self._controller = threading.Thread(
                target=self._control_loop,
                args=(False,),
                name=f"surface-helper-{self.config.name}",
                daemon=True,
            )
            self._controller.start()
            return self._state

    def wait_for_ready(self, timeout_s: float | None = None) -> EnvironmentState:
        """Wait for a readiness/degradation result, bounded by startup timeout."""
        timeout = self.config.budget.startup_timeout_s if timeout_s is None else timeout_s
        if not math.isfinite(timeout) or not 0 <= timeout <= 86400:
            raise ValueError("timeout must be finite and within one day")
        deadline = time.monotonic() + timeout
        with self._condition:
            while self._state.phase not in {"configured", "ready", "degraded", "stopped"}:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return self._state
                self._condition.wait(remaining)
            return self._state

    def stop(self, timeout_s: float | None = None) -> EnvironmentState:
        """Cancel, quiesce, and wait boundedly for this supervisor's child."""
        wait_s = self.config.budget.shutdown_timeout_s if timeout_s is None else timeout_s
        if not math.isfinite(wait_s) or not 0 <= wait_s <= 86400:
            raise ValueError("timeout must be finite and within one day")
        with self._condition:
            controller = self._controller
            proc = self._process
            controller_live = controller is not None and controller.is_alive()
            if (not controller_live and (proc is None or proc.poll() is not None)):
                if self._process is proc:
                    self._process = None
                self._set_state_locked(
                    phase="stopped",
                    process_id=None,
                    sensing_ready=False,
                    input_eligible=False,
                    readiness_reason="stopped",
                )
                return self._state
            self._set_state_locked(
                phase="quiescing",
                sensing_ready=False,
                input_eligible=False,
                readiness_reason="quiescing",
            )
            self._stop_event.set()
            self._condition.notify_all()

        if not controller_live and proc is not None:
            stopped = self._terminate_child(proc)
            with self._condition:
                self._set_state_locked(
                    phase="stopped" if stopped else "degraded",
                    process_id=None if stopped else proc.pid,
                    process_returncode=proc.poll(),
                    sensing_ready=False,
                    input_eligible=False,
                    readiness_reason="stopped" if stopped else "stop_unconfirmed",
                )
            return self.state()

        assert controller is not None
        join_budget = (3 * wait_s if timeout_s is None else wait_s)
        controller.join(join_budget + self.config.budget.watchdog_interval_s + 0.25)
        with self._condition:
            if controller.is_alive():
                # Process creation may still be in the OS. Do not guess a PID
                # or kill an unrelated process in an attempt to force progress.
                return self._state
            proc = self._process
            if proc is not None and proc.poll() is None:
                self._set_state_locked(
                    phase="degraded",
                    process_id=proc.pid,
                    sensing_ready=False,
                    input_eligible=False,
                    readiness_reason="stop_unconfirmed",
                )
                return self._state
            if self._state.phase != "stopped":
                self._set_state_locked(
                    phase="stopped",
                    process_id=None,
                    sensing_ready=False,
                    input_eligible=False,
                    readiness_reason="stopped",
                )
            return self._state

    def close(self) -> None:
        """Stop this process lifecycle and reject any later start request."""
        self.stop()
        with self._condition:
            self._closed = True

    def _control_loop(self, initial_restart: bool) -> None:
        attempt = 0
        while not self._stop_event.is_set():
            if (initial_restart or attempt > 0) and not self._reserve_restart():
                with self._condition:
                    self._set_state_locked(
                        phase="degraded",
                        process_id=None,
                        sensing_ready=False,
                        input_eligible=False,
                        readiness_reason="restart_budget_exhausted",
                    )
                return
            if attempt:
                delay = self.config.restart_policy.initial_backoff_s
                for _ in range(attempt - 1):
                    if delay >= self.config.restart_policy.max_backoff_s / 2:
                        delay = self.config.restart_policy.max_backoff_s
                        break
                    delay *= 2
                if self._stop_event.wait(delay):
                    break
            attempt += 1
            try:
                environment = dict(os.environ) if self.config.inherit_environment else {}
                environment.update(self.config.environment)
                if self.config.kind == "windows_session":
                    if os.name != "nt":
                        raise RuntimeError("windows_session helper requires a Windows host")
                    parent_session = _windows_session_id(os.getpid())
                    if parent_session == 0:
                        raise RuntimeError("windows_session helper cannot run from Session 0")
                    if (self.config.expected_session_id is not None
                            and parent_session != self.config.expected_session_id):
                        raise RuntimeError(
                            f"supervisor_session_mismatch:{parent_session}"
                            f"!={self.config.expected_session_id}"
                        )
                proc = subprocess.Popen(
                    self.config.argv,
                    cwd=str(self.config.working_directory) if self.config.working_directory else None,
                    env=environment,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    shell=False,
                    close_fds=True,
                    bufsize=0,
                )
            except (OSError, ValueError, RuntimeError) as exc:
                with self._condition:
                    self._set_state_locked(
                        phase="degraded",
                        process_id=None,
                        process_returncode=None,
                        session_id=None,
                        sensing_ready=False,
                        input_eligible=False,
                        readiness_reason=f"spawn_failed:{type(exc).__name__}:{exc}"[:512],
                    )
                if not self.config.restart_policy.enabled or not self._has_restart_room():
                    return
                continue
            with self._condition:
                self._process = proc

            incarnation = str(uuid.uuid4())
            started_ns = time.time_ns()
            try:
                session_id = _windows_session_id(proc.pid) if os.name == "nt" else None
                expected = self.config.expected_session_id
                if expected is not None and session_id != expected:
                    raise RuntimeError(f"child_session_mismatch:{session_id}!={expected}")
                if self.config.kind == "windows_session" and session_id == 0:
                    raise RuntimeError("windows_session helper cannot run from Session 0")
            except (OSError, RuntimeError) as exc:
                stopped = self._terminate_child(proc)
                with self._condition:
                    self._set_state_locked(
                        phase="degraded",
                        process_id=None if stopped else proc.pid,
                        process_returncode=proc.poll(),
                        session_id=None,
                        sensing_ready=False,
                        input_eligible=False,
                        readiness_reason=(
                            f"session_validation_failed:{exc}"
                            + ("" if stopped else ":stop_unconfirmed")
                        )[:512],
                    )
                if not stopped:
                    return
                if not self.config.restart_policy.enabled or not self._has_restart_room():
                    return
                continue

            with self._condition:
                self._generation += 1
                generation = self._generation
                self._process = proc
                self._set_state_locked(
                    phase="starting",
                    environment_incarnation=incarnation,
                    generation=generation,
                    process_id=proc.pid,
                    process_returncode=None,
                    session_id=session_id,
                    sensing_ready=False,
                    input_eligible=False,
                    readiness_reason="awaiting_helper_readiness",
                    last_heartbeat_ns=None,
                    started_at_ns=started_ns,
                )
                self._reader = threading.Thread(
                    target=self._read_status,
                    args=(proc, incarnation, generation),
                    name=f"surface-helper-status-{self.config.name}",
                    daemon=True,
                )
                self._reader.start()
                self._condition.notify_all()

            outcome = self._watch_child(proc)
            if outcome == "stopped":
                with self._condition:
                    stopped_reason = self._state.readiness_reason
                    limited = stopped_reason == "stdout_rate_budget_exceeded"
                    self._set_state_locked(
                        phase="degraded" if limited else "quiescing",
                        sensing_ready=False,
                        input_eligible=False,
                        readiness_reason=stopped_reason if limited else "quiescing",
                    )
                stopped = self._terminate_child(proc)
                with self._condition:
                    self._set_state_locked(
                        phase="stopped" if stopped and not limited else "degraded",
                        process_id=None if stopped else proc.pid,
                        process_returncode=proc.poll(),
                        sensing_ready=False,
                        input_eligible=False,
                        readiness_reason=(
                            stopped_reason if limited else "stopped"
                            if stopped else "stop_unconfirmed"
                        ),
                    )
                return
            if outcome == "runtime_budget_exhausted":
                return
            if outcome == "unhealthy":
                with self._condition:
                    self._set_state_locked(
                        phase="quiescing",
                        sensing_ready=False,
                        input_eligible=False,
                        readiness_reason="unhealthy_restart",
                    )
                stopped = self._terminate_child(proc)
                if not stopped:
                    with self._condition:
                        self._set_state_locked(
                            phase="degraded",
                            process_id=proc.pid,
                            process_returncode=proc.poll(),
                            readiness_reason="unhealthy_child_stop_unconfirmed",
                        )
                    return
                if not self.config.restart_policy.enabled:
                    with self._condition:
                        self._set_state_locked(
                            phase="degraded",
                            process_id=None,
                            process_returncode=proc.poll(),
                            readiness_reason="restart_disabled_after_unhealthy",
                        )
                    return
            else:
                # The direct child exited unexpectedly. Its return code and
                # reason were recorded by _watch_child before retry scheduling.
                pass
            if not self.config.restart_policy.enabled or not self._has_restart_room():
                with self._condition:
                    if self._state.phase != "degraded":
                        self._set_state_locked(
                            phase="degraded",
                            process_id=None,
                            sensing_ready=False,
                            input_eligible=False,
                            readiness_reason="restart_budget_exhausted",
                        )
                return

        proc = self._current_process()
        stopped = True
        if proc is not None:
            with self._condition:
                self._set_state_locked(
                    phase="quiescing",
                    sensing_ready=False,
                    input_eligible=False,
                    readiness_reason="supervisor_stop",
                )
            stopped = self._terminate_child(proc)
        with self._condition:
            self._set_state_locked(
                phase="stopped" if stopped else "degraded",
                process_id=None if stopped else proc.pid,
                process_returncode=proc.poll() if proc else None,
                sensing_ready=False,
                input_eligible=False,
                readiness_reason="stopped" if stopped else "stop_unconfirmed",
            )

    def _watch_child(self, proc: subprocess.Popen[bytes]) -> str:
        deadline = time.monotonic() + self.config.budget.startup_timeout_s
        runtime_started = time.monotonic()
        while not self._stop_event.is_set():
            state = self.state()
            if state.phase == "degraded" and self.config.restart_policy.restart_on_unhealthy:
                return "unhealthy"
            returncode = proc.poll()
            if returncode is not None:
                with self._condition:
                    self._set_state_locked(
                        phase="degraded",
                        process_returncode=returncode,
                        process_id=None,
                        sensing_ready=False,
                        input_eligible=False,
                        readiness_reason=f"helper_exited:{returncode}",
                    )
                return "exited"

            now = time.monotonic()
            if (self.config.budget.max_runtime_s is not None
                    and now - runtime_started >= self.config.budget.max_runtime_s):
                with self._condition:
                    self._set_state_locked(
                        phase="quiescing",
                        sensing_ready=False,
                        input_eligible=False,
                        readiness_reason="maximum_runtime_reached",
                    )
                stopped = self._terminate_child(proc)
                with self._condition:
                    self._set_state_locked(
                        phase="degraded",
                        process_id=None if stopped else proc.pid,
                        process_returncode=proc.poll(),
                        readiness_reason=(
                            "maximum_runtime_reached" if stopped
                            else "maximum_runtime_stop_unconfirmed"
                        ),
                    )
                return "runtime_budget_exhausted"

            if state.phase == "starting" and now >= deadline:
                with self._condition:
                    self._set_state_locked(
                        phase="degraded",
                        sensing_ready=False,
                        input_eligible=False,
                        readiness_reason="readiness_timeout",
                    )
                if self.config.restart_policy.restart_on_unhealthy:
                    return "unhealthy"
            heartbeat_timeout = self.config.budget.heartbeat_timeout_s
            if heartbeat_timeout is not None and state.phase == "ready":
                last = state.last_heartbeat_ns or state.started_at_ns or time.time_ns()
                if (time.time_ns() - last) / 1_000_000_000 > heartbeat_timeout:
                    with self._condition:
                        self._set_state_locked(
                            phase="degraded",
                            sensing_ready=False,
                            input_eligible=False,
                            readiness_reason="heartbeat_timeout",
                        )
                    if self.config.restart_policy.restart_on_unhealthy:
                        return "unhealthy"
            self._stop_event.wait(self.config.budget.watchdog_interval_s)
        return "stopped"

    def _read_status(self, proc: subprocess.Popen[bytes], incarnation: str, generation: int) -> None:
        stream = proc.stdout
        if stream is None:
            return
        limit = self.config.budget.max_stdout_line_bytes
        output_window_started = time.monotonic()
        output_window_bytes = 0

        def over_output_budget(size: int) -> bool:
            nonlocal output_window_started, output_window_bytes
            now = time.monotonic()
            if now - output_window_started >= 1.0:
                output_window_started = now
                output_window_bytes = 0
            output_window_bytes += size
            return output_window_bytes > self.config.budget.max_stdout_bytes_per_second

        def exhaust_output_budget() -> None:
            with self._condition:
                if self._process is proc:
                    self._set_state_locked(
                        phase="degraded",
                        sensing_ready=False,
                        input_eligible=False,
                        readiness_reason="stdout_rate_budget_exceeded",
                    )
                self._stop_event.set()

        while not self._stop_event.is_set():
            try:
                line = stream.readline(limit + 1)
            except (OSError, ValueError):
                return
            if not line:
                return
            if over_output_budget(len(line)):
                exhaust_output_budget()
                return
            if len(line) > limit and not line.endswith(b"\n"):
                # Drain an oversized line without storing it or parsing a
                # truncated prefix as a readiness message.
                while line and not line.endswith(b"\n"):
                    if self._stop_event.is_set():
                        return
                    try:
                        line = stream.readline(limit + 1)
                    except (OSError, ValueError):
                        return
                    if not line:
                        return
                    if over_output_budget(len(line)):
                        exhaust_output_budget()
                        return
                continue
            if len(line) > limit:
                continue
            try:
                event = json.loads(line)
            except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
                continue
            if not isinstance(event, dict) or event.get("protocol") != _STATUS_PROTOCOL:
                continue
            event_name = event.get("event")
            if event_name not in {"ready", "degraded", "heartbeat"}:
                continue
            now = time.time_ns()
            with self._condition:
                state = self._state
                if (self._stop_event.is_set() or self._process is not proc
                        or state.phase == "quiescing"
                        or state.environment_incarnation != incarnation
                        or state.generation != generation or proc.poll() is not None):
                    return
                if event_name == "heartbeat":
                    self._set_state_locked(last_heartbeat_ns=now)
                    continue
                sensing = event.get("sensing_ready") is True
                input_eligible = event.get("input_eligible") is True
                reason = event.get("reason", "")
                if not isinstance(reason, str):
                    reason = ""
                if event_name == "degraded":
                    phase = "degraded"
                    reason = reason or "helper_reported_degraded"
                elif not sensing and not input_eligible:
                    phase = "degraded"
                    reason = reason or "surface_channels_not_ready"
                else:
                    phase = "ready"
                    reason = reason or "helper_ready"
                self._set_state_locked(
                    phase=phase,
                    sensing_ready=sensing,
                    input_eligible=input_eligible,
                    readiness_reason=reason[:512],
                    last_heartbeat_ns=now,
                )

    def _terminate_child(self, proc: subprocess.Popen[bytes]) -> bool:
        """Stop and reap only the direct ``Popen`` child owned by this instance.

        Closing stdin is the helper's graceful-quiesce signal. If it does not
        exit, termination escalates against this exact child handle only.
        """
        if proc.stdin is not None:
            try:
                proc.stdin.close()
            except (OSError, ValueError):
                pass
        if proc.poll() is None:
            try:
                proc.wait(timeout=self.config.budget.shutdown_timeout_s)
            except subprocess.TimeoutExpired:
                try:
                    proc.terminate()
                except OSError:
                    pass
                try:
                    proc.wait(timeout=self.config.budget.shutdown_timeout_s)
                except subprocess.TimeoutExpired:
                    try:
                        proc.kill()
                    except OSError:
                        pass
                    try:
                        proc.wait(timeout=self.config.budget.shutdown_timeout_s)
                    except subprocess.TimeoutExpired:
                        pass
        stopped = proc.poll() is not None
        with self._condition:
            if self._process is proc and stopped:
                self._process = None
            self._condition.notify_all()
        return stopped

    def _current_process(self) -> subprocess.Popen[bytes] | None:
        with self._condition:
            return self._process

    def _reserve_restart(self) -> bool:
        with self._condition:
            return self._reserve_restart_locked()

    def _reserve_restart_locked(self) -> bool:
        policy = self.config.restart_policy
        if not policy.enabled:
            return False
        self._prune_restart_times_locked()
        if len(self._restart_times) >= policy.max_restarts:
            return False
        self._restart_times.append(time.monotonic())
        self._refresh_restart_count_locked()
        return True

    def _has_restart_room(self) -> bool:
        with self._condition:
            if not self.config.restart_policy.enabled:
                return False
            self._prune_restart_times_locked()
            self._refresh_restart_count_locked()
            return len(self._restart_times) < self.config.restart_policy.max_restarts

    def _prune_restart_times_locked(self) -> None:
        cutoff = time.monotonic() - self.config.restart_policy.window_s
        while self._restart_times and self._restart_times[0] < cutoff:
            self._restart_times.popleft()

    def _refresh_restart_count_locked(self) -> None:
        self._prune_restart_times_locked()
        count = len(self._restart_times)
        if count != self._state.restarts_in_window:
            self._state = replace(
                self._state,
                restarts_in_window=count,
                updated_at_ns=time.time_ns(),
            )

    def _set_state_locked(self, **updates: Any) -> None:
        self._prune_restart_times_locked()
        self._state = replace(
            self._state,
            **updates,
            restarts_in_window=len(self._restart_times),
            updated_at_ns=time.time_ns(),
        )
        self._condition.notify_all()


def _windows_session_id(process_id: int) -> int:
    """Read a Windows process session ID without changing session ownership."""
    if os.name != "nt":
        raise OSError("Windows session ID is unavailable on this host")
    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    get_session = kernel32.ProcessIdToSessionId
    session_id = ctypes.c_uint32()
    get_session.argtypes = (ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32))
    get_session.restype = ctypes.c_int
    if not get_session(process_id, ctypes.byref(session_id)):
        raise ctypes.WinError(ctypes.get_last_error())
    return int(session_id.value)
