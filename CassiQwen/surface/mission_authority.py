"""In-memory, host-owned authorization windows for Surface operations."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


_MAX_WINDOW_NS = 24 * 60 * 60 * 1_000_000_000
_MAX_GRANT_NS = 60 * 60 * 1_000_000_000
_MAX_UPDATES = 4096
_MAX_OPERATIONS = 16
_SOURCE_FIELDS = (
    "binding_id",
    "backend_id",
    "source_id",
    "source_instance",
    "source_epoch",
    "environment_incarnation",
    "geometry_revision",
)
_STABLE_SOURCE_FIELDS = (
    "backend_id",
    "source_id",
    "source_instance",
    "environment_incarnation",
)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _mission_digest(program: Mapping[str, Any]) -> str:
    generation = program.get("generation")
    if isinstance(generation, bool) or not isinstance(generation, int) or generation < 0:
        raise PermissionError("the active research program has no valid generation")
    payload = {
        "title": str(program.get("title", "")),
        "mission": str(program.get("mission", "")),
        "generation": generation,
    }
    return hashlib.sha256(_canonical(payload)).hexdigest()


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > 256:
        raise ValueError(f"{label} must be a nonempty identifier")
    return value


def _integer(value: Any, label: str, minimum: int, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{label} must be an integer of at least {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{label} must not exceed {maximum}")
    return value


def _operations(value: Any) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or not value or len(value) > _MAX_OPERATIONS:
        raise ValueError("operations must contain 1–16 supported operation names")
    result: list[str] = []
    for item in value:
        operation = _identifier(item, "operation")
        if len(operation) > 96 or operation in result:
            raise ValueError("operations must be unique supported operation names")
        result.append(operation)
    return tuple(result)


@dataclass(frozen=True)
class _Approval:
    program_id: str
    generation: int
    mission_sha256: str
    source: Mapping[str, Any]
    operations: frozenset[str]
    expires_ns: int
    deadline_monotonic_ns: int
    max_updates: int
    max_lease_ns: int


class MissionAuthority:
    """Loopback-owned, source-bound approval windows for Surface operations.

    Local same-origin consent creates exact, bounded in-memory mission
    approvals. Human takeover is separately confirmed at its point of use.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._approvals: dict[tuple[str, ...], _Approval] = {}
        self._pending_takeovers: dict[tuple[str, str], _Approval] = {}
        self._entity: Any | None = None

    @staticmethod
    def _key(program_id: str, source: Mapping[str, Any]) -> tuple[str, ...]:
        return (program_id, *(_identifier(source.get(name), name) for name in _STABLE_SOURCE_FIELDS))

    def bind_entity(self, entity: Any) -> None:
        self._entity = entity


    @staticmethod
    def _active_program(entity: Any, program_id: str) -> Mapping[str, Any]:
        program = entity.researcher.program(program_id)
        if not isinstance(program, Mapping) or program.get("program_id") != program_id or program.get("status") != "active":
            raise PermissionError("Surface access requires the same existing active research program")
        return program

    @classmethod
    def _current_source(cls, entity: Any, request: Mapping[str, Any], *, require_visible_identity: bool) -> tuple[Mapping[str, Any], Mapping[str, Any], int, str]:
        program_id = _identifier(request.get("program_id"), "program_id")
        binding_id = _identifier(request.get("binding_id"), "binding_id")
        program = cls._active_program(entity, program_id)
        generation = program.get("generation")
        if isinstance(generation, bool) or not isinstance(generation, int) or generation < 0:
            raise PermissionError("the active research program has no valid generation")
        digest = _mission_digest(program)
        if request.get("program_generation") != generation or request.get("mission_sha256") != digest:
            raise PermissionError("the active mission changed; approve its current identity explicitly")
        binding = entity.inspect_surface_binding(binding_id, program_id=program_id)
        if not isinstance(binding, Mapping) or binding.get("binding_id") != binding_id or binding.get("detached") is True:
            raise PermissionError("approval requires the current attached source binding")
        identity: dict[str, Any] = {key: binding.get(key) for key in _SOURCE_FIELDS}
        if not all(identity.get(key) is not None for key in _SOURCE_FIELDS):
            raise PermissionError("the source binding lacks a complete dynamic identity")
        for key in _SOURCE_FIELDS:
            if request.get(key) != identity[key]:
                raise PermissionError("the approved source identity changed; inspect and approve it again")
        if require_visible_identity:
            source_rows = entity.surface_sources(identity["backend_id"], program_id=program_id)
            source = next((row for row in source_rows if row.get("source_id") == identity["source_id"]), None)
            if not isinstance(source, Mapping):
                raise PermissionError("the exact source is not currently available to this program")
            available = set(source.get("operations", ()))
            if not set(_operations(request.get("operations"))).issubset(available):
                raise PermissionError("an approved operation is outside the current source scope")
        return program, identity, generation, digest

    def approve_mission(self, entity: Any, request: Mapping[str, Any]) -> Mapping[str, Any]:
        program, source, generation, digest = self._current_source(entity, request, require_visible_identity=True)
        del program
        operations = _operations(request.get("operations"))
        expires_ns = _integer(request.get("expires_ns"), "expires_ns", 1)
        now_wall = time.time_ns()
        duration_ns = expires_ns - now_wall
        if duration_ns <= 0 or duration_ns > _MAX_WINDOW_NS:
            raise ValueError("mission approval expiry must be within the next 24 hours")
        max_updates = _integer(request.get("max_updates"), "max_updates", 1, _MAX_UPDATES)
        max_lease_seconds = _integer(
            request.get("max_lease_seconds"),
            "max_lease_seconds",
            1,
            _MAX_GRANT_NS // 1_000_000_000,
        )
        approval = _Approval(
            program_id=_identifier(request.get("program_id"), "program_id"),
            generation=generation,
            mission_sha256=digest,
            source=dict(source),
            operations=frozenset(operations),
            expires_ns=expires_ns,
            deadline_monotonic_ns=time.monotonic_ns() + duration_ns,
            max_updates=max_updates,
            max_lease_ns=max_lease_seconds * 1_000_000_000,
        )
        key = self._key(approval.program_id, source)
        with self._lock:
            self._approvals[key] = approval
        return {
            "state": "approved",
            "program_id": approval.program_id,
            "program_generation": approval.generation,
            "mission_sha256": approval.mission_sha256,
            **dict(approval.source),
            "operations": list(operations),
            "expires_ns": expires_ns,
            "max_updates": max_updates,
            "max_lease_seconds": max_lease_seconds,
        }

    def _matching_approval(self, proposal: Mapping[str, Any]) -> _Approval:
        purpose = proposal.get("purpose")
        mission_id = proposal.get("mission_id")
        binding_id = proposal.get("binding_id")
        if not isinstance(mission_id, str) or not isinstance(binding_id, str):
            raise PermissionError("Surface proposal has no approved mission and binding identity")
        if purpose == "surface-grant":
            key = self._key(mission_id, proposal)
            with self._lock:
                approval = self._approvals.get(key)
        elif purpose == "surface-human-control":
            key = (mission_id, binding_id)
            with self._lock:
                approval = self._pending_takeovers.get(key)
        else:
            raise PermissionError("unsupported Surface authorization purpose")
        if approval is None:
            raise PermissionError("no active host approval matches this Surface mission and source")
        now_wall = time.time_ns()
        now_mono = time.monotonic_ns()
        if now_wall >= approval.expires_ns or now_mono >= approval.deadline_monotonic_ns:
            if purpose == "surface-grant":
                with self._lock:
                    if self._approvals.get(key) is approval:
                        self._approvals.pop(key, None)
            raise PermissionError("the host Surface approval window has expired")
        if purpose == "surface-grant":
            if proposal.get("mission_id") != approval.program_id:
                raise PermissionError("Surface proposal belongs to another mission")
        fields = _SOURCE_FIELDS
        for key_name in fields:
            if proposal.get(key_name) != approval.source.get(key_name):
                raise PermissionError("the Surface source identity changed after approval")
        if self._entity is None:
            raise PermissionError("the host Surface authority is not attached to its entity")
        program = self._active_program(self._entity, approval.program_id)
        if program.get("generation") != approval.generation or _mission_digest(program) != approval.mission_sha256:
            if purpose == "surface-grant":
                with self._lock:
                    if self._approvals.get(key) is approval:
                        self._approvals.pop(key, None)
            raise PermissionError("the active mission changed after host approval")
        current = self._entity.inspect_surface_binding(binding_id, program_id=approval.program_id)
        if not isinstance(current, Mapping) or current.get("detached") is True or any(
            current.get(key_name) != approval.source.get(key_name) for key_name in fields
        ):
            raise PermissionError("the approved source binding is no longer current")
        requested = _operations(proposal.get("operations"))
        if not set(requested).issubset(approval.operations):
            raise PermissionError("Surface proposal expands the host-approved operation set")
        requested_expiry = _integer(proposal.get("expires_ns"), "expires_ns", 1)
        if requested_expiry <= now_mono or requested_expiry > approval.deadline_monotonic_ns:
            raise PermissionError("Surface broker lease exceeds the host approval window")
        if purpose == "surface-grant" and requested_expiry - now_mono > approval.max_lease_ns:
            raise PermissionError("Surface broker lease exceeds the locally approved lease duration")
        scope = proposal.get("scope")
        if not isinstance(scope, Mapping):
            raise PermissionError("Surface grant proposal has no exact scope")
        if purpose == "surface-grant":
            if (
                scope.get("program_id") != approval.program_id
                or scope.get("program_generation") != approval.generation
                or scope.get("mission_sha256") != approval.mission_sha256
            ):
                raise PermissionError("Surface grant mission identity differs from the approved window")
            max_updates = _integer(scope.get("max_updates"), "max_updates", 1, _MAX_UPDATES)
            if max_updates > approval.max_updates:
                raise PermissionError("Surface grant exceeds the host-approved update limit")
        elif purpose == "surface-human-control":
            if set(requested) != approval.operations:
                raise PermissionError("human control must match its separately approved exact operation set")
        else:
            raise PermissionError("unsupported Surface authorization purpose")
        return approval

    def __call__(self, proposal: Mapping[str, Any]) -> Mapping[str, Any]:
        if not isinstance(proposal, Mapping):
            raise PermissionError("invalid Surface authorization proposal")
        self._matching_approval(proposal)
        operations = _operations(proposal.get("operations"))
        scope = proposal.get("scope")
        if not isinstance(scope, Mapping):
            raise PermissionError("Surface grant proposal has no exact scope")
        return {"approved": True, "operations": list(operations), "scope": dict(scope)}

    def status(self, program_id: str, binding_id: str) -> Mapping[str, Any]:
        program_id = _identifier(program_id, "program_id")
        binding_id = _identifier(binding_id, "binding_id")
        if self._entity is None:
            raise PermissionError("the host Surface authority is not attached to its entity")
        current = self._entity.inspect_surface_binding(binding_id, program_id=program_id)
        program = self._active_program(self._entity, program_id)
        key = self._key(program_id, current)
        with self._lock:
            approval = self._approvals.get(key)
            if approval is not None and (
                time.time_ns() >= approval.expires_ns
                or time.monotonic_ns() >= approval.deadline_monotonic_ns
                or program.get("generation") != approval.generation
                or _mission_digest(program) != approval.mission_sha256
                or any(current.get(name) != approval.source.get(name) for name in _SOURCE_FIELDS)
            ):
                self._approvals.pop(key, None)
                approval = None
        if approval is None:
            return {"configured": True, "active": False, "state": "none"}
        return {
            "configured": True,
            "active": True,
            "state": "active",
            "program_id": approval.program_id,
            "program_generation": approval.generation,
            "mission_sha256": approval.mission_sha256,
            **dict(approval.source),
            "operations": sorted(approval.operations),
            "expires_ns": approval.expires_ns,
            "max_updates": approval.max_updates,
            "max_lease_seconds": approval.max_lease_ns // 1_000_000_000,
        }

    def revoke_approval(self, program_id: str, binding_id: str) -> bool:
        program_id = _identifier(program_id, "program_id")
        binding_id = _identifier(binding_id, "binding_id")
        current = None
        if self._entity is not None:
            try:
                current = self._entity.inspect_surface_binding(binding_id, program_id=program_id)
            except Exception:
                # Emergency revocation still removes the original approval if its binding vanished.
                pass
        current_key = self._key(program_id, current) if isinstance(current, Mapping) else None
        with self._lock:
            keys = [
                key for key, approval in self._approvals.items()
                if approval.program_id == program_id and (
                    key == current_key or approval.source.get("binding_id") == binding_id
                )
            ]
            for key in keys:
                self._approvals.pop(key, None)
            self._pending_takeovers.pop((program_id, binding_id), None)
        return bool(keys)

    def take_control(self, entity: Any, request: Mapping[str, Any]) -> Mapping[str, Any]:
        program_id = _identifier(request.get("program_id"), "program_id")
        binding_id = _identifier(request.get("binding_id"), "binding_id")
        program, source, generation, digest = self._current_source(entity, request, require_visible_identity=True)
        del program
        operations = _operations(request.get("operations"))
        expires_ns = _integer(request.get("expires_ns"), "expires_ns", 1)
        now_wall = time.time_ns()
        duration_ns = expires_ns - now_wall
        if duration_ns <= 0 or duration_ns > _MAX_GRANT_NS:
            raise ValueError("human-control approval must be within the next hour")
        approval = _Approval(
            program_id=program_id,
            generation=generation,
            mission_sha256=digest,
            source=dict(source),
            operations=frozenset(operations),
            expires_ns=expires_ns,
            deadline_monotonic_ns=time.monotonic_ns() + duration_ns,
            max_updates=_MAX_UPDATES,
            max_lease_ns=duration_ns,
        )
        key = (program_id, binding_id)
        with self._lock:
            if key in self._pending_takeovers:
                raise PermissionError("a human-control approval is already in progress for this source")
            self._pending_takeovers[key] = approval
        try:
            return entity.take_surface_control(
                binding_id,
                program_id=program_id,
                operations=list(operations),
                expires_ns=expires_ns,
            )
        finally:
            with self._lock:
                if self._pending_takeovers.get(key) is approval:
                    self._pending_takeovers.pop(key, None)


