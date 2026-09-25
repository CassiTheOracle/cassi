#!/usr/bin/env python3
"""Keep Cassi's trading services alive: restart on exit or stale health, stop on request.

The supervisor owns process lifetime only.  Each service keeps its own data
authority (ingestion store, entity home); the supervisor records pids, exits,
restarts, and logs under its home directory.

    python run_cassi_trading_service.py --home H run       # foreground supervisor
    python run_cassi_trading_service.py --home H start     # background supervisor; clears STOP
    python run_cassi_trading_service.py --home H stop      # graceful stop; stays off until start
    python run_cassi_trading_service.py --home H status
    python run_cassi_trading_service.py --home H install   # Windows logon task, rechecked every 5 minutes

``H/services.json`` lists the services and is re-read whenever it changes.
Python services named by ``script`` stop gracefully: the supervisor creates
``H/run/<name>.stop`` and the child raises KeyboardInterrupt in its main
thread.  Services named by ``argv`` are terminated.

A service may declare ``stage``: before each start the supervisor copies a
settled build (files unchanged for ``settle_seconds``) into a private
directory, so the running child keeps its own executables while the build is
rebuilt, and ``rename`` gives copies image names that cleanup of the build's
processes cannot match.  A service may declare ``required_child``: once a
descendant with that image name has been seen, its disappearance restarts the
service.  A service may declare ``start_when``: it starts only once every
listed port accepts connections and at least ``available_ram_gb`` of memory is
free, so a heavy service waits for room on a shared machine and then starts
by itself.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import runpy
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import psutil

SERVICES_SCHEMA = "cassi.trading-services.v1"
STATUS_SCHEMA = "cassi.trading-service-status.v1"
DEFAULT_HOME = Path("E:/CassiData/outputs/CassiTrading/_service")
TASK_NAME = "Cassi Trading Service"
HEALTHY_AFTER_SECONDS = 600.0
BACKOFF_INITIAL_SECONDS = 5.0
BACKOFF_MAX_SECONDS = 300.0
LOGS_KEPT = 20
CHILD_CHECK_SECONDS = 15.0
START_RECHECK_SECONDS = 15.0
_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_NEW_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
_DETACHED = getattr(subprocess, "DETACHED_PROCESS", 0)
_BREAKAWAY = getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0)


def _stamp(value: float | None = None) -> str:
    moment = datetime.fromtimestamp(time.time() if value is None else value, tz=timezone.utc)
    return moment.isoformat(timespec="seconds").replace("+00:00", "Z")


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp",
    ) as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
    for attempt in range(5):
        try:
            os.replace(handle.name, path)
            return
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(0.1)


def _console_python() -> str:
    executable = Path(sys.executable)
    if executable.name.lower() == "pythonw.exe" and executable.with_name("python.exe").exists():
        return str(executable.with_name("python.exe"))
    return str(executable)


def _windowless_python() -> str:
    executable = Path(sys.executable)
    candidate = executable.with_name("pythonw.exe")
    return str(candidate if candidate.exists() else executable)


def _port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.5)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def _kill_tree(pid: int) -> None:
    try:
        root = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return
    for process in [*root.children(recursive=True), root]:
        try:
            process.kill()
        except psutil.NoSuchProcess:
            pass


def _same_file(source: Path, target: Path) -> bool:
    try:
        left, right = source.stat(), target.stat()
    except FileNotFoundError:
        return False
    return left.st_size == right.st_size and abs(left.st_mtime - right.st_mtime) < 1.0


def _writable(path: Path) -> bool:
    """A running executable or loaded library refuses a write open on Windows."""
    try:
        with open(path, "r+b"):
            return True
    except FileNotFoundError:
        return True
    except OSError:
        return False


def _descendant_names(pid: int) -> set[str]:
    names: set[str] = set()
    for child in psutil.Process(pid).children(recursive=True):
        try:
            names.add(child.name().lower())
        except psutil.Error:
            pass
    return names


@dataclass(frozen=True)
class StageSpec:
    source: str
    target: str
    files: tuple[str, ...]
    rename: tuple[tuple[str, str], ...]
    settle_seconds: float

    @classmethod
    def parse(cls, name: str, row: Any) -> "StageSpec":
        if not isinstance(row, Mapping):
            raise ValueError(f"{name}: stage must be an object")
        source, target = row.get("source"), row.get("target")
        for key, value in (("source", source), ("target", target)):
            if not isinstance(value, str) or not Path(value).is_absolute():
                raise ValueError(f"{name}: stage {key} must be an absolute path")
        files = row.get("files")
        if not isinstance(files, list) or not files or not all(isinstance(f, str) and f for f in files):
            raise ValueError(f"{name}: stage files must be a nonempty list of names or patterns")
        rename = row.get("rename", {})
        if not isinstance(rename, Mapping) or not all(
            isinstance(key, str) and isinstance(value, str) and value and Path(value).name == value
            for key, value in rename.items()
        ):
            raise ValueError(f"{name}: stage rename must map file names to file names")
        settle = row.get("settle_seconds", 120.0)
        if isinstance(settle, bool) or not isinstance(settle, (int, float)) or settle < 0:
            raise ValueError(f"{name}: stage settle_seconds must be nonnegative")
        return cls(
            source=source, target=target, files=tuple(files),
            rename=tuple(sorted(rename.items())), settle_seconds=float(settle),
        )

    def refresh(self, now: float) -> str:
        """Copy a settled, changed source as one set; otherwise keep the current copy."""
        source, target = Path(self.source), Path(self.target)
        found = sorted({path for pattern in self.files for path in source.glob(pattern) if path.is_file()})
        if not found:
            return f"stage kept: {source} has no matching files"
        newest = max(path.stat().st_mtime for path in found)
        if now - newest < self.settle_seconds:
            return f"stage kept: {source} changed {now - newest:.0f}s ago"
        names = dict(self.rename)
        changed = [
            (path, target / names.get(path.name, path.name))
            for path in found
            if not _same_file(path, target / names.get(path.name, path.name))
        ]
        if not changed:
            return "stage current"
        locked = [destination.name for _, destination in changed if not _writable(destination)]
        if locked:
            return f"stage kept: in use {', '.join(locked)}"
        target.mkdir(parents=True, exist_ok=True)
        staged: list[tuple[Path, Path]] = []
        try:
            for path, destination in changed:
                temporary = destination.with_name(destination.name + ".staging")
                shutil.copy2(path, temporary)
                staged.append((temporary, destination))
            for temporary, destination in staged:
                os.replace(temporary, destination)
        except OSError as exc:
            for temporary, _ in staged:
                temporary.unlink(missing_ok=True)
            return f"stage incomplete: {exc}"
        return f"staged {len(changed)} file(s) from {source}"


@dataclass(frozen=True)
class StartWhen:
    ports: tuple[int, ...]
    available_ram_gb: float | None

    @classmethod
    def parse(cls, name: str, row: Any) -> "StartWhen":
        if not isinstance(row, Mapping):
            raise ValueError(f"{name}: start_when must be an object")
        ports = row.get("ports", [])
        if not isinstance(ports, list) or not all(
            isinstance(port, int) and not isinstance(port, bool) and 0 < port < 65536 for port in ports
        ):
            raise ValueError(f"{name}: start_when ports must be TCP ports")
        ram = row.get("available_ram_gb")
        if ram is not None and (isinstance(ram, bool) or not isinstance(ram, (int, float)) or ram <= 0):
            raise ValueError(f"{name}: start_when available_ram_gb must be positive")
        return cls(ports=tuple(ports), available_ram_gb=None if ram is None else float(ram))

    def unmet(self) -> str | None:
        closed = [str(port) for port in self.ports if not _port_open(port)]
        if closed:
            return f"waiting for port {', '.join(closed)}"
        if self.available_ram_gb is not None:
            available = psutil.virtual_memory().available / 2**30
            if available < self.available_ram_gb:
                return f"waiting for {self.available_ram_gb:g} GB free RAM ({available:.1f} GB free)"
        return None


@dataclass(frozen=True)
class ServiceSpec:
    name: str
    command: tuple[str, ...]
    cwd: str
    env: tuple[tuple[str, str], ...]
    graceful: bool
    health_path: str | None
    stale_seconds: float
    stop_timeout_seconds: float
    external_port: int | None
    stage: StageSpec | None = None
    required_child: str | None = None
    start_when: StartWhen | None = None

    @classmethod
    def parse(cls, row: Any, home: Path) -> "ServiceSpec":
        if not isinstance(row, Mapping):
            raise ValueError("each service must be an object")
        name = row.get("name")
        if not isinstance(name, str) or not _NAME.match(name):
            raise ValueError(f"service name {name!r} must match {_NAME.pattern}")
        cwd = row.get("cwd")
        if not isinstance(cwd, str) or not Path(cwd).is_absolute() or not Path(cwd).is_dir():
            raise ValueError(f"{name}: cwd must be an existing absolute directory")
        env = row.get("env", {})
        if not isinstance(env, Mapping) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in env.items()
        ):
            raise ValueError(f"{name}: env must map text to text")
        script, argv = row.get("script"), row.get("argv")
        if (script is None) == (argv is None):
            raise ValueError(f"{name}: give exactly one of script or argv")
        if script is not None:
            args = row.get("args", [])
            if not isinstance(script, str) or not isinstance(args, list) or not all(isinstance(a, str) for a in args):
                raise ValueError(f"{name}: script must be text and args a list of text")
            path = Path(script) if Path(script).is_absolute() else Path(cwd) / script
            if not path.is_file():
                raise ValueError(f"{name}: script {path} does not exist")
            command = (
                _console_python(), str(Path(__file__).resolve()), "--home", str(home),
                "child", "--stop-file", str(home / "run" / f"{name}.stop"), "--", str(path.resolve()), *args,
            )
        else:
            if not isinstance(argv, list) or not argv or not all(isinstance(a, str) for a in argv):
                raise ValueError(f"{name}: argv must be a nonempty list of text")
            command = tuple(argv)
        health_path = row.get("health_path")
        if health_path is not None and not isinstance(health_path, str):
            raise ValueError(f"{name}: health_path must be text")
        numbers = {}
        for key, default in (("stale_seconds", 300.0), ("stop_timeout_seconds", 30.0)):
            value = row.get(key, default)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                raise ValueError(f"{name}: {key} must be positive")
            numbers[key] = float(value)
        port = row.get("external_port")
        if port is not None and (isinstance(port, bool) or not isinstance(port, int) or not 0 < port < 65536):
            raise ValueError(f"{name}: external_port must be a TCP port")
        stage = row.get("stage")
        start_when = row.get("start_when")
        required_child = row.get("required_child")
        if required_child is not None and (not isinstance(required_child, str) or not required_child):
            raise ValueError(f"{name}: required_child must be a process image name")
        return cls(
            name=name,
            command=command,
            cwd=cwd,
            env=tuple(sorted(env.items())),
            graceful=script is not None,
            health_path=health_path,
            stale_seconds=numbers["stale_seconds"],
            stop_timeout_seconds=numbers["stop_timeout_seconds"],
            external_port=port,
            stage=None if stage is None else StageSpec.parse(name, stage),
            required_child=required_child,
            start_when=None if start_when is None else StartWhen.parse(name, start_when),
        )


@dataclass
class ServiceRuntime:
    spec: ServiceSpec
    process: subprocess.Popen | None = None
    create_time: float | None = None
    started_at: float | None = None
    log_path: str | None = None
    restarts: int = 0
    failures: int = 0
    next_start: float = 0.0
    last_exit_code: int | None = None
    last_exit_at: float | None = None
    last_reason: str | None = None
    stopping_since: float | None = None
    pending_spec: ServiceSpec | None = None
    removing: bool = False
    external: bool = False
    child_seen: bool = False
    child_checked_at: float = 0.0


class Supervisor:
    def __init__(self, home: Path) -> None:
        self.home = home
        self.services_path = home / "services.json"
        self.status_path = home / "status.json"
        self.stop_path = home / "STOP"
        self.runtimes: dict[str, ServiceRuntime] = {}
        self.config_error: str | None = None
        self.started = time.time()
        self._services_mtime: int | None = None
        self._last_status = 0.0

    # configuration -----------------------------------------------------
    def load_specs(self) -> dict[str, ServiceSpec] | None:
        try:
            mtime = self.services_path.stat().st_mtime_ns
        except FileNotFoundError:
            self.config_error = f"{self.services_path} is missing"
            return None
        if mtime == self._services_mtime:
            return None
        self._services_mtime = mtime
        try:
            document = json.loads(self.services_path.read_text(encoding="utf-8"))
            if not isinstance(document, Mapping) or document.get("schema") != SERVICES_SCHEMA:
                raise ValueError(f"services.json must declare schema {SERVICES_SCHEMA}")
            rows = document.get("services")
            if not isinstance(rows, list):
                raise ValueError("services.json needs a services list")
            specs: dict[str, ServiceSpec] = {}
            for row in rows:
                if isinstance(row, Mapping) and row.get("enabled", True) is False:
                    continue
                spec = ServiceSpec.parse(row, self.home)
                if spec.name in specs:
                    raise ValueError(f"service {spec.name} is declared twice")
                specs[spec.name] = spec
        except (OSError, ValueError) as exc:
            self.config_error = str(exc)
            return None
        self.config_error = None
        return specs

    def apply(self, specs: Mapping[str, ServiceSpec], now: float) -> None:
        for name, runtime in list(self.runtimes.items()):
            if name not in specs:
                runtime.removing = True
                if runtime.process is None:
                    del self.runtimes[name]
                else:
                    self.begin_stop(runtime, now, "removed")
        for name, spec in specs.items():
            runtime = self.runtimes.get(name)
            if runtime is None:
                self.runtimes[name] = ServiceRuntime(spec=spec, next_start=now)
            elif runtime.spec != spec:
                runtime.removing = False
                if runtime.process is None:
                    runtime.spec, runtime.next_start, runtime.failures = spec, now, 0
                else:
                    runtime.pending_spec = spec
                    self.begin_stop(runtime, now, "configuration-changed")

    # process lifetime --------------------------------------------------
    def start(self, runtime: ServiceRuntime, now: float) -> None:
        spec = runtime.spec
        if spec.external_port is not None and _port_open(spec.external_port):
            runtime.external = True
            runtime.next_start = now + 30.0
            return
        runtime.external = False
        if spec.start_when is not None:
            unmet = spec.start_when.unmet()
            if unmet is not None:
                runtime.last_reason = unmet
                runtime.next_start = now + START_RECHECK_SECONDS
                return
        stop_file = self.home / "run" / f"{spec.name}.stop"
        stop_file.parent.mkdir(parents=True, exist_ok=True)
        stop_file.unlink(missing_ok=True)
        log_dir = self.home / "logs" / spec.name
        log_dir.mkdir(parents=True, exist_ok=True)
        for old in sorted(log_dir.glob("*.log"))[:-(LOGS_KEPT - 1)]:
            old.unlink(missing_ok=True)
        log_path = log_dir / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.log"
        env = {**os.environ, **dict(spec.env), "PYTHONUNBUFFERED": "1", "CASSI_SERVICE_NAME": spec.name}
        with open(log_path, "ab") as log:
            if spec.stage is not None:
                log.write(f"[{_stamp()}] supervisor {spec.stage.refresh(now)}\n".encode("utf-8"))
            log.write(f"[{_stamp()}] supervisor start: {' '.join(spec.command)}\n".encode("utf-8"))
            log.flush()
            try:
                process = subprocess.Popen(
                    spec.command, cwd=spec.cwd, env=env, stdin=subprocess.DEVNULL,
                    stdout=log, stderr=subprocess.STDOUT, creationflags=_NO_WINDOW | _NEW_GROUP,
                )
            except OSError as exc:
                log.write(f"[{_stamp()}] supervisor could not start: {exc}\n".encode("utf-8"))
                self._record_failure(runtime, now, None, f"start failed: {exc}")
                return
        runtime.process = process
        runtime.started_at = now
        runtime.log_path = str(log_path)
        runtime.stopping_since = None
        runtime.child_seen = False
        runtime.child_checked_at = now
        try:
            runtime.create_time = psutil.Process(process.pid).create_time()
        except psutil.NoSuchProcess:
            runtime.create_time = None

    def begin_stop(self, runtime: ServiceRuntime, now: float, reason: str) -> None:
        if runtime.process is None or runtime.stopping_since is not None:
            return
        runtime.stopping_since = now
        runtime.last_reason = reason
        if runtime.spec.graceful:
            stop_file = self.home / "run" / f"{runtime.spec.name}.stop"
            stop_file.parent.mkdir(parents=True, exist_ok=True)
            stop_file.write_text(reason + "\n", encoding="utf-8")
        else:
            runtime.process.terminate()

    def _record_failure(self, runtime: ServiceRuntime, now: float, code: int | None, reason: str) -> None:
        if runtime.started_at is not None and now - runtime.started_at >= HEALTHY_AFTER_SECONDS:
            runtime.failures = 0
        runtime.failures += 1
        runtime.restarts += 1
        runtime.last_exit_code = code
        runtime.last_exit_at = now
        runtime.last_reason = reason
        runtime.next_start = now + min(
            BACKOFF_MAX_SECONDS, BACKOFF_INITIAL_SECONDS * 2 ** (runtime.failures - 1),
        )

    def _health_age(self, runtime: ServiceRuntime, now: float) -> float | None:
        if runtime.spec.health_path is None:
            return None
        try:
            return max(0.0, now - Path(runtime.spec.health_path).stat().st_mtime)
        except FileNotFoundError:
            return None

    def _check_child(self, runtime: ServiceRuntime, now: float) -> None:
        image = runtime.spec.required_child
        if image is None or runtime.process is None or now - runtime.child_checked_at < CHILD_CHECK_SECONDS:
            return
        runtime.child_checked_at = now
        try:
            names = _descendant_names(runtime.process.pid)
        except psutil.Error:
            return
        if image.lower() in names:
            runtime.child_seen = True
        elif runtime.child_seen:
            self.begin_stop(runtime, now, f"lost child {image}")

    def tick(self, now: float) -> None:
        for name, runtime in list(self.runtimes.items()):
            process = runtime.process
            if process is not None:
                code = process.poll()
                if code is None:
                    if runtime.stopping_since is not None:
                        if now - runtime.stopping_since > runtime.spec.stop_timeout_seconds:
                            _kill_tree(process.pid)
                        continue
                    if (
                        runtime.spec.health_path is not None
                        and runtime.started_at is not None
                        and now - runtime.started_at > runtime.spec.stale_seconds
                    ):
                        age = self._health_age(runtime, now)
                        if age is None or age > runtime.spec.stale_seconds:
                            self.begin_stop(runtime, now, "stale-health")
                    if runtime.stopping_since is None:
                        self._check_child(runtime, now)
                    continue
                stopping_reason = runtime.last_reason if runtime.stopping_since is not None else None
                runtime.process = None
                runtime.stopping_since = None
                if runtime.removing:
                    del self.runtimes[name]
                    continue
                if runtime.pending_spec is not None:
                    runtime.spec, runtime.pending_spec = runtime.pending_spec, None
                    runtime.last_exit_code, runtime.last_exit_at = code, now
                    runtime.failures, runtime.next_start = 0, now
                    continue
                self._record_failure(runtime, now, code, stopping_reason or f"exited with code {code}")
            if runtime.process is None and not runtime.removing and now >= runtime.next_start:
                self.start(runtime, now)

    def stop_all(self, reason: str) -> None:
        now = time.time()
        for runtime in self.runtimes.values():
            self.begin_stop(runtime, now, reason)
        while any(runtime.process is not None for runtime in self.runtimes.values()):
            now = time.time()
            for runtime in self.runtimes.values():
                process = runtime.process
                if process is None:
                    continue
                if process.poll() is not None:
                    runtime.last_exit_code, runtime.last_exit_at = process.returncode, now
                    runtime.process = None
                elif now - (runtime.stopping_since or now) > runtime.spec.stop_timeout_seconds:
                    _kill_tree(process.pid)
            self.write_status(now, force=True, stopping=True)
            time.sleep(0.5)

    def adopt_orphans(self) -> None:
        """Stop children left behind by a supervisor that died without stopping them."""
        try:
            previous = json.loads(self.status_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        services = previous.get("services") if isinstance(previous, Mapping) else None
        if not isinstance(services, Mapping):
            return
        orphans: list[tuple[str, psutil.Process, float]] = []
        for name, row in services.items():
            if not isinstance(row, Mapping) or not isinstance(row.get("pid"), int) or row.get("create_time") is None:
                continue
            try:
                process = psutil.Process(row["pid"])
                if abs(process.create_time() - float(row["create_time"])) > 0.01:
                    continue
            except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError, TypeError):
                continue
            stop_file = self.home / "run" / f"{name}.stop"
            stop_file.parent.mkdir(parents=True, exist_ok=True)
            stop_file.write_text("supervisor-restart\n", encoding="utf-8")
            orphans.append((name, process, time.time() + float(row.get("stop_timeout_seconds") or 30.0)))
        for name, process, deadline in orphans:
            try:
                process.wait(timeout=max(0.0, deadline - time.time()))
            except psutil.TimeoutExpired:
                _kill_tree(process.pid)
            except psutil.NoSuchProcess:
                pass
            print(f"[{_stamp()}] stopped orphaned {name} pid {process.pid}", flush=True)

    # reporting ---------------------------------------------------------
    def write_status(self, now: float, *, force: bool = False, stopping: bool = False) -> None:
        if not force and now - self._last_status < 2.0:
            return
        self._last_status = now
        services: dict[str, Any] = {}
        for name, runtime in sorted(self.runtimes.items()):
            if runtime.process is not None:
                state = "stopping" if runtime.stopping_since is not None else "running"
            elif runtime.external:
                state = "external"
            else:
                state = "stopped" if stopping else "waiting"
            health_age = self._health_age(runtime, now)
            services[name] = {
                "state": state,
                "pid": None if runtime.process is None else runtime.process.pid,
                "create_time": None if runtime.process is None else runtime.create_time,
                "started_at": None if runtime.started_at is None or runtime.process is None else _stamp(runtime.started_at),
                "restarts": runtime.restarts,
                "consecutive_failures": runtime.failures,
                "last_exit_code": runtime.last_exit_code,
                "last_exit_at": None if runtime.last_exit_at is None else _stamp(runtime.last_exit_at),
                "last_reason": runtime.last_reason,
                "next_start_at": None if runtime.process is not None else _stamp(runtime.next_start),
                "log": runtime.log_path,
                "health_age_seconds": None if health_age is None else round(health_age, 1),
                "stop_timeout_seconds": runtime.spec.stop_timeout_seconds,
                "required_child_seen": None if runtime.spec.required_child is None else runtime.child_seen,
            }
        _write_json(self.status_path, {
            "schema": STATUS_SCHEMA,
            "updated_at": _stamp(now),
            "supervisor": {
                "pid": os.getpid(),
                "started_at": _stamp(self.started),
                "state": "stopping" if stopping else "running",
                "config_error": self.config_error,
            },
            "services": services,
        })

    def run(self) -> int:
        self.adopt_orphans()
        try:
            while not self.stop_path.exists():
                now = time.time()
                specs = self.load_specs()
                if specs is not None:
                    self.apply(specs, now)
                self.tick(now)
                self.write_status(now)
                time.sleep(1.0)
            reason = "operator-stop"
        except KeyboardInterrupt:
            reason = "supervisor-interrupted"
        self.stop_all(reason)
        self.write_status(time.time(), force=True, stopping=True)
        return 0


class _Lock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.handle: Any = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(self.path, "a+b")
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            return False
        self.handle = handle
        return True

    def release(self) -> None:
        """Unlock before closing: Windows frees a lock left on a closed handle only later."""
        if self.handle is not None:
            try:
                self.handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
            self.handle.close()
            self.handle = None


def _supervisor_alive(home: Path) -> bool:
    probe = _Lock(home / "supervisor.lock")
    if probe.acquire():
        probe.release()
        return False
    return True


def _acquire(lock: _Lock, patience: float) -> bool:
    """Status probes hold the lock for an instant; only a live supervisor holds it longer."""
    deadline = time.time() + patience
    while not lock.acquire():
        if time.time() > deadline:
            return False
        time.sleep(0.2)
    return True


def _await_supervisor(home: Path, since: float, timeout: float) -> bool:
    """True once a supervisor started at or after ``since`` is reporting status."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            supervisor = json.loads((home / "status.json").read_text(encoding="utf-8"))["supervisor"]
            started = datetime.fromisoformat(supervisor["started_at"].replace("Z", "+00:00")).timestamp()
            if started >= since - 1.0 and psutil.pid_exists(int(supervisor["pid"])):
                return True
        except (OSError, ValueError, TypeError, KeyError):
            pass
        time.sleep(0.5)
    return False


def _child(stop_file: Path, command: list[str]) -> None:
    """Run a Python service script in this process; its stop file raises KeyboardInterrupt."""
    import _thread

    if not command:
        raise SystemExit("child needs a script")
    script = Path(command[0]).resolve()

    def watch() -> None:
        while not stop_file.exists():
            time.sleep(0.5)
        _thread.interrupt_main()

    threading.Thread(target=watch, name="cassi-service-stop", daemon=True).start()
    sys.argv = [str(script), *command[1:]]
    sys.path[0] = str(script.parent)
    runpy.run_path(str(script), run_name="__main__")


def _task_installed() -> bool:
    if os.name != "nt":
        return False
    result = subprocess.run(
        ["schtasks", "/Query", "/TN", TASK_NAME], capture_output=True, text=True, creationflags=_NO_WINDOW,
    )
    return result.returncode == 0


def _start(home: Path) -> int:
    (home / "STOP").unlink(missing_ok=True)
    if _supervisor_alive(home):
        print("supervisor already running")
        return 0
    if _task_installed():
        for _ in range(3):
            requested = time.time()
            subprocess.run(["schtasks", "/Run", "/TN", TASK_NAME], check=True, creationflags=_NO_WINDOW)
            if _await_supervisor(home, requested, 30.0):
                print(f"started scheduled task {TASK_NAME!r}")
                return 0
        print(f"scheduled task {TASK_NAME!r} did not bring the supervisor up; starting it detached")
    command = [_windowless_python(), str(Path(__file__).resolve()), "--home", str(home), "run"]
    options: dict[str, Any] = {
        "cwd": str(Path(__file__).resolve().parent), "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "close_fds": True,
    }
    requested = time.time()
    try:
        subprocess.Popen(command, creationflags=_DETACHED | _NEW_GROUP | _BREAKAWAY, **options)
    except OSError:
        subprocess.Popen(command, creationflags=_DETACHED | _NEW_GROUP, **options)
    if _await_supervisor(home, requested, 30.0):
        print("started detached supervisor")
        return 0
    print("supervisor did not start")
    return 1


def _stop(home: Path, timeout: float) -> int:
    (home / "STOP").write_text(f"{_stamp()}\n", encoding="utf-8")
    deadline = time.time() + timeout
    while _supervisor_alive(home):
        if time.time() > deadline:
            print("supervisor still stopping; STOP remains in place")
            return 1
        time.sleep(1.0)
    print("supervisor stopped; run start to resume")
    return 0


def _status(home: Path) -> int:
    alive = _supervisor_alive(home)
    try:
        status = json.loads((home / "status.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        status = None
    stopped = (home / "STOP").exists()
    print(f"supervisor: {'running' if alive else 'not running'}{' (STOP set)' if stopped else ''}")
    if not isinstance(status, Mapping):
        return 0 if alive else 1
    supervisor = status.get("supervisor") or {}
    if supervisor.get("config_error"):
        print(f"configuration error: {supervisor['config_error']}")
    print(f"status updated {status.get('updated_at')}")
    for name, row in (status.get("services") or {}).items():
        age = row.get("health_age_seconds")
        print(
            f"  {name:<14} {row.get('state'):<9} pid={row.get('pid')} restarts={row.get('restarts')} "
            f"health_age={age if age is not None else '-'} last={row.get('last_reason')}"
        )
    return 0 if alive else 1


def _install(home: Path) -> int:
    if os.name != "nt":
        raise SystemExit("install registers a Windows scheduled task")
    script = Path(__file__).resolve()
    arguments = f'"{script}" --home "{home}" run'.replace("'", "''")
    command = f"""
$action = New-ScheduledTaskAction -Execute '{_windowless_python()}' -Argument '{arguments}' -WorkingDirectory '{script.parent}'
$logon = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\\$env:USERNAME"
$recheck = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5)
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName '{TASK_NAME}' -Action $action -Trigger @($logon, $recheck) -Settings $settings `
    -Description 'Keeps Cassi market feeds and trading research services running.' -Force | Out-Null
"""
    subprocess.run(["powershell", "-NoProfile", "-Command", command], check=True)
    print(f"installed scheduled task {TASK_NAME!r}: at logon and every 5 minutes")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--home", type=Path, default=DEFAULT_HOME)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("run")
    commands.add_parser("start")
    stop = commands.add_parser("stop")
    stop.add_argument("--timeout", type=float, default=180.0)
    commands.add_parser("status")
    commands.add_parser("install")
    child = commands.add_parser("child")
    child.add_argument("--stop-file", type=Path, required=True)
    child.add_argument("service", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    home = args.home.resolve()
    if args.command == "child":
        service = args.service[1:] if args.service[:1] == ["--"] else args.service
        _child(args.stop_file, service)
        return 0
    if args.command == "start":
        return _start(home)
    if args.command == "stop":
        return _stop(home, args.timeout)
    if args.command == "status":
        return _status(home)
    if args.command == "install":
        return _install(home)
    if (home / "STOP").exists():
        print("supervisor is stopped by operator; run start to resume")
        return 0
    lock = _Lock(home / "supervisor.lock")
    if not _acquire(lock, 3.0):
        print("supervisor already running")
        return 0
    try:
        return Supervisor(home).run()
    finally:
        lock.release()


if __name__ == "__main__":
    raise SystemExit(main())
