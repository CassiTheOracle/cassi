"""Native Windows session backend for the shared CASSI Surface protocol.

The Python half owns no native window handles and makes no policy decisions. It
starts the small, per-user-session .NET helper and transports bounded control
messages over a CurrentUserOnly named pipe. Captured pixels travel as a separate
binary frame, never as base64 in control-plane JSON.
"""

from __future__ import annotations

import ctypes
import json
import os
import secrets
import shutil
import subprocess
import threading
import time
import tempfile
from collections import deque
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from .records import SurfaceWaitError


_MAX_HEADER_BYTES = 1 << 20
_MAX_FRAME_BYTES = 64 << 20
_PIPE_BUFFER_BYTES = 32 << 10


class WindowsSurfaceError(RuntimeError):
    """A Windows helper operation was unavailable or rejected."""


class _PipeFailure(WindowsSurfaceError):
    """The authenticated helper pipe failed; an external effect may be unknown."""


class _NamedPipe:
    """Small synchronous client for the private byte-mode helper pipe."""

    _GENERIC_READ = 0x80000000
    _GENERIC_WRITE = 0x40000000
    _OPEN_EXISTING = 3
    _FILE_ATTRIBUTE_NORMAL = 0x00000080
    _PIPE_READMODE_BYTE = 0x00000000
    _PIPE_NOWAIT = 0x00000001
    _INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
    _ERROR_NO_DATA = 232
    _ERROR_PIPE_BUSY = 231
    _ERROR_BROKEN_PIPE = 109
    _ERROR_PIPE_NOT_CONNECTED = 233

    def __init__(
        self,
        name: str,
        *,
        timeout: float,
        process: subprocess.Popen[Any],
        diagnostics: Callable[[], str],
    ) -> None:
        self._kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self._kernel.WaitNamedPipeW.argtypes = (ctypes.c_wchar_p, ctypes.c_uint32)
        self._kernel.WaitNamedPipeW.restype = ctypes.c_int
        self._kernel.CreateFileW.argtypes = (
            ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
            ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
        )
        self._kernel.CreateFileW.restype = ctypes.c_void_p
        self._kernel.SetNamedPipeHandleState.argtypes = (
            ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint32),
        )
        self._kernel.SetNamedPipeHandleState.restype = ctypes.c_int
        self._kernel.PeekNamedPipe.argtypes = (
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_uint32),
        )
        self._kernel.PeekNamedPipe.restype = ctypes.c_int
        self._kernel.ReadFile.argtypes = (
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p,
        )
        self._kernel.ReadFile.restype = ctypes.c_int
        self._kernel.WriteFile.argtypes = (
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p,
        )
        self._kernel.WriteFile.restype = ctypes.c_int
        self._kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
        self._kernel.CloseHandle.restype = ctypes.c_int
        self._handle: int | None = None
        self._process = process
        self._diagnostics = diagnostics
        pipe_path = rf"\\.\pipe\{name}"
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if process.poll() is not None:
                detail = diagnostics()
                suffix = f": {detail}" if detail else ""
                raise _PipeFailure(
                    f"native Windows helper exited with code {process.returncode}{suffix}"
                )
            if not self._kernel.WaitNamedPipeW(pipe_path, 250):
                error = ctypes.get_last_error()
                if error not in (self._ERROR_PIPE_BUSY, 0):
                    time.sleep(0.025)
                continue
            handle = self._kernel.CreateFileW(
                pipe_path, self._GENERIC_READ | self._GENERIC_WRITE, 0, None,
                self._OPEN_EXISTING, self._FILE_ATTRIBUTE_NORMAL, None,
            )
            if handle != self._INVALID_HANDLE_VALUE:
                self._handle = handle
                mode = ctypes.c_uint32(self._PIPE_READMODE_BYTE | self._PIPE_NOWAIT)
                if not self._kernel.SetNamedPipeHandleState(handle, ctypes.byref(mode), None, None):
                    self.close()
                    raise _PipeFailure("could not set private helper pipe to bounded byte mode")
                return
            error = ctypes.get_last_error()
            if error not in (self._ERROR_PIPE_BUSY, self._ERROR_NO_DATA, 0):
                time.sleep(0.025)
        raise _PipeFailure("timed out waiting for the per-user Windows helper pipe")

    def _read_into(self, output: bytearray, offset: int, count: int, deadline: float) -> None:
        assert self._handle is not None
        while count:
            if time.monotonic() >= deadline:
                raise _PipeFailure("Windows helper response timed out")
            available = ctypes.c_uint32()
            if not self._kernel.PeekNamedPipe(
                self._handle, None, 0, None, ctypes.byref(available), None,
            ):
                error = ctypes.get_last_error()
                if error in (self._ERROR_BROKEN_PIPE, self._ERROR_PIPE_NOT_CONNECTED):
                    raise _PipeFailure("Windows helper disconnected during a response")
                raise _PipeFailure(f"Windows helper pipe read failed (Win32 error {error})")
            if available.value == 0:
                time.sleep(0.002)
                continue
            amount = min(count, available.value, _PIPE_BUFFER_BYTES)
            target = (ctypes.c_ubyte * amount).from_buffer(output, offset)
            read = ctypes.c_uint32()
            if not self._kernel.ReadFile(self._handle, target, amount, ctypes.byref(read), None):
                error = ctypes.get_last_error()
                if error in (self._ERROR_NO_DATA, self._ERROR_PIPE_BUSY):
                    time.sleep(0.002)
                    continue
                if error in (self._ERROR_BROKEN_PIPE, self._ERROR_PIPE_NOT_CONNECTED):
                    raise _PipeFailure("Windows helper disconnected during a response")
                raise _PipeFailure(f"Windows helper pipe read failed (Win32 error {error})")
            if read.value == 0:
                raise _PipeFailure("Windows helper returned an empty pipe read")
            offset += read.value
            count -= read.value

    def _read_exact(self, count: int, deadline: float) -> bytes:
        if count < 0 or count > _MAX_FRAME_BYTES:
            raise _PipeFailure("Windows helper frame exceeded the configured byte limit")
        output = bytearray(count)
        self._read_into(output, 0, count, deadline)
        return bytes(output)

    def _write_all(self, payload: bytes, deadline: float) -> None:
        assert self._handle is not None
        offset = 0
        while offset < len(payload):
            if time.monotonic() >= deadline:
                raise _PipeFailure("Windows helper request timed out while writing")
            amount = min(len(payload) - offset, _PIPE_BUFFER_BYTES)
            chunk = ctypes.create_string_buffer(payload[offset:offset + amount])
            written = ctypes.c_uint32()
            if not self._kernel.WriteFile(
                self._handle, chunk, amount, ctypes.byref(written), None,
            ):
                error = ctypes.get_last_error()
                if error in (self._ERROR_NO_DATA, self._ERROR_PIPE_BUSY):
                    time.sleep(0.002)
                    continue
                if error in (self._ERROR_BROKEN_PIPE, self._ERROR_PIPE_NOT_CONNECTED):
                    raise _PipeFailure("Windows helper disconnected before request completion")
                raise _PipeFailure(f"Windows helper pipe write failed (Win32 error {error})")
            if written.value == 0:
                time.sleep(0.002)
                continue
            offset += written.value

    def request(self, value: Mapping[str, Any], *, timeout: float) -> tuple[dict[str, Any], bytes]:
        if self._handle is None:
            raise _PipeFailure("Windows helper pipe is closed")
        try:
            encoded = json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise WindowsSurfaceError(f"request is not JSON-safe: {exc}") from exc
        if len(encoded) > _MAX_HEADER_BYTES:
            raise WindowsSurfaceError("request exceeds the Windows helper control-message limit")
        deadline = time.monotonic() + timeout
        try:
            self._write_all(len(encoded).to_bytes(4, "little") + encoded + b"\0\0\0\0", deadline)
            header_size = int.from_bytes(self._read_exact(4, deadline), "little")
            if not 0 < header_size <= _MAX_HEADER_BYTES:
                raise _PipeFailure("Windows helper returned an invalid response header length")
            header = json.loads(self._read_exact(header_size, deadline).decode("utf-8"))
            if not isinstance(header, dict):
                raise _PipeFailure("Windows helper returned a non-object control response")
            payload_size = int.from_bytes(self._read_exact(4, deadline), "little")
            if payload_size > _MAX_FRAME_BYTES:
                raise _PipeFailure("Windows helper returned an oversized pixel frame")
            payload = self._read_exact(payload_size, deadline) if payload_size else b""
            return header, payload
        except (UnicodeError, json.JSONDecodeError, OverflowError, ValueError) as exc:
            raise _PipeFailure(f"Windows helper returned malformed IPC data: {exc}") from exc

    def close(self) -> None:
        handle, self._handle = self._handle, None
        if handle is not None:
            self._kernel.CloseHandle(handle)


class WindowsBackend:
    """Windows Graphics Capture, UI Automation, and bounded native input.

    The helper is launched only on the current, non-service Windows desktop.
    This class does not grant control or repeat a request whose result is
    uncertain; authorization and reconciliation remain with SurfaceBroker.
    """

    backend_id = "windows-native"

    def __init__(self, *, helper_timeout_seconds: float = 30.0) -> None:
        if not 1.0 <= helper_timeout_seconds <= 120.0:
            raise ValueError("helper_timeout_seconds must be in 1..120")
        self._timeout = float(helper_timeout_seconds)
        self._lock = threading.RLock()
        self._pipe: _NamedPipe | None = None
        self._process: subprocess.Popen[Any] | None = None
        self._build_artifacts: Any = None
        self._output_lock = threading.Lock()
        self._output_lines: deque[str] = deque(maxlen=32)
        self._start_error: str | None = None
        self._closed = False
        self._session_id: int | None = None
        self._environment_incarnation = secrets.token_hex(16)

    def _helper_diagnostics(self) -> str:
        with self._output_lock:
            return "".join(self._output_lines).strip()[-8000:]

    def _collect_helper_output(self, process: subprocess.Popen[str]) -> None:
        if process.stdout is None:
            return
        for line in process.stdout:
            with self._output_lock:
                self._output_lines.append(line)

    def _ensure_helper(self) -> _NamedPipe:
        with self._lock:
            if self._closed:
                raise WindowsSurfaceError("Windows backend is closed")
            if os.name != "nt":
                raise WindowsSurfaceError("Windows native backend is unavailable on this host")
            if self._pipe is not None:
                return self._pipe
            if self._start_error is not None:
                raise WindowsSurfaceError(self._start_error)
            dotnet = shutil.which("dotnet")
            project = Path(__file__).resolve().parent / "native_windows" / "WindowsSurfaceHost.csproj"
            if not dotnet:
                self._start_error = "the Windows backend requires the already-installed .NET SDK; dotnet was not found"
                raise WindowsSurfaceError(self._start_error)
            if not project.is_file():
                self._start_error = f"native Windows helper source is missing: {project}"
                raise WindowsSurfaceError(self._start_error)
            pipe_name = f"cassi_surface_{os.getpid()}_{secrets.token_hex(16)}"
            build_artifacts = None
            try:
                build_artifacts = tempfile.TemporaryDirectory(prefix="cassi-surface-win-")
                build_root = Path(build_artifacts.name)
                empty_feed = build_root / "empty-feed"
                empty_feed.mkdir()
                obj_dir = build_root / "obj"
                bin_dir = build_root / "bin"
                env = os.environ.copy()
                env.update({
                    "DOTNET_NOLOGO": "1",
                    "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
                    "DOTNET_SKIP_FIRST_TIME_EXPERIENCE": "1",
                    "NUGET_XMLDOC_MODE": "skip",
                })
                flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                try:
                    build = subprocess.run(
                        [
                            dotnet, "build", str(project), "--configuration", "Release",
                            "--verbosity", "quiet", "--nologo",
                            f"-p:BaseIntermediateOutputPath={obj_dir}{os.sep}",
                            f"-p:MSBuildProjectExtensionsPath={obj_dir}{os.sep}",
                            f"-p:BaseOutputPath={bin_dir}{os.sep}",
                            f"-p:RestoreSources={empty_feed}",
                        ],
                        cwd=project.parent, env=env, stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                        errors="replace", timeout=max(60.0, self._timeout),
                        creationflags=flags,
                    )
                except subprocess.TimeoutExpired as exc:
                    details = exc.stdout or ""
                    if isinstance(details, bytes):
                        details = details.decode("utf-8", errors="replace")
                    raise WindowsSurfaceError(
                        f"offline .NET helper build timed out after {max(60.0, self._timeout)} seconds"
                        + (f":\n{details[-8000:]}" if details else "")
                    ) from exc
                if build.returncode:
                    details = (build.stdout or "").strip()[-12000:]
                    raise WindowsSurfaceError(
                        f"offline .NET helper build failed (exit {build.returncode})"
                        + (f":\n{details}" if details else "")
                    )
                runtimeconfig = next(bin_dir.rglob("WindowsSurfaceHost.runtimeconfig.json"), None)
                helper_dll = runtimeconfig.with_name("WindowsSurfaceHost.dll") if runtimeconfig else None
                if helper_dll is None or not helper_dll.is_file():
                    raise WindowsSurfaceError("offline .NET helper build produced no runnable assembly")
                process = subprocess.Popen(
                    [dotnet, str(helper_dll), pipe_name, str(os.getpid())],
                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace", bufsize=1,
                    env=env, creationflags=flags,
                )
                self._process = process
                self._build_artifacts = build_artifacts
                build_artifacts = None
                threading.Thread(
                    target=self._collect_helper_output, args=(process,),
                    name="Cassi Windows helper output", daemon=True,
                ).start()
                pipe = _NamedPipe(
                    pipe_name, timeout=self._timeout, process=process,
                    diagnostics=self._helper_diagnostics,
                )
                self._pipe = pipe
                self._session_id = self._query_session_id()
                response, _ = pipe.request({"op": "hello"}, timeout=self._timeout)
                if not response.get("ok"):
                    raise WindowsSurfaceError(str(response.get("error", "helper handshake failed")))
                identity = response.get("identity", {})
                if identity.get("session_id") != self._session_id or identity.get("session_id") == 0:
                    raise WindowsSurfaceError("helper handshake session does not match this interactive user session")
                return pipe
            except Exception as exc:
                details = self._helper_diagnostics()
                message = str(exc)
                if details and details not in message:
                    message = f"{message}\n{details}"
                self._start_error = f"could not start the per-user Windows helper: {message}"
                if self._pipe is not None:
                    self._pipe.close()
                    self._pipe = None
                if self._process is not None:
                    self._process.terminate()
                    try:
                        self._process.wait(timeout=2.0)
                    except subprocess.TimeoutExpired:
                        self._process.kill()
                        self._process.wait(timeout=2.0)
                    self._process = None
                if self._build_artifacts is not None:
                    self._build_artifacts.cleanup()
                    self._build_artifacts = None
                if build_artifacts is not None:
                    build_artifacts.cleanup()
                raise WindowsSurfaceError(self._start_error) from exc

    @staticmethod
    def _query_session_id() -> int:
        if os.name != "nt":
            raise WindowsSurfaceError("Windows session identity is unavailable on this host")
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        session = ctypes.c_uint32()
        process_id = kernel.GetCurrentProcessId()
        if not kernel.ProcessIdToSessionId(process_id, ctypes.byref(session)):
            raise WindowsSurfaceError(f"could not determine the current Windows session (error {ctypes.get_last_error()})")
        if session.value == 0:
            raise WindowsSurfaceError("Session 0 is not an authorized interactive surface session")
        return int(session.value)

    def _request(self, value: Mapping[str, Any], *, timeout: float | None = None) -> tuple[dict[str, Any], bytes]:
        pipe = self._ensure_helper()
        with self._lock:
            if self._closed:
                raise WindowsSurfaceError("Windows backend is closed")
            try:
                response, payload = pipe.request(value, timeout=timeout or self._timeout)
            except _PipeFailure:
                # Do not launch a replacement helper or replay a request. A lost
                # response after dispatch is an unresolved external effect.
                raise
            if response.get("ok") is not True:
                error = response.get("error")
                if isinstance(error, Mapping):
                    detail = error.get("message", "native helper rejected the request")
                    kind = error.get("kind", "unavailable")
                else:
                    detail, kind = str(error or "native helper rejected the request"), "unavailable"
                raise WindowsSurfaceError(f"{kind}: {detail}")
            return response, payload

    def describe(self) -> dict[str, Any]:
        if os.name != "nt":
            reason = "Windows Graphics Capture, UI Automation, and SendInput require a Windows user session"
            return {
                "backend_id": self.backend_id,
                "environment_incarnation": self._environment_incarnation,
                "status": "unavailable",
                "reason": reason,
                "capabilities": self._unavailable_capabilities(reason),
            }
        try:
            response, _ = self._request({"op": "describe"})
            return response["description"]
        except WindowsSurfaceError as exc:
            reason = str(exc)
            return {
                "backend_id": self.backend_id,
                "environment_incarnation": self._environment_incarnation,
                "status": "unavailable",
                "reason": reason,
                "capabilities": self._unavailable_capabilities(reason),
            }

    @staticmethod
    def _unavailable_capabilities(reason: str) -> dict[str, Any]:
        return {
            operation: {"status": "unavailable", "reason": reason}
            for operation in (
                "visual.window", "visual.display", "accessibility.tree",
                "binding.revalidate", "binding.foreground", "binding.follow_foreground",
                "binding.demonstration", "binding.unbind", "semantic_target.revalidate",
                "accessibility.invoke", "accessibility.set_value", "accessibility.select",
                "accessibility.toggle", "accessibility.expand", "accessibility.focus",
                "keyboard.key", "keyboard.text", "pointer.absolute", "pointer.relative",
                "pointer.button", "pointer.wheel", "physical_input_events",
                "audio.capture", "clipboard", "touch", "pen", "controller",
            )
        }

    def sources(self) -> list[dict[str, Any]]:
        response, _ = self._request({"op": "sources"})
        sources = response.get("sources")
        if not isinstance(sources, list) or any(not isinstance(source, dict) for source in sources):
            raise WindowsSurfaceError("native helper returned malformed source inventory")
        return sources

    def bind(self, source_id: str) -> dict[str, Any]:
        if not isinstance(source_id, str) or not source_id or len(source_id) > 256:
            raise ValueError("source_id must be bounded nonempty text")
        response, _ = self._request({"op": "bind", "source_id": source_id})
        binding = response.get("binding")
        if not isinstance(binding, dict):
            raise WindowsSurfaceError("native helper returned malformed binding")
        return binding

    def capture(self, binding: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(binding, Mapping):
            raise TypeError("binding must be a mapping")
        response, pixels = self._request({"op": "capture", "binding": dict(binding)}, timeout=max(2.0, self._timeout))
        result = response.get("capture")
        if not isinstance(result, dict):
            raise WindowsSurfaceError("native helper returned malformed capture metadata")
        if pixels:
            expected = result.get("width", 0) * result.get("height", 0) * 4
            if result.get("pixel_format") != "BGRA8" or len(pixels) != expected:
                raise WindowsSurfaceError("native helper pixel payload disagrees with its reported format and dimensions")
        elif result.get("capture_state") == "waiting_for_frame":
            raise SurfaceWaitError({"kind": "frame-pending",
                                    "reason": str(result.get("reason") or "waiting for a fresh Windows capture frame")})
        elif result.get("capture_state") == "live":
            raise WindowsSurfaceError("native helper reported a live image without pixel bytes")
        elif result.get("accessibility") is None and result.get("screen_text") is None:
            raise WindowsSurfaceError(str(result.get("reason") or "native capture returned no observable channel"))
        result["pixels"] = pixels or None
        return result

    def revalidate(self, binding: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(binding, Mapping):
            raise TypeError("binding must be a mapping")
        try:
            response, payload = self._request({"op": "revalidate", "binding": dict(binding)})
        except WindowsSurfaceError as exc:
            return {"supported": False, "valid": False, "reason": str(exc)}
        current = response.get("revalidation")
        if (
            payload or not isinstance(current, dict)
            or not isinstance(current.get("supported"), bool)
            or not isinstance(current.get("valid"), bool)
        ):
            return {"supported": False, "valid": False, "reason": "native helper returned a malformed revalidation receipt"}
        return current

    def foreground_binding(self, binding: Mapping[str, Any]) -> bool:
        if not isinstance(binding, Mapping):
            raise TypeError("binding must be a mapping")
        response, payload = self._request({"op": "foreground_binding", "binding": dict(binding)})
        foreground = response.get("foreground_binding")
        if payload or not isinstance(foreground, dict) or not isinstance(foreground.get("foreground"), bool):
            raise WindowsSurfaceError("native helper returned a malformed foreground receipt")
        return foreground["foreground"]

    def set_follow_foreground(self, binding: Mapping[str, Any], enabled: bool) -> dict[str, Any]:
        if not isinstance(binding, Mapping) or not isinstance(enabled, bool):
            raise TypeError("binding must be a mapping and enabled must be a boolean")
        response, payload = self._request({
            "op": "set_follow_foreground", "binding": dict(binding), "enabled": enabled,
        })
        receipt = response.get("follow_foreground")
        if payload or not isinstance(receipt, dict):
            raise WindowsSurfaceError("native helper returned a malformed foreground-gate receipt")
        return receipt

    def set_demonstration(self, binding: Mapping[str, Any], enabled: bool) -> dict[str, Any]:
        if not isinstance(binding, Mapping) or not isinstance(enabled, bool):
            raise TypeError("binding must be a mapping and enabled must be a boolean")
        response, payload = self._request({
            "op": "set_demonstration", "binding": dict(binding), "enabled": enabled,
        })
        receipt = response.get("demonstration")
        if payload or not isinstance(receipt, dict):
            raise WindowsSurfaceError("native helper returned a malformed demonstration receipt")
        return receipt

    def unbind(self, binding: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(binding, Mapping):
            raise TypeError("binding must be a mapping")
        response, payload = self._request({"op": "unbind", "binding": dict(binding)})
        receipt = response.get("unbound")
        if payload or not isinstance(receipt, dict) or receipt.get("unbound") is not True:
            raise WindowsSurfaceError("native helper did not confirm source unbind")
        return receipt

    def revalidate_target(
        self, binding: Mapping[str, Any], semantic_target: Mapping[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(binding, Mapping) or not isinstance(semantic_target, Mapping):
            raise TypeError("binding and semantic_target must be mappings")
        try:
            response, payload = self._request({
                "op": "revalidate_target",
                "binding": dict(binding),
                "semantic_target": dict(semantic_target),
            })
        except WindowsSurfaceError as exc:
            return {"supported": False, "valid": False, "detail": str(exc)}
        validation = response.get("target_validation")
        if (
            payload or not isinstance(validation, dict)
            or not isinstance(validation.get("supported"), bool)
            or not isinstance(validation.get("valid"), bool)
        ):
            return {
                "supported": False, "valid": False,
                "detail": "native helper returned a malformed target-validation receipt",
            }
        return validation

    def dispatch(self, binding: Mapping[str, Any], action: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(binding, Mapping) or not isinstance(action, Mapping):
            raise TypeError("binding and action must be mappings")
        try:
            response, _ = self._request({
                "op": "dispatch", "binding": dict(binding), "action": dict(action),
            })
            result = response.get("dispatch")
            if isinstance(result, dict):
                return result
            return {
                "disposition": "unknown", "delivered_count": 0,
                "ack_strength": "none", "detail": "helper returned no dispatch receipt",
            }
        except _PipeFailure as exc:
            return {
                "disposition": "unknown", "delivered_count": 0,
                "ack_strength": "none",
                "detail": {"reason": str(exc), "external_effect_may_have_started": True,
                           "automatic_replay": False},
            }

    def neutralize(self, binding: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(binding, Mapping):
            raise TypeError("binding must be a mapping")
        try:
            response, _ = self._request({"op": "neutralize", "binding": dict(binding)})
            result = response.get("neutralize")
            if isinstance(result, dict):
                return result
            return {"confirmed": False, "detail": "native helper returned no neutralization receipt"}
        except _PipeFailure as exc:
            return {"confirmed": False, "detail": {"reason": str(exc), "release_state": "unknown"}}

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            pipe, process = self._pipe, self._process
            if pipe is not None:
                try:
                    pipe.request({"op": "close"}, timeout=2.0)
                except WindowsSurfaceError:
                    pass
                pipe.close()
                self._pipe = None
            self._closed = True
            if process is not None:
                try:
                    process.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    # This is the child process launched by this backend; never
                    # discover or terminate any process by title or executable.
                    process.terminate()
                    try:
                        process.wait(timeout=1.0)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=2.0)
                self._process = None
            if self._build_artifacts is not None:
                self._build_artifacts.cleanup()
                self._build_artifacts = None


__all__ = ["WindowsBackend", "WindowsSurfaceError"]
