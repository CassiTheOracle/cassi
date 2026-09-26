"""Immutable, content-verified spill storage for exact paged field generations.

The store persists compressed ``PageLeaf`` objects without changing a page
root.  A successful ``put`` means both the content-addressed object and its
checksummed placement manifest are visible after a same-volume atomic rename;
callers can publish that receipt only after this method returns.  NVMe/HDD are
operator-provided tier labels, never inferred device-performance claims.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import os
import re
import threading
import uuid
import weakref
from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator


_PAGE_TIER_SCHEMA = "cassifi.page-tier-placement.v1"
_USAGE_SCHEMA = "cassifi.page-tier-usage.v1"
_TIERS = frozenset(("nvme", "hdd"))
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_PAGE_INDEX_RE = re.compile(r"^(?:0|[1-9][0-9]*)$")
_OBJECT_CHUNK_BYTES = 1024 * 1024
_SHARED_RESERVATION_LOCK = threading.RLock()
_SHARED_RESERVATIONS: dict[tuple[int, str, str, str], dict[str, Any]] = {}
_SHARED_RESERVATION_OWNERS: dict[int, set[tuple[int, str, str, str]]] = {}
_SHARED_RESERVATION_OWNER_IDS = itertools.count(1)




class PageTierStoreError(ValueError):
    """Base class for page-tier storage, identity, and durability failures."""


class PageTierMissingError(PageTierStoreError):
    """The exact page placement or object is not present in this tier."""


class PageTierUnavailableError(PageTierStoreError):
    """The requested tier has no operator-registered storage root."""

    def __init__(self, tier: str) -> None:
        self.tier = tier
        super().__init__(f"{tier} page tier is not configured")



class PageTierCorruptError(PageTierStoreError):
    """A placement manifest or content-addressed object failed verification."""


class PageTierStaleError(PageTierStoreError):
    """A stored placement does not match the requested page generation."""


class PageTierCapacityError(PageTierStoreError):
    """A tier's explicit byte limit cannot admit the requested object."""

    def __init__(self, tier: str, requested_bytes: int, used_bytes: int, limit_bytes: int) -> None:
        self.tier = tier
        self.requested_bytes = requested_bytes
        self.used_bytes = used_bytes
        self.limit_bytes = limit_bytes
        super().__init__(
            f"{tier} page tier capacity exceeded: {used_bytes} + "
            f"{requested_bytes} > {limit_bytes} bytes"
        )


@dataclass(frozen=True, slots=True)
class PageTierReceipt:
    """Verified immutable placement identity returned by ``put``/``recover``."""

    root_sha256: str
    page_index: int
    page_version: str
    tier: str
    object_sha256: str
    byte_count: int


@contextmanager
def _process_lock(root: Path) -> Iterator[None]:
    """Serialize cooperating writers across threads and processes on one tier."""

    lock_path = root / ".page-tier-store.lock"
    flags = os.O_RDWR | os.O_CREAT
    fd = os.open(lock_path, flags, 0o600)
    locked = False
    try:
        if os.fstat(fd).st_size == 0:
            os.write(fd, b"\0")
            os.fsync(fd)
        if os.name == "nt":
            import msvcrt

            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
            locked = True
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX)
            locked = True
        yield
    finally:
        if locked:
            if os.name == "nt":
                import msvcrt

                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _fsync_directory(path: Path) -> None:
    """Persist a renamed directory entry where the platform supports it."""

    if os.name == "nt":
        # Windows flushes the file before MoveFileEx/os.replace; Python does
        # not expose a portable directory handle that can be fsynced there.
        return
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _ensure_directory(path: Path) -> None:
    """Create path components and make each newly-created entry durable."""

    missing: list[Path] = []
    probe = path
    while not probe.exists():
        missing.append(probe)
        parent = probe.parent
        if parent == probe:
            break
        probe = parent
    if probe.exists() and not probe.is_dir():
        raise PageTierStoreError(f"page tier path is not a directory: {probe}")
    for directory in reversed(missing):
        try:
            directory.mkdir()
        except FileExistsError:
            if not directory.is_dir():
                raise PageTierStoreError(f"page tier path is not a directory: {directory}")
        _fsync_directory(directory.parent)


def _atomic_write(path: Path, payload: bytes) -> None:
    """Write a private same-volume temporary file, flush, then atomically name it."""

    _ensure_directory(path.parent)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}")
    fd: int | None = None
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            fd = None
            written = handle.write(payload)
            if written != len(payload):
                raise OSError("short page-tier write")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        if fd is not None:
            os.close(fd)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _assert_no_symlink_ancestors(path: Path, boundary: Path) -> None:
    path = Path(path)
    boundary = Path(boundary)
    current = path
    while True:
        if current.is_symlink():
            raise PageTierCorruptError(f"page-tier path must not be a symlink: {current}")
        if current == boundary:
            return
        if current.parent == current:
            raise PageTierCorruptError(f"page-tier path escaped its namespace: {path}")
        current = current.parent


def _atomic_copy_verified(
    source: Path,
    destination: Path,
    object_sha256: str,
    byte_count: int,
) -> None:
    _ensure_directory(destination.parent)
    temporary = destination.with_name(
        f".{destination.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}"
    )
    fd: int | None = None
    digest = hashlib.sha256()
    copied = 0
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with source.open("rb") as source_handle, os.fdopen(fd, "wb") as target_handle:
            fd = None
            while True:
                block = source_handle.read(_OBJECT_CHUNK_BYTES)
                if not block:
                    break
                written = target_handle.write(block)
                if written != len(block):
                    raise OSError("short page-tier migration write")
                digest.update(block)
                copied += written
            target_handle.flush()
            os.fsync(target_handle.fileno())
        if copied != byte_count or digest.hexdigest() != object_sha256:
            raise PageTierCorruptError("legacy page-tier object failed migration verification")
        os.replace(temporary, destination)
        _fsync_directory(destination.parent)
    finally:
        if fd is not None:
            os.close(fd)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass

def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")



def _encode_usage(byte_count: int) -> bytes:
    record: dict[str, Any] = {
        "schema": _USAGE_SCHEMA,
        "used_bytes": byte_count,
    }
    record["checksum_sha256"] = hashlib.sha256(_canonical_json(record)).hexdigest()
    return _canonical_json(record) + b"\n"


def _decode_usage(raw: bytes) -> int:
    try:
        record = json.loads(raw.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PageTierCorruptError("page-tier usage record is invalid JSON") from exc
    if not isinstance(record, dict) or set(record) != {
        "schema",
        "used_bytes",
        "checksum_sha256",
    }:
        raise PageTierCorruptError("page-tier usage record fields are invalid")
    if record["schema"] != _USAGE_SCHEMA:
        raise PageTierCorruptError("page-tier usage schema is invalid")
    byte_count = record["used_bytes"]
    if isinstance(byte_count, bool) or not isinstance(byte_count, int) or byte_count < 0:
        raise PageTierCorruptError("page-tier usage byte count is invalid")
    unsigned = {key: value for key, value in record.items() if key != "checksum_sha256"}
    checksum = hashlib.sha256(_canonical_json(unsigned)).hexdigest()
    if (
        record["checksum_sha256"] != checksum
        or raw != _canonical_json(record) + b"\n"
    ):
        raise PageTierCorruptError("page-tier usage checksum or encoding is invalid")
    return byte_count



def _valid_sha256(value: object) -> bool:
    return isinstance(value, str) and _SHA256_RE.fullmatch(value) is not None


def _checked_sha256(value: object, name: str) -> str:
    if not _valid_sha256(value):
        raise PageTierStoreError(f"{name} must be a lowercase SHA-256 digest")
    return str(value)


def _checked_page_index(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PageTierStoreError("page_index must be a nonnegative integer")
    return value


def _checked_tier(value: object) -> str:
    if value not in _TIERS:
        raise PageTierStoreError("page tier must be 'nvme' or 'hdd'")
    return str(value)


def _shared_reservation_key(
    manager: Any, root: Path, tier: str, object_sha256: str
) -> tuple[int, str, str, str]:
    root_key = os.path.normcase(str(Path(root).resolve()))
    return id(manager), root_key, tier, object_sha256


def _acquire_shared_reservation(
    owner: int,
    key: tuple[int, str, str, str],
    manager: Any,
    tier: str,
    byte_count: int,
    program_id: str | None,
) -> bool:
    with _SHARED_RESERVATION_LOCK:
        entry = _SHARED_RESERVATIONS.get(key)
        if entry is not None:
            if entry["manager"] is not manager:
                raise PageTierStoreError("shared reservation manager identity changed")
            if entry["byte_count"] != byte_count:
                raise PageTierCorruptError("shared page-tier object size changed")
            if owner in entry["owners"]:
                return False
            entry["owners"].add(owner)
        else:
            token = manager.reserve(
                tier,
                byte_count,
                kind="resident",
                program_id=program_id,
            )
            _SHARED_RESERVATIONS[key] = {
                "byte_count": byte_count,
                "manager": manager,
                "token": token,
                "owners": {owner},
            }
        _SHARED_RESERVATION_OWNERS.setdefault(owner, set()).add(key)
        return True


def _release_shared_reservation_locked(
    owner: int, key: tuple[int, str, str, str]
) -> None:
    entry = _SHARED_RESERVATIONS.get(key)
    if entry is None or owner not in entry["owners"]:
        return
    entry["owners"].remove(owner)
    owner_keys = _SHARED_RESERVATION_OWNERS.get(owner)
    if owner_keys is not None:
        owner_keys.discard(key)
        if not owner_keys:
            _SHARED_RESERVATION_OWNERS.pop(owner, None)
    if entry["owners"]:
        return
    _SHARED_RESERVATIONS.pop(key, None)
    token = entry["token"]
    release = getattr(token, "release", None)
    if callable(release):
        release()


def _release_shared_reservation(
    owner: int, key: tuple[int, str, str, str]
) -> None:
    with _SHARED_RESERVATION_LOCK:
        _release_shared_reservation_locked(owner, key)


def _release_shared_reservation_owner(owner: int) -> None:
    with _SHARED_RESERVATION_LOCK:
        for key in tuple(_SHARED_RESERVATION_OWNERS.get(owner, ())):
            _release_shared_reservation_locked(owner, key)


def _hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while True:
            block = handle.read(_OBJECT_CHUNK_BYTES)
            if not block:
                break
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


class PageTierStore:
    """Durable immutable page-object placement on configured NVMe/HDD roots.

    ``limits`` must provide explicit byte limits for every configured tier;
    a residency manager may provide those limits and is charged once for each
    distinct stored object. An omitted root disables only that tier.
    """

    def __init__(
        self,
        nvme_root: str | os.PathLike[str] | None = None,
        hdd_root: str | os.PathLike[str] | None = None,
        *,
        limits: Mapping[str, int] | None = None,
        resource_manager: Any = None,
        program_id: str | None = None,
    ) -> None:
        configured_roots = {"nvme": nvme_root, "hdd": hdd_root}
        if all(root is None for root in configured_roots.values()):
            raise PageTierStoreError("at least one page-tier root must be configured")
        bound_tiers = {
            tier for tier, root in configured_roots.items() if root is not None
        }
        if limits is None:
            manager_limits = getattr(resource_manager, "limits", None)
            if manager_limits is None or any(
                not hasattr(manager_limits, f"{tier}_bytes") for tier in bound_tiers
            ):
                raise PageTierStoreError(
                    "explicit byte limits are required for every configured tier"
                )
            raw_limits = {
                tier: getattr(manager_limits, f"{tier}_bytes") for tier in bound_tiers
            }
        elif isinstance(limits, Mapping):
            raw_limits = dict(limits)
        else:
            raise PageTierStoreError("limits must map configured tiers to byte limits")
        if set(raw_limits) != bound_tiers:
            raise PageTierStoreError(
                "limits must contain exactly the configured page tiers"
            )
        checked_limits: dict[str, int] = {}
        for tier, value in raw_limits.items():
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise PageTierStoreError(f"{tier} limit must be a nonnegative integer")
            checked_limits[tier] = value

        roots: dict[str, Path] = {}
        for tier, raw_root in configured_roots.items():
            if raw_root is None:
                continue
            if not isinstance(raw_root, (str, os.PathLike)):
                raise PageTierStoreError(f"{tier} root must be a filesystem path")
            root = Path(raw_root).expanduser().resolve()
            _ensure_directory(root)
            if not root.is_dir():
                raise PageTierStoreError(f"{tier} root is not a directory: {root}")
            namespace = root / "page-tier"
            if namespace.is_symlink():
                raise PageTierStoreError(f"{tier} page-tier namespace must not be a symlink")
            _ensure_directory(namespace)
            tier_root = namespace / tier
            if tier_root.is_symlink():
                raise PageTierStoreError(f"{tier} page-tier root must not be a symlink")
            _ensure_directory(tier_root)
            for name in ("objects", "placements"):
                path = tier_root / name
                _ensure_directory(path)
                if path.is_symlink():
                    raise PageTierStoreError(f"{tier} page-tier {name} path must not be a symlink")
            roots[tier] = root

        if resource_manager is not None and not callable(
            getattr(resource_manager, "reserve", None)
        ):
            raise PageTierStoreError("resource_manager must provide reserve()")
        self.roots = roots
        self._tiers = tuple(tier for tier in ("nvme", "hdd") if tier in roots)
        self.limits = checked_limits
        self.resource_manager = resource_manager
        self.program_id = None if program_id is None else str(program_id)
        self._lock = threading.RLock()
        self._object_sizes: dict[str, dict[str, int]] = {
            tier: {} for tier in self._tiers
        }
        self._used_bytes: dict[str, int] = {tier: 0 for tier in self._tiers}
        self._corrupt_objects: dict[str, set[str]] = {
            tier: set() for tier in self._tiers
        }
        self._reservation_owner = next(_SHARED_RESERVATION_OWNER_IDS)
        self._reservation_keys: dict[
            str, set[tuple[int, str, str, str]]
        ] = {tier: set() for tier in self._tiers}
        self._reservation_finalizer = weakref.finalize(
            self,
            _release_shared_reservation_owner,
            self._reservation_owner,
        )
        self._receipts: dict[tuple[str, str, int, str], PageTierReceipt] = {}
        self._recovery_errors: list[PageTierStoreError] = []

        if resource_manager is not None:
            register_storage = getattr(resource_manager, "register_storage", None)
            if callable(register_storage):
                for tier in self._tiers:
                    register_storage(tier, roots[tier])

        self.recover()

    @property
    def recovery_errors(self) -> tuple[PageTierStoreError, ...]:
        """Errors found while scanning advisory placements; valid receipts survive."""

        return tuple(self._recovery_errors)

    def _tier_root(self, tier: str) -> Path:
        return self.roots[tier] / "page-tier" / tier

    def _object_root(self, tier: str) -> Path:
        return self._tier_root(tier) / "objects"

    def _placement_root(self, tier: str) -> Path:
        return self._tier_root(tier) / "placements"

    def _usage_path(self, tier: str) -> Path:
        return self._tier_root(tier) / "usage.json"

    def _read_usage(self, tier: str) -> int:
        path = self._usage_path(tier)
        if path.is_symlink():
            raise PageTierCorruptError("page-tier usage record must not be a symlink")
        try:
            return _decode_usage(path.read_bytes())
        except FileNotFoundError as exc:
            raise PageTierMissingError("page-tier usage record is missing; recover required") from exc
        except OSError as exc:
            raise PageTierCorruptError("cannot read page-tier usage record") from exc

    def _write_usage(self, tier: str, byte_count: int) -> None:
        path = self._usage_path(tier)
        if path.is_symlink():
            raise PageTierCorruptError("page-tier usage record must not be a symlink")
        _atomic_write(path, _encode_usage(byte_count))


    def _object_path(self, tier: str, object_sha256: str) -> Path:
        return self._object_root(tier) / object_sha256[:2] / object_sha256

    def _manifest_path(
        self, tier: str, root_sha256: str, page_index: int, page_version: str
    ) -> Path:
        return (
            self._placement_root(tier)
            / root_sha256
            / str(page_index)
            / f"{page_version}.json"
        )

    def _require_bound_tier(self, tier: str) -> str:
        tier = _checked_tier(tier)
        if tier not in self.roots:
            raise PageTierUnavailableError(tier)
        return tier

    def _reservation_key(
        self, tier: str, object_sha256: str
    ) -> tuple[int, str, str, str] | None:
        if self.resource_manager is None:
            return None
        return _shared_reservation_key(
            self.resource_manager,
            self.roots[tier],
            tier,
            object_sha256,
        )

    def _acquire_reservation(
        self, tier: str, object_sha256: str, byte_count: int
    ) -> tuple[tuple[int, str, str, str] | None, bool]:
        key = self._reservation_key(tier, object_sha256)
        if key is None or byte_count <= 0:
            return key, False
        added = _acquire_shared_reservation(
            self._reservation_owner,
            key,
            self.resource_manager,
            tier,
            byte_count,
            self.program_id,
        )
        if added:
            self._reservation_keys[tier].add(key)
        return key, added

    def _release_reservation(
        self, tier: str, key: tuple[int, str, str, str] | None
    ) -> None:
        if key is not None and key in self._reservation_keys[tier]:
            _release_shared_reservation(self._reservation_owner, key)
            self._reservation_keys[tier].discard(key)

    def _replace_inventory(self, tier: str, discovered: dict[str, int]) -> None:
        total = sum(discovered.values())
        if total > self.limits[tier]:
            raise PageTierCapacityError(tier, total, 0, self.limits[tier])

        known = self._object_sizes[tier]
        old_keys = self._reservation_keys[tier]
        new_keys: set[tuple[int, str, str, str]] = set()
        acquired: list[tuple[int, str, str, str]] = []
        try:
            if self.resource_manager is not None:
                for digest, size in discovered.items():
                    if size <= 0 or digest in self._corrupt_objects[tier]:
                        continue
                    key = self._reservation_key(tier, digest)
                    if key is None:
                        continue
                    if key not in old_keys:
                        added = _acquire_shared_reservation(
                            self._reservation_owner,
                            key,
                            self.resource_manager,
                            tier,
                            size,
                            self.program_id,
                        )
                        if added:
                            acquired.append(key)
                    new_keys.add(key)
        except BaseException:
            for key in acquired:
                _release_shared_reservation(self._reservation_owner, key)
            raise

        for key in old_keys - new_keys:
            _release_shared_reservation(self._reservation_owner, key)
        old_keys.clear()
        old_keys.update(new_keys)
        known.clear()
        known.update(discovered)
        self._used_bytes[tier] = total

    def _verify_object_file(
        self, tier: str, object_sha256: str, byte_count: int
    ) -> bool:
        path = self._object_path(tier, object_sha256)
        _assert_no_symlink_ancestors(path, self.roots[tier])
        if path.is_symlink():
            raise PageTierCorruptError("page-tier object path must not be a symlink")
        if not path.exists():
            return False
        if not path.is_file():
            raise PageTierCorruptError("page-tier object path is not a file")
        try:
            digest, actual_bytes = _hash_file(path)
        except OSError as exc:
            raise PageTierMissingError(
                f"cannot verify {tier} page-tier object {object_sha256}"
            ) from exc
        if digest != object_sha256 or actual_bytes != byte_count:
            raise PageTierCorruptError(
                "existing content-addressed page-tier object failed verification"
            )
        return True

    def _register_object(
        self,
        tier: str,
        object_sha256: str,
        byte_count: int,
        *,
        already_counted: bool = False,
    ) -> None:
        used = self._used_bytes[tier]
        new_used = used if already_counted else used + byte_count
        if new_used > self.limits[tier]:
            raise PageTierCapacityError(tier, byte_count, used, self.limits[tier])
        key, added = self._acquire_reservation(tier, object_sha256, byte_count)
        try:
            if not already_counted:
                self._write_usage(tier, new_used)
        except BaseException:
            if added:
                self._release_reservation(tier, key)
            raise
        self._object_sizes[tier][object_sha256] = byte_count
        self._used_bytes[tier] = new_used

    def _unregister_object(self, tier: str, object_sha256: str, byte_count: int) -> None:
        if self._object_sizes[tier].get(object_sha256) != byte_count:
            raise PageTierCorruptError("page-tier inventory removal size mismatches")
        new_used = self._used_bytes[tier] - byte_count
        if new_used < 0:
            raise PageTierCorruptError("page-tier usage counter would become negative")
        self._write_usage(tier, new_used)
        self._object_sizes[tier].pop(object_sha256)
        self._used_bytes[tier] = new_used
        self._release_reservation(tier, self._reservation_key(tier, object_sha256))

    def _ensure_object(
        self, tier: str, data: bytes, object_sha256: str
    ) -> None:
        byte_count = len(data)
        known_size = self._object_sizes[tier].get(object_sha256)
        if known_size is not None and known_size != byte_count:
            raise PageTierCorruptError(
                "existing content-addressed object has a different byte count"
            )
        exists = self._verify_object_file(tier, object_sha256, byte_count)
        newly_registered = known_size is None
        if newly_registered:
            self._register_object(
                tier,
                object_sha256,
                byte_count,
                already_counted=exists,
            )
        if exists:
            return

        object_path = self._object_path(tier, object_sha256)
        try:
            _atomic_write(object_path, data)
        except BaseException:
            if newly_registered and not object_path.exists() and not object_path.is_symlink():
                try:
                    self._unregister_object(tier, object_sha256, byte_count)
                except BaseException:
                    pass
            raise

    @staticmethod
    def _remove_temporary(path: Path) -> bool:
        if ".tmp-" not in path.name:
            return False
        if path.is_symlink() or not path.is_file():
            raise PageTierCorruptError(f"invalid temporary page-tier entry: {path}")
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return True

    def _scan_objects(self, tier: str) -> dict[str, int]:
        object_root = self._object_root(tier)
        _assert_no_symlink_ancestors(object_root, self.roots[tier])
        discovered: dict[str, int] = {}
        corrupt: set[str] = set()
        for shard in object_root.iterdir():
            if self._remove_temporary(shard):
                continue
            if shard.is_symlink() or not shard.is_dir() or not re.fullmatch(
                r"[0-9a-f]{2}", shard.name
            ):
                raise PageTierCorruptError(f"invalid object shard: {shard}")
            for path in shard.iterdir():
                if self._remove_temporary(path):
                    continue
                if (
                    path.is_symlink()
                    or not path.is_file()
                    or not _valid_sha256(path.name)
                    or path.name[:2] != shard.name
                ):
                    raise PageTierCorruptError(f"invalid page-tier object path: {path}")
                try:
                    digest, size = _hash_file(path)
                except OSError:
                    try:
                        size = int(path.stat().st_size)
                    except OSError as exc:
                        raise PageTierMissingError(
                            f"cannot inspect {tier} page-tier object {path.name}"
                        ) from exc
                    corrupt.add(path.name)
                else:
                    if digest != path.name or size <= 0:
                        corrupt.add(path.name)
                discovered[path.name] = size
        self._corrupt_objects[tier] = corrupt
        return discovered

    def _receipt_from_record(self, record: Mapping[str, Any]) -> PageTierReceipt:
        required = {
            "schema",
            "tier",
            "root_sha256",
            "page_index",
            "page_version",
            "object_sha256",
            "byte_count",
            "checksum_sha256",
        }
        if set(record) != required or record.get("schema") != _PAGE_TIER_SCHEMA:
            raise PageTierCorruptError("page-tier manifest schema or fields are invalid")
        unsigned = {key: record[key] for key in record if key != "checksum_sha256"}
        checksum = hashlib.sha256(_canonical_json(unsigned)).hexdigest()
        if record.get("checksum_sha256") != checksum:
            raise PageTierCorruptError("page-tier manifest checksum mismatches")
        try:
            tier = _checked_tier(record["tier"])
            root_sha256 = _checked_sha256(record["root_sha256"], "root_sha256")
            page_index = _checked_page_index(record["page_index"])
            page_version = _checked_sha256(record["page_version"], "page_version")
            object_sha256 = _checked_sha256(record["object_sha256"], "object_sha256")
        except PageTierStoreError as exc:
            raise PageTierCorruptError("page-tier manifest identity is invalid") from exc
        byte_count = record["byte_count"]
        if isinstance(byte_count, bool) or not isinstance(byte_count, int) or byte_count <= 0:
            raise PageTierCorruptError("page-tier manifest byte count is invalid")
        return PageTierReceipt(
            root_sha256=root_sha256,
            page_index=page_index,
            page_version=page_version,
            tier=tier,
            object_sha256=object_sha256,
            byte_count=byte_count,
        )

    def _read_manifest(
        self,
        path: Path,
        tier: str,
        *,
        placement_root: Path | None = None,
    ) -> PageTierReceipt:
        boundary = self.roots[tier]
        if placement_root is not None:
            boundary = placement_root.parent.parent
        _assert_no_symlink_ancestors(path, boundary)
        try:
            raw = path.read_bytes()
        except FileNotFoundError as exc:
            raise PageTierMissingError(f"missing {tier} page-tier placement manifest") from exc
        except OSError as exc:
            raise PageTierCorruptError(f"cannot read {tier} page-tier manifest") from exc
        try:
            record = json.loads(raw.decode("ascii"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PageTierCorruptError("page-tier manifest is not canonical JSON") from exc
        if not isinstance(record, dict):
            raise PageTierCorruptError("page-tier manifest must be an object")
        receipt = self._receipt_from_record(record)
        if raw != _canonical_json(record) + b"\n":
            raise PageTierCorruptError("page-tier manifest encoding is not canonical")
        if receipt.tier != tier:
            raise PageTierCorruptError("page-tier manifest is stored under the wrong tier")
        if placement_root is None:
            expected_path = self._manifest_path(
                tier, receipt.root_sha256, receipt.page_index, receipt.page_version
            )
        else:
            expected_path = (
                placement_root
                / receipt.root_sha256
                / str(receipt.page_index)
                / f"{receipt.page_version}.json"
            )
        if path != expected_path:
            raise PageTierCorruptError("page-tier manifest path mismatches its identity")
        return receipt

    def _read_object(self, receipt: PageTierReceipt) -> bytes:
        path = self._object_path(receipt.tier, receipt.object_sha256)
        _assert_no_symlink_ancestors(path, self.roots[receipt.tier])
        try:
            data = path.read_bytes()
        except FileNotFoundError as exc:
            raise PageTierMissingError(
                f"missing {receipt.tier} page-tier object {receipt.object_sha256}"
            ) from exc
        except OSError as exc:
            raise PageTierCorruptError(
                f"cannot read {receipt.tier} page-tier object {receipt.object_sha256}"
            ) from exc
        if len(data) != receipt.byte_count:
            raise PageTierCorruptError("page-tier object byte count mismatches receipt")
        if hashlib.sha256(data).hexdigest() != receipt.object_sha256:
            raise PageTierCorruptError("page-tier object SHA-256 mismatches receipt")
        return data
    def _migrate_legacy_tier(self, legacy_root: Path, tier: str) -> bool:
        placement_root = legacy_root / "placements"
        if placement_root.is_symlink():
            self._recovery_errors.append(
                PageTierCorruptError("legacy page-tier placements path must not be a symlink")
            )
            return False
        if not placement_root.exists():
            return True
        if not placement_root.is_dir():
            self._recovery_errors.append(
                PageTierCorruptError("legacy page-tier placements path is not a directory")
            )
            return False

        legacy_objects = legacy_root / "objects"
        if legacy_objects.is_symlink():
            self._recovery_errors.append(
                PageTierCorruptError("legacy page-tier objects path must not be a symlink")
            )
            return False
        complete = True
        for root_path in sorted(placement_root.iterdir()):
            if (
                root_path.is_symlink()
                or not root_path.is_dir()
                or not _valid_sha256(root_path.name)
            ):
                self._recovery_errors.append(
                    PageTierCorruptError(f"invalid legacy placement root: {root_path}")
                )
                complete = False
                continue
            for page_path in sorted(root_path.iterdir()):
                if (
                    page_path.is_symlink()
                    or not page_path.is_dir()
                    or _PAGE_INDEX_RE.fullmatch(page_path.name) is None
                ):
                    self._recovery_errors.append(
                        PageTierCorruptError(f"invalid legacy placement page: {page_path}")
                    )
                    complete = False
                    continue
                for path in sorted(page_path.iterdir()):
                    if ".tmp-" in path.name:
                        continue
                    if (
                        path.is_symlink()
                        or not path.is_file()
                        or path.suffix != ".json"
                        or not _valid_sha256(path.stem)
                    ):
                        self._recovery_errors.append(
                            PageTierCorruptError(f"invalid legacy manifest path: {path}")
                        )
                        complete = False
                        continue
                    try:
                        _assert_no_symlink_ancestors(path, placement_root)
                        raw = path.read_bytes()
                        record = json.loads(raw.decode("ascii"))
                        if not isinstance(record, dict):
                            raise PageTierCorruptError(
                                "legacy page-tier manifest must be an object"
                            )
                        record_tier = _checked_tier(record.get("tier"))
                        if record_tier != tier:
                            continue
                        receipt = self._read_manifest(
                            path, tier, placement_root=placement_root
                        )
                        source_object = (
                            legacy_objects
                            / receipt.object_sha256[:2]
                            / receipt.object_sha256
                        )
                        destination_object = self._object_path(
                            tier, receipt.object_sha256
                        )
                        _assert_no_symlink_ancestors(
                            destination_object, self.roots[tier]
                        )
                        if destination_object.exists() or destination_object.is_symlink():
                            if destination_object.is_symlink():
                                raise PageTierCorruptError(
                                    "migrated page-tier object must not be a symlink"
                                )
                            self._verify_object_file(
                                tier, receipt.object_sha256, receipt.byte_count
                            )
                        else:
                            _assert_no_symlink_ancestors(source_object, legacy_objects)
                            if not source_object.is_file():
                                raise PageTierMissingError(
                                    "legacy placement references a missing object"
                                )
                            _atomic_copy_verified(
                                source_object,
                                destination_object,
                                receipt.object_sha256,
                                receipt.byte_count,
                            )

                        destination_manifest = self._manifest_path(
                            tier,
                            receipt.root_sha256,
                            receipt.page_index,
                            receipt.page_version,
                        )
                        _assert_no_symlink_ancestors(
                            destination_manifest, self.roots[tier]
                        )
                        if (
                            destination_manifest.exists()
                            or destination_manifest.is_symlink()
                        ):
                            existing = self._read_manifest(destination_manifest, tier)
                            if existing != receipt:
                                raise PageTierStaleError(
                                    "legacy placement conflicts with namespaced placement"
                                )
                        else:
                            _atomic_write(destination_manifest, raw)
                    except (PageTierStoreError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                        if isinstance(exc, PageTierStoreError):
                            error = exc
                        else:
                            error = PageTierCorruptError(
                                f"cannot migrate legacy page-tier manifest: {path}"
                            )
                        self._recovery_errors.append(error)
                        complete = False
        return complete

    def _migrate_legacy_layout(self) -> None:
        source_roots = tuple(dict.fromkeys(self.roots[tier] for tier in self._tiers))
        for source_root in source_roots:
            legacy_root = source_root / "page-tier"
            legacy_objects = legacy_root / "objects"
            legacy_placements = legacy_root / "placements"
            if not any(
                path.exists() or path.is_symlink()
                for path in (legacy_objects, legacy_placements)
            ):
                continue
            marker_suffix = hashlib.sha256(
                os.path.normcase(str(legacy_root)).encode("utf-8")
            ).hexdigest()
            try:
                _assert_no_symlink_ancestors(legacy_root, source_root)
                with _process_lock(legacy_root):
                    for tier in self._tiers:
                        marker = (
                            self._tier_root(tier)
                            / f".legacy-layout-v1-{marker_suffix}"
                        )
                        _assert_no_symlink_ancestors(marker, self.roots[tier])
                        if marker.exists():
                            if marker.read_bytes() != b"page-tier-legacy-v1\n":
                                raise PageTierCorruptError(
                                    "legacy page-tier migration marker is invalid"
                                )
                            continue
                        with _process_lock(self._tier_root(tier)):
                            if self._migrate_legacy_tier(legacy_root, tier):
                                _atomic_write(marker, b"page-tier-legacy-v1\n")
            except (PageTierStoreError, OSError) as exc:
                if isinstance(exc, PageTierStoreError):
                    self._recovery_errors.append(exc)
                else:
                    self._recovery_errors.append(
                        PageTierCorruptError(
                            f"cannot migrate legacy page-tier layout at {legacy_root}"
                        )
                    )


    def _read_all_manifests(self, tier: str) -> list[PageTierReceipt]:
        placement_root = self._placement_root(tier)
        _assert_no_symlink_ancestors(placement_root, self.roots[tier])
        receipts: list[PageTierReceipt] = []
        for root_path in placement_root.iterdir():
            if self._remove_temporary(root_path):
                continue
            if (
                root_path.is_symlink()
                or not root_path.is_dir()
                or not _valid_sha256(root_path.name)
            ):
                self._recovery_errors.append(
                    PageTierCorruptError(f"invalid placement root path: {root_path}")
                )
                continue
            for page_path in root_path.iterdir():
                if self._remove_temporary(page_path):
                    continue
                if (
                    page_path.is_symlink()
                    or not page_path.is_dir()
                    or _PAGE_INDEX_RE.fullmatch(page_path.name) is None
                ):
                    self._recovery_errors.append(
                        PageTierCorruptError(f"invalid placement page path: {page_path}")
                    )
                    continue
                for path in page_path.iterdir():
                    if self._remove_temporary(path):
                        continue
                    if (
                        path.is_symlink()
                        or not path.is_file()
                        or path.suffix != ".json"
                        or not _valid_sha256(path.stem)
                    ):
                        self._recovery_errors.append(
                            PageTierCorruptError(
                                f"invalid placement manifest path: {path}"
                            )
                        )
                        continue
                    try:
                        receipt = self._read_manifest(path, tier)
                        if (
                            receipt.root_sha256 != root_path.name
                            or receipt.page_index != int(page_path.name)
                            or f"{receipt.page_version}.json" != path.name
                        ):
                            raise PageTierCorruptError(
                                "page-tier manifest path does not match its identity"
                            )
                        object_size = self._object_sizes[tier].get(
                            receipt.object_sha256
                        )
                        if object_size is None:
                            raise PageTierMissingError(
                                "placement references missing object "
                                f"{receipt.object_sha256}"
                            )
                        if object_size != receipt.byte_count:
                            raise PageTierCorruptError(
                                "page-tier manifest byte count mismatches object"
                            )
                        if receipt.object_sha256 in self._corrupt_objects[tier]:
                            raise PageTierCorruptError(
                                "placement references a corrupt page-tier object"
                            )
                    except PageTierStoreError as exc:
                        self._recovery_errors.append(exc)
                        continue
                    receipts.append(receipt)
        return receipts

    def recover(self) -> tuple[PageTierReceipt, ...]:
        """Rebuild and verify placements from checksummed manifests after restart.

        Malformed or corrupt manifests are omitted from the recovered receipts
        and exposed through ``recovery_errors`` so canonical backing can remain
        available. Unreferenced immutable objects are retained and charged
        because they may be from an interrupted object-before-manifest write.
        """

        recovered: list[PageTierReceipt] = []
        with self._lock:
            self._recovery_errors.clear()
            self._receipts.clear()
            self._migrate_legacy_layout()
            for tier in self._tiers:
                with _process_lock(self._tier_root(tier)):
                    discovered = self._scan_objects(tier)
                    self._replace_inventory(tier, discovered)
                    for receipt in self._read_all_manifests(tier):
                        key = (
                            tier,
                            receipt.root_sha256,
                            receipt.page_index,
                            receipt.page_version,
                        )
                        prior = self._receipts.get(key)
                        if prior is not None and prior != receipt:
                            raise PageTierCorruptError(
                                "duplicate page-tier placement has conflicting identity"
                            )
                        self._receipts[key] = receipt
                        recovered.append(receipt)
                    self._write_usage(tier, self._used_bytes[tier])
        return tuple(sorted(
            recovered,
            key=lambda receipt: (
                receipt.tier,
                receipt.root_sha256,
                receipt.page_index,
                receipt.page_version,
            ),
        ))

    def lookup(
        self,
        tier: str,
        *,
        root_sha256: str,
        page_index: int,
        page_version: str,
        object_sha256: str,
    ) -> PageTierReceipt | None:
        """Find a receipt only for the exact requested root/page generation.

        Returns ``None`` only when that exact placement manifest is absent.
        Corrupt manifests, stale identities, and unbacked manifests raise a
        typed ``PageTierStoreError`` so the caller can choose canonical backing.
        """

        tier = self._require_bound_tier(tier)
        root_sha256 = _checked_sha256(root_sha256, "root_sha256")
        page_index = _checked_page_index(page_index)
        page_version = _checked_sha256(page_version, "page_version")
        object_sha256 = _checked_sha256(object_sha256, "object_sha256")
        path = self._manifest_path(tier, root_sha256, page_index, page_version)
        _assert_no_symlink_ancestors(path, self.roots[tier])
        if not path.exists():
            return None
        receipt = self._read_manifest(path, tier)
        if (
            receipt.root_sha256 != root_sha256
            or receipt.page_index != page_index
            or receipt.page_version != page_version
            or receipt.object_sha256 != object_sha256
        ):
            raise PageTierStaleError("page-tier placement does not match requested page")
        object_path = self._object_path(tier, receipt.object_sha256)
        _assert_no_symlink_ancestors(object_path, self.roots[tier])
        if object_path.is_symlink() or not object_path.is_file():
            raise PageTierMissingError("page-tier placement object is missing")
        return receipt

    def get(self, receipt: PageTierReceipt) -> bytes:
        """Reload and verify one exact receipt, including its manifest and bytes."""

        if not isinstance(receipt, PageTierReceipt):
            raise PageTierStoreError("get requires a PageTierReceipt")
        tier = self._require_bound_tier(receipt.tier)
        root_sha256 = _checked_sha256(receipt.root_sha256, "root_sha256")
        page_index = _checked_page_index(receipt.page_index)
        page_version = _checked_sha256(receipt.page_version, "page_version")
        object_sha256 = _checked_sha256(receipt.object_sha256, "object_sha256")
        if (
            isinstance(receipt.byte_count, bool)
            or not isinstance(receipt.byte_count, int)
            or receipt.byte_count <= 0
        ):
            raise PageTierStoreError("receipt byte_count must be positive")
        path = self._manifest_path(tier, root_sha256, page_index, page_version)
        stored = self._read_manifest(path, tier)
        if stored != receipt:
            raise PageTierStaleError("stored placement does not match receipt")
        return self._read_object(receipt)

    def put(
        self,
        tier: str,
        data: bytes,
        *,
        root_sha256: str,
        page_index: int,
        page_version: str,
        object_sha256: str,
        expected_bytes: int | None = None,
    ) -> PageTierReceipt:
        """Persist exact compressed page bytes and atomically publish a receipt.

        ``page_version`` is the ``PageTree.digest(index)``/``PageLeaf.digest``;
        ``object_sha256`` is the distinct digest of the compressed bytes.  The
        call does not mutate or evict the source or alter the committed root.
        """

        tier = self._require_bound_tier(tier)
        root_sha256 = _checked_sha256(root_sha256, "root_sha256")
        page_index = _checked_page_index(page_index)
        page_version = _checked_sha256(page_version, "page_version")
        object_sha256 = _checked_sha256(object_sha256, "object_sha256")
        if not isinstance(data, bytes) or not data:
            raise PageTierStoreError("page object data must be nonempty bytes")
        byte_count = len(data)
        if expected_bytes is not None and (
            isinstance(expected_bytes, bool)
            or not isinstance(expected_bytes, int)
            or expected_bytes <= 0
            or expected_bytes != byte_count
        ):
            raise PageTierStoreError("page object byte count does not match expected_bytes")
        if hashlib.sha256(data).hexdigest() != object_sha256:
            raise PageTierStoreError("page object digest does not match data")

        receipt = PageTierReceipt(
            root_sha256=root_sha256,
            page_index=page_index,
            page_version=page_version,
            tier=tier,
            object_sha256=object_sha256,
            byte_count=byte_count,
        )
        manifest_path = self._manifest_path(tier, root_sha256, page_index, page_version)
        with self._lock:
            with _process_lock(self._tier_root(tier)):
                self._used_bytes[tier] = self._read_usage(tier)
                if self._used_bytes[tier] > self.limits[tier]:
                    raise PageTierCapacityError(
                        tier, 0, self._used_bytes[tier], self.limits[tier]
                    )
                existing: PageTierReceipt | None = None
                _assert_no_symlink_ancestors(manifest_path, self.roots[tier])
                if manifest_path.exists() or manifest_path.is_symlink():
                    existing = self._read_manifest(manifest_path, tier)
                    if existing != receipt:
                        raise PageTierStaleError(
                            "page root/index/version already has another placement"
                        )
                self._ensure_object(tier, data, object_sha256)
                if existing is not None:
                    self._receipts[
                        (tier, root_sha256, page_index, page_version)
                    ] = existing
                    return existing
                record: dict[str, Any] = {
                    "schema": _PAGE_TIER_SCHEMA,
                    "tier": tier,
                    "root_sha256": root_sha256,
                    "page_index": page_index,
                    "page_version": page_version,
                    "object_sha256": object_sha256,
                    "byte_count": byte_count,
                }
                record["checksum_sha256"] = hashlib.sha256(
                    _canonical_json(record)
                ).hexdigest()
                manifest_bytes = _canonical_json(record) + b"\n"
                _atomic_write(manifest_path, manifest_bytes)
                self._receipts[(tier, root_sha256, page_index, page_version)] = receipt
                return receipt

    def used_bytes(self, tier: str) -> int:
        """Return unique verified object bytes charged against a tier limit."""

        tier = self._require_bound_tier(tier)
        with self._lock:
            self._used_bytes[tier] = self._read_usage(tier)
            return self._used_bytes[tier]
