"""Fixed physical resource policy for the one owner-operated regional field.

Reservations are operational state, not learned memory.  Scratch and transfer
buffers consume their physical tier as well as their independent sublimit.
Nothing in this module advances field time or chooses a scientific objective.
"""
from __future__ import annotations

import ctypes
import math
import os
import shutil
import threading
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, Mapping


RESOURCE_SCHEMA = "cassifi.elastic-resources.v1"
TIERS = ("ram", "vram", "storage")
KINDS = ("resident", "scratch", "transfer")


class ResourceWait(ValueError):
    """An operation can retain its continuation until resources are available."""

    def __init__(self, tier: str, requested: int, available: int, *,
                 kind: str = "resident", reason: str = "capacity") -> None:
        self.tier = tier
        self.requested = int(requested)
        self.available = max(0, int(available))
        self.kind = kind
        self.reason = reason
        super().__init__(f"{tier} {kind} needs {requested} bytes; "
                         f"{self.available} available ({reason})")

    def as_dict(self) -> dict[str, Any]:
        return {"schema": RESOURCE_SCHEMA, "status": "resource-wait",
                "tier": self.tier, "kind": self.kind, "reason": self.reason,
                "requested_bytes": self.requested,
                "available_bytes": self.available}


@dataclass(frozen=True, slots=True)
class ResourceLimits:
    ram_bytes: int = 64 * 1024 * 1024
    vram_bytes: int = 64 * 1024 * 1024
    storage_bytes: int = 1024 * 1024 * 1024
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
    __slots__ = ("manager", "tier", "kind", "nbytes", "released", "program_id")

    def __init__(
        self,
        manager: "ResidencyManager",
        tier: str,
        kind: str,
        nbytes: int,
        program_id: str | None = None,
    ) -> None:
        self.manager, self.tier, self.kind = manager, tier, kind
        self.nbytes, self.released = nbytes, False
        self.program_id = program_id

    def release(self) -> None:
        with self.manager._lock:
            if not self.released:
                self.manager._used[self.tier][self.kind] -= self.nbytes
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
        self._lock = threading.RLock()
        self._used = {tier: {kind: 0 for kind in KINDS} for tier in TIERS}
        self._high = {tier: 0 for tier in TIERS}
        self._kind_high = {kind: 0 for kind in KINDS}
        self._physical: dict[str, int] = {}
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

    def _physical_available(self, tier: str) -> int:
        try:
            if tier == "ram":
                value = max(0, available_ram_bytes() - self.limits.ram_headroom_bytes)
            elif tier == "vram":
                import torch
                if not torch.cuda.is_available():
                    raise ResourceWait(tier, 0, 0, reason="device-unavailable")
                free, _total = torch.cuda.mem_get_info()
                value = max(0, int(free) - self.limits.vram_headroom_bytes)
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

    def available(self, tier: str) -> int:
        if tier not in TIERS:
            raise ValueError(f"unsupported resource tier: {tier}")
        with self._lock:
            remaining = self._budget[tier] - sum(self._used[tier].values())
            return max(0, min(remaining, self._physical_available(tier)))

    def room(self, tier: str) -> int:
        """The measured physical room on one tier, ignoring reservations.

        A consumer that can release its own reservations uses this to tell a
        ceiling it can lift from a ceiling the machine imposes.
        """

        if tier not in TIERS:
            raise ValueError(f"unsupported resource tier: {tier}")
        with self._lock:
            return self._physical_available(tier)

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

    def _widen(self, tier: str, byte_count: int, kind: str = "resident") -> int:
        """Widen one tier share, and its allocation kind, within measured room.

        A tier budget is the field's declared share of a physical tier and a
        kind budget is that share's independent sublimit.  When the policy
        grants growth, a reservation that does not fit its declared share may
        widen both up to the room the machine reports, so the field uses
        capacity that exists rather than a placeholder slice of it.  The kind
        sublimit never exceeds the tier it is drawn from.
        """

        if not self.limits.auto_grow or kind not in KINDS:
            return 0
        physical = self._physical_available(tier)
        used = sum(self._used[tier].values())
        current = self._budget[tier]
        # Grow into room the machine reports, but stop at the declared low
        # watermark: the share it takes leaves working room for the rest of
        # the field to page, load, and generate in.
        ceiling = int(physical * self.limits.low_watermark)
        target = min(ceiling, max(used + byte_count, current * 2))
        if target > current:
            self._budget[tier] = target
            self._growths.append(
                {
                    "scope": "tier",
                    "tier": tier,
                    "from_bytes": current,
                    "to_bytes": target,
                    "requested_bytes": int(byte_count),
                    "used_bytes": used,
                    "physical_bytes": int(self._physical.get(tier, 0)),
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
    ) -> _Reservation:
        if tier not in TIERS or kind not in KINDS:
            raise ValueError("invalid physical tier or allocation kind")
        if isinstance(byte_count, bool) or not isinstance(byte_count, int) or byte_count < 0:
            raise ValueError("reserved byte count must be a nonnegative integer")
        with self._lock:
            try:
                if self.limits.auto_grow and byte_count > (
                    self._budget[tier] - sum(self._used[tier].values())
                ):
                    self._widen(tier, byte_count, kind)
                available = self.available(tier)
                if kind != "resident":
                    occupied = sum(row[kind] for row in self._used.values())
                    available = min(available, self._kind_budget[kind] - occupied)
                    if byte_count > available:
                        self._widen(tier, byte_count, kind)
                        available = min(
                            self.available(tier), self._kind_budget[kind] - occupied
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
                            kind=kind,
                            reason="program-budget" if not optional else "prefetch-pressure",
                        )
                if byte_count > available:
                    raise ResourceWait(
                        tier, byte_count, available, kind=kind,
                        reason="prefetch-pressure" if optional else "capacity",
                    )
            except ResourceWait as exc:
                self._waits += 1
                self._last_wait = exc.as_dict()
                raise
            self._used[tier][kind] += byte_count
            if program_id is not None and program_id in self._programs:
                self._program_used[program_id][tier] += byte_count
            self._high[tier] = max(self._high[tier], sum(self._used[tier].values()))
            self._kind_high[kind] = max(
                self._kind_high[kind],
                sum(row[kind] for row in self._used.values()),
            )
            token = _Reservation(self, tier, kind, byte_count, program_id)
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
            if used["ram"] > configured["maximum_bytes"]:
                raise ResourceWait(
                    "ram", used["ram"], configured["maximum_bytes"],
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
            return {
                "schema": RESOURCE_SCHEMA,
                "limits": self.limits.as_dict(),
                "budget_bytes": dict(self._budget),
                "kind_budget_bytes": dict(self._kind_budget),
                "growths": [dict(row) for row in self._growths],
                "used_bytes": {
                    tier: sum(row.values()) for tier, row in self._used.items()
                },
                "allocations": {tier: dict(row) for tier, row in self._used.items()},
                "high_water_bytes": dict(self._high),
                "kind_high_water_bytes": dict(self._kind_high),
                "last_available_bytes": dict(self._physical),
                "wait_count": self._waits,
                "last_wait": None if self._last_wait is None else dict(self._last_wait),
                "programs": self.program_reports(),
            }
