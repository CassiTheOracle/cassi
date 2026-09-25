"""Fixed physical resource policy for the one owner-operated regional field.

Reservations are operational state, not learned memory.  Scratch and transfer
buffers consume their physical tier as well as their independent sublimit.
Nothing in this module advances field time or chooses a scientific objective.
"""
from __future__ import annotations

import ctypes
import hashlib
import math
import os
import shutil
import threading
import time
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from typing import Any, Mapping, Sequence


RESOURCE_SCHEMA = "cassifi.elastic-resources.v1"
VRAM_DEVICE_SCHEMA = "cassifi.vram-devices.v1"
MAX_RETIRED_TRANSFERS = 128
MAX_PHYSICAL_WAIT_HOPS = 64
MAX_PHYSICAL_WAIT_PREREQUISITE_LEND = 8
MAX_PHYSICAL_WAIT_OBLIGATIONS = 256
KINDS = ("resident", "scratch", "transfer")
TIERS = ("ram", "vram", "storage", "cpu_cache", "nvme", "hdd")
@dataclass(frozen=True, slots=True)
class PhysicalWaitObligation:
    """Typed, bounded continuation state for an unmet physical prerequisite."""

    activity_id: str
    continuation_id: str | None
    retry_id: str
    holding_activity_id: str | None
    priority: str
    requested_resources: Mapping[str, int]
    resource: Mapping[str, Any]
    prerequisite_activity_ids: tuple[str, ...]
    blocked_by_activity_ids: tuple[str, ...]
    cycle_activity_ids: tuple[str, ...]
    state: str
    reason: str
    opened_at_ns: int
    updated_at_ns: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": "physical-resource-prerequisite",
            "activity_id": self.activity_id,
            "continuation_id": self.continuation_id,
            "retry_id": self.retry_id,
            "holding_activity_id": self.holding_activity_id,
            "priority": self.priority,
            "requested_resources": dict(self.requested_resources),
            "resource": dict(self.resource),
            "prerequisite_activity_ids": list(self.prerequisite_activity_ids),
            "blocked_by_activity_ids": list(self.blocked_by_activity_ids),
            "cycle_activity_ids": list(self.cycle_activity_ids),
            "state": self.state,
            "reason": self.reason,
            "opened_at_ns": self.opened_at_ns,
            "updated_at_ns": self.updated_at_ns,
        }


class ResourceWait(ValueError):
    """An operation can retain its continuation until resources are available."""

    def __init__(
        self, tier: str, requested: int, available: int, *,
        kind: str = "resident", reason: str = "capacity",
        device: str | None = None,
        continuation_id: str | None = None, retry_id: str | None = None,
        obligation: PhysicalWaitObligation | None = None,
    ) -> None:
        self.tier = tier
        self.requested = int(requested)
        self.available = max(0, int(available))
        self.kind = kind
        self.reason = reason
        self.device = device
        self.continuation_id = continuation_id
        self.retry_id = retry_id or continuation_id
        self.obligation = obligation
        super().__init__(f"{tier} {kind} needs {requested} bytes; "
                         f"{self.available} available ({reason})")

    def as_dict(self) -> dict[str, Any]:
        result = {"schema": RESOURCE_SCHEMA, "status": "resource-wait",
                  "tier": self.tier, "kind": self.kind, "reason": self.reason,
                  "device": self.device,
                  "requested_bytes": self.requested,
                  "available_bytes": self.available,
                  "continuation_id": self.continuation_id,
                  "retry_id": self.retry_id}
        if self.obligation is not None:
            result["obligation"] = self.obligation.as_dict()
        return result


# The historical single-device account.  Reservations that name no device
# charge this key; it is a hard capacity identity only once the operator has
# explicitly registered that device's capacity.
DEFAULT_VRAM_DEVICE = "0"
# The durable reservation rows this module consumes.  A different version is
# refused loudly instead of reinterpreted.
JOURNAL_RESERVATION_SCHEMA = "cassi.field-brain.resource-reservation.v1"


def _tier_limit_name(tier: str) -> str:
    return f"{tier}_bytes"


def _storage_volume_identity(path: Path) -> str | None:
    """Return a real filesystem-volume identity, or ``None`` if unavailable."""
    probe = path
    try:
        while not probe.exists() and probe.parent != probe:
            probe = probe.parent
    except OSError:
        pass
    if os.name == "nt":
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            volume_path_name = kernel32.GetVolumePathNameW
            volume_path_name.argtypes = [
                ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32,
            ]
            volume_path_name.restype = ctypes.c_int
            mount = ctypes.create_unicode_buffer(32768)
            if not volume_path_name(str(probe), mount, len(mount)):
                return None
            mount_path = mount.value
            if not mount_path.endswith("\\"):
                mount_path += "\\"

            volume_name = kernel32.GetVolumeNameForVolumeMountPointW
            volume_name.argtypes = [
                ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32,
            ]
            volume_name.restype = ctypes.c_int
            volume = ctypes.create_unicode_buffer(128)
            if volume_name(mount_path, volume, len(volume)):
                return f"windows-volume:{volume.value.rstrip(chr(92)).casefold()}"

            volume_information = kernel32.GetVolumeInformationW
            volume_information.argtypes = [
                ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32,
                ctypes.POINTER(ctypes.c_uint32),
                ctypes.POINTER(ctypes.c_uint32),
                ctypes.POINTER(ctypes.c_uint32),
                ctypes.c_wchar_p, ctypes.c_uint32,
            ]
            volume_information.restype = ctypes.c_int
            serial = ctypes.c_uint32()
            if volume_information(
                mount_path, None, 0, ctypes.byref(serial), None, None, None, 0,
            ):
                return f"windows-serial:{serial.value:08x}"
        except (AttributeError, OSError, TypeError, ValueError):
            return None
        return None
    try:
        return f"filesystem-device:{probe.stat().st_dev}"
    except OSError:
        return None



def _device_key(device: str | int | None) -> str | None:
    """Normalize a physical-device identity for vram accounting.

    ``None`` means the historical default device.  A device key is a hard
    capacity identity; locality hints never feed this value.
    """

    if device is None:
        return DEFAULT_VRAM_DEVICE
    if isinstance(device, bool) or not isinstance(device, (int, str)):
        raise ValueError("vram device must be a nonnegative integer or bounded text")
    if isinstance(device, int):
        if device < 0:
            raise ValueError("vram device index must be nonnegative")
        return str(device)
    if not device or len(device.encode("utf-8")) > 64 or any(
        ord(character) < 32 for character in device
    ):
        raise ValueError("vram device must be bounded nonempty text")
    return device


def _validated_reservation(row: Any) -> Mapping[str, Any]:
    """Validate a journal reservation row against its declared schema version.

    Versioned validation keeps persisted rows backward-compatible: version v1
    continues to mean exactly the fields this module reads, and an
    unrecognised version raises instead of being silently reinterpreted.
    """

    if not isinstance(row, Mapping):
        raise ValueError("journal reservation must be an object")
    schema = row.get("schema")
    if not isinstance(schema, str) or not schema.startswith(
        "cassi.field-brain.resource-reservation."
    ):
        raise ValueError("journal reservation schema is unrecognised")
    version = schema[len("cassi.field-brain.resource-reservation."):]
    if version != "v1":
        raise ValueError(
            f"journal reservation schema version {version!r} requires a "
            "matching consumer; refusing silent reinterpretation"
        )
    for name in ("reservation_id", "cap", "lease"):
        if name not in row:
            raise ValueError(f"journal reservation is missing {name}")
    lease = row["lease"]
    if not isinstance(lease, Mapping) or not isinstance(lease.get("fence"), int):
        raise ValueError("journal reservation lease fence is invalid")
    if not isinstance(row["cap"], Mapping):
        raise ValueError("journal reservation cap must be an object")
    return row



@dataclass(frozen=True, slots=True)
class ResourceLimits:
    ram_bytes: int = 64 * 1024 * 1024
    vram_bytes: int = 64 * 1024 * 1024
    storage_bytes: int = 1024 * 1024 * 1024
    cpu_cache_bytes: int = 4 * 1024 * 1024
    nvme_bytes: int = 1024 * 1024 * 1024
    hdd_bytes: int = 1024 * 1024 * 1024
    scratch_bytes: int = 16 * 1024 * 1024
    transfer_bytes: int = 8 * 1024 * 1024
    ram_headroom_bytes: int = 256 * 1024 * 1024
    vram_headroom_bytes: int = 512 * 1024 * 1024
    max_logical_bytes: int = 1024 * 1024 * 1024
    auto_grow: bool = True
    device: str = "cpu"
    high_watermark: float = 0.9
    low_watermark: float = 0.75

    def __post_init__(self) -> None:
        for item in fields(self):
            if not item.name.endswith("_bytes"):
                continue
            value = getattr(self, item.name)
            minimum = 0 if "headroom" in item.name else 1
            if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
                raise ValueError(f"{item.name} must be an integer >= {minimum}")
        if not isinstance(self.auto_grow, bool):
            raise ValueError("auto_grow must be boolean")
        if self.device not in {"cpu", "cuda", "auto"}:
            raise ValueError("device must be cpu, cuda, or auto")
        for name in ("low_watermark", "high_watermark"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        if not 0 < self.low_watermark < self.high_watermark <= 1:
            raise ValueError("watermarks require 0 < low < high <= 1")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any] | None = None) -> ResourceLimits:
        if value is None:
            return cls()
        if isinstance(value, cls):
            return value
        if not isinstance(value, Mapping):
            raise ValueError("resource limits must be an object")
        unknown = set(value) - {item.name for item in fields(cls)}
        if unknown:
            raise ValueError(f"unknown resource limits: {sorted(unknown)}")
        return cls(**dict(value))

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)



class ResidencyTransfer:
    """A bounded cross-tier copy whose endpoint charges survive until fenced visibility."""

    def __init__(self, manager: "ResidencyManager", transfer_id: str,
                 source: str, destination: str, byte_count: int,
                 tokens: list[_Reservation]) -> None:
        self.manager = manager
        self.transfer_id = transfer_id
        self.source = source
        self.destination = destination
        self.byte_count = byte_count
        self.tokens = tokens
        self.state = "copying"
        self._lock = threading.Lock()

    def fence(self, reason: str = "cancelled") -> Mapping[str, Any]:
        with self._lock:
            if self.state in {"visible", "retired"}:
                raise ValueError("visible transfer cannot be fenced")
            self.state = "fenced"
            with self.manager._lock:
                row = self.manager._transfers[self.transfer_id]
                row.update(state=self.state, fence_reason=str(reason))
                return dict(row)

    def make_visible(self) -> Mapping[str, Any]:
        with self._lock:
            if self.state != "copying":
                raise ValueError("only an unfenced copy can become visible")
            self.state = "visible"
            with self.manager._lock:
                row = self.manager._transfers[self.transfer_id]
                row["state"] = self.state
                self._retire_locked()
                self.manager._prune_transfers_locked()
                return dict(row)

    def reconcile(self, *, observed_visible: bool) -> Mapping[str, Any]:
        with self._lock:
            if self.state != "fenced":
                raise ValueError("transfer does not require reconciliation")
            self.state = "visible" if observed_visible else "retired"
            with self.manager._lock:
                row = self.manager._transfers[self.transfer_id]
                row.update(state=self.state, reconciled=True)
                self._retire_locked()
                self.manager._prune_transfers_locked()
                return dict(row)

    def _retire_locked(self) -> None:
        for token in self.tokens:
            token.release()
        self.tokens.clear()


def available_ram_bytes() -> int:
    """Physical memory this machine can hand out right now.

    A declared share is a budget, so a caller sizing one needs the machine's
    current room rather than a fixed number.
    """

    if os.name == "nt":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong),
                        ("total_physical", ctypes.c_ulonglong),
                        ("available_physical", ctypes.c_ulonglong),
                        ("total_page", ctypes.c_ulonglong),
                        ("available_page", ctypes.c_ulonglong),
                        ("total_virtual", ctypes.c_ulonglong),
                        ("available_virtual", ctypes.c_ulonglong),
                        ("available_extended", ctypes.c_ulonglong)]
        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            raise OSError("GlobalMemoryStatusEx failed")
        return int(status.available_physical)
    return int(os.sysconf("SC_AVPHYS_PAGES")) * int(os.sysconf("SC_PAGE_SIZE"))


class _Reservation:
    __slots__ = ("manager", "tier", "kind", "nbytes", "released", "program_id",
                 "device")

    def __init__(
        self,
        manager: "ResidencyManager",
        tier: str,
        kind: str,
        nbytes: int,
        program_id: str | None = None,
        device: str | None = None,
    ) -> None:
        self.manager, self.tier, self.kind = manager, tier, kind
        self.nbytes, self.released = nbytes, False
        self.program_id = program_id
        self.device = device

    def release(self) -> None:
        with self.manager._lock:
            if not self.released:
                self.manager._used[self.tier][self.kind] -= self.nbytes
                if self.device is not None:
                    device_used = self.manager._device_used.get(
                        (self.tier, self.device)
                    )
                    if device_used is not None:
                        device_used[self.kind] = max(
                            0, device_used[self.kind] - self.nbytes
                        )
                if self.program_id is not None:
                    used = self.manager._program_used.get(self.program_id)
                    if used is not None:
                        used[self.tier] = max(0, used[self.tier] - self.nbytes)
                    tokens = self.manager._program_tokens.get(self.program_id)
                    if tokens is not None:
                        tokens.discard(self)
                self.released = True

    def __enter__(self) -> "_Reservation":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.release()


class ResidencyManager:
    """Measured byte reservations shared by page, transfer, and kernel consumers.

    A manager can be shared by multiple program images.  Program policy is
    deliberately operational (and therefore not part of field identity), while
    physical reservations remain one global account per manager.
    """

    _shared: dict[str, "ResidencyManager"] = {}
    _shared_lock = threading.RLock()

    @classmethod
    def shared(
        cls,
        scope: str,
        limits: ResourceLimits | Mapping[str, Any] | None = None,
        *,
        storage_root: Path | str | None = None,
    ) -> "ResidencyManager":
        key = str(scope)
        with cls._shared_lock:
            manager = cls._shared.get(key)
            if manager is None:
                manager = cls(limits, storage_root=storage_root)
                cls._shared[key] = manager
            elif limits is not None:
                manager.reconfigure(limits)
            return manager
    @classmethod
    def reset_shared(cls, scope_prefix: str) -> None:
        """Drop ephemeral process reservations when an owner is reopened."""
        prefix = str(scope_prefix)
        with cls._shared_lock:
            for key in tuple(cls._shared):
                if key.startswith(prefix):
                    cls._shared.pop(key, None)
    
    def __init__(self, limits: ResourceLimits | Mapping[str, Any] | None = None,
                 *, storage_root: Path | str | None = None) -> None:
        self.limits = ResourceLimits.from_dict(limits)
        self.storage_root = Path.cwd() if storage_root is None else Path(storage_root)
        self._storage_roots: dict[str, Path] = {}
        self._storage_identity: dict[str, str] = {}
        self._transfers: dict[str, dict[str, Any]] = {}
        self._transfer_leases: dict[str, ResidencyTransfer] = {}
        self._lock = threading.RLock()
        storage_identity = _storage_volume_identity(self.storage_root)
        if storage_identity is not None:
            self._storage_identity["storage"] = storage_identity
        self._used = {tier: {kind: 0 for kind in KINDS} for tier in TIERS}
        self._high = {tier: 0 for tier in TIERS}
        self._kind_high = {kind: 0 for kind in KINDS}
        self._physical: dict[str, int] = {}
        self._device_physical: dict[tuple[str, str], int] = {}
        self._vram_devices: dict[str, dict[str, Any]] = {}
        self._device_used: dict[tuple[str, str], dict[str, int]] = {
            (tier, device): {kind: 0 for kind in KINDS}
            for tier, device in ((("vram", DEFAULT_VRAM_DEVICE),))
        }
        self._device_high: dict[tuple[str, str], int] = {}
        self._budget = {
            tier: int(getattr(self.limits, f"{tier}_bytes")) for tier in TIERS
        }
        self._kind_budget = {
            kind: int(self.limits.max_logical_bytes) for kind in KINDS
        }
        self._growths: list[dict[str, Any]] = []
        self._waits = 0
        self._last_wait: dict[str, Any] | None = None
        self._programs: dict[str, dict[str, Any]] = {}
        self._program_used: dict[str, dict[str, int]] = {}
        self._program_tokens: dict[str, set[_Reservation]] = {}

    def register_storage(self, tier: str, root: Path | str) -> str | None:
        """Bind a storage tier to an actual filesystem volume identity.

        Media type is an operator-supplied fact: the module never guesses
        device speed or classifies an unknown disk as NVMe/HDD.
        """
        if tier not in {"nvme", "hdd"}:
            raise ValueError("storage tier must be nvme or hdd")
        path = Path(root).resolve()
        identity = _storage_volume_identity(path)
        with self._lock:
            if identity is not None and any(
                other != tier and other in {"nvme", "hdd"}
                and device == identity
                for other, device in self._storage_identity.items()
            ):
                raise ValueError("storage tiers cannot bind the same physical volume")
            self._storage_roots[tier] = path
            if identity is None:
                self._storage_identity.pop(tier, None)
            else:
                self._storage_identity[tier] = identity
        return identity
    def storage_root_for(self, tier: str) -> Path:
        """Return the operator-registered root for an explicit media tier."""
        if tier not in {"nvme", "hdd"}:
            raise ValueError("storage tier must be nvme or hdd")
        with self._lock:
            root = self._storage_roots.get(tier)
        if root is None:
            raise ResourceWait(tier, 0, 0, reason="storage-volume-unbound")
        return root

    def register_vram_device(
        self,
        device: str | int | None,
        *,
        total_bytes: int,
        headroom_bytes: int | None = None,
        identity: str | None = None,
        probe: Any = None,
    ) -> str:
        """Declare one physical vram device's capacity for explicit accounting.

        Capacity must be explicit: the module never pretends that a CUDA
        probe for device 0 describes a Vulkan device or any other adapter.
        ``probe``, when given, must return the device's currently free bytes;
        without one the declared ``total_bytes`` is the measured ceiling and
        reports label it ``declared-capacity``.  The returned key is the
        device identity every reservation, transfer, and lease must reuse.
        """

        if device is None:
            raise ValueError("vram device registration requires an explicit key")
        key = _device_key(device)
        if key is None:
            raise ValueError("vram device registration requires an explicit key")
        if isinstance(total_bytes, bool) or not isinstance(total_bytes, int) or total_bytes < 1:
            raise ValueError("vram device total_bytes must be a positive integer")
        headroom = (
            self.limits.vram_headroom_bytes if headroom_bytes is None
            else headroom_bytes
        )
        if isinstance(headroom, bool) or not isinstance(headroom, int) or headroom < 0:
            raise ValueError("vram device headroom_bytes must be a nonnegative integer")
        if probe is not None and not callable(probe):
            raise ValueError("vram device probe must be callable or None")
        if identity is not None:
            if not isinstance(identity, str) or not identity or any(
                ord(character) < 32 for character in identity
            ) or len(identity.encode("utf-8")) > 192:
                raise ValueError("vram device identity must be bounded nonempty text")
        with self._lock:
            prior = self._vram_devices.get(key)
            if prior is not None and (
                prior["total_bytes"] != int(total_bytes)
                or prior["headroom_bytes"] != int(headroom)
                or (prior["identity"] or None) != (identity or None)
            ):
                raise ValueError("vram device is already registered with different capacity")
            self._vram_devices[key] = {
                "device": key,
                "identity": identity,
                "total_bytes": int(total_bytes),
                "headroom_bytes": int(headroom),
                "probe": probe,
            }
            self._device_used.setdefault(( "vram", key), {kind: 0 for kind in KINDS})
        return key

    def _device_room(self, device: str) -> int:
        """The physical room one registered vram device reports, in bytes."""

        registered = self._vram_devices.get(device)
        if registered is None:
            raise ResourceWait("vram", 0, 0, reason="vram-device-undeclared",
                               device=device)
        try:
            probe = registered["probe"]
            if probe is not None:
                value = max(0, int(probe()) - int(registered["headroom_bytes"]))
            else:
                value = max(0, int(registered["total_bytes"]) - int(registered["headroom_bytes"]))
        except ResourceWait:
            raise
        except (OSError, ValueError, RuntimeError, TypeError, ImportError) as exc:
            raise ResourceWait("vram", 0, 0, reason="resource-query-unavailable",
                               device=device) from exc
        self._device_physical[("vram", device)] = value
        return value

    def _physical_available(self, tier: str, device: str | None = None) -> int:
        if tier == "vram" and self._vram_devices:
            if device is not None:
                return self._device_room(device)
            # Registered devices supersede the legacy torch.cuda device-0
            # guess: the tier's physical room is the sum of declared rooms.
            return sum(self._device_room(registered) for registered in self._vram_devices)
        if tier == "vram" and device is not None:
            return self._device_room(device)
        try:
            if tier == "cpu_cache":
                # CPU cache is a bounded working-window accounting tier, not
                # a claim about hardware cache capacity.
                value = int(self._budget[tier])
            elif tier == "ram":
                value = max(0, available_ram_bytes() - self.limits.ram_headroom_bytes)
            elif tier == "vram":
                import torch
                if not torch.cuda.is_available():
                    raise ResourceWait(tier, 0, 0, reason="device-unavailable")
                free, _total = torch.cuda.mem_get_info()
                value = max(0, int(free) - self.limits.vram_headroom_bytes)
            else:
                if tier in {"nvme", "hdd"}:
                    root = self._storage_roots.get(tier)
                    if root is None:
                        raise ResourceWait(tier, 0, 0, reason="storage-volume-unbound")
                else:
                    root = self.storage_root
                while not root.exists() and root.parent != root:
                    root = root.parent
                value = int(shutil.disk_usage(root).free)
        except ResourceWait:
            raise
        except (OSError, ValueError, RuntimeError, ImportError) as exc:
            raise ResourceWait(tier, 0, 0, reason="resource-query-unavailable") from exc
        self._physical[tier] = value
        return value

    def available(self, tier: str, *, device: str | int | None = None) -> int:
        if tier not in TIERS:
            raise ValueError(f"unsupported resource tier: {tier}")
        if tier != "vram" and device is not None:
            raise ValueError("device key applies only to the vram tier")
        explicit = device is not None
        key = _device_key(device) if (tier == "vram" and explicit) else None
        with self._lock:
            remaining = self._budget[tier] - sum(self._used[tier].values())
            if tier == "vram" and self._vram_devices:
                if explicit:
                    if key not in self._vram_devices:
                        raise ResourceWait(
                            tier, 0, 0, device=key,
                            reason="vram-device-undeclared",
                        )
                    device_used = sum(
                        self._device_used.get(("vram", key), {}).values()
                    )
                    return max(0, min(remaining, self._device_room(key) - device_used))
                # Tier-level query over declared devices: the field's room is
                # the sum of each device's remaining room, not device 0's alone.
                physical = sum(
                    max(
                        0,
                        self._device_room(registered)
                        - sum(self._device_used.get(("vram", registered), {}).values()),
                    )
                    for registered in self._vram_devices
                )
                return max(0, min(remaining, physical))
            physical = self._physical_available(tier)
            if tier in {"storage", "nvme", "hdd"}:
                identity = self._storage_identity.get(tier)
                if identity is not None:
                    shared_used = sum(
                        sum(self._used[other].values())
                        for other in ("storage", "nvme", "hdd")
                        if self._storage_identity.get(other) == identity
                    )
                    physical = max(0, physical - shared_used)
            return max(0, min(remaining, physical))

    def room(self, tier: str, *, device: str | int | None = None) -> int:
        """The measured physical room on one tier, ignoring reservations.

        A consumer that can release its own reservations uses this to tell a
        ceiling it can lift from a ceiling the machine imposes.
        """

        if tier not in TIERS:
            raise ValueError(f"unsupported resource tier: {tier}")
        if tier != "vram" and device is not None:
            raise ValueError("device key applies only to the vram tier")
        key = _device_key(device) if tier == "vram" else None
        with self._lock:
            if key is not None:
                return self._device_room(key)
            if tier == "vram" and self._vram_devices:
                return sum(self._device_room(registered) for registered in self._vram_devices)
            return self._physical_available(tier)

    def begin_transfer(
        self, transfer_id: str, source: str, destination: str, byte_count: int,
        *, program_id: str | None = None,
        source_device: str | int | None = None,
        destination_device: str | int | None = None,
        staging_bytes: int | None = None,
    ) -> ResidencyTransfer:
        """Reserve both endpoints and bounded host staging through visibility.

        VRAM endpoints require their explicit registered device identities.
        Copies with no RAM endpoint reserve a host-RAM staging window by
        default; callers may report a smaller exact chunk window, or zero only
        when their real transport path does not stage through host memory.
        Fenced copies retain endpoint and staging charges until reconciliation.
        """

        identifier = str(transfer_id)
        if not identifier or len(identifier.encode("utf-8")) > 192:
            raise ValueError("transfer_id must be bounded nonempty text")
        if source not in TIERS or destination not in TIERS:
            raise ValueError("transfer requires supported tiers")
        if isinstance(byte_count, bool) or not isinstance(byte_count, int) or byte_count < 1:
            raise ValueError("transfer byte count must be a positive integer")
        if staging_bytes is not None and (
            isinstance(staging_bytes, bool)
            or not isinstance(staging_bytes, int)
            or staging_bytes < 0
        ):
            raise ValueError("transfer staging_bytes must be a nonnegative integer")
        if source == destination and source != "vram":
            raise ValueError("transfer requires distinct supported tiers")
        if source == "vram" and source_device is None:
            raise ValueError("vram transfer source requires an explicit device")
        if destination == "vram" and destination_device is None:
            raise ValueError("vram transfer destination requires an explicit device")
        if source != "vram" and source_device is not None:
            raise ValueError("source device key applies only to a vram endpoint")
        if destination != "vram" and destination_device is not None:
            raise ValueError("destination device key applies only to a vram endpoint")
        source_key = _device_key(source_device) if source == "vram" else None
        destination_key = (
            _device_key(destination_device) if destination == "vram" else None
        )
        if source == destination and source_key == destination_key:
            raise ValueError("same-tier vram transfer requires two distinct devices")
        stage_bytes = (
            int(staging_bytes)
            if staging_bytes is not None
            else byte_count if source != "ram" and destination != "ram" else 0
        )
        with self._lock:
            if identifier in self._transfers:
                raise ValueError("transfer_id is already in use")
            tokens: list[_Reservation] = []
            try:
                tokens.append(self.reserve(
                    source, byte_count, kind="transfer",
                    program_id=program_id, device=source_key,
                ))
                tokens.append(self.reserve(
                    destination, byte_count, kind="transfer",
                    program_id=program_id, device=destination_key,
                ))
                if stage_bytes:
                    tokens.append(self.reserve(
                        "ram", stage_bytes, kind="transfer",
                        program_id=program_id,
                    ))
            except Exception:
                for token in tokens:
                    token.release()
                raise
            self._transfers[identifier] = {
                "transfer_id": identifier,
                "source_tier": source,
                "destination_tier": destination,
                "byte_count": byte_count,
                "staging_tier": "ram" if stage_bytes else None,
                "staging_bytes": stage_bytes,
                "source_device": self._storage_identity.get(source),
                "destination_device": self._storage_identity.get(destination),
                "source_vram_device": source_key,
                "destination_vram_device": destination_key,
                "state": "copying",
            }
            lease = ResidencyTransfer(self, identifier, source, destination, byte_count, tokens)
            self._transfer_leases[identifier] = lease
            return lease

    def reconcile_transfer(self, transfer_id: str, *, observed_visible: bool) -> Mapping[str, Any]:
        """Resolve a fenced transfer using observed destination visibility."""
        with self._lock:
            identifier = str(transfer_id)
            row = self._transfers.get(identifier)
            lease = self._transfer_leases.get(identifier)
            if row is None:
                raise KeyError(f"unknown transfer: {transfer_id}")
            if row["state"] != "fenced":
                raise ValueError("transfer does not require reconciliation")
        if lease is not None:
            return lease.reconcile(observed_visible=observed_visible)
        with self._lock:
            row.update(state="visible" if observed_visible else "retired", reconciled=True)
            self._prune_transfers_locked()
            return dict(row)
    def transfer_report(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return {key: dict(row) for key, row in sorted(self._transfers.items())}

    def _prune_transfers_locked(self) -> None:
        retired = [
            transfer_id for transfer_id, row in self._transfers.items()
            if row["state"] in {"visible", "retired"}
        ]
        for transfer_id in retired[:-MAX_RETIRED_TRANSFERS]:
            self._transfers.pop(transfer_id, None)
            self._transfer_leases.pop(transfer_id, None)

    def watermark_floor(self, tier: str) -> int:
        """The declared low watermark of one tier's share, in bytes.

        A consumer that must give memory back asks for this floor: the field
        returns to the low watermark so it can ask for less, and the share is
        refilled from the high watermark as work continues.
        """

        if tier not in TIERS:
            raise ValueError(f"unsupported resource tier: {tier}")
        with self._lock:
            return int(self._budget[tier] * self.limits.low_watermark)

    def _widen(
        self, tier: str, byte_count: int, kind: str = "resident",
        device: str | None = None,
    ) -> int:
        """Widen one tier share, and its allocation kind, within measured room.

        A tier budget is the field's declared share of a physical tier and a
        kind budget is that share's independent sublimit.  When the policy
        grants growth, a reservation that does not fit its declared share may
        widen both up to the room the machine reports, so the field uses
        capacity that exists rather than a placeholder slice of it.  The kind
        sublimit never exceeds the tier it is drawn from.  A registered device
        caps both: the share never widens past the device's declared room.
        """

        if not self.limits.auto_grow or kind not in KINDS:
            return 0
        physical = self._physical_available(tier, device)
        used = sum(self._used[tier].values())
        current = self._budget[tier]
        # Grow into room the machine reports, but stop at the declared low
        # watermark: the share it takes leaves working room for the rest of
        # the field to page, load, and generate in.
        ceiling = int(physical * self.limits.low_watermark)
        if tier == "vram" and device is not None:
            registered = self._vram_devices.get(device)
            if registered is not None:
                ceiling = min(ceiling, int(registered["total_bytes"]) - int(registered["headroom_bytes"]))
        target = min(ceiling, max(used + byte_count, current * 2))
        if target > current:
            self._budget[tier] = target
            self._growths.append(
                {
                    "scope": "tier",
                    "tier": tier,
                    "device": device,
                    "from_bytes": current,
                    "to_bytes": target,
                    "requested_bytes": int(byte_count),
                    "used_bytes": used,
                    "physical_bytes": int(
                        self._device_physical.get((tier, device),
                                                  self._physical.get(tier, 0))
                    ),
                }
            )
        if kind != "resident":
            occupied = sum(row[kind] for row in self._used.values())
            cap = self._kind_budget[kind]
            if byte_count > cap - occupied:
                widened = min(self._budget[tier], physical)
                if widened > cap:
                    self._kind_budget[kind] = widened
                    self._growths.append(
                        {
                            "scope": "kind",
                            "tier": tier,
                            "kind": kind,
                            "from_bytes": cap,
                            "to_bytes": widened,
                            "requested_bytes": int(byte_count),
                            "used_bytes": occupied,
                            "physical_bytes": int(self._physical.get(tier, 0)),
                        }
                    )
        del self._growths[:-16]
        return self._budget[tier]

    def reconfigure(
        self, limits: ResourceLimits | Mapping[str, Any] | None = None
    ) -> ResourceLimits:
        """Adopt a newly declared policy for this manager's one account.

        A reduction that would strand reservations already in flight is
        refused, so a live consumer keeps the bytes it already holds.
        """

        successor = ResourceLimits.from_dict(limits)
        with self._lock:
            for tier in TIERS:
                used = sum(self._used[tier].values())
                if used > getattr(successor, f"{tier}_bytes"):
                    raise ResourceWait(
                        tier,
                        used,
                        getattr(successor, f"{tier}_bytes"),
                        reason="policy-reduction",
                    )
            self.limits = successor
            self._budget = {
                tier: int(getattr(successor, f"{tier}_bytes")) for tier in TIERS
            }
            self._kind_budget = {
                kind: int(successor.max_logical_bytes) for kind in KINDS
            }
        return successor

    def reserve(
        self, tier: str, byte_count: int, *, kind: str = "resident",
        program_id: str | None = None, optional: bool = False,
        device: str | int | None = None,
    ) -> _Reservation:
        if tier not in TIERS or kind not in KINDS:
            raise ValueError("invalid physical tier or allocation kind")
        if tier != "vram" and device is not None:
            raise ValueError("device key applies only to the vram tier")
        if isinstance(byte_count, bool) or not isinstance(byte_count, int) or byte_count < 0:
            raise ValueError("reserved byte count must be a nonnegative integer")
        device_key = _device_key(device) if tier == "vram" else None
        with self._lock:
            registered = (
                self._vram_devices.get(device_key)
                if device_key is not None else None
            )
            if device is not None and registered is None:
                # An explicitly named device key is a hard capacity identity:
                # an undeclared device is refused, never measured by guessing.
                raise ResourceWait(
                    tier, byte_count, 0, kind=kind, device=device_key,
                    reason="vram-device-undeclared",
                )
            # Reservations on an unregistered key keep the historical default
            # account: aggregate ceilings only, no device constraint.
            constraint_key = device_key if registered is not None else None
            try:
                if self.limits.auto_grow and byte_count > (
                    self._budget[tier] - sum(self._used[tier].values())
                ):
                    self._widen(tier, byte_count, kind, constraint_key)
                available = (
                    self.available(tier) if constraint_key is None
                    else self.available(tier, device=constraint_key)
                )
                if kind != "resident":
                    occupied = sum(row[kind] for row in self._used.values())
                    available = min(available, self._kind_budget[kind] - occupied)
                    if byte_count > available:
                        self._widen(tier, byte_count, kind, constraint_key)
                        available = min(
                            (
                                self.available(tier) if constraint_key is None
                                else self.available(tier, device=constraint_key)
                            ),
                            self._kind_budget[kind] - occupied
                        )
                if program_id is not None and program_id in self._programs:
                    row = self._programs[program_id]
                    used = self._program_used.setdefault(
                        program_id, {name: 0 for name in TIERS}
                    )
                    program_available = max(
                        0, int(row["policy"]["maximum_bytes"]) - sum(used.values())
                    )
                    if byte_count > program_available and not (
                        row["policy"].get("borrow") and row.get("active")
                    ):
                        raise ResourceWait(
                            tier, byte_count, min(available, program_available),
                            kind=kind, device=device_key,
                            reason="program-budget" if not optional else "prefetch-pressure",
                        )
                if byte_count > available:
                    raise ResourceWait(
                        tier, byte_count, available, kind=kind, device=device_key,
                        reason="prefetch-pressure" if optional else "capacity",
                    )
            except ResourceWait as exc:
                self._waits += 1
                self._last_wait = exc.as_dict()
                raise
            self._used[tier][kind] += byte_count
            if device_key is not None:
                device_used = self._device_used.setdefault(
                    (tier, device_key), {name: 0 for name in KINDS}
                )
                device_used[kind] += byte_count
            if program_id is not None and program_id in self._programs:
                self._program_used[program_id][tier] += byte_count
            self._high[tier] = max(self._high[tier], sum(self._used[tier].values()))
            if device_key is not None:
                self._device_high[(tier, device_key)] = max(
                    self._device_high.get((tier, device_key), 0),
                    sum(self._device_used.get((tier, device_key), {}).values()),
                )
            self._kind_high[kind] = max(
                self._kind_high[kind],
                sum(row[kind] for row in self._used.values()),
            )
            token = _Reservation(
                self, tier, kind, byte_count, program_id,
                device=device_key,
            )
            if program_id is not None:
                self._program_tokens.setdefault(program_id, set()).add(token)
            return token
    @staticmethod
    def _program_policy(policy: Mapping[str, Any] | None) -> dict[str, Any]:
        raw = {} if policy is None else dict(policy)
        allowed = {"minimum_bytes", "maximum_bytes", "prefetch_bytes", "borrow"}
        unknown = set(raw) - allowed
        if unknown:
            raise ValueError(f"unknown program residency policy: {sorted(unknown)}")
        maximum = raw.get("maximum_bytes", 0)
        if isinstance(maximum, bool) or not isinstance(maximum, int) or maximum <= 0:
            raise ValueError("maximum_bytes must be a positive integer")
        result = {
            "minimum_bytes": raw.get("minimum_bytes", 0),
            "maximum_bytes": maximum,
            "prefetch_bytes": raw.get("prefetch_bytes", 0),
            "borrow": raw.get("borrow", False),
        }
        for name in ("minimum_bytes", "prefetch_bytes"):
            value = result[name]
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        if result["minimum_bytes"] > maximum:
            raise ValueError("minimum_bytes cannot exceed maximum_bytes")
        if not isinstance(result["borrow"], bool):
            raise ValueError("borrow must be boolean")
        return result

    def configure_program(
        self,
        program_id: str,
        *,
        computer_id: str,
        policy: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        program_id = str(program_id)
        computer_id = str(computer_id)
        configured = self._program_policy(policy or {
            "minimum_bytes": 0,
            "maximum_bytes": self.limits.ram_bytes,
            "prefetch_bytes": 0,
            "borrow": False,
        })
        with self._lock:
            prior = self._programs.get(program_id)
            if prior is not None and prior["computer_id"] != computer_id:
                raise ValueError("program is already bound to another computer")
            used = self._program_used.setdefault(
                program_id, {tier: 0 for tier in TIERS}
            )
            used_total = sum(used.values())
            if used_total > configured["maximum_bytes"]:
                raise ResourceWait(
                    "ram", used_total, configured["maximum_bytes"],
                    reason="program-policy-reduction",
                )
            self._programs[program_id] = {
                "program_id": program_id,
                "computer_id": computer_id,
                "policy": configured,
                "active": bool(prior and prior.get("active")),
            }
            self._program_tokens.setdefault(program_id, set())
            return self.program_report(program_id)

    def activate_program(self, program_id: str) -> dict[str, Any]:
        with self._lock:
            row = self._programs.get(str(program_id))
            if row is None:
                raise KeyError(f"unknown program residency: {program_id}")
            row["active"] = True
            return self.program_report(str(program_id))

    def release_program(self, program_id: str) -> dict[str, Any]:
        with self._lock:
            key = str(program_id)
            row = self._programs.get(key)
            if row is None:
                raise KeyError(f"unknown program residency: {program_id}")
            for token in tuple(self._program_tokens.get(key, ())):
                token.release()
            row["active"] = False
            return self.program_report(key)

    def program_report(self, program_id: str) -> dict[str, Any]:
        key = str(program_id)
        row = self._programs.get(key)
        if row is None:
            raise KeyError(f"unknown program residency: {program_id}")
        used = self._program_used.setdefault(key, {tier: 0 for tier in TIERS})
        return {
            "program_id": key,
            "computer_id": row["computer_id"],
            "policy": dict(row["policy"]),
            "active": bool(row.get("active")),
            "used_bytes": dict(used),
            "available_bytes": max(0, row["policy"]["maximum_bytes"] - sum(used.values())),
        }

    def program_reports(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return {key: self.program_report(key) for key in sorted(self._programs)}


    def report(self) -> dict[str, Any]:
        """Read-only accounting; does not initialise a GPU or change state."""
        with self._lock:
            by_tier: dict[str, Any] = {}
            for tier in TIERS:
                try:
                    physical = self._physical_available(tier)
                    if tier == "vram" and self._vram_devices:
                        query = (
                            "measured"
                            if any(row["probe"] is not None for row in self._vram_devices.values())
                            else "declared-capacity"
                        )
                    else:
                        query = "measured" if tier != "cpu_cache" else "bounded-working-window"
                except ResourceWait as exc:
                    physical, query = 0, exc.reason
                device_used = (
                    {
                        device: sum(self._device_used.get(("vram", device), {}).values())
                        for device in sorted(self._vram_devices)
                    }
                    if tier == "vram" else {}
                )
                by_tier[tier] = {
                    "used_bytes": sum(self._used[tier].values()),
                    "budget_bytes": self._budget[tier],
                    "physical_available_bytes": physical,
                    "measurement": query,
                    "device_identity": self._storage_identity.get(tier),
                    "device_used_bytes": device_used,
                }
            devices: dict[str, Any] = {}
            for device in sorted(self._vram_devices):
                registered = self._vram_devices[device]
                bucket = self._device_used.get(("vram", device), {})
                try:
                    device_available = self.available("vram", device=device)
                    measurement = "measured" if registered["probe"] is not None else "declared-capacity"
                except ResourceWait as exc:
                    device_available, measurement = 0, exc.reason
                devices[device] = {
                    "schema": VRAM_DEVICE_SCHEMA,
                    "device": device,
                    "identity": registered["identity"],
                    "declared_total_bytes": registered["total_bytes"],
                    "headroom_bytes": registered["headroom_bytes"],
                    "used_bytes": dict(bucket),
                    "available_bytes": max(0, device_available),
                    "high_water_bytes": self._device_high.get(("vram", device), 0),
                    "measurement": measurement,
                    "last_available_bytes": self._device_physical.get(("vram", device)),
                }
            return {
                "schema": RESOURCE_SCHEMA,
                "limits": self.limits.as_dict(),
                "vram_devices": devices,
                "budget_bytes": dict(self._budget),
                "kind_budget_bytes": dict(self._kind_budget),
                "growths": [dict(row) for row in self._growths],
                "used_bytes": {
                    tier: sum(row.values()) for tier, row in self._used.items()
                },
                "allocations": {tier: dict(row) for tier, row in self._used.items()},
                "tier_measurements": by_tier,
                "storage_devices": dict(self._storage_identity),
                "transfers": {key: dict(row) for key, row in self._transfers.items()},
                "high_water_bytes": dict(self._high),
                "kind_high_water_bytes": dict(self._kind_high),
                "last_available_bytes": dict(self._physical),
                "wait_count": self._waits,
                "last_wait": None if self._last_wait is None else dict(self._last_wait),
                "programs": self.program_reports(),
            }
 
PHYSICAL_RESOURCE_NAMES = (
    "physical_cores", "ram_bytes", "vram_bytes", "transfer_bytes", "peak_bytes",
)


class PhysicalAdmissionCancelled(RuntimeError):
    """A queued physical operation was cancelled before it acquired resources."""


def _physical_vector(
    value: Mapping[str, Any] | None, label: str, *, complete: bool = False
) -> dict[str, int]:
    raw = {} if value is None else dict(value)
    unknown = set(raw) - set(PHYSICAL_RESOURCE_NAMES)
    if unknown:
        raise ValueError(f"unknown {label}: {sorted(unknown)}")
    if complete and set(raw) != set(PHYSICAL_RESOURCE_NAMES):
        raise ValueError(f"{label} must define every physical resource")
    result: dict[str, int] = {}
    for name in PHYSICAL_RESOURCE_NAMES:
        amount = raw.get(name, 0)
        if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
            raise ValueError(f"{label} values must be nonnegative integers")
        result[name] = amount
    return result


class PhysicalWorkLease:
    """A physical operation's journal reservation and live byte reservations.

    A lease owns all of its charges until retirement is confirmed. Fencing a
    lease prevents a late result from publishing but deliberately does not
    release its CPU or byte charges.
    """

    def __init__(
        self,
        admission: "PhysicalAdmission",
        reservation: Mapping[str, Any],
        tokens: list[_Reservation],
        *,
        activity_id: str,
        continuation_id: str | None,
        priority: str,
        resources: Mapping[str, int],
        wait_ns: int,
        queued_at_ns: int,
        vram_device: str | None = None,
    ) -> None:
        self.admission = admission
        self.reservation = dict(reservation)
        self.tokens = tokens
        self.activity_id = activity_id
        self.continuation_id = continuation_id
        self.priority = priority
        self.resources = dict(resources)
        self.wait_ns = wait_ns
        self.queued_at_ns = queued_at_ns
        self.vram_device = vram_device
        self.started_ns = time.monotonic_ns()
        self._state = "open"
        self._terminal: tuple[str, str, dict[str, int]] | None = None
        self._lock = threading.Lock()
        self._stages: dict[str, dict[str, int]] = {}
        self._cache_window_bytes = 0
        self._cache_peak_bytes = 0
        self._cache_tokens: list[_Reservation] = []

    def mark_stage(self, name: str, event: str) -> int:
        """Record an observed stage boundary against this exact lease."""
        if name not in {"transfer", "compute", "commit"} or event not in {"start", "end"}:
            raise ValueError("physical lease stage boundary is invalid")
        timestamp = time.monotonic_ns()
        with self._lock:
            if self._state != "open":
                raise ValueError("physical lease stage requires an open lease")
            row = self._stages.setdefault(name, {})
            if event in row:
                raise ValueError("physical lease stage boundary was already recorded")
            row[event] = timestamp
        return timestamp
    def finish_open_stages(self) -> None:
        """Close observed host-stage intervals at the exception boundary."""
        timestamp = time.monotonic_ns()
        with self._lock:
            if self._state != "open":
                return
            for bounds in self._stages.values():
                if "start" in bounds and "end" not in bounds:
                    bounds["end"] = timestamp

    def reserve_cache_window(self, byte_count: int) -> None:
        """Charge a CPU working window to the bounded accounting tier."""
        if isinstance(byte_count, bool) or not isinstance(byte_count, int) or byte_count < 0:
            raise ValueError("CPU cache working window must be nonnegative bytes")
        if not byte_count:
            return
        try:
            token = self.admission.manager.reserve("cpu_cache", byte_count, kind="resident")
        except ResourceWait as exc:
            exc.continuation_id = self.continuation_id
            exc.retry_id = self.continuation_id or self.activity_id
            with self.admission._condition:
                self.admission._make_resource_wait_locked(
                    exc,
                    self.activity_id,
                    self.continuation_id,
                    self.priority,
                    self.resources,
                    getattr(self, "prerequisite_activity_ids", ()),
                    getattr(self, "holding_activity_id", None) or self.activity_id,
                )
            raise
        with self._lock:
            if self._state != "open":
                token.release()
                raise ValueError("physical lease is no longer open")
            self._cache_tokens.append(token)
            self.tokens.append(token)
            self._cache_window_bytes += byte_count
            self._cache_peak_bytes = max(self._cache_peak_bytes, self._cache_window_bytes)
    def release_cache_window(self) -> None:
        """Release only the working-window charge after compute stops using it."""
        with self._lock:
            for token in self._cache_tokens:
                token.release()
                if token in self.tokens:
                    self.tokens.remove(token)
            self._cache_tokens.clear()
            self._cache_window_bytes = 0
        with self.admission._condition:
            self.admission._refresh_wait_obligations_locked()
            self.admission._condition.notify_all()

    @property
    def reservation_id(self) -> str:
        return str(self.reservation["reservation_id"])

    def retire(
        self,
        status: str = "completed",
        *,
        measured_consumption: Mapping[str, int] | None = None,
        settlement_id: str | None = None,
    ) -> Mapping[str, Any]:
        if status not in {"completed", "failed", "cancelled", "released"}:
            raise ValueError("physical work retirement status is invalid")
        full_measured = (
            dict(self.resources)
            if measured_consumption is None
            else _physical_vector(measured_consumption, "measured consumption")
        )
        measured = {
            name: full_measured.get(name, 0) for name in self.reservation["cap"]
        }
        identifier = settlement_id or (
            f"physical-retire:{self.reservation_id}:{status}"
        )
        with self._lock:
            if self._terminal is not None:
                if self._terminal != (identifier, status, measured):
                    raise ValueError("physical work lease was already retired")
                return _validated_reservation(
                    self.admission.journal.reservation(self.reservation_id)
                ) or {}
            if self._state != "open":
                raise ValueError("a fenced physical work lease requires reconciliation")
            result = _validated_reservation(self.admission.journal.settle_resources(
                self.reservation_id,
                identifier,
                measured_consumption=measured,
                status=status,
                lease_fence=int(self.reservation["lease"]["fence"]),
            ))
            self._terminal = (identifier, status, measured)
            self._state = status
            for token in self.tokens:
                token.release()
            self.tokens.clear()
        self.admission._retire_lane(self, status, measured)
        return result

    def fence(self, reason: str) -> Mapping[str, Any]:
        with self._lock:
            if self._state == "fenced":
                return _validated_reservation(
                    self.admission.journal.reservation(self.reservation_id)
                ) or {}
            if self._state != "open":
                raise ValueError("retired physical work cannot be fenced")
            result = _validated_reservation(
                self.admission.journal.fence_resources(
                    self.reservation_id,
                    f"physical-fence:{self.reservation_id}",
                    reason=reason,
                )
            )
            self._state = "fenced"
            self.reservation = dict(result)
        self.admission._record(
            self, "reconciliation-required", {}, ended_ns=time.monotonic_ns()
        )
        with self.admission._condition:
            self.admission._refresh_wait_obligations_locked()
            self.admission._condition.notify_all()
        return result

    def reconcile(
        self,
        reconciliation_id: str,
        *,
        observed_released: bool,
        measured_consumption: Mapping[str, int] | None = None,
    ) -> Mapping[str, Any]:
        full_measured = (
            dict(self.resources)
            if measured_consumption is None
            else _physical_vector(measured_consumption, "measured consumption")
        )
        measured = {
            name: full_measured.get(name, 0) for name in self.reservation["cap"]
        }
        with self._lock:
            if self._state not in {"fenced", "reconciliation-required"}:
                raise ValueError("physical work lease does not require reconciliation")
            result = _validated_reservation(
                self.admission.journal.reconcile_resources(
                    self.reservation_id,
                    reconciliation_id,
                    observed_released=observed_released,
                    measured_consumption=measured if observed_released else None,
                )
            )
            self.reservation = dict(result)
            if observed_released:
                self._state = "released"
                for token in self.tokens:
                    token.release()
                self.tokens.clear()
        if observed_released:
            self.admission._retire_lane(self, "reconciled", measured)
            with self.admission._condition:
                self.admission._mark_reconciled_waits_locked(
                    self.reservation_id
                )
                self.admission._condition.notify_all()
        else:
            self.admission._record(
                self, "reconciliation-required", {}, ended_ns=time.monotonic_ns()
            )
        return result

    def __enter__(self) -> "PhysicalWorkLease":
        return self

    def __exit__(self, exc_type: Any, _exc: Any, _traceback: Any) -> None:
        if self._state == "open":
            self.retire("failed" if exc_type is not None else "completed")


class PhysicalAdmission:
    """Fair owner-wide execution admission backed by the shared byte account.

    ``capacity`` is the host-declared successor budget. Background work cannot
    consume ``foreground_reserve``; foreground work may use the entire budget.
    Journal reservations make that limit global across this entity's callers,
    while ``ResidencyManager`` tokens account actual RAM/VRAM/transfer/scratch
    bytes against the field's existing physical account.  ``vram_device``
    names which registered physical device's bytes a lease charges; it is a
    hard capacity identity, distinct from ``locality_id`` scheduling hints.
    """

    def __init__(
        self,
        manager: ResidencyManager,
        journal: Any,
        *,
        owner_id: str,
        capacity: Mapping[str, int],
        foreground_reserve: Mapping[str, int] | None = None,
        resource_class: str = "physical-execution",
        mission_account_id: str = "mission:physical-execution",
        foreground_burst: int = 3,
    ) -> None:
        if not isinstance(manager, ResidencyManager):
            raise TypeError("physical admission requires the field's ResidencyManager")
        if not all(
            callable(getattr(journal, name, None))
            for name in ("reserve_resources", "settle_resources", "fence_resources",
                         "reconcile_resources", "reservation")
        ):
            raise TypeError("physical admission requires an EntityJournal resource API")
        self.manager = manager
        self.journal = journal
        self.owner_id = str(owner_id)
        self.resource_class = str(resource_class)
        self.mission_account_id = str(mission_account_id)
        self.capacity = _physical_vector(capacity, "physical capacity", complete=True)
        self.foreground_reserve = _physical_vector(
            foreground_reserve, "foreground reserve"
        )
        if self.capacity["physical_cores"] < 1:
            raise ValueError("physical capacity must include at least one core")
        if any(
            self.foreground_reserve[name] > self.capacity[name]
            for name in PHYSICAL_RESOURCE_NAMES
        ):
            raise ValueError("foreground reserve exceeds physical capacity")
        if (
            isinstance(foreground_burst, bool)
            or not isinstance(foreground_burst, int)
            or foreground_burst < 1
        ):
            raise ValueError("foreground_burst must be a positive integer")
        self.foreground_burst = foreground_burst
        self._condition = threading.Condition()
        self._next_ticket = 0
        self._active_cohorts: dict[tuple[str, str], int] = {}
        self._waiting: list[
            tuple[int, str, int, str | None, str | None, int, str, str | None]
        ] = []
        self._foreground_streak = 0
        self._active_cores = 0
        self._background_cores = 0
        self._wait_count = 0
        self._cancelled_wait_count = 0
        self._resource_wait_count = 0
        self._max_queue_depth = 0
        self._wait_history: list[dict[str, Any]] = []
        self._trace: list[dict[str, Any]] = []
        self._leases: dict[str, PhysicalWorkLease] = {}
        self._admitting: set[str] = set()
        self._queue_requests: dict[str, dict[str, Any]] = {}
        self._wait_obligations: dict[str, PhysicalWaitObligation] = {}
        self._last_lent_activity_ids: tuple[str, ...] = ()
    def _holding_activity_locked(
        self, activity: str, continuation: str | None, explicit: str | None,
    ) -> str | None:
        if explicit is not None:
            return explicit
        lease = self._leases.get(activity)
        if lease is not None and lease._state in {"open", "fenced"}:
            return activity
        if continuation is not None:
            matches = [
                row.activity_id for row in self._leases.values()
                if row.continuation_id == continuation
                and row._state in {"open", "fenced"}
            ]
            if len(matches) == 1:
                return matches[0]
        return None

    def _wait_capacity_dimensions_locked(
        self, resource: Mapping[str, Any],
    ) -> dict[str, int]:
        tier = resource.get("tier")
        if tier == "physical_cores":
            dimensions = {
                "core-capacity": max(
                    0, self.capacity["physical_cores"] - self._active_cores,
                ),
            }
            if resource.get("priority") == "background":
                dimensions["background-reserve"] = max(
                    0,
                    self.capacity["physical_cores"]
                    - self.foreground_reserve["physical_cores"]
                    - self._background_cores,
                )
            return dimensions
        if tier not in TIERS:
            return {}

        manager = self.manager
        device = resource.get("device")
        if tier != "vram" and device is not None:
            raise ValueError("device key applies only to the vram tier")
        with manager._lock:
            used = sum(manager._used[tier].values())
            dimensions = {
                "tier": max(0, manager._budget[tier] - used),
            }
            if tier == "vram" and manager._vram_devices:
                if device is not None:
                    key = _device_key(device)
                    if key not in manager._vram_devices:
                        raise ResourceWait(
                            tier, 0, 0, device=key,
                            reason="vram-device-undeclared",
                        )
                    device_used = sum(
                        manager._device_used.get(("vram", key), {}).values()
                    )
                    room = manager._device_room(key) - device_used
                else:
                    room = sum(
                        max(
                            0,
                            manager._device_room(key)
                            - sum(
                                manager._device_used.get(("vram", key), {}).values()
                            ),
                        )
                        for key in manager._vram_devices
                    )
                dimensions["device"] = max(0, room)
            elif tier in {"storage", "nvme", "hdd"}:
                physical = manager._physical_available(tier)
                identity = manager._storage_identity.get(tier)
                if identity is not None:
                    shared_used = sum(
                        sum(manager._used[other].values())
                        for other in ("storage", "nvme", "hdd")
                        if manager._storage_identity.get(other) == identity
                    )
                    dimensions["volume"] = max(0, physical - shared_used)
                else:
                    dimensions["physical"] = max(0, physical)
            elif tier != "cpu_cache":
                dimensions["physical"] = max(
                    0, manager._physical_available(tier, device=device)
                )

            kind = resource.get("kind")
            if kind in KINDS and kind != "resident":
                occupied = sum(row[kind] for row in manager._used.values())
                dimensions["kind"] = max(
                    0, manager._kind_budget[kind] - occupied
                )
            return dimensions

    def _lease_holds_resource(
        self, lease: PhysicalWorkLease, resource: Mapping[str, Any],
    ) -> int:
        name = resource.get("tier")
        dimension = resource.get("dimension")
        if name == "physical_cores":
            dimensions = (
                (dimension,) if dimension is not None
                else tuple(resource.get("constraints", ()))
            )
            if dimensions:
                holds = "core-capacity" in dimensions or (
                    "background-reserve" in dimensions
                    and lease.priority == "background"
                )
                if not holds:
                    return 0
            elif (
                resource.get("constraint") == "background-reserve"
                and lease.priority != "background"
            ):
                return 0
            return max(0, int(lease.resources.get("physical_cores", 0)))
        if name not in TIERS:
            return 0
        dimensions = (
            (dimension,) if dimension is not None
            else tuple(resource.get("constraints", ()))
        )
        if not dimensions:
            try:
                dimensions = tuple(self._wait_capacity_dimensions_locked(resource))
            except (ResourceWait, ValueError, OSError, RuntimeError):
                return 0
        device = resource.get("device")
        device_key = _device_key(device) if device is not None else None
        kind = resource.get("kind")
        identity = self.manager._storage_identity.get(name)
        total = 0
        for token in lease.tokens:
            if token.released:
                continue
            holds = False
            for current in dimensions:
                if current == "tier":
                    holds = token.tier == name
                elif current == "volume":
                    holds = (
                        identity is not None
                        and token.tier in {"storage", "nvme", "hdd"}
                        and self.manager._storage_identity.get(token.tier) == identity
                    )
                elif current == "kind":
                    holds = kind is not None and token.kind == kind
                elif current == "device":
                    holds = (
                        token.tier == "vram"
                        and (device_key is None or token.device == device_key)
                    )
                elif current == "physical":
                    holds = (
                        not (
                            name in {"storage", "nvme", "hdd"}
                            and identity is None
                        )
                        and token.tier == name
                        and (name != "vram" or device_key is None
                             or token.device == device_key)
                    )
                if holds:
                    break
            if holds:
                total += token.nbytes
        return total

    def _blocking_activities_locked(
        self, resource: Mapping[str, Any],
    ) -> tuple[str, ...]:
        dimensions = resource.get("constraints")
        if dimensions is None:
            try:
                capacities = self._wait_capacity_dimensions_locked(resource)
            except (ResourceWait, ValueError, OSError, RuntimeError):
                return ()
            if not capacities:
                return ()
            available = min(capacities.values())
            dimensions = tuple(
                dimension for dimension, room in capacities.items()
                if room == available
            )
        matched_resource = {**resource, "constraints": tuple(dimensions)}
        return tuple(sorted(
            activity for activity, lease in self._leases.items()
            if lease._state in {"open", "fenced", "reconciliation-required"}
            and self._lease_holds_resource(lease, matched_resource) > 0
        ))

    def _available_for_wait_locked(self, resource: Mapping[str, Any]) -> int:
        try:
            dimensions = self._wait_capacity_dimensions_locked(resource)
        except (ResourceWait, ValueError, OSError, RuntimeError):
            return 0
        if dimensions:
            return max(0, min(dimensions.values()))
        return max(0, int(resource.get("available", 0)))

    def _new_obligation_locked(
        self,
        activity: str,
        continuation: str | None,
        priority: str,
        requested: Mapping[str, int],
        resource: Mapping[str, Any],
        prerequisites: tuple[str, ...],
        holding_activity_id: str | None,
        *,
        reason: str,
        state: str = "waiting",
    ) -> PhysicalWaitObligation:
        now = time.monotonic_ns()
        owner = self._holding_activity_locked(
            activity, continuation, holding_activity_id,
        )
        blockers = self._blocking_activities_locked(resource)
        exact_prerequisites = prerequisites
        existing = self._wait_obligations.get(activity)
        opened = existing.opened_at_ns if existing is not None else now
        obligation = PhysicalWaitObligation(
            activity_id=activity,
            continuation_id=continuation,
            retry_id=continuation or activity,
            holding_activity_id=owner,
            priority=priority,
            requested_resources=dict(requested),
            resource=dict(resource),
            prerequisite_activity_ids=tuple(exact_prerequisites),
            blocked_by_activity_ids=blockers,
            cycle_activity_ids=(),
            state=state,
            reason=reason,
            opened_at_ns=opened,
            updated_at_ns=now,
        )
        if activity not in self._wait_obligations:
            self._prune_wait_obligations_locked()
        if (
            len(self._wait_obligations) < MAX_PHYSICAL_WAIT_OBLIGATIONS
            or activity in self._wait_obligations
        ):
            self._wait_obligations[activity] = obligation
        self._refresh_wait_cycles_locked()
        return self._wait_obligations.get(activity, obligation)

    def _wait_nodes_locked(self) -> dict[str, list[dict[str, Any]]]:
        nodes: dict[str, list[dict[str, Any]]] = {}
        row_count = 0
        for obligation in self._wait_obligations.values():
            if row_count >= MAX_PHYSICAL_WAIT_OBLIGATIONS:
                break
            if obligation.state not in {"waiting", "blocked"}:
                continue
            owner = obligation.holding_activity_id
            lease = self._leases.get(owner) if owner is not None else None
            if lease is None or lease._state != "open":
                continue
            nodes.setdefault(owner, []).append({
                "activity_id": obligation.activity_id,
                "owner": owner,
                "resource": obligation.resource,
                "prerequisites": obligation.prerequisite_activity_ids,
                "reason": obligation.reason,
                "priority": obligation.priority,
                "obligation": obligation,
            })
            row_count += 1
        examined = 0
        for activity, request in self._queue_requests.items():
            if (
                examined >= MAX_PHYSICAL_WAIT_OBLIGATIONS
                or row_count >= MAX_PHYSICAL_WAIT_OBLIGATIONS
            ):
                break
            examined += 1
            if request.get("state") not in {"waiting", "blocked"}:
                continue
            owner = request.get("holding_activity_id")
            lease = self._leases.get(owner) if owner is not None else None
            if lease is None or lease._state != "open":
                continue
            nodes.setdefault(owner, []).append({
                "activity_id": activity,
                "owner": owner,
                "resource": request["resource"],
                "prerequisites": request["prerequisite_activity_ids"],
                "reason": "physical-core-capacity",
                "priority": request["priority"],
                "queue_request": request,
            })
            row_count += 1
        return nodes
    def _refresh_wait_cycles_locked(self) -> None:
        nodes = self._wait_nodes_locked()
        owners = set(nodes)
        edges: dict[str, set[str]] = {}
        for owner, rows in nodes.items():
            # Multiple parked requests from one holder are alternatives. A
            # closed verdict requires every one to remain inside the same
            # closed prerequisite set.
            row_edges: set[str] = set()
            closed = True
            for row in rows:
                resource = row["resource"]
                if row["reason"] not in {
                    "capacity", "physical-core-capacity", "wait-cycle",
                }:
                    closed = False
                    break
                try:
                    dimensions = self._wait_capacity_dimensions_locked(resource)
                except (ResourceWait, ValueError, OSError, RuntimeError):
                    closed = False
                    break
                if not dimensions:
                    closed = False
                    break
                available = min(dimensions.values())
                limiting_dimensions = tuple(
                    dimension for dimension, room in dimensions.items()
                    if room == available
                )
                matched_resource = {
                    **resource, "constraints": limiting_dimensions,
                }
                blockers = self._blocking_activities_locked(matched_resource)
                prerequisites = set(row["prerequisites"])
                if not blockers or prerequisites != set(blockers):
                    closed = False
                    break
                requested = int(resource.get("requested", 0))
                needed = max(0, requested - available)
                open_blockers = [
                    key for key in blockers
                    if key in self._leases and self._leases[key]._state == "open"
                ]
                available_after_release = min(
                    room + sum(
                        self._lease_holds_resource(
                            self._leases[key],
                            {**resource, "dimension": dimension},
                        )
                        for key in open_blockers
                    )
                    for dimension, room in dimensions.items()
                )
                if (
                    needed <= 0
                    or available_after_release < requested
                    or not set(blockers) <= owners
                ):
                    closed = False
                    break
                row_edges.update(blockers)
            if closed and row_edges:
                edges[owner] = row_edges

        cycles: list[tuple[str, ...]] = []
        indices: dict[str, int] = {}
        lowlinks: dict[str, int] = {}
        stack: list[str] = []
        on_stack: set[str] = set()
        next_index = 0

        def connect(owner: str) -> None:
            nonlocal next_index
            indices[owner] = next_index
            lowlinks[owner] = next_index
            next_index += 1
            stack.append(owner)
            on_stack.add(owner)
            for prerequisite in sorted(edges.get(owner, ())):
                if prerequisite not in edges:
                    continue
                if prerequisite not in indices:
                    connect(prerequisite)
                    lowlinks[owner] = min(lowlinks[owner], lowlinks[prerequisite])
                elif prerequisite in on_stack:
                    lowlinks[owner] = min(lowlinks[owner], indices[prerequisite])
            if lowlinks[owner] != indices[owner]:
                return
            component: set[str] = set()
            while stack:
                member = stack.pop()
                on_stack.remove(member)
                component.add(member)
                if member == owner:
                    break
            if (
                len(component) <= MAX_PHYSICAL_WAIT_HOPS
                and all(
                    edges.get(member) and edges[member] <= component
                    for member in component
                )
            ):
                cycles.append(tuple(sorted(component)))

        for start in sorted(edges):
            if start not in indices:
                connect(start)
        cycle_by_owner: dict[str, tuple[str, ...]] = {
            owner: cycle for cycle in cycles for owner in cycle
        }
        now = time.monotonic_ns()
        for key, obligation in tuple(self._wait_obligations.items()):
            cycle = cycle_by_owner.get(obligation.holding_activity_id or "")
            if obligation.state in {"waiting", "blocked"}:
                next_state = "blocked" if cycle else "waiting"
                next_cycle = () if cycle is None else cycle
                if obligation.state != next_state or obligation.cycle_activity_ids != next_cycle:
                    self._wait_obligations[key] = replace(
                        obligation,
                        state=next_state,
                        cycle_activity_ids=next_cycle,
                        updated_at_ns=now,
                    )
        for request in self._queue_requests.values():
            cycle = cycle_by_owner.get(request.get("holding_activity_id") or "")
            if request.get("state") in {"waiting", "blocked"}:
                request["state"] = "blocked" if cycle else "waiting"
                request["cycle_activity_ids"] = () if cycle is None else cycle


    def _refresh_wait_obligations_locked(self) -> None:
        now = time.monotonic_ns()
        for key, obligation in tuple(self._wait_obligations.items()):
            if obligation.state not in {
                "waiting", "blocked", "ready", "reconciliation-required",
            }:
                continue
            owner = obligation.holding_activity_id
            lease = self._leases.get(owner) if owner is not None else None
            if obligation.reason == "reservation-requires-reconciliation":
                state = "reconciliation-required"
            elif lease is not None and lease._state in {"fenced", "reconciliation-required"}:
                state = "reconciliation-required"
            elif self._available_for_wait_locked(obligation.resource) >= int(
                obligation.resource.get("requested", 0)
            ):
                state = "ready"
            else:
                state = "waiting"
            if lease is not None and lease._state not in {
                "open", "fenced", "reconciliation-required",
            }:
                owner = None
            self._wait_obligations[key] = replace(
                obligation,
                holding_activity_id=owner,
                state=state,
                cycle_activity_ids=(),
                blocked_by_activity_ids=self._blocking_activities_locked(
                    obligation.resource
                ),
                updated_at_ns=now,
            )
        self._refresh_wait_cycles_locked()

    def _make_resource_wait_locked(
        self,
        wait: ResourceWait,
        activity: str,
        continuation: str | None,
        priority: str,
        requested: Mapping[str, int],
        prerequisites: tuple[str, ...],
        holding_activity_id: str | None,
        *,
        state: str = "waiting",
    ) -> ResourceWait:
        self._resource_wait_count += 1
        wait.continuation_id = continuation
        wait.retry_id = continuation or activity
        resource = {
            "tier": wait.tier,
            "kind": wait.kind,
            "device": wait.device,
            "requested": wait.requested,
            "available": wait.available,
            "reason": wait.reason,
            "priority": priority,
        }
        obligation = self._new_obligation_locked(
            activity, continuation, priority, requested, resource,
            prerequisites, holding_activity_id, reason=wait.reason, state=state,
        )
        wait.obligation = obligation
        return wait

    def _lendable_activities_locked(self) -> tuple[str, ...]:
        waiting_activities: set[str] = set()
        for index, (activity, row) in enumerate(self._queue_requests.items()):
            if index >= MAX_PHYSICAL_WAIT_OBLIGATIONS:
                break
            if row.get("state") == "waiting" and row.get("priority") == "background":
                waiting_activities.add(activity)
        roots = [
            row for row in self._wait_obligations.values()
            if row.priority == "foreground" and row.state in {"waiting", "ready"}
        ]
        roots.sort(key=lambda row: (row.opened_at_ns, row.activity_id))
        if not roots or not waiting_activities:
            self._last_lent_activity_ids = ()
            return ()
        cursor = getattr(self, "_lend_cursor", 0) % len(roots)
        roots = roots[cursor:] + roots[:cursor]
        self._lend_cursor = cursor + 1
        queue = [
            (activity_id, 0)
            for row in roots for activity_id in row.prerequisite_activity_ids
        ]
        seen: set[str] = set()
        lent: list[str] = []
        hops = 0
        while queue and hops < MAX_PHYSICAL_WAIT_HOPS:
            activity_id, depth = queue.pop(0)
            hops += 1
            if activity_id in seen:
                continue
            seen.add(activity_id)
            if activity_id in waiting_activities and activity_id not in lent:
                lent.append(activity_id)
                if len(lent) >= MAX_PHYSICAL_WAIT_PREREQUISITE_LEND:
                    break
            if depth >= MAX_PHYSICAL_WAIT_HOPS:
                continue
            pending = self._wait_obligations.get(activity_id)
            if pending is not None and pending.state in {"waiting", "ready"}:
                queue.extend(
                    (item, depth + 1)
                    for item in pending.prerequisite_activity_ids
                )
        self._last_lent_activity_ids = tuple(lent)
        return self._last_lent_activity_ids

    def _prune_wait_obligations_locked(self) -> None:
        while len(self._wait_obligations) > MAX_PHYSICAL_WAIT_OBLIGATIONS:
            terminal = next(
                (key for key, row in self._wait_obligations.items()
                 if row.state in {"ready", "cancelled", "resumed"}),
                None,
            )
            if terminal is None:
                break
            self._wait_obligations.pop(terminal, None)

    def _record_waiter_locked(
        self,
        entry: tuple[int, str, int, str | None, str | None, int, str, str | None],
        status: str,
        ended_ns: int,
        *,
        reason: str | None = None,
    ) -> dict[str, Any]:
        row = {
            "ticket": entry[0],
            "priority": entry[1],
            "requested_cores": entry[2],
            "locality_id": entry[3],
            "batch_id": entry[4],
            "activity_id": entry[6],
            "continuation_id": entry[7],
            "queued_at_ns": entry[5],
            "ended_at_ns": ended_ns,
            "wait_ns": max(0, ended_ns - entry[5]),
            "status": status,
            "reason": reason,
        }
        self._wait_history.append(row)
        del self._wait_history[:-256]
        return row

    def _finish_waiter(
        self,
        row: dict[str, Any] | None,
        status: str,
        *,
        reason: str | None = None,
    ) -> None:
        if row is None:
            return
        with self._condition:
            row["status"] = status
            row["reason"] = reason

    def _selected_ticket(
        self,
    ) -> tuple[int, str, int, str | None, str | None, int, str, str | None] | None:
        background_limit = (
            self.capacity["physical_cores"]
            - self.foreground_reserve["physical_cores"]
        )
        fitting = [
            row for row in self._waiting
            if self._queue_requests.get(row[6], {}).get("state", "waiting") == "waiting"
            and (
                self._active_cores + row[2] <= self.capacity["physical_cores"]
                and (
                    row[1] == "foreground"
                    or self._background_cores + row[2] <= background_limit
                )
            )
        ]
        foreground = [row for row in fitting if row[1] == "foreground"]
        background = [row for row in fitting if row[1] == "background"]
        if background and self._foreground_streak >= self.foreground_burst:
            candidates = background
            lent = set(self._lendable_activities_locked())
            prerequisites = [row for row in background if row[6] in lent]
            if prerequisites:
                candidates = prerequisites
        else:
            candidates = foreground or background
        if not candidates:
            return None
        first = min(candidates)
        local = [
            row for row in candidates
            if row[3] is not None
            and row[4] is not None
            and self._active_cohorts.get((row[3], row[4]), 0) > 0
            and row[0] - first[0] <= 2
            and row[5] - first[5] <= 50_000_000
        ]
        return min(local, key=lambda row: row[0]) if local else first

    @staticmethod
    def _activity_text(value: Any, label: str) -> str:
        if not isinstance(value, str) or not value or len(value.encode("utf-8")) > 192:
            raise ValueError(f"{label} must be bounded nonempty text")
        if any(ord(character) < 32 for character in value):
            raise ValueError(f"{label} contains a control character")
        return value

    def _reservation_id(self, activity: str) -> str:
        return (
            "physical:"
            + hashlib.sha256(
                f"{self.owner_id}\0{activity}".encode("utf-8")
            ).hexdigest()[:48]
        )

    def _physical_tokens(
        self, resources: Mapping[str, int], vram_device: str | None = None,
    ) -> list[_Reservation]:
        requests = (
            ("ram", resources["ram_bytes"], "resident", None),
            ("vram", resources["vram_bytes"], "resident", vram_device),
            ("ram", resources["transfer_bytes"], "transfer", None),
            ("ram", resources["peak_bytes"], "scratch", None),
        )
        tokens: list[_Reservation] = []
        try:
            for tier, amount, kind, device in requests:
                if amount:
                    tokens.append(self.manager.reserve(
                        tier, amount, kind=kind, device=device,
                    ))
        except Exception:
            for token in tokens:
                token.release()
            raise
        return tokens

    def acquire(
        self,
        activity_id: str,
        priority: str = "background",
        *,
        continuation_id: str | None = None,
        resources: Mapping[str, int] | None = None,
        locality_id: str | None = None,
        batch_id: str | None = None,
        vram_device: str | int | None = None,
        cancel_event: Any | None = None,
        lease_duration_ns: int = 60_000_000_000,
        prerequisite_activity_ids: Sequence[str] | None = None,
        holding_activity_id: str | None = None,
    ) -> PhysicalWorkLease:
        activity = self._activity_text(activity_id, "activity_id")
        if priority not in {"foreground", "background"}:
            raise ValueError("activity priority must be foreground or background")
        continuation = (
            None if continuation_id is None
            else self._activity_text(continuation_id, "continuation_id")
        )
        locality = (
            None if locality_id is None
            else self._activity_text(locality_id, "locality_id")
        )
        batch = (
            None if batch_id is None
            else self._activity_text(batch_id, "batch_id")
        )
        if prerequisite_activity_ids is None:
            prerequisites: tuple[str, ...] = ()
        else:
            if isinstance(prerequisite_activity_ids, (str, bytes)):
                raise ValueError("prerequisite_activity_ids must be a sequence of activity ids")
            prerequisites = tuple(
                self._activity_text(item, "prerequisite_activity_id")
                for item in prerequisite_activity_ids
            )
            if len(prerequisites) > MAX_PHYSICAL_WAIT_HOPS:
                raise ValueError("too many physical prerequisite activity ids")
            if len(set(prerequisites)) != len(prerequisites):
                raise ValueError("physical prerequisite activity ids must be unique")
        holding = (
            None if holding_activity_id is None
            else self._activity_text(holding_activity_id, "holding_activity_id")
        )
        # A VRAM reservation must identify one explicitly registered physical
        # device. Never turn an omitted identity into a CUDA-0 or aggregate
        # capacity guess for owner-wide physical admission.
        device_key = (
            None if vram_device is None
            else _device_key(vram_device)
        )
        requested = _physical_vector(
            {"physical_cores": 1} if resources is None else resources,
            "physical work request",
        )
        if requested["vram_bytes"] and device_key is None:
            wait = ResourceWait(
                "vram", requested["vram_bytes"], 0,
                reason="vram-device-required",
                continuation_id=continuation,
            )
            wait.retry_id = continuation or activity
            with self._condition:
                self._make_resource_wait_locked(
                    wait, activity, continuation, priority, requested,
                    prerequisites, holding,
                )
            raise wait
        if device_key is not None and device_key not in self.manager._vram_devices:
            wait = ResourceWait(
                "vram", requested["vram_bytes"], 0, device=device_key,
                reason="vram-device-undeclared",
                continuation_id=continuation,
            )
            wait.retry_id = continuation or activity
            with self._condition:
                self._make_resource_wait_locked(
                    wait, activity, continuation, priority, requested,
                    prerequisites, holding,
                )
            raise wait
        # CPU-only work has no VRAM device identity.
        lease_device = device_key
        cores = requested["physical_cores"]
        if cores < 1:
            raise ValueError("physical work must reserve at least one physical core")
        if (
            isinstance(lease_duration_ns, bool)
            or not isinstance(lease_duration_ns, int)
            or lease_duration_ns <= 0
        ):
            raise ValueError("physical work lease duration must be positive")
        for name, amount in requested.items():
            ceiling = self.capacity[name]
            if priority == "background":
                ceiling -= self.foreground_reserve[name]
            if amount > ceiling:
                wait = ResourceWait(
                    name, amount, max(0, ceiling), reason="successor-capacity",
                    continuation_id=continuation,
                )
                wait.retry_id = continuation or activity
                with self._condition:
                    self._make_resource_wait_locked(
                        wait, activity, continuation, priority, requested,
                        prerequisites, holding,
                    )
                raise wait

        queued_at = time.monotonic_ns()
        with self._condition:
            existing = self._leases.get(activity)
            if existing is not None:
                if (
                    existing.priority != priority
                    or existing.continuation_id != continuation
                    or existing.resources != requested
                    or existing.locality_id != locality
                    or existing.batch_id != batch
                    or existing.vram_device != lease_device
                    or getattr(existing, "prerequisite_activity_ids", ()) != prerequisites
                    or getattr(existing, "holding_activity_id", None) != holding
                ):
                    raise ValueError("activity already has a different physical reservation")
                if existing._state in {"open", "fenced"}:
                    return existing
                raise ValueError("activity already has a retired physical reservation")
            while activity in self._admitting:
                if cancel_event is not None and cancel_event.is_set():
                    raise PhysicalAdmissionCancelled(
                        f"physical operation {activity!r} was cancelled while queued"
                    )
                self._condition.wait(timeout=0.05)
                existing = self._leases.get(activity)
                if existing is not None:
                    if (
                        existing.priority == priority
                        and existing.continuation_id == continuation
                        and existing.resources == requested
                        and existing.locality_id == locality
                        and existing.batch_id == batch
                        and existing.vram_device == lease_device
                        and getattr(existing, "prerequisite_activity_ids", ()) == prerequisites
                        and getattr(existing, "holding_activity_id", None) == holding
                        and existing._state == "open"
                    ):
                        return existing
                    raise ValueError("activity already has a physical reservation")
            prior_wait = self._wait_obligations.get(activity)
            if prior_wait is not None and prior_wait.state in {
                "cancelled", "resumed",
            }:
                self._wait_obligations.pop(activity, None)
            self._admitting.add(activity)
            ticket = self._next_ticket
            self._next_ticket += 1
            entry = (
                ticket, priority, cores, locality, batch, queued_at,
                activity, continuation,
            )
            holding_owner = self._holding_activity_locked(
                activity, continuation, holding,
            )
            available_cores = max(
                0, self.capacity["physical_cores"] - self._active_cores,
            )
            core_constraint = "capacity"
            if priority == "background":
                background_room = max(
                    0,
                    self.capacity["physical_cores"]
                    - self.foreground_reserve["physical_cores"]
                    - self._background_cores,
                )
                if background_room <= available_cores:
                    core_constraint = "background-reserve"
                    available_cores = background_room
            core_resource = {
                "tier": "physical_cores",
                "kind": "resident",
                "requested": cores,
                "available": available_cores,
                "reason": "physical-core-capacity",
                "priority": priority,
                "constraint": core_constraint,
            }
            queue_prerequisites = tuple(prerequisites)
            self._queue_requests[activity] = {
                "priority": priority,
                "continuation_id": continuation,
                "holding_activity_id": holding_owner,
                "requested_resources": dict(requested),
                "resource": core_resource,
                "prerequisite_activity_ids": tuple(queue_prerequisites),
                "state": "waiting",
                "cycle_activity_ids": (),
            }
            self._refresh_wait_cycles_locked()
            self._waiting.append(entry)
            self._wait_count += 1
            self._max_queue_depth = max(self._max_queue_depth, len(self._waiting))
            wait_row: dict[str, Any] | None = None
            try:
                while True:
                    request = self._queue_requests[activity]
                    if cancel_event is not None and cancel_event.is_set():
                        request["state"] = "cancelled"
                        request["reason"] = "cancelled-before-admission"
                    if request.get("state") == "cancelled":
                        cancel_reason = request.get(
                            "reason", "cancelled-before-admission"
                        )
                        if entry in self._waiting:
                            self._waiting.remove(entry)
                        self._queue_requests.pop(activity, None)
                        self._new_obligation_locked(
                            activity, continuation, priority, requested,
                            request["resource"],
                            tuple(request["prerequisite_activity_ids"]),
                            holding_owner,
                            reason=cancel_reason, state="cancelled",
                        )
                        self._admitting.discard(activity)
                        self._cancelled_wait_count += 1
                        self._record_waiter_locked(
                            entry, "cancelled", time.monotonic_ns(),
                            reason=cancel_reason,
                        )
                        self._condition.notify_all()
                        raise PhysicalAdmissionCancelled(
                            f"physical operation {activity!r} was cancelled while queued"
                        )
                    if request.get("state") == "blocked":
                        if entry in self._waiting:
                            self._waiting.remove(entry)
                        self._queue_requests.pop(activity, None)
                        resource = dict(request["resource"])
                        resource["available"] = self._available_for_wait_locked(resource)
                        self._record_waiter_locked(
                            entry, "resource-wait", time.monotonic_ns(),
                            reason="wait-cycle",
                        )
                        wait = ResourceWait(
                            "physical_cores", cores, resource["available"],
                            reason="wait-cycle", continuation_id=continuation,
                        )
                        wait.retry_id = continuation or activity
                        self._make_resource_wait_locked(
                            wait, activity, continuation, priority, requested,
                            tuple(request["prerequisite_activity_ids"]),
                            holding_owner,
                        )
                        self._admitting.discard(activity)
                        self._condition.notify_all()
                        raise wait
                    if self._selected_ticket() == entry:
                        self._waiting.remove(entry)
                        self._queue_requests.pop(activity, None)
                        self._active_cores += cores
                        if locality is not None and batch is not None:
                            cohort = (locality, batch)
                            self._active_cohorts[cohort] = self._active_cohorts.get(cohort, 0) + 1
                        if priority == "background":
                            self._background_cores += cores
                            self._foreground_streak = 0
                        else:
                            self._foreground_streak += 1
                        wait_row = self._record_waiter_locked(
                            entry, "selected", time.monotonic_ns(),
                        )
                        break
                    self._refresh_wait_cycles_locked()
                    self._condition.wait(timeout=0.05)
            except BaseException as exc:
                if entry in self._waiting:
                    self._waiting.remove(entry)
                    if isinstance(exc, PhysicalAdmissionCancelled):
                        self._cancelled_wait_count += 1
                        status = "cancelled"
                    else:
                        status = "interrupted"
                    self._record_waiter_locked(
                        entry, status, time.monotonic_ns(),
                        reason=type(exc).__name__,
                    )
                self._queue_requests.pop(activity, None)
                self._admitting.discard(activity)
                self._refresh_wait_cycles_locked()
                self._condition.notify_all()
                raise
        wait_ns = max(0, time.monotonic_ns() - queued_at)
        reservation_id = self._reservation_id(activity)
        try:
            prior = self.journal.reservation(reservation_id)
            if prior is not None:
                _validated_reservation(prior)
        except Exception as exc:
            self._release_lane(priority, cores, locality, batch)
            with self._condition:
                self._admitting.discard(activity)
                self._condition.notify_all()
            self._finish_waiter(
                wait_row, "admission-failed",
                reason=getattr(exc, "reason", type(exc).__name__),
            )
            raise
        if prior is not None:
            _validated_reservation(prior)
            self._release_lane(priority, cores, locality, batch)
            with self._condition:
                self._admitting.discard(activity)
                self._condition.notify_all()
            self._finish_waiter(
                wait_row, "resource-wait",
                reason="reservation-requires-reconciliation",
            )
            wait = ResourceWait(
                "physical_cores", cores, 0,
                reason="reservation-requires-reconciliation",
                continuation_id=continuation,
            )
            wait.retry_id = continuation or activity
            with self._condition:
                self._make_resource_wait_locked(
                    wait, activity, continuation, priority, requested,
                    prerequisites, holding, state="reconciliation-required",
                )
            raise wait
        cap = {name: amount for name, amount in requested.items() if amount}
        reservation: Mapping[str, Any] | None = None
        try:
            reservation = _validated_reservation(self.journal.reserve_resources(
                reservation_id=reservation_id,
                mission_account_id=self.mission_account_id,
                owner_id=self.owner_id,
                member_id=None,
                work_order_id=continuation or activity,
                resource_class=self.resource_class,
                cap=cap,
                capacity=self.capacity,
                foreground_reserve=self.foreground_reserve,
                priority=priority,
                lease_expires_ns=time.time_ns() + lease_duration_ns,
            ))
            tokens = self._physical_tokens(requested, device_key)
        except Exception as exc:
            self._finish_waiter(
                wait_row,
                "resource-wait" if isinstance(exc, ResourceWait) else "admission-failed",
                reason=getattr(exc, "reason", type(exc).__name__),
            )
            reservation_unsettled = False
            if reservation is not None:
                try:
                    self.journal.settle_resources(
                        reservation_id,
                        f"physical-admission-failed:{reservation_id}",
                        measured_consumption={name: 0 for name in cap},
                        status="released",
                        lease_fence=int(reservation["lease"]["fence"]),
                    )
                except Exception:
                    # A durable reservation that could not be settled remains
                    # charged, so a later caller must explicitly reconcile it.
                    reservation_unsettled = True
            self._release_lane(priority, cores, locality, batch)
            with self._condition:
                self._admitting.discard(activity)
                if isinstance(exc, ResourceWait):
                    exc.continuation_id = continuation
                    exc.retry_id = continuation or activity
                    wait = self._make_resource_wait_locked(
                        exc, activity, continuation, priority, requested,
                        prerequisites, holding,
                        state=(
                            "reconciliation-required"
                            if reservation_unsettled else "waiting"
                        ),
                    )
                    if reservation_unsettled and wait.obligation is not None:
                        obligation = replace(
                            wait.obligation,
                            reason="reservation-requires-reconciliation",
                        )
                        self._wait_obligations[activity] = obligation
                        wait.obligation = obligation
                self._condition.notify_all()
            raise
        lease = PhysicalWorkLease(
            self,
            reservation,
            tokens,
            activity_id=activity,
            continuation_id=continuation,
            priority=priority,
            resources=requested,
            wait_ns=wait_ns,
            queued_at_ns=queued_at,
            vram_device=lease_device,
        )
        lease.locality_id = locality
        lease.batch_id = batch
        lease.prerequisite_activity_ids = prerequisites
        lease.holding_activity_id = holding
        with self._condition:
            self._leases[activity] = lease
            self._admitting.discard(activity)
            for key, obligation in tuple(self._wait_obligations.items()):
                if (
                    obligation.retry_id == (continuation or activity)
                    and obligation.state not in {"cancelled", "resumed"}
                ):
                    self._wait_obligations[key] = replace(
                        obligation,
                        state="resumed",
                        cycle_activity_ids=(),
                        reason="resources-acquired",
                        updated_at_ns=time.monotonic_ns(),
                    )
            if wait_row is not None:
                wait_row["status"] = "admitted"
            self._condition.notify_all()
            if len(self._leases) > 1024:
                for key, old in tuple(self._leases.items()):
                    if old._state not in {"open", "fenced"}:
                        self._leases.pop(key)
                        if len(self._leases) <= 768:
                            break
        return lease

    def acquire_group(
        self,
        group_id: str,
        member_count: int,
        member_resources: Mapping[str, int],
        *,
        priority: str = "background",
        continuation_id: str | None = None,
        locality_id: str | None = None,
        batch_id: str | None = None,
        vram_device: str | int | None = None,
        cancel_event: Any | None = None,
        lease_duration_ns: int = 60_000_000_000,
    ) -> PhysicalWorkLease:
        """Reserve one whole group's capacity as a single admission lane.

        ``member_count * member_resources`` is reserved atomically: a group
        that cannot fit in full never starts, so a batched group can neither
        strand a partial reservation nor consume the foreground reserve.
        The group activity identity is ``group_id`` itself, so queue-side
        status, cancellation and release all address the whole group.
        """
        if (
            isinstance(member_count, bool)
            or not isinstance(member_count, int)
            or member_count < 1
        ):
            raise ValueError("group member count must be a positive integer")
        per_member = _physical_vector(member_resources, "group member resources")
        if not any(per_member.values()):
            raise ValueError("group member resources must reserve something")
        total = {
            name: amount * member_count
            for name, amount in per_member.items()
        }
        lease = self.acquire(
            group_id,
            priority,
            continuation_id=continuation_id,
            resources=total,
            locality_id=locality_id,
            batch_id=batch_id,
            vram_device=vram_device,
            cancel_event=cancel_event,
            lease_duration_ns=lease_duration_ns,
        )
        lease.group_member_count = member_count
        lease.group_member_resources = dict(per_member)
        return lease

    def release_group(self, group_id: str, status: str = "completed") -> bool:
        """Release one whole group reservation and every charge it holds."""
        if status not in {"completed", "failed", "cancelled", "released"}:
            raise ValueError("group release status is invalid")
        lease = self.get_lease(group_id)
        if lease is None or lease._state != "open":
            return False
        lease.retire(status)
        return True

    def get_wait_status(self, activity_id: str) -> dict[str, Any]:
        """Return the exact parked resource obligation without granting a slot."""
        activity = self._activity_text(activity_id, "activity_id")
        with self._condition:
            self._refresh_wait_obligations_locked()
            obligation = self._wait_obligations.get(activity)
            if obligation is not None:
                return obligation.as_dict()
            queued = self._queue_requests.get(activity)
            if queued is not None:
                return {
                    "kind": "physical-resource-prerequisite",
                    "activity_id": activity,
                    "continuation_id": queued.get("continuation_id"),
                    "retry_id": queued.get("continuation_id") or activity,
                    "holding_activity_id": queued.get("holding_activity_id"),
                    "priority": queued.get("priority"),
                    "requested_resources": dict(queued["requested_resources"]),
                    "resource": dict(queued["resource"]),
                    "prerequisite_activity_ids": list(
                        queued["prerequisite_activity_ids"]
                    ),
                    "blocked_by_activity_ids": list(
                        self._blocking_activities_locked(queued["resource"])
                    ),
                    "cycle_activity_ids": list(queued.get("cycle_activity_ids", ())),
                    "state": queued.get("state", "waiting"),
                    "reason": queued.get("reason", "physical-core-capacity"),
                }
            return {
                "kind": "physical-resource-prerequisite",
                "activity_id": activity,
                "state": "not-waiting",
                "prerequisite_activity_ids": [],
                "blocked_by_activity_ids": [],
                "cycle_activity_ids": [],
            }

    def cancel_wait(self, activity_id: str) -> dict[str, Any]:
        """Cancel one exact parked continuation; held leases remain untouched."""
        activity = self._activity_text(activity_id, "activity_id")
        with self._condition:
            now = time.monotonic_ns()
            queued = self._queue_requests.get(activity)
            if queued is not None:
                queued["state"] = "cancelled"
                queued["reason"] = "cancelled-by-owner"
                cancelled = self._new_obligation_locked(
                    activity,
                    queued.get("continuation_id"),
                    queued["priority"],
                    queued["requested_resources"],
                    queued["resource"],
                    tuple(queued["prerequisite_activity_ids"]),
                    queued.get("holding_activity_id"),
                    reason="cancelled-by-owner",
                    state="cancelled",
                )
                self._condition.notify_all()
                return cancelled.as_dict()
            obligation = self._wait_obligations.get(activity)
            if obligation is None or obligation.state in {"cancelled", "resumed"}:
                return self.get_wait_status(activity)
            cancelled = replace(
                obligation,
                state="cancelled",
                cycle_activity_ids=(),
                reason="cancelled-by-owner",
                updated_at_ns=now,
            )
            self._wait_obligations[activity] = cancelled
            self._refresh_wait_cycles_locked()
            self._condition.notify_all()
            return cancelled.as_dict()

    def get_lease(self, activity_id: str) -> PhysicalWorkLease | None:
        """Return the live in-process lease for an exact activity identity."""
        activity = self._activity_text(activity_id, "activity_id")
        with self._condition:
            return self._leases.get(activity)

    def get_activity_status(self, activity_id: str) -> dict[str, Any]:
        """Return durable admission state without allocating execution credit.

        An open reservation from a previous process is not reusable: its worker
        may still be using the device, so it requires explicit observation and
        reconciliation. In-process open leases are reported as active.
        """
        activity = self._activity_text(activity_id, "activity_id")
        resource_wait = self.get_wait_status(activity)
        reservation_id = self._reservation_id(activity)
        reservation = self.journal.reservation(reservation_id)
        if reservation is None:
            return {
                "activity_id": activity,
                "reservation_id": reservation_id,
                "status": "not-admitted",
                "state": None,
                "reservation": None,
                "resource_wait": resource_wait,
            }
        _validated_reservation(reservation)

        state = reservation.get("state")
        terminal_states = {"completed", "failed", "cancelled", "released"}
        if state in terminal_states:
            status = "retired"
        else:
            with self._condition:
                lease = self._leases.get(activity)
            durable_lease = reservation.get("lease")
            if (
                state in {"reserved", "running"}
                and isinstance(durable_lease, Mapping)
                and durable_lease.get("state") == "open"
                and lease is not None
                and lease._state == "open"
            ):
                status = "active"
            else:
                status = "reconciliation-required"
        return {
            "activity_id": activity,
            "reservation_id": reservation_id,
            "status": status,
            "state": state,
            "reservation": reservation,
            "resource_wait": resource_wait,
        }

    def _release_lane(
        self,
        priority: str,
        cores: int,
        locality: str | None = None,
        batch: str | None = None,
    ) -> None:
        with self._condition:
            self._active_cores = max(0, self._active_cores - cores)
            if priority == "background":
                self._background_cores = max(0, self._background_cores - cores)
            if locality is not None and batch is not None:
                cohort = (locality, batch)
                remaining = self._active_cohorts.get(cohort, 0) - 1
                if remaining > 0:
                    self._active_cohorts[cohort] = remaining
                else:
                    self._active_cohorts.pop(cohort, None)
            self._refresh_wait_obligations_locked()
            self._condition.notify_all()

    def _record(
        self,
        lease: PhysicalWorkLease,
        status: str,
        measured: Mapping[str, int],
        *,
        ended_ns: int,
    ) -> None:
        active_ns = max(0, ended_ns - lease.started_ns)
        stage_rows = {
            name: {
                "start_ns": bounds["start"],
                "end_ns": bounds["end"],
                "wall_ns": max(0, bounds["end"] - bounds["start"]),
            }
            for name, bounds in lease._stages.items()
            if "start" in bounds and "end" in bounds
        }
        ordered = sorted(
            (item["start_ns"], item["end_ns"]) for item in stage_rows.values()
        )
        covered_ns = 0
        covered_end = 0
        for start_ns, end_ns in ordered:
            covered_ns += max(0, end_ns - max(start_ns, covered_end))
            covered_end = max(covered_end, end_ns)
        stage_wall_ns = sum(item["wall_ns"] for item in stage_rows.values())
        row = {
            "activity_id": lease.activity_id,
            "continuation_id": lease.continuation_id,
            "reservation_id": lease.reservation_id,
            "priority": lease.priority,
            "locality_id": getattr(lease, "locality_id", None),
            "batch_id": getattr(lease, "batch_id", None),
            "vram_device": lease.vram_device,
            "status": status,
            "queued_at_ns": lease.queued_at_ns,
            "admitted_at_ns": lease.started_ns,
            "ended_at_ns": ended_ns,
            "wait_ns": lease.wait_ns,
            "active_ns": active_ns,
            "stages": stage_rows,
            "critical_path_ns": max(active_ns, covered_ns),
            "overlap_ns": max(0, stage_wall_ns - covered_ns),
            "cache_window_bytes": lease._cache_window_bytes,
            "cache_window_peak_bytes": lease._cache_peak_bytes,
            "reserved": dict(lease.resources),
            "measured": dict(measured),
        }
        with self._condition:
            self._trace.append(row)
            del self._trace[:-128]

    def _retire_lane(
        self,
        lease: PhysicalWorkLease,
        status: str,
        measured: Mapping[str, int],
    ) -> None:
        self._record(lease, status, measured, ended_ns=time.monotonic_ns())
        self._release_lane(
            lease.priority,
            lease.resources["physical_cores"],
            getattr(lease, "locality_id", None),
            getattr(lease, "batch_id", None),
        )
    def _mark_reconciled_waits_locked(self, reservation_id: str) -> None:
        for key, obligation in tuple(self._wait_obligations.items()):
            if (
                obligation.state == "reconciliation-required"
                and obligation.reason == "reservation-requires-reconciliation"
                and self._reservation_id(key) == reservation_id
            ):
                self._wait_obligations[key] = replace(
                    obligation,
                    state="ready",
                    reason="reservation-reconciled",
                    updated_at_ns=time.monotonic_ns(),
                )
        self._refresh_wait_obligations_locked()


    def reconcile(
        self,
        reservation_id: str,
        reconciliation_id: str,
        *,
        observed_released: bool,
        measured_consumption: Mapping[str, int] | None = None,
    ) -> Mapping[str, Any]:
        """Reconcile a fenced operation after restart or a late device result."""
        reservation = self.journal.reservation(reservation_id)
        if reservation is None:
            raise ValueError("physical work reservation is unavailable")
        _validated_reservation(reservation)
        measured = (
            dict(reservation.get("cap", {}))
            if measured_consumption is None
            else _physical_vector(measured_consumption, "measured consumption")
        )
        result = self.journal.reconcile_resources(
            reservation_id,
            reconciliation_id,
            observed_released=observed_released,
            measured_consumption=measured if observed_released else None,
        )
        if observed_released:
            with self._condition:
                self._mark_reconciled_waits_locked(reservation_id)
                self._condition.notify_all()
        return result

    def report(self) -> dict[str, Any]:
        with self._condition:
            self._refresh_wait_obligations_locked()
            rows = tuple(self._trace)
            waiting = tuple(
                row for row in self._waiting
                if self._queue_requests.get(row[6], {}).get("state", "waiting")
                == "waiting"
            )
            wait_history = tuple(dict(row) for row in self._wait_history)
            resource_waits = [
                row.as_dict()
                for row in self._wait_obligations.values()
                if row.state not in {"cancelled", "resumed"}
            ]
            resource_waits.extend(
                {
                    "kind": "physical-resource-prerequisite",
                    "activity_id": activity,
                    "continuation_id": request.get("continuation_id"),
                    "retry_id": request.get("continuation_id") or activity,
                    "holding_activity_id": request.get("holding_activity_id"),
                    "priority": request.get("priority"),
                    "requested_resources": dict(request["requested_resources"]),
                    "resource": dict(request["resource"]),
                    "prerequisite_activity_ids": list(
                        request["prerequisite_activity_ids"]
                    ),
                    "blocked_by_activity_ids": list(
                        self._blocking_activities_locked(request["resource"])
                    ),
                    "cycle_activity_ids": list(
                        request.get("cycle_activity_ids", ())
                    ),
                    "state": request.get("state", "waiting"),
                    "reason": "physical-core-capacity",
                }
                for activity, request in self._queue_requests.items()
                if request.get("state") == "blocked"
            )
            blocked_waits = [
                row for row in resource_waits if row.get("state") == "blocked"
            ]
            priority_lends = list(self._last_lent_activity_ids)

            def distribution(values: list[int]) -> dict[str, int]:
                ordered = sorted(values)
                if not ordered:
                    return {
                        "count": 0, "mean": 0, "p50": 0,
                        "p95": 0, "p99": 0, "max": 0,
                    }

                def percentile(fraction: float) -> int:
                    index = max(0, math.ceil(fraction * len(ordered)) - 1)
                    return ordered[index]

                return {
                    "count": len(ordered),
                    "mean": sum(ordered) // len(ordered),
                    "p50": percentile(0.50),
                    "p95": percentile(0.95),
                    "p99": percentile(0.99),
                    "max": ordered[-1],
                }

            continuations: dict[str, int] = {}
            awaiting_retry: set[str] = set()
            retries = 0
            for row in rows:
                key = row["continuation_id"] or row["activity_id"]
                if key in awaiting_retry:
                    retries += 1
                    awaiting_retry.remove(key)
                continuations[key] = continuations.get(key, 0) + 1
                if row["status"] in {"failed", "reconciliation-required"}:
                    awaiting_retry.add(key)

            def byte_totals(field: str) -> dict[str, int]:
                return {
                    name: sum(
                        int(row[field].get(name, 0))
                        for row in rows
                    )
                    for name in PHYSICAL_RESOURCE_NAMES[1:]
                }

            stage_wall_ns = {
                name: distribution([
                    int(row["stages"][name]["wall_ns"])
                    for row in rows if name in row["stages"]
                ])
                for name in ("transfer", "compute", "commit")
            }
            recent_work = [
                {
                    **row,
                    "reserved": dict(row["reserved"]),
                    "measured": dict(row["measured"]),
                }
                for row in rows
            ]
            concurrent_overlaps: list[dict[str, Any]] = []
            for index, left in enumerate(recent_work):
                for right in recent_work[index + 1:]:
                    if left["activity_id"] == right["activity_id"]:
                        continue
                    for left_stage, left_span in left["stages"].items():
                        for right_stage, right_span in right["stages"].items():
                            start_ns = max(left_span["start_ns"], right_span["start_ns"])
                            end_ns = min(left_span["end_ns"], right_span["end_ns"])
                            if end_ns > start_ns:
                                concurrent_overlaps.append({
                                    "left_activity_id": left["activity_id"],
                                    "left_stage": left_stage,
                                    "right_activity_id": right["activity_id"],
                                    "right_stage": right_stage,
                                    "start_ns": start_ns,
                                    "end_ns": end_ns,
                                    "overlap_ns": end_ns - start_ns,
                                })
            concurrent_overlaps = concurrent_overlaps[-128:]
            foreground = [row for row in rows if row["priority"] == "foreground"]
            waiting_work = [
                {
                    "ticket": row[0],
                    "priority": row[1],
                    "requested_cores": row[2],
                    "locality_id": row[3],
                    "batch_id": row[4],
                    "queued_at_ns": row[5],
                    "activity_id": row[6],
                    "continuation_id": row[7],
                }
                for row in waiting
            ]
            waiter_continuations: dict[str, int] = {}
            for row in wait_history:
                key = row["continuation_id"] or row["activity_id"]
                waiter_continuations[key] = waiter_continuations.get(key, 0) + 1
            waiter_outcomes: dict[str, int] = {}
            for row in wait_history:
                status = str(row["status"])
                waiter_outcomes[status] = waiter_outcomes.get(status, 0) + 1
            queue_depth = len(waiting)
            return {
                "capacity": dict(self.capacity),
                "foreground_reserve": dict(self.foreground_reserve),
                "active_physical_cores": self._active_cores,
                "active_background_cores": self._background_cores,
                "queued": queue_depth,
                "waiting_work": waiting_work,
                "resource_waits": resource_waits,
                "blocked_waits": blocked_waits,
                "priority_lends": priority_lends,
                "foreground_queued": sum(row[1] == "foreground" for row in waiting),
                "background_queued": sum(row[1] == "background" for row in waiting),
                "max_queue_depth": self._max_queue_depth,
                "wait_count": self._wait_count,
                "cancelled_wait_count": self._cancelled_wait_count,
                "resource_wait_count": self._resource_wait_count,
                "wait_history": list(wait_history),
                "recent_work": recent_work,
                "concurrent_overlaps": concurrent_overlaps,
                "telemetry": {
                    "attempts": len(rows),
                    "unique_continuations": len(continuations),
                    "window_size": len(rows),
                    "wait_ns": distribution([int(row["wait_ns"]) for row in rows]),
                    "queue_wait_ns": distribution([
                        int(row["wait_ns"]) for row in wait_history
                    ]),
                    "cancelled_queue_wait_ns": distribution([
                        int(row["wait_ns"]) for row in wait_history
                        if row["status"] == "cancelled"
                    ]),
                    "waiter_outcomes": waiter_outcomes,
                    "waiter_continuations": waiter_continuations,
                    "cancelled_wait_count": self._cancelled_wait_count,
                    "resource_wait_count": self._resource_wait_count,
                    "active_ns": distribution([int(row["active_ns"]) for row in rows]),
                    "stage_wall_ns": stage_wall_ns,
                    "critical_path_ns": distribution(
                        [int(row["critical_path_ns"]) for row in rows]
                    ),
                    "overlap_ns": distribution(
                        [int(row["overlap_ns"]) for row in rows]
                    ),
                    "concurrent_overlap_ns": distribution([
                        int(row["overlap_ns"]) for row in concurrent_overlaps
                    ]),
                    "cache_window_peak_bytes": max(
                        (int(row["cache_window_peak_bytes"]) for row in rows),
                        default=0,
                    ),
                    "foreground_wait_ns": distribution(
                        [int(row["wait_ns"]) for row in foreground]
                    ),
                    "foreground_active_ns": distribution(
                        [int(row["active_ns"]) for row in foreground]
                    ),
                    "reserved_bytes": byte_totals("reserved"),
                    "measured_bytes": byte_totals("measured"),
                    "peak_reserved_bytes": max(
                        (int(row["reserved"].get("peak_bytes", 0)) for row in rows),
                        default=0,
                    ),
                    "peak_measured_bytes": max(
                        (int(row["measured"].get("peak_bytes", 0)) for row in rows),
                        default=0,
                    ),
                    "retries_by_continuation": retries,
                    "fences": sum(
                        row["status"] == "reconciliation-required" for row in rows
                    ),
                },
                "residency": self.manager.report(),
            }
