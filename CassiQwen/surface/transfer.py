"""Explicit, bounded artifact transfer into one authorized local scope.

The transfer utility is deliberately not a clipboard or host-authority provider.
It stores only transfer metadata in its ledger; payload bytes go only to the
scoped destination.  An authority callback supplied by the Surface broker must
approve each transfer before the utility touches the destination.
"""

from __future__ import annotations

import codecs
import contextlib
import hashlib
import json
import os
import re
import stat
import threading
import unicodedata
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@-]{0,191}$")
_MEDIA_TYPE_RE = re.compile(r"^[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+$")
_ALLOWED_ENCODINGS = frozenset(
    {
        "ascii",
        "cp1252",
        "iso8859-1",
        "utf-8",
        "utf-16",
        "utf-16-le",
        "utf-16-be",
        "utf-32",
        "utf-32-le",
        "utf-32-be",
    }
)
_PROVENANCE_KEYS = frozenset(
    {
        "mission_id",
        "source_artifact_id",
        "source_operation_id",
        "source_sha256",
        "source_system",
    }
)
_RECORD_SCHEMA = "cassi.surface.artifact-transfer.v1"
_MAX_RECEIPT_RESERVATION = 4096
_DEFAULT_BUFFER_BYTES = 1 << 20
_DEFAULT_TRANSFER_LIMIT = 1 << 30
_DEFAULT_RETAINED_LIMIT = 4 << 30


class TransferError(RuntimeError):
    """Base class for a rejected or incomplete artifact transfer."""


class TransferDenied(TransferError):
    """The broker did not authorize the exact transfer request."""


class TransferConflict(TransferError):
    """A transfer identity or destination is already bound to other bytes."""


class TransferIntegrityError(TransferError):
    """The received or retained bytes do not match their declared digest."""


class TransferResourceLimit(TransferError):
    """The transfer would exceed a declared byte or storage budget."""


class TransferPathError(TransferError):
    """The destination is not a safe relative path within its configured root."""


class ClipboardDenied(TransferError):
    """Clipboard access is disabled; no global clipboard fallback is provided."""


def _identifier(value: Any, name: str) -> str:
    if (
        not isinstance(value, str)
        or not _IDENTIFIER_RE.fullmatch(value)
        or value.casefold().startswith(
            ("secret:", "credential:", "vault:", "keyring:", "wincred:", "dpapi:", "token:")
        )
    ):
        raise ValueError(f"{name} must be a bounded opaque identifier, not a secret reference")
    return value


def _digest(value: Any, name: str) -> str:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _check_regular_file(path: Path, *, context: str) -> os.stat_result:
    try:
        info = path.lstat()
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise TransferPathError(f"cannot inspect {context}") from exc
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if (
        stat.S_ISLNK(info.st_mode)
        or bool(getattr(info, "st_file_attributes", 0) & reparse_flag)
        or not stat.S_ISREG(info.st_mode)
    ):
        raise TransferPathError(f"{context} is not a regular non-reparse file")
    return info


def _check_directory(path: Path, *, context: str) -> os.stat_result:
    try:
        info = path.lstat()
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise TransferPathError(f"cannot inspect {context}") from exc
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if (
        stat.S_ISLNK(info.st_mode)
        or bool(getattr(info, "st_file_attributes", 0) & reparse_flag)
        or not stat.S_ISDIR(info.st_mode)
    ):
        raise TransferPathError(f"{context} is not a regular non-reparse directory")
    return info


def _inside(root: Path, candidate: Path) -> bool:
    try:
        canonical_root = os.path.normcase(os.fspath(root.resolve(strict=True)))
        canonical_candidate = os.path.normcase(os.fspath(candidate.resolve(strict=True)))
        return os.path.commonpath((canonical_root, canonical_candidate)) == canonical_root
    except (OSError, ValueError):
        return False


def _safe_relative_path(raw: Any) -> tuple[str, tuple[str, ...]]:
    if not isinstance(raw, (str, os.PathLike)):
        raise TransferPathError("destination must be a relative path")
    try:
        path_text = os.fspath(raw)
    except TypeError:
        raise TransferPathError("destination must be a relative path") from None
    if not isinstance(path_text, str) or not path_text or "\x00" in path_text:
        raise TransferPathError("destination must be a non-empty relative path")
    # Treat both separator spellings as separators on every platform so a
    # Windows traversal cannot become an ordinary filename on Linux (or vice
    # versa).
    normalized = path_text.replace("\\", "/")
    import ntpath

    drive, _ = ntpath.splitdrive(normalized)
    if drive or normalized.startswith("/") or normalized.startswith("//"):
        raise TransferPathError("absolute and drive-qualified destinations are forbidden")
    parts = normalized.split("/")
    if not parts or any(part in ("", ".", "..") for part in parts):
        raise TransferPathError("destination traversal and empty path components are forbidden")
    try:
        path_bytes = len(normalized.encode("utf-8"))
    except UnicodeEncodeError:
        raise TransferPathError("destination is not valid Unicode") from None
    if path_bytes > 2048 or len(parts) > 32:
        raise TransferPathError("destination exceeds its path budget")
    for part in parts:
        if len(part.encode("utf-8")) > 255:
            raise TransferPathError("destination component exceeds its portable length budget")
    for part in parts:
        if (
            ":" in part
            or part.endswith((".", " "))
            or any(ord(char) < 32 or ord(char) == 127 for char in part)
            or unicodedata.normalize("NFC", part) != part
        ):
            raise TransferPathError("destination contains a non-portable path component")
        device_base = part.split(".", 1)[0].upper()
        if device_base in {"CON", "PRN", "AUX", "NUL"} or re.fullmatch(
            r"(?:COM|LPT)[1-9¹²³]", device_base
        ):
            raise TransferPathError("destination uses a reserved Windows device name")
    return "/".join(parts), tuple(parts)


def _canonical_encoding(value: Any, name: str) -> str:
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError(f"{name} must name a supported text encoding")
    try:
        canonical = codecs.lookup(value).name
    except LookupError:
        raise ValueError(f"{name} must name a supported text encoding") from None
    if canonical not in _ALLOWED_ENCODINGS:
        raise ValueError(f"{name} is not an allowed bounded text encoding")
    return canonical


def _provenance(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping) or not value:
        raise ValueError("provenance must be a non-empty bounded identifier mapping")
    if len(value) > len(_PROVENANCE_KEYS):
        raise ValueError("provenance contains unsupported fields")
    result: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or key not in _PROVENANCE_KEYS:
            raise ValueError("provenance contains an unsupported or sensitive field")
        if not isinstance(item, str) or len(item) > 192:
            raise ValueError("provenance values must be bounded opaque identifiers")
        if key == "source_sha256":
            result[key] = _digest(item, "provenance.source_sha256")
        else:
            result[key] = _identifier(item, f"provenance.{key}")
    return result


def _text_conversion(value: Any, media_type: str) -> dict[str, str] | None:
    if value is None:
        return None
    if not media_type.startswith("text/"):
        raise ValueError("declared text conversion requires a text media type")
    if not isinstance(value, Mapping) or set(value) != {
        "source_encoding",
        "destination_encoding",
        "newline",
    }:
        raise ValueError(
            "text_conversion must declare source_encoding, destination_encoding, and newline"
        )
    newline = value["newline"]
    if newline not in {"preserve", "lf", "crlf"}:
        raise ValueError("text_conversion.newline must be preserve, lf, or crlf")
    return {
        "source_encoding": _canonical_encoding(
            value["source_encoding"], "text_conversion.source_encoding"
        ),
        "destination_encoding": _canonical_encoding(
            value["destination_encoding"], "text_conversion.destination_encoding"
        ),
        "newline": newline,
    }


def _byte_views(content: Any, chunk_limit: int) -> Iterator[memoryview]:
    if isinstance(content, (bytes, bytearray, memoryview)):
        chunks = iter((content,))
    else:
        try:
            chunks = iter(content)
        except Exception:
            raise TypeError("content must be bytes or an iterable of byte buffers") from None
    while True:
        try:
            chunk = next(chunks)
        except StopIteration:
            return
        except Exception:
            raise TransferError("artifact content stream failed") from None
        if not isinstance(chunk, (bytes, bytearray, memoryview)):
            raise TypeError("content chunks must be bytes-like; text must be explicitly encoded")
        view = memoryview(chunk)
        if not view.contiguous:
            raise TypeError("content chunks must be contiguous byte buffers")
        try:
            view = view.cast("B")
        except TypeError:
            raise TypeError("content chunks must expose exact byte values") from None
        for offset in range(0, len(view), chunk_limit):
            yield view[offset : offset + chunk_limit]


def _source_metadata_and_conversion(
    content: Any,
    conversion: Mapping[str, str],
    *,
    max_input_bytes: int,
) -> tuple[bytes, int, str]:
    raw = bytearray()
    source_hash = hashlib.sha256()
    source_length = 0
    for chunk in _byte_views(content, min(64 * 1024, max_input_bytes)):
        source_length += len(chunk)
        if source_length > max_input_bytes:
            raise TransferResourceLimit("declared text conversion exceeds its buffer budget")
        source_hash.update(chunk)
        raw.extend(chunk)
    try:
        text = bytes(raw).decode(conversion["source_encoding"], errors="strict")
        newline = conversion["newline"]
        if newline != "preserve":
            text = text.replace("\r\n", "\n").replace("\r", "\n")
            if newline == "crlf":
                text = text.replace("\n", "\r\n")
        converted = text.encode(conversion["destination_encoding"], errors="strict")
    except UnicodeError:
        raise TransferIntegrityError("text conversion failed strict decoding or encoding") from None
    return converted, source_length, source_hash.hexdigest()


def _hash_stream(content: Any, chunk_limit: int, max_bytes: int) -> tuple[int, str]:
    digest = hashlib.sha256()
    length = 0
    for chunk in _byte_views(content, chunk_limit):
        length += len(chunk)
        if length > max_bytes:
            raise TransferResourceLimit("content exceeds the transfer byte budget")
        digest.update(chunk)
    return length, digest.hexdigest()


def _sync_directory(directory: Path) -> None:
    if os.name == "nt":
        # MoveFileExW with WRITE_THROUGH is used for the atomic publication on
        # Windows; the standard library does not expose a portable directory
        # FlushFileBuffers operation there.
        return
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(directory, flags)
    except OSError as exc:
        raise TransferError("destination directory cannot be opened for fsync") from exc
    try:
        os.fsync(descriptor)
    except OSError as exc:
        raise TransferError("destination directory fsync failed") from exc
    finally:
        os.close(descriptor)


def _move_replace(source: Path, destination: Path) -> None:
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        move_file = ctypes.WinDLL("kernel32", use_last_error=True).MoveFileExW
        move_file.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD)
        move_file.restype = wintypes.BOOL
        # MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH
        if not move_file(os.fspath(source), os.fspath(destination), 0x1 | 0x8):
            raise OSError(ctypes.get_last_error(), "atomic metadata publication failed")
    else:
        os.replace(source, destination)


def _publish_no_replace(source: Path, destination: Path) -> None:
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        move_file = ctypes.WinDLL("kernel32", use_last_error=True).MoveFileExW
        move_file.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD)
        move_file.restype = wintypes.BOOL
        # No REPLACE_EXISTING flag: a concurrently-created destination wins.
        # WRITE_THROUGH makes the namespace operation durable before return.
        if not move_file(os.fspath(source), os.fspath(destination), 0x8):
            error = ctypes.get_last_error()
            if error in {80, 183}:  # ERROR_FILE_EXISTS / ERROR_ALREADY_EXISTS
                raise FileExistsError(error, "destination already exists", os.fspath(destination))
            raise OSError(error, "atomic artifact publication failed")
    else:
        # A hard-link publish is atomic and never replaces an existing file.
        # It is supported by ordinary local NTFS/ext-family filesystems; if the
        # destination filesystem disallows it, fail closed rather than use a
        # racy check-then-overwrite rename.
        os.link(source, destination, follow_symlinks=False)
        os.unlink(source)


def _open_read_no_follow(path: Path) -> int:
    if os.name == "nt":
        import ctypes
        import msvcrt
        from ctypes import wintypes

        create_file = ctypes.WinDLL("kernel32", use_last_error=True).CreateFileW
        create_file.argtypes = (
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        )
        create_file.restype = wintypes.HANDLE
        handle = create_file(
            os.fspath(path),
            0x80000000,  # GENERIC_READ
            0x1 | 0x2 | 0x4,  # share read, write, and delete
            None,
            3,  # OPEN_EXISTING
            0x00200000 | 0x08000000,  # OPEN_REPARSE_POINT | SEQUENTIAL_SCAN
            None,
        )
        invalid_handle = ctypes.c_void_p(-1).value
        if handle == invalid_handle:
            raise OSError(ctypes.get_last_error(), "could not open artifact without following reparse points")
        try:
            descriptor = msvcrt.open_osfhandle(int(handle), os.O_RDONLY | getattr(os, "O_BINARY", 0))
        except BaseException:
            ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(handle)
            raise
    else:
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
    try:
        info = os.fstat(descriptor)
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if (
            not stat.S_ISREG(info.st_mode)
            or bool(getattr(info, "st_file_attributes", 0) & reparse_flag)
        ):
            raise TransferPathError("artifact is not a regular non-reparse file")
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _hash_file(path: Path, chunk_bytes: int, max_bytes: int) -> tuple[int, str]:
    descriptor = _open_read_no_follow(path)
    digest = hashlib.sha256()
    length = 0
    try:
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            while True:
                chunk = stream.read(chunk_bytes)
                if not chunk:
                    break
                length += len(chunk)
                if length > max_bytes:
                    raise TransferIntegrityError("retained artifact exceeds its receipt length")
                digest.update(chunk)
    finally:
        os.close(descriptor)
    return length, digest.hexdigest()


class ScopedArtifactTransfer:
    """Transfer exact or explicitly converted content under one allowed root.

    ``authorizer`` is normally the core Surface broker's policy callback.  It
    receives the complete metadata binding and must return ``True`` (or a
    mapping with ``authorized: True``).  With no callback every operation is
    denied.  Source bytes are never returned in a receipt, written to the
    ledger, or sent to the authorizer.
    """

    def __init__(
        self,
        state_home: str | os.PathLike[str],
        allowed_root: str | os.PathLike[str],
        *,
        destination_scope: str,
        authorizer: Callable[[Mapping[str, Any]], Any] | None = None,
        max_transfer_bytes: int = _DEFAULT_TRANSFER_LIMIT,
        max_retained_bytes: int = _DEFAULT_RETAINED_LIMIT,
        buffer_bytes: int = _DEFAULT_BUFFER_BYTES,
    ) -> None:
        if (
            isinstance(max_transfer_bytes, bool)
            or not isinstance(max_transfer_bytes, int)
            or max_transfer_bytes <= 0
        ):
            raise ValueError("max_transfer_bytes must be a positive integer")
        if (
            isinstance(max_retained_bytes, bool)
            or not isinstance(max_retained_bytes, int)
            or max_retained_bytes <= 0
        ):
            raise ValueError("max_retained_bytes must be a positive integer")
        if isinstance(buffer_bytes, bool) or not isinstance(buffer_bytes, int) or buffer_bytes < 32:
            raise ValueError("buffer_bytes must be at least 32")
        self.destination_scope = _identifier(destination_scope, "destination_scope")
        self.authorizer = authorizer
        self.max_transfer_bytes = int(max_transfer_bytes)
        self.max_retained_bytes = int(max_retained_bytes)
        self.buffer_bytes = int(buffer_bytes)
        self._chunk_bytes = min(64 * 1024, self.buffer_bytes)
        self._max_conversion_input = max(1, self.buffer_bytes // 32)
        self._mutex = threading.RLock()
        self._closed = False

        home = Path(state_home)
        home.mkdir(parents=True, exist_ok=True)
        self.state_home = home.resolve(strict=True)
        _check_directory(self.state_home, context="transfer state home")
        self._ledger = self.state_home / ".surface-transfer-ledger"
        try:
            self._ledger.mkdir(mode=0o700)
        except FileExistsError:
            pass
        _check_directory(self._ledger, context="transfer ledger")
        self._ledger = self._ledger.resolve(strict=True)
        if not _inside(self.state_home, self._ledger):
            raise TransferPathError("transfer ledger escaped its configured state home")
        self._lock_file = self._ledger / "store.lock"
        self._initialize_lock_file()

        root = Path(allowed_root)
        root.mkdir(parents=True, exist_ok=True)
        self.allowed_root = root.resolve(strict=True)
        _check_directory(self.allowed_root, context="allowed destination root")
        if _inside(self._ledger, self.allowed_root):
            raise TransferPathError("allowed destination root cannot be inside the transfer ledger")

    def _ensure_open(self) -> None:
        if self._closed:
            raise TransferError("transfer store is closed")

    def _initialize_lock_file(self) -> None:
        flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            _check_regular_file(self._lock_file, context="transfer lock")
        except FileNotFoundError:
            pass
        descriptor = os.open(self._lock_file, flags, 0o600)
        try:
            if os.fstat(descriptor).st_size == 0:
                os.write(descriptor, b"\x00")
                os.fsync(descriptor)
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode):
                raise TransferPathError("transfer lock is not a regular file")
        finally:
            os.close(descriptor)

    @contextlib.contextmanager
    def _locked(self) -> Iterator[None]:
        self._ensure_open()
        with self._mutex:
            flags = os.O_RDWR | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
            _check_regular_file(self._lock_file, context="transfer lock")
            descriptor = os.open(self._lock_file, flags)
            try:
                info = os.fstat(descriptor)
                if not stat.S_ISREG(info.st_mode) or info.st_size < 1:
                    raise TransferPathError("transfer lock is invalid")
                if os.name == "nt":
                    import msvcrt

                    os.lseek(descriptor, 0, os.SEEK_SET)
                    msvcrt.locking(descriptor, msvcrt.LK_LOCK, 1)
                    try:
                        yield
                    finally:
                        os.lseek(descriptor, 0, os.SEEK_SET)
                        msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(descriptor, fcntl.LOCK_EX)
                    try:
                        yield
                    finally:
                        fcntl.flock(descriptor, fcntl.LOCK_UN)
            finally:
                os.close(descriptor)

    def _manifest_path(self, transfer_id: str) -> Path:
        key = hashlib.sha256(transfer_id.encode("utf-8")).hexdigest()
        return self._ledger / f"{key}.json"

    def _stage_path(self, destination_parent: Path, transfer_id: str) -> Path:
        key = hashlib.sha256(transfer_id.encode("utf-8")).hexdigest()
        return destination_parent / f".cassi-transfer-{key}.part"

    def _resolve_destination(self, parts: tuple[str, ...]) -> Path:
        current = self.allowed_root
        if not _inside(current, current):
            raise TransferPathError("configured destination root is not resolvable")
        for part in parts[:-1]:
            candidate = current / part
            try:
                candidate.lstat()
            except FileNotFoundError:
                try:
                    candidate.mkdir(mode=0o700)
                except FileExistsError:
                    pass
            _check_directory(candidate, context="destination parent")
            if _inside(self._ledger, candidate):
                raise TransferPathError("destination cannot enter the private transfer ledger")
            if not _inside(self.allowed_root, candidate):
                raise TransferPathError("destination parent escaped its configured root")
            current = candidate
        destination = current / parts[-1]
        try:
            _check_regular_file(destination, context="destination")
        except FileNotFoundError:
            pass
        if not _inside(self.allowed_root, current):
            raise TransferPathError("destination escaped its configured root")
        return destination

    @staticmethod
    def _record_bytes(record: Mapping[str, Any]) -> bytes:
        return json.dumps(
            record,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")

    def _write_record(self, record: Mapping[str, Any]) -> None:
        target = self._manifest_path(str(record["transfer_id"]))
        temp = self._ledger / f".{target.stem}.record.tmp"
        try:
            try:
                _check_regular_file(temp, context="transfer metadata staging file")
            except FileNotFoundError:
                pass
            else:
                temp.unlink()
            descriptor = os.open(
                temp,
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | getattr(os, "O_BINARY", 0)
                | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(self._record_bytes(record))
                stream.flush()
                os.fsync(stream.fileno())
            _move_replace(temp, target)
            _sync_directory(self._ledger)
        except TransferError:
            raise
        except OSError as exc:
            raise TransferError("could not durably record transfer state") from exc

    def _read_record(self, transfer_id: str) -> dict[str, Any] | None:
        path = self._manifest_path(transfer_id)
        try:
            _check_regular_file(path, context="transfer receipt")
        except FileNotFoundError:
            return None
        descriptor = _open_read_no_follow(path)
        try:
            with os.fdopen(descriptor, "rb", closefd=False) as stream:
                raw = stream.read(_MAX_RECEIPT_RESERVATION + 1)
        finally:
            os.close(descriptor)
        if len(raw) > _MAX_RECEIPT_RESERVATION:
            raise TransferIntegrityError("transfer receipt exceeds its metadata budget")
        try:
            value = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise TransferIntegrityError("transfer receipt is corrupt") from None
        if (
            not isinstance(value, dict)
            or value.get("schema") != _RECORD_SCHEMA
            or value.get("transfer_id") != transfer_id
            or value.get("status") not in {"incomplete", "publishing", "complete"}
        ):
            raise TransferIntegrityError("transfer receipt has an invalid schema or identity")
        return value

    def _retained_usage(self) -> int:
        used = 0
        try:
            entries = self._ledger.iterdir()
        except OSError as exc:
            raise TransferError("cannot inspect retained transfer evidence") from exc
        for path in entries:
            if path.suffix != ".json":
                continue
            info = _check_regular_file(path, context="retained transfer receipt")
            if info.st_size > _MAX_RECEIPT_RESERVATION:
                raise TransferIntegrityError("retained transfer receipt exceeds its metadata budget")
            record = self._read_record_from_path(path)
            length = record.get("length")
            if isinstance(length, bool) or not isinstance(length, int) or length < 0:
                raise TransferIntegrityError("retained transfer receipt has an invalid length")
            if record["status"] == "complete":
                used += length + info.st_size
            else:
                used += length + _MAX_RECEIPT_RESERVATION
        return used

    def _read_record_from_path(self, path: Path) -> dict[str, Any]:
        descriptor = _open_read_no_follow(path)
        try:
            with os.fdopen(descriptor, "rb", closefd=False) as stream:
                raw = stream.read(_MAX_RECEIPT_RESERVATION + 1)
        finally:
            os.close(descriptor)
        if len(raw) > _MAX_RECEIPT_RESERVATION:
            raise TransferIntegrityError("retained transfer receipt exceeds its metadata budget")
        try:
            value = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise TransferIntegrityError("retained transfer receipt is corrupt") from None
        if not isinstance(value, dict) or value.get("schema") != _RECORD_SCHEMA:
            raise TransferIntegrityError("retained transfer receipt has an invalid schema")
        transfer_id = value.get("transfer_id")
        if (
            not isinstance(transfer_id, str)
            or value.get("status") not in {"incomplete", "publishing", "complete"}
            or path.name != f"{hashlib.sha256(transfer_id.encode('utf-8')).hexdigest()}.json"
        ):
            raise TransferIntegrityError("retained transfer receipt has an invalid identity")
        length = value.get("length")
        if isinstance(length, bool) or not isinstance(length, int) or length < 0:
            raise TransferIntegrityError("retained transfer receipt has an invalid length")
        return value

    def _authorize(self, record: Mapping[str, Any], operation: str) -> None:
        if self.authorizer is None:
            raise TransferDenied("no core authorization callback is configured")
        request = json.loads(self._record_bytes(record))
        request["operation"] = operation
        try:
            decision = self.authorizer(request)
        except Exception:
            raise TransferDenied("core authorization did not approve the request") from None
        approved = decision is True or (
            isinstance(decision, Mapping) and decision.get("authorized") is True
        )
        if not approved:
            raise TransferDenied("core authorization did not approve the request")

    def _identity_record(
        self,
        *,
        transfer_id: Any,
        artifact_id: Any,
        byte_length: Any,
        sha256: Any,
        media_type: Any,
        provenance: Any,
        privacy_label: Any,
        source_scope: Any,
        destination: Any,
        recipient: Any,
        text_conversion: Any,
    ) -> tuple[dict[str, Any], tuple[str, ...]]:
        transfer_id = _identifier(transfer_id, "transfer_id")
        artifact_id = _identifier(artifact_id, "artifact_id")
        if isinstance(byte_length, bool) or not isinstance(byte_length, int) or byte_length < 0:
            raise ValueError("byte_length must be a non-negative integer")
        if byte_length > self.max_transfer_bytes:
            raise TransferResourceLimit("declared artifact exceeds max_transfer_bytes")
        digest = _digest(sha256, "sha256")
        if not isinstance(media_type, str) or len(media_type) > 127 or not _MEDIA_TYPE_RE.fullmatch(media_type):
            raise ValueError("media_type must be a bounded type/subtype value")
        media_type = media_type.lower()
        privacy_label = _identifier(privacy_label, "privacy_label")
        source_scope = _identifier(source_scope, "source_scope")
        recipient = _identifier(recipient, "recipient")
        relative, parts = _safe_relative_path(destination)
        provenance_value = _provenance(provenance)
        conversion = _text_conversion(text_conversion, media_type)
        record = {
            "schema": _RECORD_SCHEMA,
            "transfer_id": transfer_id,
            "artifact_id": artifact_id,
            "sha256": digest,
            "length": byte_length,
            "media_type": media_type,
            "provenance": provenance_value,
            "privacy_label": privacy_label,
            "source_scope": source_scope,
            "destination_scope": self.destination_scope,
            "destination": relative,
            "recipient": recipient,
            "text_conversion": conversion,
            "status": "incomplete",
            "source_length": None,
            "source_sha256": None,
            "recovered": False,
        }
        if len(self._record_bytes(record)) > _MAX_RECEIPT_RESERVATION:
            raise ValueError("transfer metadata exceeds its receipt budget")
        return record, parts

    @staticmethod
    def _identity_matches(stored: Mapping[str, Any], requested: Mapping[str, Any]) -> bool:
        keys = (
            "schema",
            "transfer_id",
            "artifact_id",
            "sha256",
            "length",
            "media_type",
            "provenance",
            "privacy_label",
            "source_scope",
            "destination_scope",
            "destination",
            "recipient",
            "text_conversion",
        )
        return all(stored.get(key) == requested.get(key) for key in keys)

    def _check_content_identity(
        self,
        *,
        output_length: int,
        output_sha256: str,
        source_length: int,
        source_sha256: str,
        requested: Mapping[str, Any],
        stored: Mapping[str, Any] | None,
    ) -> None:
        if output_length != requested["length"] or output_sha256 != requested["sha256"]:
            raise TransferIntegrityError("content differs from its declared length or SHA-256")
        if stored is not None and stored.get("source_sha256") is not None:
            if (
                stored.get("source_sha256") != source_sha256
                or stored.get("source_length") != source_length
            ):
                raise TransferConflict("transfer identity was reused with different source bytes")

    def _write_payload(self, stage: Path, content: Any, record: Mapping[str, Any]) -> tuple[int, str]:
        try:
            try:
                _check_regular_file(stage, context="incomplete transfer file")
            except FileNotFoundError:
                pass
            else:
                raise TransferConflict("incomplete staging path already exists; refusing to overwrite it")
            descriptor = os.open(
                stage,
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | getattr(os, "O_BINARY", 0)
                | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            digest = hashlib.sha256()
            length = 0
            with os.fdopen(descriptor, "wb") as stream:
                for chunk in _byte_views(content, self._chunk_bytes):
                    length += len(chunk)
                    if length > record["length"] or length > self.max_transfer_bytes:
                        raise TransferResourceLimit("content exceeds its declared transfer length")
                    digest.update(chunk)
                    stream.write(chunk)
                stream.flush()
                os.fsync(stream.fileno())
            return length, digest.hexdigest()
        except TransferError:
            raise
        except OSError as exc:
            raise TransferError("could not stage artifact bytes") from exc

    def _verify_file(self, path: Path, record: Mapping[str, Any]) -> None:
        length, digest = _hash_file(path, self._chunk_bytes, record["length"])
        if length != record["length"] or digest != record["sha256"]:
            raise TransferIntegrityError("staged or published bytes failed digest verification")

    def _finalize(self, record: dict[str, Any], *, recovered: bool = False) -> dict[str, Any]:
        record["status"] = "complete"
        record["recovered"] = bool(recovered)
        self._write_record(record)
        return self._public_receipt(record)

    @staticmethod
    def _public_receipt(record: Mapping[str, Any]) -> dict[str, Any]:
        # Deliberately metadata-only.  In particular, the artifact bytes and
        # protected OS secret handles never enter this control-plane result.
        return {
            key: record[key]
            for key in (
                "schema",
                "transfer_id",
                "artifact_id",
                "sha256",
                "length",
                "media_type",
                "provenance",
                "privacy_label",
                "source_scope",
                "destination_scope",
                "destination",
                "recipient",
                "text_conversion",
                "status",
                "source_length",
                "source_sha256",
                "recovered",
            )
        }

    def transfer(
        self,
        *,
        transfer_id: str,
        artifact_id: str,
        content: Any,
        byte_length: int,
        sha256: str,
        media_type: str,
        provenance: Mapping[str, str],
        privacy_label: str,
        source_scope: str,
        destination: str | os.PathLike[str],
        recipient: str,
        text_conversion: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        """Stage, verify and atomically publish a specifically authorized copy.

        Text conversion is opt-in and supports only declared source/destination
        encodings plus an explicit newline policy.  Without it, all bytes are
        copied exactly regardless of media type.
        """
        self._ensure_open()
        record, parts = self._identity_record(
            transfer_id=transfer_id,
            artifact_id=artifact_id,
            byte_length=byte_length,
            sha256=sha256,
            media_type=media_type,
            provenance=provenance,
            privacy_label=privacy_label,
            source_scope=source_scope,
            destination=destination,
            recipient=recipient,
            text_conversion=text_conversion,
        )
        self._authorize(record, "artifact.transfer")

        with self._locked():
            stored = self._read_record(record["transfer_id"])
            if stored is not None and not self._identity_matches(stored, record):
                raise TransferConflict("transfer identity is already bound to different metadata or content")
            retained_usage = self._retained_usage()
            if stored is None:
                if retained_usage + record["length"] + _MAX_RECEIPT_RESERVATION > self.max_retained_bytes:
                    raise TransferResourceLimit("transfer exceeds max_retained_bytes")
                self._write_record(record)
            elif retained_usage > self.max_retained_bytes:
                raise TransferResourceLimit("existing transfer reservations exceed max_retained_bytes")
            else:
                record = stored

            destination_path = self._resolve_destination(parts)
            destination_parent = destination_path.parent
            stage = self._stage_path(destination_parent, record["transfer_id"])
            if not _inside(self.allowed_root, destination_parent):
                raise TransferPathError("staging location escaped its configured destination root")

            destination_present = destination_path.exists()
            if destination_present:
                self._verify_file(destination_path, record)

            conversion = record["text_conversion"]
            if conversion is None:
                if record["status"] == "complete" or destination_present:
                    source_length, source_sha256 = _hash_stream(
                        content, self._chunk_bytes, record["length"]
                    )
                    output_length, output_sha256 = source_length, source_sha256
                else:
                    output_length, output_sha256 = self._write_payload(stage, content, record)
                    source_length, source_sha256 = output_length, output_sha256
            else:
                converted, source_length, source_sha256 = _source_metadata_and_conversion(
                    content,
                    conversion,
                    max_input_bytes=self._max_conversion_input,
                )
                output_length = len(converted)
                output_sha256 = hashlib.sha256(converted).hexdigest()
                if output_length > record["length"] or output_length > self.max_transfer_bytes:
                    raise TransferResourceLimit("converted content exceeds its declared transfer length")
                if record["status"] != "complete" and not destination_present:
                    self._write_payload(stage, (converted,), record)

            self._check_content_identity(
                output_length=output_length,
                output_sha256=output_sha256,
                source_length=source_length,
                source_sha256=source_sha256,
                requested=record,
                stored=stored,
            )

            if record["status"] == "complete":
                if not destination_path.exists():
                    raise TransferIntegrityError("completed transfer destination is missing")
                self._verify_file(destination_path, record)
                return self._public_receipt(record)

            record["source_length"] = source_length
            record["source_sha256"] = source_sha256
            record["status"] = "publishing"
            self._write_record(record)

            # Resolve all components again immediately before publication.  A
            # final object that is a symlink/reparse point or leaves the root
            # is refused rather than followed.
            destination_path = self._resolve_destination(parts)
            destination_parent = destination_path.parent
            if destination_path.exists():
                self._verify_file(destination_path, record)
                try:
                    _check_regular_file(stage, context="incomplete transfer file")
                except FileNotFoundError:
                    pass
                else:
                    if not os.path.samefile(stage, destination_path):
                        raise TransferConflict(
                            "matching destination exists beside a separate incomplete staging file"
                        )
                    stage.unlink()
                _sync_directory(destination_parent)
                return self._finalize(record, recovered=True)

            self._verify_file(stage, record)
            try:
                _publish_no_replace(stage, destination_path)
            except FileExistsError:
                self._verify_file(destination_path, record)
                try:
                    same_file = os.path.samefile(stage, destination_path)
                except OSError:
                    same_file = False
                if not same_file:
                    raise TransferConflict(
                        "matching destination appeared beside a separate incomplete staging file"
                    )
                stage.unlink()
            _sync_directory(destination_parent)
            self._verify_file(destination_path, record)
            return self._finalize(record)

    def inspect(self, transfer_id: str) -> dict[str, Any] | None:
        transfer_id = _identifier(transfer_id, "transfer_id")
        request = {
            "schema": _RECORD_SCHEMA,
            "transfer_id": transfer_id,
            "destination_scope": self.destination_scope,
        }
        with self._locked():
            record = self._read_record(transfer_id)
        self._authorize(record or request, "artifact.inspect")
        return None if record is None else self._public_receipt(record)

    def close(self) -> None:
        with self._mutex:
            self._closed = True

    def __enter__(self) -> "ScopedArtifactTransfer":
        self._ensure_open()
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()


class DisabledClipboardCapability:
    """Explicitly unavailable clipboard operations; never reads human clipboard."""

    backend_id = "clipboard-disabled"

    def describe(self) -> dict[str, Any]:
        reason = "clipboard access is disabled; explicit named-payload plumbing is not provisioned"
        return {
            "backend_id": self.backend_id,
            "operations": {
                "read": {
                    "supported": False,
                    "status": "unavailable",
                    "reason": reason,
                    "default_authorized": False,
                },
                "write": {
                    "supported": False,
                    "status": "unavailable",
                    "reason": reason,
                    "default_authorized": False,
                },
            },
        }

    def read(self, *, payload_id: str, source_scope: str, recipient: str) -> bytes:
        raise ClipboardDenied("clipboard reads are disabled; human clipboard contents are never implicit")

    def write(
        self,
        *,
        payload_id: str,
        content: bytes,
        destination: str,
        recipient: str,
    ) -> None:
        raise ClipboardDenied("clipboard writes are disabled; no automatic cross-environment sharing exists")


__all__ = [
    "ClipboardDenied",
    "DisabledClipboardCapability",
    "ScopedArtifactTransfer",
    "TransferConflict",
    "TransferDenied",
    "TransferError",
    "TransferIntegrityError",
    "TransferPathError",
    "TransferResourceLimit",
]
