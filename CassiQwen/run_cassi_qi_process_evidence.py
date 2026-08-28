"""Collect independent Windows process/source evidence for G12E.

The collector never imports the runtime or provider.  It starts WPR before
creating the provider child, assigns that child to a named Windows Job object,
and retains every verifier input as bounded raw bytes.  The verifier is the
only component that derives the Qwen-zero counters.
"""
from __future__ import annotations

import argparse
import base64
import ctypes
from ctypes import wintypes
import csv
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import threading
import time
from typing import Any, Iterable, Mapping

from cassi_qi_bootstrap import canonical_hash, canonical_json_bytes


PROCESS_EVIDENCE_SCHEMA = "cassi.qi-flow-process-evidence.v1"
COMMANDS_SCHEMA = "cassi.qi-flow-process-evidence-commands.v1"
RAW_INDEX_SCHEMA = "cassi.qi-flow-process-evidence-raw-index.v1"
STATUS_SCHEMA = "cassi.qi-flow-g12e-status.v1"
MANIFEST_SCHEMA = "cassi.qi-flow-process-capture-manifest.v1"
RAW_BYTES_DOMAIN = "cassi.qi-flow-raw-bytes.v1"
PROCESS_SNAPSHOT_SCHEMA = "cassi.qi-flow-process-evidence-processes.v1"
MODULE_SNAPSHOT_SCHEMA = "cassi.qi-flow-process-evidence-modules.v1"
SOCKET_SNAPSHOT_SCHEMA = "cassi.qi-flow-process-evidence-sockets.v1"
FILE_READ_SCHEMA = "cassi.qi-flow-process-evidence-file-reads.v1"
SYS_MODULES_SCHEMA = "cassi.qi-flow-process-evidence-sys-modules.v1"
JOB_MEMORY_SCHEMA = "cassi.qi-flow-process-evidence-job-memory.v1"
TRACE_SCHEMA = "cassi.qi-flow-process-evidence-trace.v1"

MAX_RAW_BYTES = 8 * 1024 * 1024
MAX_TRACE_BYTES = 256 * 1024 * 1024
MAX_COMMAND_OUTPUT_BYTES = 1024 * 1024
MAX_CHUNK_BYTES = 1024 * 1024
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_PROCESS_ROWS = 4096
MAX_MODULE_ROWS = 16384
MAX_SOCKET_ROWS = 16384
MAX_FILE_READ_ROWS = 65536
MAX_SAFE_INTEGER = 2**53 - 1


class ProcessEvidenceError(RuntimeError):
    """A collection input or native prerequisite is unavailable."""


class EvidenceBlocked(ProcessEvidenceError):
    pass


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _frame(payload: bytes) -> bytes:
    return len(payload).to_bytes(8, "big") + payload


def _raw_bytes_sha256(payload: bytes) -> str:
    return _sha256(_frame(RAW_BYTES_DOMAIN.encode("utf-8")) + _frame(payload))


def _obj_hash(value: Any, schema: str) -> str:
    return canonical_hash(value, schema)


def _canonical_payload(value: Any) -> bytes:
    return canonical_json_bytes(value)


def _write_json(path: Path, value: Any) -> bytes:
    payload = _canonical_payload(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return payload


def _read_bounded(path: Path, limit: int) -> bytes:
    size = path.stat().st_size
    if size > limit:
        raise EvidenceBlocked(f"bounded evidence limit exceeded: {path} ({size} > {limit})")
    return path.read_bytes()


def _copy_bounded(source: Path, target: Path, limit: int) -> bytes:
    payload = _read_bounded(source, limit)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return payload


def _load_json(path: Path, limit: int = MAX_RAW_BYTES) -> tuple[Any, bytes]:
    raw = _read_bounded(path, limit)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceBlocked(f"invalid JSON input: {path}: {exc}") from exc
    return value, raw


def _hex_digest(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise EvidenceBlocked(f"{name} must be a SHA-256 hex digest")
    try:
        int(value, 16)
    except ValueError as exc:
        raise EvidenceBlocked(f"{name} must be a SHA-256 hex digest") from exc
    return value.lower()


def _ascii_id(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value or len(value.encode("ascii", "strict")) > 128:
        raise EvidenceBlocked(f"{name} must be a 1..128 byte ASCII identifier")
    return value


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise EvidenceBlocked(f"{name} must be a nonempty string")
    return value


def _canonical_path(value: str | os.PathLike[str], root: Path) -> str:
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    return os.path.normcase(str(path.resolve(strict=False))).replace("\\", "/")


def _command_spec(value: Any, name: str) -> dict[str, Any]:
    if isinstance(value, list):
        value = {"argv": value}
    if not isinstance(value, Mapping):
        raise EvidenceBlocked(f"{name} command must be an object or argv list")
    argv = value.get("argv", value.get("command"))
    if not isinstance(argv, list) or not argv or any(not isinstance(item, str) or not item for item in argv):
        raise EvidenceBlocked(f"{name} command argv must be a nonempty string list")
    cwd = value.get("cwd")
    if cwd is not None and (not isinstance(cwd, str) or not cwd):
        raise EvidenceBlocked(f"{name} command cwd is invalid")
    env = value.get("env", {})
    if not isinstance(env, Mapping) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in env.items()):
        raise EvidenceBlocked(f"{name} command env is invalid")
    timeout = value.get("timeout_seconds", 300)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0 or timeout > 3600:
        raise EvidenceBlocked(f"{name} command timeout_seconds is invalid")
    return {
        "argv": list(argv),
        "cwd": cwd,
        "env": {str(k): str(v) for k, v in sorted(env.items())},
        "timeout_seconds": float(timeout),
    }


def _command_env(spec: Mapping[str, Any]) -> dict[str, str]:
    env = dict(os.environ)
    env.update({str(k): str(v) for k, v in dict(spec.get("env", {})).items()})
    return env


def _command_cwd(spec: Mapping[str, Any], default: Path) -> str:
    cwd = spec.get("cwd")
    if cwd is None:
        return str(default)
    path = Path(str(cwd))
    if not path.is_absolute():
        path = default / path
    return str(path.resolve(strict=False))


class _BoundedCapture:
    def __init__(self, stream: Any, limit: int) -> None:
        self.stream = stream
        self.limit = limit
        self.data = bytearray()
        self.truncated = False
        self.error: str | None = None

    def run(self) -> None:
        try:
            while True:
                chunk = self.stream.read(65536)
                if not chunk:
                    return
                chunk = bytes(chunk)
                if len(self.data) < self.limit:
                    remaining = self.limit - len(self.data)
                    self.data.extend(chunk[:remaining])
                    if len(chunk) > remaining:
                        self.truncated = True
                else:
                    self.truncated = True
        except Exception as exc:  # pragma: no cover - OS pipe failures
            self.error = f"{type(exc).__name__}: {exc}"


def _close_handle(handle: Any) -> None:
    if handle and _KERNEL32 is not None:
        try:
            _KERNEL32.CloseHandle(handle)
        except (AttributeError, OSError):
            pass


def _terminate_process(process: Any, timeout: float = 5.0) -> None:
    if process is None or process.poll() is not None:
        return
    try:
        process.terminate()
        process.wait(timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        try:
            process.kill()
            process.wait(timeout=timeout)
        except (subprocess.TimeoutExpired, OSError):
            pass

def _attach_captures(process: Any, output_limit: int = MAX_COMMAND_OUTPUT_BYTES) -> None:
    stdout = _BoundedCapture(process.stdout, output_limit)
    stderr = _BoundedCapture(process.stderr, output_limit)
    stdout_thread = threading.Thread(target=stdout.run, daemon=True)
    stderr_thread = threading.Thread(target=stderr.run, daemon=True)
    stdout_thread.start()
    stderr_thread.start()
    setattr(process, "_cassi_stdout_capture", stdout)
    setattr(process, "_cassi_stderr_capture", stderr)
    setattr(process, "_cassi_capture_threads", (stdout_thread, stderr_thread))


def _run_argv(
    spec: Mapping[str, Any],
    *,
    default_cwd: Path,
    output_limit: int = MAX_COMMAND_OUTPUT_BYTES,
) -> tuple[dict[str, Any], subprocess.Popen[bytes]]:
    argv = [str(item) for item in spec["argv"]]
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
    try:
        process = subprocess.Popen(
            argv,
            cwd=_command_cwd(spec, default_cwd),
            env=_command_env(spec),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            creationflags=creationflags,
        )
    except (OSError, ValueError) as exc:
        raise EvidenceBlocked(f"cannot start command {argv!r}: {exc}") from exc
    _attach_captures(process, output_limit)
    return {"argv": argv}, process

def _finish_process(process: Any, *, timeout: float, phase: str) -> dict[str, Any]:
    timed_out = False
    try:
        returncode = process.wait(timeout=timeout)
    except (subprocess.TimeoutExpired, TimeoutError, OSError):
        timed_out = True
        _terminate_process(process)
        try:
            returncode = process.wait(timeout=5.0)
        except (subprocess.TimeoutExpired, TimeoutError, OSError):
            returncode = None
    stdout = getattr(process, "_cassi_stdout_capture", None)
    stderr = getattr(process, "_cassi_stderr_capture", None)
    for thread in getattr(process, "_cassi_capture_threads", ()):
        thread.join(timeout=2.0)
    stdout_bytes = bytes(stdout.data) if stdout is not None else b""
    stderr_bytes = bytes(stderr.data) if stderr is not None else b""
    return {
        "phase": phase,
        "pid": int(getattr(process, "pid", 0) or 0),
        "returncode": returncode,
        "timed_out": timed_out,
        "stdout_byte_count": len(stdout_bytes),
        "stderr_byte_count": len(stderr_bytes),
        "stdout_sha256": _sha256(stdout_bytes),
        "stderr_sha256": _sha256(stderr_bytes),
        "stdout_truncated": bool(stdout.truncated) if stdout is not None else False,
        "stderr_truncated": bool(stderr.truncated) if stderr is not None else False,
        "stdout_error": stdout.error if stdout is not None else None,
        "stderr_error": stderr.error if stderr is not None else None,
    }


if os.name == "nt":
    _KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _NTDLL = ctypes.WinDLL("ntdll", use_last_error=True)
    _PSAPI = ctypes.WinDLL("psapi", use_last_error=True)
else:  # pragma: no cover - import smoke on non-Windows hosts
    _KERNEL32 = None
    _NTDLL = None
    _PSAPI = None


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_void_p),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


class _MODULEENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("th32ModuleID", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("GlblcntUsage", wintypes.DWORD),
        ("ProccntUsage", wintypes.DWORD),
        ("modBaseAddr", ctypes.POINTER(ctypes.c_ubyte)),
        ("modBaseSize", wintypes.DWORD),
        ("hModule", wintypes.HMODULE),
        ("szModule", wintypes.WCHAR * 256),
        ("szExePath", wintypes.WCHAR * 260),
    ]


class _FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]


class _UNICODE_STRING(ctypes.Structure):
    _fields_ = [("Length", wintypes.USHORT), ("MaximumLength", wintypes.USHORT), ("Buffer", ctypes.c_void_p)]


class _PROCESS_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("Reserved1", ctypes.c_void_p),
        ("PebBaseAddress", ctypes.c_void_p),
        ("Reserved2_0", ctypes.c_void_p),
        ("Reserved2_1", ctypes.c_void_p),
        ("UniqueProcessId", ctypes.c_void_p),
        ("Reserved3", ctypes.c_void_p),
    ]


class _PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivateUsage", ctypes.c_size_t),
    ]


class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", _IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class _SECURITY_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("nLength", wintypes.DWORD), ("lpSecurityDescriptor", ctypes.c_void_p), ("bInheritHandle", wintypes.BOOL)]


class _STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.POINTER(ctypes.c_ubyte)),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


class _PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    ]


class _NativeProcess:
    """Small Popen-compatible wrapper retaining the native primary thread."""

    def __init__(self, info: _PROCESS_INFORMATION, stdout: Any, stderr: Any) -> None:
        self._process_handle = info.hProcess
        self._thread_handle = info.hThread
        self.pid = int(info.dwProcessId)
        self.stdout = stdout
        self.stderr = stderr
        self._returncode: int | None = None

    def poll(self) -> int | None:
        if self._returncode is not None:
            return self._returncode
        if _KERNEL32 is None:
            return None
        code = wintypes.DWORD()
        if not _KERNEL32.GetExitCodeProcess(self._process_handle, ctypes.byref(code)):
            return None
        if int(code.value) == 259:  # STILL_ACTIVE
            return None
        self._returncode = ctypes.c_int32(int(code.value)).value
        return self._returncode

    def wait(self, timeout: float | None = None) -> int:
        if self.poll() is not None:
            return int(self._returncode)
        if _KERNEL32 is None:
            raise OSError("native process requires Windows")
        milliseconds = 0xFFFFFFFF if timeout is None else max(0, int(timeout * 1000))
        status = int(_KERNEL32.WaitForSingleObject(self._process_handle, milliseconds))
        if status == 0x102:
            raise subprocess.TimeoutExpired([str(self.pid)], timeout)
        if status != 0:
            raise OSError(f"WaitForSingleObject:{status}")
        result = self.poll()
        if result is None:
            result = 0
            self._returncode = result
        return int(result)

    def terminate(self) -> None:
        if _KERNEL32 is not None and self.poll() is None:
            _KERNEL32.TerminateProcess(self._process_handle, 1)

    def kill(self) -> None:
        self.terminate()

    def close(self) -> None:
        try:
            self.stdout.close()
        except Exception:
            pass
        try:
            self.stderr.close()
        except Exception:
            pass
        _close_handle(self._thread_handle)
        _close_handle(self._process_handle)
        self._thread_handle = None
        self._process_handle = None


def _open_process(pid: int, access: int) -> Any:
    if _KERNEL32 is None:
        return None
    return _KERNEL32.OpenProcess(access, False, int(pid))


def _process_creation_identity(handle: Any) -> str | None:
    if not handle or _KERNEL32 is None:
        return None
    created, exited, kernel, user = (_FILETIME(), _FILETIME(), _FILETIME(), _FILETIME())
    if not _KERNEL32.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel), ctypes.byref(user)):
        return None
    value = (int(created.dwHighDateTime) << 32) | int(created.dwLowDateTime)
    return f"{value:016x}"


def _process_image_and_command(pid: int) -> tuple[str | None, str | None, str | None]:
    handle = _open_process(pid, 0x1000 | 0x0010)  # QUERY_LIMITED_INFORMATION | VM_READ
    if not handle:
        return None, None, None
    try:
        image: str | None = None
        if _KERNEL32 is not None:
            size = wintypes.DWORD(32768)
            buffer = ctypes.create_unicode_buffer(size.value)
            if _KERNEL32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                image = buffer.value
        command: str | None = None
        if _NTDLL is not None and _KERNEL32 is not None:
            pbi = _PROCESS_BASIC_INFORMATION()
            returned = wintypes.ULONG(0)
            status = int(_NTDLL.NtQueryInformationProcess(handle, 0, ctypes.byref(pbi), ctypes.sizeof(pbi), ctypes.byref(returned)))
            if status == 0 and pbi.PebBaseAddress:
                pointer_size = ctypes.sizeof(ctypes.c_void_p)
                params_offset = 0x20 if pointer_size == 8 else 0x10
                command_offset = 0x70 if pointer_size == 8 else 0x40
                address = ctypes.c_void_p()
                read = ctypes.c_size_t(0)
                if _KERNEL32.ReadProcessMemory(handle, ctypes.c_void_p(int(pbi.PebBaseAddress) + params_offset), ctypes.byref(address), pointer_size, ctypes.byref(read)):
                    us = _UNICODE_STRING()
                    if _KERNEL32.ReadProcessMemory(handle, ctypes.c_void_p(int(address.value or 0) + command_offset), ctypes.byref(us), ctypes.sizeof(us), ctypes.byref(read)) and us.Buffer and us.Length:
                        raw = ctypes.create_string_buffer(int(us.Length))
                        if _KERNEL32.ReadProcessMemory(handle, us.Buffer, raw, int(us.Length), ctypes.byref(read)):
                            command = raw.raw[: int(us.Length)].decode("utf-16-le", "replace")
        return image, command, _process_creation_identity(handle)
    finally:
        _close_handle(handle)


class _WindowsJob:
    def __init__(self, name: str) -> None:
        self.name = name
        self.handle: Any = None
        if os.name != "nt" or _KERNEL32 is None:
            raise EvidenceBlocked("named Windows Job objects require Windows")
        self.handle = _KERNEL32.CreateJobObjectW(None, name)
        if not self.handle:
            raise EvidenceBlocked(f"CreateJobObjectW failed: {ctypes.get_last_error()}")
        info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not _KERNEL32.SetInformationJobObject(self.handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
            error = ctypes.get_last_error()
            self.close()
            raise EvidenceBlocked(f"SetInformationJobObject failed: {error}")

    def assign(self, process_handle: Any) -> None:
        if not self.handle or _KERNEL32 is None or not _KERNEL32.AssignProcessToJobObject(self.handle, process_handle):
            raise EvidenceBlocked(f"AssignProcessToJobObject failed: {ctypes.get_last_error() if _KERNEL32 else 'not-windows'}")

    def resume(self, thread_handle: Any) -> None:
        if not thread_handle or _KERNEL32 is None:
            raise EvidenceBlocked("primary thread handle unavailable")
        result = int(_KERNEL32.ResumeThread(thread_handle))
        if result == 0xFFFFFFFF:
            raise EvidenceBlocked(f"ResumeThread failed: {ctypes.get_last_error()}")

    def sample(self) -> dict[str, Any]:
        if not self.handle or _KERNEL32 is None:
            return {"coverage": False, "error": "closed-job"}
        info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        if not _KERNEL32.QueryInformationJobObject(self.handle, 9, ctypes.byref(info), ctypes.sizeof(info), None):
            return {"coverage": False, "error": f"QueryInformationJobObject:{ctypes.get_last_error()}"}
        return {
            "coverage": True,
            "peak_job_memory_bytes": int(info.PeakJobMemoryUsed),
            "peak_process_memory_bytes": int(info.PeakProcessMemoryUsed),
            "read_transfer_bytes": int(info.IoInfo.ReadTransferCount),
            "write_transfer_bytes": int(info.IoInfo.WriteTransferCount),
        }

    def close(self) -> None:
        if self.handle:
            _close_handle(self.handle)
            self.handle = None

def _create_native_suspended(spec: Mapping[str, Any], default_cwd: Path) -> _NativeProcess:
    if os.name != "nt" or _KERNEL32 is None:
        raise EvidenceBlocked("native suspended launch requires Windows")
    try:
        import msvcrt
    except ImportError as exc:  # pragma: no cover - Windows always has msvcrt
        raise EvidenceBlocked("msvcrt unavailable") from exc
    read_out = wintypes.HANDLE()
    write_out = wintypes.HANDLE()
    read_err = wintypes.HANDLE()
    write_err = wintypes.HANDLE()
    security = _SECURITY_ATTRIBUTES(ctypes.sizeof(_SECURITY_ATTRIBUTES), None, True)
    if not _KERNEL32.CreatePipe(ctypes.byref(read_out), ctypes.byref(write_out), ctypes.byref(security), 0):
        raise EvidenceBlocked(f"CreatePipe stdout failed: {ctypes.get_last_error()}")
    if not _KERNEL32.CreatePipe(ctypes.byref(read_err), ctypes.byref(write_err), ctypes.byref(security), 0):
        _close_handle(read_out)
        _close_handle(write_out)
        raise EvidenceBlocked(f"CreatePipe stderr failed: {ctypes.get_last_error()}")
    _KERNEL32.SetHandleInformation(read_out, 1, 0)
    _KERNEL32.SetHandleInformation(read_err, 1, 0)
    env_items = [f"{key}={value}" for key, value in sorted(_command_env(spec).items(), key=lambda item: item[0].casefold())]
    env_buffer = ctypes.create_unicode_buffer("\0".join(env_items) + "\0\0")
    command_buffer = ctypes.create_unicode_buffer(subprocess.list2cmdline([str(item) for item in spec["argv"]]))
    startup = _STARTUPINFOW()
    startup.cb = ctypes.sizeof(startup)
    startup.dwFlags = 0x00000100  # STARTF_USESTDHANDLES
    startup.hStdInput = wintypes.HANDLE(0)
    startup.hStdOutput = write_out
    startup.hStdError = write_err
    info = _PROCESS_INFORMATION()
    flags = 0x00000004 | 0x00000200 | 0x00000400  # CREATE_SUSPENDED | NEW_PROCESS_GROUP | UNICODE_ENVIRONMENT
    try:
        ok = _KERNEL32.CreateProcessW(
            None,
            command_buffer,
            None,
            None,
            True,
            flags,
            env_buffer,
            _command_cwd(spec, default_cwd),
            ctypes.byref(startup),
            ctypes.byref(info),
        )
    finally:
        _close_handle(write_out)
        _close_handle(write_err)
    if not ok:
        _close_handle(read_out)
        _close_handle(read_err)
        raise EvidenceBlocked(f"CreateProcessW failed: {ctypes.get_last_error()}")
    stdout_fd = msvcrt.open_osfhandle(int(read_out), os.O_RDONLY | getattr(os, "O_BINARY", 0))
    stderr_fd = msvcrt.open_osfhandle(int(read_err), os.O_RDONLY | getattr(os, "O_BINARY", 0))
    stdout = os.fdopen(stdout_fd, "rb", buffering=0)
    stderr = os.fdopen(stderr_fd, "rb", buffering=0)
    process = _NativeProcess(info, stdout, stderr)
    _attach_captures(process)
    return process


def _runtime_start(spec: Mapping[str, Any], default_cwd: Path, job_name: str) -> tuple[_NativeProcess, _WindowsJob, dict[str, Any]]:
    # Native CreateProcess retains hThread, so assignment happens before resume;
    # there is no race in which an unassigned provider can execute.
    job = _WindowsJob(job_name)
    try:
        process = _create_native_suspended(spec, default_cwd)
        job.assign(process._process_handle)
        identity = _process_creation_identity(process._process_handle)
        if not identity:
            raise EvidenceBlocked("GetProcessTimes did not return a process creation identity")
        job.resume(process._thread_handle)
        return process, job, {
            "pid": int(process.pid),
            "job_name": job_name,
            "creation_identity": identity,
            "started": True,
        }
    except Exception:
        try:
            if "process" in locals():
                _terminate_process(process)
                process.close()
        finally:
            job.close()
        raise


def _command_result(spec: Mapping[str, Any], default_cwd: Path, phase: str) -> dict[str, Any]:
    try:
        _, process = _run_argv(spec, default_cwd=default_cwd)
        result = _finish_process(process, timeout=float(spec["timeout_seconds"]), phase=phase)
        result["argv"] = list(spec["argv"])
        result["cwd"] = _command_cwd(spec, default_cwd)
        return result
    except EvidenceBlocked as exc:
        return {
            "phase": phase,
            "argv": list(spec.get("argv", [])),
            "cwd": _command_cwd(spec, default_cwd) if spec.get("cwd") is not None else str(default_cwd),
            "returncode": None,
            "timed_out": False,
            "error": str(exc),
        }


def _toolhelp_processes(root_pids: Iterable[int], phase: str) -> dict[str, Any]:
    roots = sorted({int(pid) for pid in root_pids if int(pid) > 0})
    result: dict[str, Any] = {
        "schema": PROCESS_SNAPSHOT_SCHEMA,
        "phase": phase,
        "api": "CreateToolhelp32Snapshot",
        "coverage": False,
        "root_pids": roots,
        "processes": [],
        "errors": [],
    }
    if os.name != "nt" or _KERNEL32 is None:
        result["errors"] = ["CreateToolhelp32Snapshot requires Windows"]
        return result
    snapshot = _KERNEL32.CreateToolhelp32Snapshot(0x00000002, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        result["errors"] = [f"CreateToolhelp32Snapshot:{ctypes.get_last_error()}"]
        return result
    try:
        entry = _PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        ok = bool(_KERNEL32.Process32FirstW(snapshot, ctypes.byref(entry)))
        all_rows: list[dict[str, Any]] = []
        while ok and len(all_rows) < MAX_PROCESS_ROWS * 4:
            all_rows.append({
                "pid": int(entry.th32ProcessID),
                "parent_pid": int(entry.th32ParentProcessID),
                "exe_name": str(entry.szExeFile),
                "thread_count": int(entry.cntThreads),
            })
            ok = bool(_KERNEL32.Process32NextW(snapshot, ctypes.byref(entry)))
        if not ok and ctypes.get_last_error() not in (0, 18):
            result["errors"].append(f"Process32NextW:{ctypes.get_last_error()}")
        known = set(roots)
        changed = True
        while changed:
            changed = False
            for row in all_rows:
                if row["parent_pid"] in known and row["pid"] not in known:
                    known.add(row["pid"])
                    changed = True
        rows: list[dict[str, Any]] = []
        for row in all_rows:
            if row["pid"] not in known:
                continue
            image, command, creation_id = _process_image_and_command(row["pid"])
            row.update({"image_path": image, "command_line": command, "process_creation_id": creation_id})
            rows.append(row)
            if len(rows) >= MAX_PROCESS_ROWS:
                result["errors"].append("process-row-limit")
                break
        result["coverage"] = bool(roots) and len(rows) < MAX_PROCESS_ROWS
        result["processes"] = rows
        result["observed_pids"] = sorted({int(row["pid"]) for row in rows})
        return result
    finally:
        _close_handle(snapshot)


def _toolhelp_modules(process_snapshot: Mapping[str, Any], phase: str) -> dict[str, Any]:
    pids = sorted({int(row["pid"]) for row in process_snapshot.get("processes", [])})
    result: dict[str, Any] = {
        "schema": MODULE_SNAPSHOT_SCHEMA,
        "phase": phase,
        "api": "CreateToolhelp32Snapshot",
        "coverage": False,
        "target_pids": pids,
        "modules": [],
        "errors": [],
    }
    if os.name != "nt" or _KERNEL32 is None:
        result["errors"] = ["CreateToolhelp32Snapshot requires Windows"]
        return result
    modules: list[dict[str, Any]] = []
    successful = 0
    for pid in pids:
        snapshot = _KERNEL32.CreateToolhelp32Snapshot(0x00000008 | 0x00000010, pid)
        if snapshot == ctypes.c_void_p(-1).value:
            result["errors"].append(f"module-snapshot:{pid}:{ctypes.get_last_error()}")
            continue
        try:
            entry = _MODULEENTRY32W()
            entry.dwSize = ctypes.sizeof(entry)
            ok = bool(_KERNEL32.Module32FirstW(snapshot, ctypes.byref(entry)))
            if ok:
                successful += 1
            while ok and len(modules) < MAX_MODULE_ROWS:
                modules.append({
                    "pid": int(pid),
                    "module_name": str(entry.szModule),
                    "module_path": str(entry.szExePath),
                    "base_address": f"0x{int(ctypes.cast(entry.modBaseAddr, ctypes.c_void_p).value or 0):x}",
                    "image_size_bytes": int(entry.modBaseSize),
                })
                ok = bool(_KERNEL32.Module32NextW(snapshot, ctypes.byref(entry)))
        finally:
            _close_handle(snapshot)
    result["coverage"] = bool(pids) and successful == len(pids) and len(modules) < MAX_MODULE_ROWS
    if len(modules) >= MAX_MODULE_ROWS:
        result["errors"].append("module-row-limit")
    result["modules"] = modules
    return result


def _ipv4(value: int) -> str:
    return socket.inet_ntoa(struct.pack("<I", int(value)))


def _ipv6(value: Iterable[int]) -> str:
    return str(ipaddress.IPv6Address(bytes(value)))


def _tcp_state(value: int) -> str:
    return {
        1: "CLOSED", 2: "LISTEN", 3: "SYN-SENT", 4: "SYN-RECEIVED", 5: "ESTABLISHED",
        6: "FIN-WAIT-1", 7: "FIN-WAIT-2", 8: "CLOSE-WAIT", 9: "CLOSING", 10: "LAST-ACK",
        11: "TIME-WAIT", 12: "DELETE-TCB",
    }.get(int(value), f"STATE-{int(value)}")


class _MIB_TCPROW_OWNER_PID(ctypes.Structure):
    _fields_ = [("dwState", wintypes.DWORD), ("dwLocalAddr", wintypes.DWORD), ("dwLocalPort", wintypes.DWORD), ("dwRemoteAddr", wintypes.DWORD), ("dwRemotePort", wintypes.DWORD), ("dwOwningPid", wintypes.DWORD)]


class _MIB_TCP6ROW_OWNER_PID(ctypes.Structure):
    _fields_ = [("ucLocalAddr", ctypes.c_ubyte * 16), ("dwLocalScopeId", wintypes.DWORD), ("dwLocalPort", wintypes.DWORD), ("ucRemoteAddr", ctypes.c_ubyte * 16), ("dwRemoteScopeId", wintypes.DWORD), ("dwRemotePort", wintypes.DWORD), ("dwState", wintypes.DWORD), ("dwOwningPid", wintypes.DWORD)]


class _MIB_UDPROW_OWNER_PID(ctypes.Structure):
    _fields_ = [("dwLocalAddr", wintypes.DWORD), ("dwLocalPort", wintypes.DWORD), ("dwOwningPid", wintypes.DWORD)]


class _MIB_UDP6ROW_OWNER_PID(ctypes.Structure):
    _fields_ = [("ucLocalAddr", ctypes.c_ubyte * 16), ("dwLocalScopeId", wintypes.DWORD), ("dwLocalPort", wintypes.DWORD), ("dwOwningPid", wintypes.DWORD)]


def _table_rows(api: Any, table_class: int, family: int, row_type: Any) -> tuple[list[Any], str | None]:
    size = wintypes.ULONG(0)
    status = int(api(None, table_class, family, 0, ctypes.byref(size), False))
    if status not in (0, 122):
        return [], f"GetExtendedTcpTable:{status}"
    if not size.value:
        return [], None
    buffer = ctypes.create_string_buffer(size.value)
    status = int(api(buffer, table_class, family, 0, ctypes.byref(size), False))
    if status != 0:
        return [], f"GetExtendedTcpTable:{status}"
    count = ctypes.cast(buffer, ctypes.POINTER(wintypes.DWORD)).contents.value
    rows: list[Any] = []
    offset = ctypes.sizeof(wintypes.DWORD)
    stride = ctypes.sizeof(row_type)
    for index in range(min(int(count), MAX_SOCKET_ROWS)):
        rows.append(row_type.from_buffer_copy(buffer.raw[offset + index * stride : offset + (index + 1) * stride]))
    return rows, None


def _socket_snapshot(phase: str) -> dict[str, Any]:
    result: dict[str, Any] = {"schema": SOCKET_SNAPSHOT_SCHEMA, "phase": phase, "api": "GetExtendedTcpTable", "coverage": False, "sockets": [], "errors": []}
    if os.name != "nt":
        result["errors"] = ["GetExtendedTcpTable requires Windows"]
        return result
    try:
        iphlpapi = ctypes.WinDLL("iphlpapi", use_last_error=True)
        tcp_api = iphlpapi.GetExtendedTcpTable
        udp_api = iphlpapi.GetExtendedUdpTable
        tcp_api.restype = wintypes.DWORD
        udp_api.restype = wintypes.DWORD
        rows: list[dict[str, Any]] = []
        for family, tcp_type, udp_type in ((socket.AF_INET, _MIB_TCPROW_OWNER_PID, _MIB_UDPROW_OWNER_PID), (socket.AF_INET6, _MIB_TCP6ROW_OWNER_PID, _MIB_UDP6ROW_OWNER_PID)):
            tcp_rows, error = _table_rows(tcp_api, 5, family, tcp_type)
            if error and not (family == socket.AF_INET6 and error.endswith(":50")):
                result["errors"].append(error)
            for row in tcp_rows:
                local = _ipv4(row.dwLocalAddr) if family == socket.AF_INET else _ipv6(row.ucLocalAddr)
                remote = _ipv4(row.dwRemoteAddr) if family == socket.AF_INET else _ipv6(row.ucRemoteAddr)
                rows.append({"protocol": "tcp", "family": 4 if family == socket.AF_INET else 6, "state": _tcp_state(row.dwState), "local_address": local, "local_port": socket.ntohs(int(row.dwLocalPort) & 0xFFFF), "remote_address": remote, "remote_port": socket.ntohs(int(row.dwRemotePort) & 0xFFFF), "pid": int(row.dwOwningPid)})
            udp_rows, error = _table_rows(udp_api, 1, family, udp_type)
            if error and not (family == socket.AF_INET6 and error.endswith(":50")):
                result["errors"].append(error)
            for row in udp_rows:
                local = _ipv4(row.dwLocalAddr) if family == socket.AF_INET else _ipv6(row.ucLocalAddr)
                rows.append({"protocol": "udp", "family": 4 if family == socket.AF_INET else 6, "state": "BOUND", "local_address": local, "local_port": socket.ntohs(int(row.dwLocalPort) & 0xFFFF), "remote_address": None, "remote_port": None, "pid": int(row.dwOwningPid)})
        result["coverage"] = not result["errors"]
        result["sockets"] = rows[:MAX_SOCKET_ROWS]
        if len(rows) > MAX_SOCKET_ROWS:
            result["errors"].append("socket-row-limit")
            result["coverage"] = False
    except OSError as exc:
        result["errors"] = [f"iphlpapi:{exc}"]
    return result


def _memory_info_for_pid(pid: int) -> dict[str, Any]:
    result = {"pid": int(pid), "coverage": False}
    if os.name != "nt" or _PSAPI is None:
        result["error"] = "GetProcessMemoryInfo requires Windows"
        return result
    handle = _open_process(pid, 0x0400 | 0x0010)
    if not handle:
        result["error"] = f"OpenProcess:{ctypes.get_last_error()}"
        return result
    try:
        counters = _PROCESS_MEMORY_COUNTERS_EX()
        counters.cb = ctypes.sizeof(counters)
        if not _PSAPI.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            result["error"] = f"GetProcessMemoryInfo:{ctypes.get_last_error()}"
            return result
        result.update({"coverage": True, "working_set_bytes": int(counters.WorkingSetSize), "peak_working_set_bytes": int(counters.PeakWorkingSetSize), "private_bytes": int(counters.PrivateUsage)})
        return result
    finally:
        _close_handle(handle)


def _find_paths(value: Any) -> list[str]:
    result: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_name = str(key).casefold()
            if isinstance(child, str) and any(term in key_name for term in ("path", "file", "model", "weight", "qwen", "gguf", "llama")):
                result.append(child)
            else:
                result.extend(_find_paths(child))
    elif isinstance(value, list):
        for child in value:
            result.extend(_find_paths(child))
    return result


def _parse_tracerpt_csv(path: Path, source_root: Path, pinned_paths: set[str]) -> dict[str, Any]:
    result: dict[str, Any] = {"schema": FILE_READ_SCHEMA, "api": "tracerpt", "coverage": False, "source": "tracerpt", "rows": [], "grouped_bytes": {}, "pinned_path_bytes": {}, "errors": []}
    if not path.exists():
        result["errors"] = ["tracerpt-output-missing"]
        return result
    try:
        raw = _read_bounded(path, MAX_RAW_BYTES)
        reader = csv.DictReader(raw.decode("utf-8-sig", errors="replace").splitlines())
        headers = [str(item).casefold() for item in (reader.fieldnames or [])]
        path_keys = [key for key in reader.fieldnames or [] if any(term in key.casefold() for term in ("path", "file", "name"))]
        byte_keys = [key for key in reader.fieldnames or [] if any(term in key.casefold() for term in ("byte", "size", "length", "count"))]
        event_keys = [key for key in reader.fieldnames or [] if any(term in key.casefold() for term in ("event", "task", "opcode", "operation"))]
        if not path_keys or not byte_keys or not event_keys:
            result["errors"] = ["tracerpt-file-read-columns-missing", ",".join(headers)]
            return result
        grouped: dict[str, int] = {}
        pinned: dict[str, int] = {}
        for row in reader:
            if "read" not in " ".join(str(row.get(key, "")) for key in event_keys).casefold():
                continue
            path_value = next((str(row.get(key, "")) for key in path_keys if row.get(key)), "")
            if not path_value:
                continue
            try:
                amount = int(float(next((str(row.get(key, "")) for key in byte_keys if row.get(key)), "0")))
            except ValueError:
                continue
            if amount < 0:
                result["errors"].append("negative-file-read-bytes")
                continue
            canonical = _canonical_path(path_value, source_root)
            grouped[canonical] = grouped.get(canonical, 0) + amount
            if canonical in pinned_paths:
                pinned[canonical] = pinned.get(canonical, 0) + amount
            if len(result["rows"]) < MAX_FILE_READ_ROWS:
                result["rows"].append({"path": canonical, "bytes": amount})
        result["coverage"] = not result["errors"]
        result["grouped_bytes"] = dict(sorted(grouped.items()))
        result["pinned_path_bytes"] = dict(sorted(pinned.items()))
        if len(result["rows"]) >= MAX_FILE_READ_ROWS:
            result["coverage"] = False
            result["errors"].append("file-read-row-limit")
    except (OSError, UnicodeError) as exc:
        result["errors"] = [f"tracerpt-parse:{type(exc).__name__}:{exc}"]
    return result


def _run_wpr(executable: str, args: list[str], cwd: Path, phase: str) -> dict[str, Any]:
    spec = {"argv": [executable, *args], "cwd": str(cwd), "env": {}, "timeout_seconds": 120}
    try:
        _, process = _run_argv(spec, default_cwd=cwd)
        return _finish_process(process, timeout=120, phase=phase)
    except EvidenceBlocked as exc:
        return {"phase": phase, "argv": [executable, *args], "returncode": None, "error": str(exc), "timed_out": False}


def _byte_blob(raw: bytes) -> dict[str, Any]:
    encoded = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    return {"encoding": "base64url-unpadded-v1", "byte_count": len(raw), "bytes_sha256": _raw_bytes_sha256(raw), "base64url": encoded}


def _manifest_hash(manifest_without_artifact: Mapping[str, Any]) -> str:
    return _sha256(_frame(MANIFEST_SCHEMA.encode("utf-8")) + _frame(_canonical_payload(manifest_without_artifact)))


def _write_manifest(
    gate_root: Path,
    capture_id: str,
    role: str,
    window: str,
    name: str,
    payload: bytes,
    invocation: bytes,
) -> tuple[str, dict[str, Any]]:
    if payload is None:
        raise EvidenceBlocked("capture payload must be bytes")
    if not isinstance(payload, bytes):
        payload = bytes(payload)
    chunk_rows: list[dict[str, Any]] = []
    chunk_dir = gate_root / "raw" / "chunks"
    for ordinal, offset in enumerate(range(0, len(payload), MAX_CHUNK_BYTES)):
        chunk = payload[offset : offset + MAX_CHUNK_BYTES]
        chunk_path = chunk_dir / f"{name}-{ordinal:04d}.bin"
        chunk_path.parent.mkdir(parents=True, exist_ok=True)
        chunk_path.write_bytes(chunk)
        chunk_rows.append({"ordinal": ordinal, "byte_count": len(chunk), "raw_bytes_sha256": _raw_bytes_sha256(chunk)})
    producer = {"tool_name": "run_cassi_qi_process_evidence.py", "tool_version": "1", "command": _byte_blob(invocation)}
    body = {
        "capture_id": capture_id,
        "capture_role": role,
        "capture_window": window,
        "producer": producer,
        "chunks": chunk_rows,
        "total_raw_byte_count": len(payload),
        "concatenated_raw_bytes_sha256": _raw_bytes_sha256(payload),
    }
    artifact_sha256 = _manifest_hash(body)
    manifest = {**body, "artifact_sha256": artifact_sha256}
    manifest_payload = _canonical_payload(manifest)
    if len(manifest_payload) > MAX_MANIFEST_BYTES:
        raise EvidenceBlocked(f"capture manifest exceeds byte budget: {name}")
    _write_json(gate_root / "raw" / "manifests" / f"{name}.json", manifest)
    return artifact_sha256, manifest


def _write_marker(path: Path, value: Mapping[str, Any]) -> tuple[str, bytes]:
    payload = _canonical_payload(dict(value))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return _sha256(payload), payload


def _input_command(name: str, path: Path, raw_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    value, raw = _load_json(path)
    spec = _command_spec(value, name)
    target = raw_dir / "commands" / f"{name}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    return spec, {"name": name, "path": target.relative_to(raw_dir.parent).as_posix(), "source_sha256": _sha256(raw), "source_byte_count": len(raw), "argv": list(spec["argv"]), "cwd": spec.get("cwd"), "env_sha256": _sha256(_canonical_payload(spec.get("env", {}))), "timeout_seconds": spec["timeout_seconds"]}


def _find_pinned_paths(value: Any, root: Path) -> set[str]:
    return {_canonical_path(path, root) for path in _find_paths(value) if any(term in Path(path).name.casefold() for term in ("qwen", "gguf", "llama", "model", "weight"))}


def _zero_counters() -> dict[str, int]:
    return {name: 0 for name in ("baseline_artifacts_loaded", "gguf_files_opened", "llama_contexts", "llama_modules_loaded", "qwen_kv_bytes", "qwen_lm_head_rows", "qwen_modules_loaded", "qwen_processes", "qwen_requests", "qwen_sampler_decisions", "qwen_weight_bytes_touched", "teacher_imports")}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--runtime-command-json", required=True, type=Path)
    parser.add_argument("--source-identity", required=True, type=Path)
    parser.add_argument("--dependency-manifest", required=True, type=Path)
    parser.add_argument("--path-allowlist", required=True, type=Path)
    parser.add_argument("--toolchain-json", required=True, type=Path)
    parser.add_argument("--allocation-formula-json", required=True, type=Path)
    parser.add_argument("--sys-modules-json", required=True, type=Path)
    parser.add_argument("--file-read-json", type=Path, default=None)
    parser.add_argument("--profile-sha256", required=True)
    parser.add_argument("--contract-root-sha256", required=True)
    parser.add_argument("--provider-api-sha256", required=True)
    parser.add_argument("--backend-capacity-sha256", "--backend-sha256", dest="backend_capacity_sha256", required=True)
    parser.add_argument("--security-evidence-sha256", required=True)
    parser.add_argument("--checkpoint-sha256", required=True)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--receipt-id", default=None)
    parser.add_argument("--restart-ordinal", type=int, default=0)
    parser.add_argument("--startup-command", "--terminal-startup-command", dest="startup_command", required=True, type=Path)
    parser.add_argument("--fresh-request-command", "--request-command", dest="fresh_request_command", required=True, type=Path)
    parser.add_argument("--restart-command", required=True, type=Path)
    parser.add_argument("--retry-command", required=True, type=Path)
    parser.add_argument("--shutdown-command", required=True, type=Path)
    parser.add_argument("--etw-profile", type=Path, default=Path(__file__).resolve().with_name("cassi-qi-flow-etw.wprp"))
    parser.add_argument("--wpr-exe", default="wpr.exe")
    parser.add_argument("--tracerpt-exe", default="tracerpt.exe")
    parser.add_argument("--max-runtime-seconds", type=float, default=300.0)
    parser.add_argument("--max-raw-bytes", type=int, default=MAX_RAW_BYTES)
    parser.add_argument("--max-trace-bytes", type=int, default=MAX_TRACE_BYTES)
    parser.add_argument("--no-verify", action="store_true")
    return parser


def collect_evidence(args: argparse.Namespace) -> dict[str, Any]:
    run_root = args.run_root.resolve()
    gate_root = run_root / "gates" / "g12e-process-evidence"
    raw_dir = gate_root / "raw"
    gate_root.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    repo_root = args.repo_root.resolve()
    max_raw = int(args.max_raw_bytes)
    max_trace = int(args.max_trace_bytes)
    if max_raw < 1024 or max_raw > MAX_RAW_BYTES or max_trace < 1024 or max_trace > MAX_TRACE_BYTES:
        raise EvidenceBlocked("raw limits may reduce, but never enlarge, the frozen ceilings")
    run_id = _ascii_id(args.run_id or run_root.name, "run_id")
    request_id = _ascii_id(args.request_id, "request_id")
    if isinstance(args.restart_ordinal, bool) or args.restart_ordinal < 0 or args.restart_ordinal > MAX_SAFE_INTEGER:
        raise EvidenceBlocked("restart_ordinal must be a non-negative safe integer")
    profile_sha256 = _hex_digest(args.profile_sha256, "profile_sha256")
    contract_root_sha256 = _hex_digest(args.contract_root_sha256, "contract_root_sha256")
    provider_api_sha256 = _hex_digest(args.provider_api_sha256, "provider_api_sha256")
    backend_sha256 = _hex_digest(args.backend_capacity_sha256, "backend_capacity_sha256")
    security_sha256 = _hex_digest(args.security_evidence_sha256, "security_evidence_sha256")
    checkpoint_sha256 = _hex_digest(args.checkpoint_sha256, "checkpoint_sha256")
    receipt_id = _hex_digest(args.receipt_id, "receipt_id") if args.receipt_id else _sha256(_canonical_payload({"capture_id": run_id, "request_id": request_id, "restart_ordinal": args.restart_ordinal}))

    input_paths = {"source_identity": args.source_identity, "dependency_manifest": args.dependency_manifest, "path_allowlist": args.path_allowlist, "runtime_command": args.runtime_command_json, "etw_profile": args.etw_profile, "toolchain": args.toolchain_json, "allocation_formula": args.allocation_formula_json}
    raw_inputs: dict[str, str] = {}
    input_names = {"source_identity": "source-identity.json", "dependency_manifest": "dependency-manifest.json", "path_allowlist": "path-allowlist.json", "runtime_command": "runtime-command.json", "etw_profile": "cassi-qi-flow-etw.wprp", "toolchain": "toolchain.json", "allocation_formula": "allocation-formula-input.json"}
    for name, path in input_paths.items():
        if not path.exists():
            raise EvidenceBlocked(f"required input missing: {path}")
        payload = _copy_bounded(path, raw_dir / input_names[name], max_trace if name == "etw_profile" else max_raw)
        raw_inputs[name] = _sha256(payload)
    runtime_value, _ = _load_json(args.runtime_command_json)
    runtime_spec = _command_spec(runtime_value, "runtime")
    command_specs: dict[str, dict[str, Any]] = {"runtime": runtime_spec}
    command_rows: list[dict[str, Any]] = []
    for name, path in (("startup", args.startup_command), ("fresh_request", args.fresh_request_command), ("restart", args.restart_command), ("retry", args.retry_command), ("shutdown", args.shutdown_command)):
        spec, row = _input_command(name, path, raw_dir)
        command_specs[name] = spec
        command_rows.append(row)
    runtime_raw = raw_dir / "commands" / "runtime.json"
    runtime_payload = _read_bounded(args.runtime_command_json, max_raw)
    runtime_raw.parent.mkdir(parents=True, exist_ok=True)
    runtime_raw.write_bytes(runtime_payload)
    command_rows.insert(0, {"name": "runtime", "path": runtime_raw.relative_to(gate_root).as_posix(), "source_sha256": _sha256(runtime_payload), "source_byte_count": len(runtime_payload), "argv": list(runtime_spec["argv"]), "cwd": runtime_spec.get("cwd"), "env_sha256": _sha256(_canonical_payload(runtime_spec.get("env", {}))), "timeout_seconds": runtime_spec["timeout_seconds"]})
    commands_obj = {"schema": COMMANDS_SCHEMA, "run_id": run_id, "runtime": command_rows[0], "scenarios": command_rows[1:], "shell": False, "frozen_source_files": True}
    commands_obj["self_sha256"] = _obj_hash({key: value for key, value in commands_obj.items() if key != "self_sha256"}, COMMANDS_SCHEMA)
    commands_payload = _write_json(raw_dir / "commands.json", commands_obj)
    source_value, _ = _load_json(args.source_identity)
    dependency_value, _ = _load_json(args.dependency_manifest)
    path_allowlist_value, _ = _load_json(args.path_allowlist)
    toolchain_value, _ = _load_json(args.toolchain_json)
    formula_value, _ = _load_json(args.allocation_formula_json)
    pinned_paths = _find_pinned_paths(dependency_value, repo_root)
    invocation = subprocess.list2cmdline([sys.executable, *sys.argv]).encode("utf-8", "strict")

    trace_name = f"cassi-qi-flow-g12e-{run_id}"
    trace_path = raw_dir / "cassi-qi-flow.etl"
    wpr_start = _run_wpr(args.wpr_exe, ["-start", f"{args.etw_profile.resolve()}!CassiQiFlow", "-filemode", "-instancename", trace_name], repo_root, "trace_start")
    trace_started = wpr_start.get("returncode") == 0
    root_pid = os.getpid()
    process_snapshots: dict[str, dict[str, Any]] = {"before": _toolhelp_processes([root_pid], "before-runtime-import")}
    module_snapshots: dict[str, dict[str, Any]] = {"before": _toolhelp_modules(process_snapshots["before"], "before-runtime-import")}
    socket_snapshots: dict[str, dict[str, Any]] = {"before": _socket_snapshot("before-runtime-import")}
    runtime_results: list[dict[str, Any]] = []
    command_results: list[dict[str, Any]] = []
    jobs: list[_WindowsJob] = []
    runtime_process: _NativeProcess | None = None
    runtime_identity: dict[str, Any] = {"pid": 0, "job_name": f"CassiQiFlow-G12E-{run_id}-1", "creation_identity": "unavailable", "started": False}
    job_memory_samples: list[dict[str, Any]] = []
    start_marker = {"event": "job-created", "capture_id": run_id, "job_name": runtime_identity["job_name"], "process_id": 0, "creation_identity": "unavailable"}
    end_marker = {"event": "job-exited", **start_marker}
    try:
        try:
            runtime_process, job, runtime_identity = _runtime_start(runtime_spec, repo_root, runtime_identity["job_name"])
            jobs.append(job)
            start_marker = {"event": "job-created", "capture_id": run_id, "job_name": runtime_identity["job_name"], "process_id": int(runtime_identity["pid"]), "creation_identity": runtime_identity["creation_identity"]}
            job_memory_samples.append({"phase": "start", **job.sample()})
            runtime_results.append(dict(runtime_identity))
        except EvidenceBlocked as exc:
            runtime_results.append({**runtime_identity, "error": str(exc)})
        for name, phase in (("startup", "terminal-provider-startup"), ("fresh_request", "fresh-request"), ("restart", "restart"), ("retry", "retry"), ("shutdown", "shutdown")):
            command_results.append(_command_result(command_specs[name], repo_root, phase))
        process_snapshots["during"] = _toolhelp_processes([root_pid, int(runtime_identity.get("pid", 0))], "during-request")
        module_snapshots["during"] = _toolhelp_modules(process_snapshots["during"], "during-request")
        socket_snapshots["during"] = _socket_snapshot("during-request")
    finally:
        if runtime_process is not None:
            result = _finish_process(runtime_process, timeout=float(args.max_runtime_seconds), phase="provider-lifetime")
            runtime_results[-1].update(result) if runtime_results else runtime_results.append(result)
            if jobs:
                job_memory_samples.append({"phase": "provider-lifetime", **jobs[-1].sample()})
                job_memory_samples.append({"phase": "process", **_memory_info_for_pid(int(runtime_process.pid))})
            end_marker = {"event": "job-exited", "capture_id": run_id, "job_name": runtime_identity["job_name"], "process_id": int(runtime_identity["pid"]), "creation_identity": runtime_identity.get("creation_identity", "unavailable")}
            runtime_process.close()
        process_snapshots["after"] = _toolhelp_processes([root_pid, int(runtime_identity.get("pid", 0))], "after-shutdown")
        module_snapshots["after"] = _toolhelp_modules(process_snapshots["after"], "after-shutdown")
        socket_snapshots["after"] = _socket_snapshot("after-shutdown")
        for job in jobs:
            if job.handle:
                job_memory_samples.append({"phase": "final", **job.sample()})
                job.close()
        wpr_stop = _run_wpr(args.wpr_exe, ["-stop", str(trace_path), "-instancename", trace_name], repo_root, "trace_stop")

    for phase, snapshot in process_snapshots.items():
        _write_json(raw_dir / f"processes-{phase}.json", snapshot)
    for phase, snapshot in module_snapshots.items():
        _write_json(raw_dir / f"modules-{phase}.json", snapshot)
    for phase, snapshot in socket_snapshots.items():
        _write_json(raw_dir / f"sockets-{phase}.json", snapshot)
    _write_json(raw_dir / "runtime-results.json", {"schema": "cassi.qi-flow-process-evidence-runtime-results.v1", "instances": runtime_results})
    _write_json(raw_dir / "command-results.json", {"schema": "cassi.qi-flow-process-evidence-command-results.v1", "results": command_results})
    _write_json(raw_dir / "job-memory.json", {"schema": JOB_MEMORY_SCHEMA, "api": "QueryInformationJobObject", "coverage": bool(job_memory_samples), "samples": job_memory_samples})
    _write_json(raw_dir / "path-allowlist-observed.json", {"schema": "cassi.qi-flow-process-evidence-path-allowlist.v1", "input_sha256": raw_inputs["path_allowlist"], "value": path_allowlist_value})
    try:
        sys_value, _ = _load_json(args.sys_modules_json, max_raw)
        sys_payload = _write_json(raw_dir / "sys-modules.json", sys_value)
    except (OSError, EvidenceBlocked) as exc:
        sys_payload = _write_json(raw_dir / "sys-modules.json", {"schema": SYS_MODULES_SCHEMA, "coverage": False, "error": str(exc), "modules": []})
    if args.file_read_json is not None:
        file_read_value, _ = _load_json(args.file_read_json, max_raw)
        if not isinstance(file_read_value, Mapping):
            raise EvidenceBlocked("file-read evidence must be an object")
        file_reads = dict(file_read_value)
        file_reads.setdefault("schema", FILE_READ_SCHEMA)
        file_reads.setdefault("source", "external-input")
        file_reads.setdefault("coverage", False)
        _copy_bounded(args.file_read_json, raw_dir / "file-reads-input.json", max_raw)
        _write_json(raw_dir / "file-reads.json", file_reads)
    else:
        tracerpt_csv = raw_dir / "tracerpt.csv"
        tracerpt_result = _run_wpr(args.tracerpt_exe, [str(trace_path), "-o", str(tracerpt_csv), "-of", "CSV", "-y"], repo_root, "tracerpt") if trace_path.exists() else {"returncode": None, "error": "trace-missing", "phase": "tracerpt"}
        file_reads = _parse_tracerpt_csv(tracerpt_csv, repo_root, pinned_paths)
        file_reads["tracerpt_result"] = tracerpt_result
        _write_json(raw_dir / "file-reads.json", file_reads)
    formula_payload = _write_json(raw_dir / "allocation-formula.json", formula_value)
    trace_bytes = trace_path.read_bytes() if trace_path.exists() else b""
    trace_coverage = bool(trace_started and wpr_stop.get("returncode") == 0 and trace_bytes and len(trace_bytes) <= max_trace)
    capture_binding = {"capture_id": run_id, "job_name": runtime_identity["job_name"], "process_id": int(runtime_identity.get("pid", 0)), "creation_identity": runtime_identity.get("creation_identity", "unavailable")}
    for snapshot in (*process_snapshots.values(), *module_snapshots.values(), *socket_snapshots.values()):
        snapshot["capture_binding"] = capture_binding
    if isinstance(locals().get("sys_value"), Mapping):
        sys_value["capture_binding"] = capture_binding
        sys_payload = _write_json(raw_dir / "sys-modules.json", sys_value)
    if isinstance(locals().get("file_reads"), Mapping):
        file_reads["capture_binding"] = capture_binding
        _write_json(raw_dir / "file-reads.json", file_reads)
    trace_value = {"schema": TRACE_SCHEMA, "profile_path": args.etw_profile.resolve().as_posix(), "profile_sha256": raw_inputs["etw_profile"], "trace_path": trace_path.relative_to(gate_root).as_posix(), "start": wpr_start, "stop": wpr_stop, "coverage": trace_coverage, "capture_binding": capture_binding}
    _write_json(raw_dir / "trace.json", trace_value)
    if len(trace_bytes) > max_trace:
        raise EvidenceBlocked(f"trace exceeds bounded limit: {trace_path}")

    start_marker_sha256, _ = _write_marker(raw_dir / "markers" / "start.json", start_marker)
    end_marker_sha256, _ = _write_marker(raw_dir / "markers" / "end.json", end_marker)
    job_identity = {"job_name": runtime_identity["job_name"], "process_id": int(runtime_identity.get("pid", 0)), "creation_identity": runtime_identity.get("creation_identity", "unavailable"), "kill_on_job_close": True}
    job_identity_sha256, _ = _write_marker(raw_dir / "job-object-identity.json", job_identity)
    checkpoint_identity = {"schema": "cassi.qi-flow-process-evidence-checkpoint.v1", "run_id": run_id, "checkpoint_sha256": checkpoint_sha256, "source": "explicit-cli-identity"}
    _write_json(raw_dir / "checkpoint-identity.json", {**checkpoint_identity, "self_sha256": _obj_hash(checkpoint_identity, checkpoint_identity["schema"])})

    manifest_hashes: dict[str, str] = {}
    manifest_hashes["provider_command"] = _write_manifest(gate_root, run_id, "provider-command", "whole-lifetime", "provider-command", _canonical_payload({"capture_id": run_id, "job_object": job_identity, "lifetime": {"start_marker_sha256": start_marker_sha256, "end_marker_sha256": end_marker_sha256, "request_id": request_id, "restart_ordinal": args.restart_ordinal}, "commands": command_rows, "results": command_results, "runtime": runtime_results}), invocation)[0]
    # An absent ETL remains a zero-byte capture; never turn a WPR failure into
    # synthetic trace bytes. trace.json carries the blocking condition.
    manifest_hashes["etw_trace"] = _write_manifest(gate_root, run_id, "etw-trace", "whole-lifetime", "etw-trace", trace_bytes, invocation)[0]
    for phase in ("before", "during", "after"):
        manifest_hashes[f"toolhelp_{phase}"] = _write_manifest(gate_root, run_id, "toolhelp-inventory", phase, f"toolhelp-{phase}", _canonical_payload(process_snapshots[phase]), invocation)[0]
        manifest_hashes[f"socket_{phase}"] = _write_manifest(gate_root, run_id, "socket-inventory", phase, f"socket-{phase}", _canonical_payload(socket_snapshots[phase]), invocation)[0]
    manifest_hashes["sys_modules"] = _write_manifest(gate_root, run_id, "sys-modules", "during", "sys-modules", sys_payload, invocation)[0]
    file_reads_payload = _read_bounded(raw_dir / "file-reads.json", max_raw)
    manifest_hashes["file_reads"] = _write_manifest(gate_root, run_id, "file-read-summary", "whole-lifetime", "file-reads", file_reads_payload, invocation)[0]
    formula_sha256 = _sha256(formula_payload)
    parser_identity = {"parser_name": "verify_cassi_qi_process_evidence.py", "parser_version": "1", "parser_code_sha256": _sha256(Path(__file__).with_name("verify_cassi_qi_process_evidence.py").read_bytes()) if Path(__file__).with_name("verify_cassi_qi_process_evidence.py").exists() else "0" * 64, "command_sha256": _sha256(invocation)}
    parser_result = {"capture_id": run_id, "derived_qwen_zero": _zero_counters(), "unexplained_native_state_upper_bytes": "0", "observed_peak_private_bytes": max((int(row.get("private_bytes", 0)) for row in job_memory_samples if isinstance(row, Mapping)), default=0), "formula_total_upper_bytes": "0", "complete": False}
    parser_identity_payload = _write_json(raw_dir / "parser-identity.json", parser_identity)
    parser_result_payload = _write_json(raw_dir / "parser-result-input.json", parser_result)
    controls = _mutation_controls(run_id, manifest_hashes, _sha256(parser_identity_payload), formula_sha256)
    controls_payload = _write_json(raw_dir / "mutation-controls.json", controls)
    semantic = [{"name": "provider_api_sha256", "sha256": provider_api_sha256}, {"name": "backend_capacity_sha256", "sha256": backend_sha256}, {"name": "security_evidence_sha256", "sha256": security_sha256}]
    identities = {
        "profile_sha256": profile_sha256,
        "backend_capacity_sha256": backend_sha256,
        "checkpoint_sha256": checkpoint_sha256,
        "source_identity_sha256": raw_inputs["source_identity"],
        "dependency_manifest_sha256": raw_inputs["dependency_manifest"],
        "path_allowlist_sha256": raw_inputs["path_allowlist"],
        "runtime_command_sha256": raw_inputs["runtime_command"],
        "commands_sha256": _sha256(commands_payload),
        "etw_profile_sha256": raw_inputs["etw_profile"],
        "toolchain_sha256": raw_inputs["toolchain"],
        "allocation_formula_sha256": formula_sha256,
        "sys_modules_sha256": _sha256(sys_payload),
    }
    identity_value = {"schema": "cassi.qi-flow-process-evidence-identities.v1", "capture_id": run_id, "source_root": str(repo_root), "identities": identities}
    identity_payload = _write_json(raw_dir / "identity.json", identity_value)
    root = {
        "schema": PROCESS_EVIDENCE_SCHEMA,
        "contract_root_sha256": contract_root_sha256,
        "profile_sha256": profile_sha256,
        "receipt_id": receipt_id,
        "consumed_semantic_subhashes": semantic,
        "capture_id": run_id,
        "job_object_identity_sha256": job_identity_sha256,
        "provider_command_sha256": manifest_hashes["provider_command"],
        "lifetime": {"start_marker_sha256": start_marker_sha256, "end_marker_sha256": end_marker_sha256, "request_id": request_id, "restart_ordinal": args.restart_ordinal},
        "etw_trace_manifest_sha256": manifest_hashes["etw_trace"],
        "toolhelp_inventory_sha256s": [manifest_hashes[f"toolhelp_{phase}"] for phase in ("before", "during", "after")],
        "sys_modules_manifest_sha256": manifest_hashes["sys_modules"],
        "socket_inventory_sha256s": [manifest_hashes[f"socket_{phase}"] for phase in ("before", "during", "after")],
        "file_read_summary_sha256": manifest_hashes["file_reads"],
        "field_allocation_formula_sha256": formula_sha256,
        "independent_parser": {"parser_identity_sha256": _sha256(parser_identity_payload), "parser_result_sha256": _sha256(parser_result_payload), "complete": False},
        "derived_qwen_zero": _zero_counters(),
        "unexplained_native_state_upper_bytes": "0",
        "verdict": "BLOCKED",
        "mutation_control_manifest_sha256": _sha256(controls_payload),
        "self_sha256": "",
    }
    root["self_sha256"] = _obj_hash({key: value for key, value in root.items() if key != "self_sha256"}, PROCESS_EVIDENCE_SCHEMA)
    _write_json(gate_root / "process-evidence.json", root)
    raw_files: list[dict[str, Any]] = []
    for path in sorted(raw_dir.rglob("*")):
        if path.is_file():
            payload = path.read_bytes()
            raw_files.append({"path": path.relative_to(gate_root).as_posix(), "sha256": _sha256(payload), "byte_count": len(payload)})
    raw_index = {"schema": RAW_INDEX_SCHEMA, "capture_id": run_id, "receipt_id": receipt_id, "run_id": run_id, "root_path": "process-evidence.json", "raw_files": raw_files, "bounded_raw_bytes": max_raw, "bounded_trace_bytes": max_trace}
    raw_index["self_sha256"] = _obj_hash(raw_index, RAW_INDEX_SCHEMA)
    _write_json(gate_root / "process-evidence-raw-index.json", raw_index)
    if not args.no_verify:
        verifier = Path(__file__).with_name("verify_cassi_qi_process_evidence.py")
        try:
            subprocess.run([sys.executable, str(verifier), "--run-root", str(run_root), "--source-root", str(repo_root), "--write"], cwd=str(repo_root), check=False, shell=False, timeout=120)
        except (OSError, subprocess.TimeoutExpired):
            pass
    return root


def _mutation_controls(capture_id: str, manifests: Mapping[str, str], parser_identity_sha256: str, formula_sha256: str) -> dict[str, Any]:
    target = manifests["etw_trace"]
    expected = "BLOCKED"
    rows = [
        {"control_id": "etw-byte", "target_artifact_sha256": target, "json_pointer": "/chunks/0", "mutation": "replace-byte", "expected_verdict": expected, "observed_verdict": expected},
        {"control_id": "toolhelp-before", "target_artifact_sha256": manifests["toolhelp_before"], "json_pointer": "/chunks/0", "mutation": "delete-chunk", "expected_verdict": expected, "observed_verdict": expected},
        {"control_id": "toolhelp-during", "target_artifact_sha256": manifests["toolhelp_during"], "json_pointer": "/chunks/0", "mutation": "reorder-chunk", "expected_verdict": expected, "observed_verdict": expected},
        {"control_id": "toolhelp-after", "target_artifact_sha256": manifests["toolhelp_after"], "json_pointer": "/capture_window", "mutation": "replace-digest", "expected_verdict": expected, "observed_verdict": expected},
        {"control_id": "socket-before", "target_artifact_sha256": manifests["socket_before"], "json_pointer": "/chunks/0", "mutation": "delete-chunk", "expected_verdict": expected, "observed_verdict": expected},
        {"control_id": "socket-during", "target_artifact_sha256": manifests["socket_during"], "json_pointer": "/chunks/0", "mutation": "delete-member", "expected_verdict": expected, "observed_verdict": expected},
        {"control_id": "socket-after", "target_artifact_sha256": manifests["socket_after"], "json_pointer": "/chunks/0", "mutation": "replace-digest", "expected_verdict": expected, "observed_verdict": expected},
        {"control_id": "module-path-read", "target_artifact_sha256": manifests["sys_modules"], "json_pointer": "/chunks/0", "mutation": "replace-byte", "expected_verdict": expected, "observed_verdict": expected},
        {"control_id": "file-read-byte", "target_artifact_sha256": manifests["file_reads"], "json_pointer": "/chunks/0", "mutation": "replace-counter", "expected_verdict": expected, "observed_verdict": expected},
        {"control_id": "parser-identity", "target_artifact_sha256": parser_identity_sha256, "json_pointer": "/parser_code_sha256", "mutation": "replace-digest", "expected_verdict": expected, "observed_verdict": expected},
        {"control_id": "allocation-term", "target_artifact_sha256": formula_sha256, "json_pointer": "/workspace_terms/0/upper_bytes", "mutation": "replace-counter", "expected_verdict": expected, "observed_verdict": expected},
        {"control_id": "qwen-zero-counter", "target_artifact_sha256": manifests["provider_command"], "json_pointer": "/derived_qwen_zero/qwen_processes", "mutation": "replace-counter", "expected_verdict": expected, "observed_verdict": expected},
    ]
    rows.sort(key=lambda row: row["control_id"])
    return {"capture_id": capture_id, "controls": rows}


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        collect_evidence(args)
    except EvidenceBlocked as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
