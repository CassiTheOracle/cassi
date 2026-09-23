from __future__ import annotations

"""Read-only CassiCosmos 7599 observations for the field owner.

The mind engine exposes a line-delimited JSON TCP bridge.  This adapter keeps
that transport behind the owner's WorldAdapter boundary and deliberately
allows only scalar read commands; deposits, stepping, clearing, snapshots, and
Qi writes are not part of this observation surface.
"""

import json
import hashlib
from dataclasses import dataclass
import math
import socket
import threading
from pathlib import Path
from typing import Any, Mapping, Sequence

from cassi_field_atlas import FieldIntelligenceError, canonical_json_bytes, sha256_value
from cassi_field_owner import (
    DeterministicWorldAdapter,
    WorldAcknowledgment,
)


_READ_COMMANDS = frozenset(
    {"ping", "state", "project", "qi_state", "qi_project"}
)
_DIRECT_FIELDS = {
    "ping": frozenset({"step", "t"}),
    "state": frozenset(
        {"step", "t", "mean_ey", "mean_ei", "max_eps2"}
    ),
    "qi_state": frozenset(
        {"revision", "state_bytes", "mode_count", "wave_mode_count", "scale_count"}
    ),
}
_PHASE_PROFILE_BIN_COUNT = 16
_PHASE_PROFILE_METRICS = {
    "phase_q": "q_sum",
    "phase_jx": "current_x_sum",
    "phase_abs_jx": "current_x_abs_sum",
}
_PHASE_PROFILE_FIELDS = frozenset(
    f"{prefix}_x{bin_index:02d}"
    for prefix in _PHASE_PROFILE_METRICS
    for bin_index in range(_PHASE_PROFILE_BIN_COUNT)
)
_PHASE_TOPOLOGY_BIN_COUNT = 4
_PHASE_TOPOLOGY_CELL_COUNT = _PHASE_TOPOLOGY_BIN_COUNT**3
_PHASE_TOPOLOGY_METRICS = {
    "phase_topology_q": "q",
    "phase_topology_jx": "jx",
    "phase_topology_jy": "jy",
    "phase_topology_jz": "jz",
}
_PHASE_TOPOLOGY_FIELDS = frozenset(
    f"{prefix}_b{bin_index:02d}"
    for prefix in _PHASE_TOPOLOGY_METRICS
    for bin_index in range(_PHASE_TOPOLOGY_CELL_COUNT)
)
_PHASE_WINDING_GRID_N = 64
_PHASE_WINDING_RADII = (2, 4, 8)
_PHASE_WINDING_PLANES = ("xy", "xz", "yz")
_PHASE_WINDING_METRICS = {
    "phase_winding": "winding_number",
    "phase_winding_circ": "phase_circulation",
    "phase_winding_current": "current_circulation",
    "phase_winding_qmin": "q_min",
}
_PHASE_WINDING_FIELDS = frozenset(
    f"{prefix}_{plane}_r{radius:02d}"
    for prefix in _PHASE_WINDING_METRICS
    for plane in _PHASE_WINDING_PLANES
    for radius in _PHASE_WINDING_RADII
)
_PROJECT_FIELDS = frozenset(
    {
        "top_i",
        "top_gx",
        "top_gy",
        "top_gz",
        "top_x",
        "top_y",
        "top_z",
        "top_ey",
        "top_ei",
        "top_phase_current_x",
        "top_q",
    }
)
_QI_PROJECT_FIELDS = frozenset(
    {"top_mode", "top_p0", "top_p1", "top_q"}
)


class CassiCosmos7599Adapter:
    """Durable, read-only WorldAdapter backed by CassiCosmos port 7599."""

    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 7599,
        timeout: float = 30.0,
        adapter_id: str = "cassi-cosmos-7599",
        max_response_bytes: int = 16 * 1024 * 1024,
    ) -> None:
        if not isinstance(host, str) or not host:
            raise FieldIntelligenceError(
                "ADAPTER_CONFIG",
                "CassiCosmos host must be a non-empty string",
            )
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            raise FieldIntelligenceError(
                "ADAPTER_CONFIG",
                "CassiCosmos port must be in the TCP port range",
            )
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
            raise FieldIntelligenceError(
                "ADAPTER_CONFIG",
                "CassiCosmos timeout must be numeric",
            )
        if not math.isfinite(float(timeout)) or float(timeout) <= 0.0:
            raise FieldIntelligenceError(
                "ADAPTER_CONFIG",
                "CassiCosmos timeout must be finite and positive",
            )
        if (
            isinstance(max_response_bytes, bool)
            or not isinstance(max_response_bytes, int)
            or max_response_bytes < 1024
        ):
            raise FieldIntelligenceError(
                "ADAPTER_CONFIG",
                "CassiCosmos response limit is invalid",
            )
        self.host = host
        self.port = port
        self.timeout = float(timeout)
        self.max_response_bytes = max_response_bytes
        self.adapter_id = adapter_id
        self._lock = threading.RLock()
        self._active_operation_id: str | None = None
        self._journal = DeterministicWorldAdapter(
            self._observe,
            adapter_id=adapter_id,
        )

    @property
    def execute_count(self) -> int:
        return self._journal.execute_count

    def bind_durable_journal(self, path: Path) -> None:
        self._journal.bind_durable_journal(path)

    def resolve(self, operation_id: str) -> WorldAcknowledgment | None:
        return self._journal.resolve(operation_id)

    def execute_once(
        self,
        *,
        operation_id: str,
        action: str,
        target: str,
        payload: Mapping[str, Any],
    ) -> WorldAcknowledgment:
        with self._lock:
            if self._active_operation_id is not None:
                raise FieldIntelligenceError(
                    "ADAPTER_DURABILITY",
                    "CassiCosmos adapter does not support nested observations",
                )
            self._active_operation_id = operation_id
            try:
                return self._journal.execute_once(
                    operation_id=operation_id,
                    action=action,
                    target=target,
                    payload=payload,
                )
            finally:
                self._active_operation_id = None

    def _observe(
        self,
        action: str,
        target: str,
        payload: Mapping[str, Any],
    ) -> WorldAcknowledgment:
        operation_id = self._active_operation_id
        if operation_id is None:
            raise FieldIntelligenceError(
                "ADAPTER_DURABILITY",
                "CassiCosmos observation has no active operation identity",
            )
        request = self._normalize_request(action, payload)
        command = request["cmd"]
        fields = request["fields"]
        try:
            raw, response = self._wire_request(request)
        except (ConnectionError, OSError, TimeoutError, ValueError) as exc:
            raw = canonical_json_bytes(
                {
                    "adapter": self.adapter_id,
                    "command": command,
                    "error": str(exc),
                    "status": "transport-unknown",
                }
            )
            return self._acknowledgment(
                operation_id=operation_id,
                target=target,
                status="unknown",
                observed_values={},
                source_content=raw,
                context={
                    "adapter": self.adapter_id,
                    "channel_id": target,
                    "command": command,
                    "fields": fields,
                    "transport_status": "unknown",
                    "error": str(exc),
                },
            )

        if response.get("ok") is not True:
            return self._acknowledgment(
                operation_id=operation_id,
                target=target,
                status="failed",
                observed_values={},
                source_content=raw,
                context={
                    "adapter": self.adapter_id,
                    "channel_id": target,
                    "command": command,
                    "fields": fields,
                    "engine_error": str(response.get("error", "unknown")),
                },
            )
        if response.get("cmd") != command:
            return self._acknowledgment(
                operation_id=operation_id,
                target=target,
                status="failed",
                observed_values={},
                source_content=raw,
                context={
                    "adapter": self.adapter_id,
                    "channel_id": target,
                    "command": command,
                    "response_command": response.get("cmd"),
                    "error": "response command differs from request",
                },
            )
        try:
            values = self._extract_values(command, fields, response)
        except (KeyError, TypeError, ValueError) as exc:
            return self._acknowledgment(
                operation_id=operation_id,
                target=target,
                status="failed",
                observed_values={},
                source_content=raw,
                context={
                    "adapter": self.adapter_id,
                    "channel_id": target,
                    "command": command,
                    "fields": fields,
                    "error": str(exc),
                },
            )
        return self._acknowledgment(
            operation_id=operation_id,
            target=target,
            status="succeeded",
            observed_values=values,
            source_content=raw,
            context={
                "adapter": self.adapter_id,
                "channel_id": target,
                "command": command,
                "fields": fields,
                "step": response.get("step"),
                "t": response.get("t"),
            },
        )

    def _normalize_request(
        self,
        action: str,
        payload: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        if action != "observe":
            raise FieldIntelligenceError(
                "READ_ONLY_ADAPTER",
                "CassiCosmos adapter accepts only observe actions",
            )
        request = payload.get("request")
        if not isinstance(request, Mapping):
            raise FieldIntelligenceError(
                "INVALID_REQUEST",
                "CassiCosmos observation request must be an object",
            )
        command = request.get("cmd")
        if not isinstance(command, str) or command not in _READ_COMMANDS:
            raise FieldIntelligenceError(
                "READ_ONLY_ADAPTER",
                "CassiCosmos command is not read-only",
                details={"command": command},
            )
        allowed = {"cmd", "fields"}
        if command in {"project", "qi_project"}:
            allowed.add("k")
        if command == "project":
            for optional in ("phase_bins", "topology_bins", "winding_probe"):
                if optional in request:
                    allowed.add(optional)
        if set(request) != allowed:
            raise FieldIntelligenceError(
                "INVALID_REQUEST",
                "CassiCosmos observation request shape is invalid",
            )
        fields = request.get("fields")
        if (
            not isinstance(fields, Sequence)
            or isinstance(fields, (str, bytes))
            or not fields
            or any(not isinstance(field, str) or not field for field in fields)
            or len(set(fields)) != len(fields)
        ):
            raise FieldIntelligenceError(
                "INVALID_REQUEST",
                "CassiCosmos observation fields are invalid",
            )
        if command in _DIRECT_FIELDS:
            allowed_fields = _DIRECT_FIELDS[command]
        elif command == "project":
            allowed_fields = (
                _PROJECT_FIELDS
                | _PHASE_PROFILE_FIELDS
                | _PHASE_TOPOLOGY_FIELDS
                | _PHASE_WINDING_FIELDS
            )
        else:
            allowed_fields = _QI_PROJECT_FIELDS
        if any(field not in allowed_fields for field in fields):
            raise FieldIntelligenceError(
                "INVALID_REQUEST",
                "CassiCosmos observation field is unavailable for command",
                details={"command": command, "fields": list(fields)},
            )
        normalized: dict[str, Any] = {
            "cmd": command,
            "fields": list(fields),
        }
        if command in {"project", "qi_project"}:
            k = request.get("k")
            if isinstance(k, bool) or not isinstance(k, int) or not 1 <= k <= 64:
                raise FieldIntelligenceError(
                    "INVALID_REQUEST",
                    "CassiCosmos projection k must be an integer from 1 to 64",
                )
            normalized["k"] = k
            if command == "project":
                profile_requested = any(
                    field in _PHASE_PROFILE_FIELDS for field in fields
                )
                phase_bins = request.get("phase_bins")
                if profile_requested:
                    if phase_bins != _PHASE_PROFILE_BIN_COUNT:
                        raise FieldIntelligenceError(
                            "INVALID_REQUEST",
                            "distributed phase fields require the fixed 16-bin profile",
                        )
                    normalized["phase_bins"] = _PHASE_PROFILE_BIN_COUNT
                elif phase_bins is not None:
                    raise FieldIntelligenceError(
                        "INVALID_REQUEST",
                        "phase_bins is valid only with distributed phase fields",
                    )
                topology_requested = any(
                    field in _PHASE_TOPOLOGY_FIELDS for field in fields
                )
                topology_bins = request.get("topology_bins")
                if topology_requested:
                    if topology_bins != _PHASE_TOPOLOGY_BIN_COUNT:
                        raise FieldIntelligenceError(
                            "INVALID_REQUEST",
                            "phase topology fields require the fixed 4x4x4 lattice",
                        )
                    normalized["topology_bins"] = _PHASE_TOPOLOGY_BIN_COUNT
                elif topology_bins is not None:
                    raise FieldIntelligenceError(
                        "INVALID_REQUEST",
                        "topology_bins is valid only with phase topology fields",
                    )
                winding_requested = any(
                    field in _PHASE_WINDING_FIELDS for field in fields
                )
                winding_probe = request.get("winding_probe")
                if winding_requested:
                    if winding_probe != 1:
                        raise FieldIntelligenceError(
                            "INVALID_REQUEST",
                            "native phase winding fields require winding_probe=1",
                        )
                    normalized["winding_probe"] = 1
                elif winding_probe is not None:
                    raise FieldIntelligenceError(
                        "INVALID_REQUEST",
                        "winding_probe is valid only with native phase winding fields",
                    )
        return json.loads(canonical_json_bytes(normalized))

    def _wire_request(
        self,
        request: Mapping[str, Any],
    ) -> tuple[bytes, Mapping[str, Any]]:
        wire = canonical_json_bytes(request) + b"\n"
        with socket.create_connection(
            (self.host, self.port),
            timeout=self.timeout,
        ) as sock:
            sock.settimeout(self.timeout)
            sock.sendall(wire)
            with sock.makefile("rb") as response_file:
                raw = response_file.readline(self.max_response_bytes + 1)
        if not raw:
            raise ConnectionError("CassiCosmos bridge returned no response")
        if len(raw) > self.max_response_bytes:
            raise ValueError("CassiCosmos bridge response exceeds byte limit")
        raw = raw.rstrip(b"\r\n")
        try:
            response = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("CassiCosmos bridge response is not JSON") from exc
        if not isinstance(response, Mapping):
            raise ValueError("CassiCosmos bridge response is not an object")
        return raw, response

    @staticmethod
    def _extract_values(
        command: str,
        fields: Sequence[str],
        response: Mapping[str, Any],
    ) -> Mapping[str, float]:
        if command in _DIRECT_FIELDS:
            values = {
                field: CassiCosmos7599Adapter._finite_number(response[field])
                for field in fields
            }
            return values
        if command == "project":
            cells = response["cells"]
            if (
                not isinstance(cells, Sequence)
                or isinstance(cells, (str, bytes))
                or not cells
            ):
                raise ValueError("CassiCosmos projection has no top cell")
            top = cells[0]
            if not isinstance(top, Mapping):
                raise TypeError("CassiCosmos projection top cell is not an object")
            top_names = {
                "top_i": "i",
                "top_gx": "gx",
                "top_gy": "gy",
                "top_gz": "gz",
                "top_x": "x",
                "top_y": "y",
                "top_z": "z",
                "top_ey": "ey",
                "top_ei": "ei",
                "top_phase_current_x": "phase_current_x",
                "top_q": "q",
            }
            profile_fields = [
                field for field in fields if field in _PHASE_PROFILE_FIELDS
            ]
            profile_bins: Sequence[Any] = ()
            if profile_fields:
                profile = response["phase_profile"]
                if (
                    not isinstance(profile, Mapping)
                    or profile.get("axis") != "x"
                    or profile.get("bin_count") != _PHASE_PROFILE_BIN_COUNT
                ):
                    raise ValueError("CassiCosmos phase profile shape is invalid")
                raw_bins = profile.get("bins")
                if (
                    not isinstance(raw_bins, Sequence)
                    or isinstance(raw_bins, (str, bytes))
                    or len(raw_bins) != _PHASE_PROFILE_BIN_COUNT
                ):
                    raise ValueError("CassiCosmos phase profile bins are invalid")
                profile_bins = raw_bins
            topology_fields = [
                field for field in fields if field in _PHASE_TOPOLOGY_FIELDS
            ]
            topology_bins: Sequence[Any] = ()
            if topology_fields:
                raw_topology = response["phase_topology"]
                if (
                    response.get("phase_topology_bins")
                    != _PHASE_TOPOLOGY_BIN_COUNT
                    or not isinstance(raw_topology, Sequence)
                    or isinstance(raw_topology, (str, bytes))
                    or len(raw_topology) != _PHASE_TOPOLOGY_CELL_COUNT
                ):
                    raise ValueError(
                        "CassiCosmos phase topology shape is invalid"
                    )
                topology_bins = raw_topology
            winding_fields = [
                field for field in fields if field in _PHASE_WINDING_FIELDS
            ]
            winding_rows: dict[tuple[str, int], Mapping[str, Any]] = {}
            if winding_fields:
                winding = response["phase_winding"]
                if (
                    not isinstance(winding, Mapping)
                    or winding.get("schema") != "cassi.phase-winding-native.v1"
                    or winding.get("grid_n") != _PHASE_WINDING_GRID_N
                    or winding.get("center")
                    != {
                        "gx": _PHASE_WINDING_GRID_N // 2,
                        "gy": _PHASE_WINDING_GRID_N // 2,
                        "gz": _PHASE_WINDING_GRID_N // 2,
                    }
                    or winding.get("radii_cells") != list(_PHASE_WINDING_RADII)
                    or winding.get("planes") != list(_PHASE_WINDING_PLANES)
                ):
                    raise ValueError("CassiCosmos native phase winding shape is invalid")
                raw_rows = winding.get("rows")
                if (
                    not isinstance(raw_rows, Sequence)
                    or isinstance(raw_rows, (str, bytes))
                    or len(raw_rows) != len(_PHASE_WINDING_PLANES)
                    * len(_PHASE_WINDING_RADII)
                ):
                    raise ValueError("CassiCosmos native phase winding rows are invalid")
                for row in raw_rows:
                    if not isinstance(row, Mapping):
                        raise TypeError(
                            "CassiCosmos native phase winding row is not an object"
                        )
                    plane = row.get("plane")
                    radius = row.get("radius_cells")
                    if (
                        not isinstance(plane, str)
                        or isinstance(radius, bool)
                        or not isinstance(radius, int)
                    ):
                        raise ValueError(
                            "CassiCosmos native phase winding row identity is invalid"
                        )
                    key = (plane, radius)
                    if (
                        key in winding_rows
                        or plane not in _PHASE_WINDING_PLANES
                        or radius not in _PHASE_WINDING_RADII
                    ):
                        raise ValueError(
                            "CassiCosmos native phase winding row identity is invalid"
                        )
                    winding_rows[key] = row
                expected_keys = {
                    (plane, radius)
                    for plane in _PHASE_WINDING_PLANES
                    for radius in _PHASE_WINDING_RADII
                }
                if set(winding_rows) != expected_keys:
                    raise ValueError(
                        "CassiCosmos native phase winding rows are incomplete"
                    )
            values: dict[str, float] = {}
            for field in fields:
                if field in top_names:
                    values[field] = CassiCosmos7599Adapter._finite_number(
                        top[top_names[field]]
                    )
                    continue
                if field in _PHASE_TOPOLOGY_FIELDS:
                    prefix, raw_index = field.rsplit("_b", 1)
                    bin_index = int(raw_index)
                    row = topology_bins[bin_index]
                    if (
                        not isinstance(row, Mapping)
                        or row.get("bin") != bin_index
                    ):
                        raise ValueError(
                            "CassiCosmos phase topology bin identity is invalid"
                        )
                    values[field] = CassiCosmos7599Adapter._finite_number(
                        row[_PHASE_TOPOLOGY_METRICS[prefix]]
                    )
                    continue
                if field in _PHASE_WINDING_FIELDS:
                    prefix, plane, raw_radius = field.rsplit("_", 2)
                    radius = int(raw_radius[1:])
                    row = winding_rows[(plane, radius)]
                    values[field] = CassiCosmos7599Adapter._finite_number(
                        row[_PHASE_WINDING_METRICS[prefix]]
                    )
                    continue
                prefix, raw_index = field.rsplit("_x", 1)
                bin_index = int(raw_index)
                row = profile_bins[bin_index]
                if (
                    not isinstance(row, Mapping)
                    or row.get("bin") != bin_index
                ):
                    raise ValueError(
                        "CassiCosmos phase profile bin identity is invalid"
                    )
                values[field] = CassiCosmos7599Adapter._finite_number(
                    row[_PHASE_PROFILE_METRICS[prefix]]
                )
            return values
        else:
            modes = response["modes"]
            if not isinstance(modes, Sequence) or isinstance(modes, (str, bytes)) or not modes:
                raise ValueError("CassiCosmos Qi projection has no top mode")
            top = modes[0]
            if not isinstance(top, Mapping):
                raise TypeError("CassiCosmos Qi projection top mode is not an object")
            names = {
                "top_mode": "mode",
                "top_p0": "p0",
                "top_p1": "p1",
                "top_q": "q",
            }
        return {
            field: CassiCosmos7599Adapter._finite_number(top[names[field]])
            for field in fields
        }

    @staticmethod
    def _finite_number(value: Any) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("CassiCosmos observation value is not numeric")
        value = float(value)
        if not math.isfinite(value):
            raise ValueError("CassiCosmos observation value is non-finite")
        return value

    def _acknowledgment(
        self,
        *,
        operation_id: str,
        target: str,
        status: str,
        observed_values: Mapping[str, float],
        source_content: bytes,
        context: Mapping[str, Any],
    ) -> WorldAcknowledgment:
        acknowledgment_id = (
            "ack:cosmos-7599:"
            + sha256_value(
                {
                    "operation_id": operation_id,
                    "target": target,
                    "source_sha256": hashlib.sha256(source_content).hexdigest(),
                    "status": status,
                }
            )
        )
        return WorldAcknowledgment(
            acknowledgment_id=acknowledgment_id,
            operation_id=operation_id,
            status=status,
            observed_values=observed_values,
            context=dict(context),
            source_content=source_content,
        )


@dataclass(frozen=True, slots=True)
class CassiCosmosSeedAuthorization:
    """Explicit capability required by the separate mutation path."""

    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise FieldIntelligenceError(
                "SEED_AUTHORIZATION",
                "CassiCosmos seed authorization requires a reason",
            )
        if len(self.reason) > 256:
            raise FieldIntelligenceError(
                "SEED_AUTHORIZATION",
                "CassiCosmos seed authorization reason is too long",
            )


def authorize_cassicosmos_seed(reason: str) -> CassiCosmosSeedAuthorization:
    """Create the explicit capability for one owner-authorized seed path."""

    return CassiCosmosSeedAuthorization(reason=reason)


class CassiCosmosSeedController:
    """Durable mutation controller kept separate from read-only observation."""

    def __init__(
        self,
        *,
        authorization: CassiCosmosSeedAuthorization,
        host: str = "127.0.0.1",
        port: int = 7599,
        timeout: float = 30.0,
        max_response_bytes: int = 16 * 1024 * 1024,
    ) -> None:
        if not isinstance(authorization, CassiCosmosSeedAuthorization):
            raise FieldIntelligenceError(
                "SEED_AUTHORIZATION",
                "CassiCosmos seed controller requires explicit authorization",
            )
        if not isinstance(host, str) or not host:
            raise FieldIntelligenceError(
                "SEED_CONFIG",
                "CassiCosmos seed host must be a non-empty string",
            )
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            raise FieldIntelligenceError(
                "SEED_CONFIG",
                "CassiCosmos seed port must be in the TCP port range",
            )
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
            raise FieldIntelligenceError(
                "SEED_CONFIG",
                "CassiCosmos seed timeout must be numeric",
            )
        if not math.isfinite(float(timeout)) or float(timeout) <= 0.0:
            raise FieldIntelligenceError(
                "SEED_CONFIG",
                "CassiCosmos seed timeout must be finite and positive",
            )
        if (
            isinstance(max_response_bytes, bool)
            or not isinstance(max_response_bytes, int)
            or max_response_bytes < 1024
        ):
            raise FieldIntelligenceError(
                "SEED_CONFIG",
                "CassiCosmos seed response limit is invalid",
            )
        self.authorization = authorization
        self.host = host
        self.port = port
        self.timeout = float(timeout)
        self.max_response_bytes = max_response_bytes
        self._lock = threading.RLock()
        self._active_operation_id: str | None = None
        self._journal = DeterministicWorldAdapter(
            self._transition,
            adapter_id="cassi-cosmos-seed-7599",
        )

    @property
    def execute_count(self) -> int:
        return self._journal.execute_count

    def bind_durable_journal(self, path: Path) -> None:
        self._journal.bind_durable_journal(path)

    def resolve(self, operation_id: str) -> WorldAcknowledgment | None:
        return self._journal.resolve(operation_id)

    def seed_and_advance(
        self,
        *,
        operation_id: str,
        deposits: Sequence[Mapping[str, Any]],
        steps: int,
    ) -> WorldAcknowledgment:
        payload = self._normalize_seed(deposits, steps)
        with self._lock:
            if self._active_operation_id is not None:
                raise FieldIntelligenceError(
                    "SEED_AUTHORIZATION",
                    "CassiCosmos seed controller does not support nested runs",
                )
            self._active_operation_id = operation_id
            try:
                return self._journal.execute_once(
                    operation_id=operation_id,
                    action="seed-and-advance",
                    target="cassi-cosmos:7599",
                    payload=payload,
                )
            finally:
                self._active_operation_id = None

    @staticmethod
    def _normalize_seed(
        deposits: Sequence[Mapping[str, Any]],
        steps: int,
    ) -> Mapping[str, Any]:
        if (
            not isinstance(deposits, Sequence)
            or isinstance(deposits, (str, bytes))
            or not deposits
            or len(deposits) > 64
        ):
            raise FieldIntelligenceError(
                "SEED_REQUEST",
                "CassiCosmos seed requires one to 64 deposits",
            )
        if isinstance(steps, bool) or not isinstance(steps, int) or not 1 <= steps <= 100000:
            raise FieldIntelligenceError(
                "SEED_REQUEST",
                "CassiCosmos seed steps must be from 1 to 100000",
            )
        normalized_deposits: list[dict[str, float]] = []
        required = {"x", "y", "z", "cy", "ci", "sigma"}
        for deposit in deposits:
            if not isinstance(deposit, Mapping) or set(deposit) != required:
                raise FieldIntelligenceError(
                    "SEED_REQUEST",
                    "CassiCosmos seed deposit shape is invalid",
                )
            normalized: dict[str, float] = {}
            for name in sorted(required):
                value = deposit[name]
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise FieldIntelligenceError(
                        "SEED_REQUEST",
                        "CassiCosmos seed values must be numeric",
                        details={"field": name},
                    )
                numeric = float(value)
                if not math.isfinite(numeric):
                    raise FieldIntelligenceError(
                        "SEED_REQUEST",
                        "CassiCosmos seed values must be finite",
                        details={"field": name},
                    )
                normalized[name] = numeric
            if normalized["sigma"] <= 0.0:
                raise FieldIntelligenceError(
                    "SEED_REQUEST",
                    "CassiCosmos seed sigma must be positive",
                )
            normalized_deposits.append(normalized)
        return {"deposits": normalized_deposits, "steps": steps}

    def _transition(
        self,
        action: str,
        target: str,
        payload: Mapping[str, Any],
    ) -> WorldAcknowledgment:
        operation_id = self._active_operation_id
        if operation_id is None:
            raise FieldIntelligenceError(
                "SEED_AUTHORIZATION",
                "CassiCosmos seed has no active operation identity",
            )
        if action != "seed-and-advance" or target != "cassi-cosmos:7599":
            raise FieldIntelligenceError(
                "SEED_AUTHORIZATION",
                "CassiCosmos seed controller received an invalid mutation",
            )
        try:
            deposits = payload["deposits"]
            steps = payload["steps"]
            commands = [
                {"cmd": "deposit", **deposit} for deposit in deposits
            ]
            commands.append({"cmd": "step", "n": steps})
            raw_lines: list[bytes] = []
            last_response: Mapping[str, Any] | None = None
            for command in commands:
                raw, response = self._wire_command(command)
                raw_lines.append(raw)
                last_response = response
                if response.get("ok") is not True:
                    return self._mutation_ack(
                        operation_id=operation_id,
                        status="unknown",
                        source_content=b"\n".join(raw_lines),
                        context={
                            "authorization_reason": self.authorization.reason,
                            "command": command["cmd"],
                            "engine_error": str(response.get("error", "unknown")),
                            "phase": "partial-or-rejected-mutation",
                        },
                    )
                if response.get("cmd") != command["cmd"]:
                    return self._mutation_ack(
                        operation_id=operation_id,
                        status="unknown",
                        source_content=b"\n".join(raw_lines),
                        context={
                            "authorization_reason": self.authorization.reason,
                            "command": command["cmd"],
                            "response_command": response.get("cmd"),
                            "phase": "ambiguous-mutation",
                        },
                    )
            assert last_response is not None
            step = CassiCosmos7599Adapter._finite_number(
                last_response["step"]
            )
            timestamp = CassiCosmos7599Adapter._finite_number(
                last_response["t"]
            )
            return self._mutation_ack(
                operation_id=operation_id,
                status="succeeded",
                observed_values={
                    "step": step,
                    "t": timestamp,
                    "deposit_count": float(len(deposits)),
                    "advanced_steps": float(steps),
                },
                source_content=b"\n".join(raw_lines),
                context={
                    "authorization_reason": self.authorization.reason,
                    "deposit_count": len(deposits),
                    "steps": steps,
                    "phase": "seeded-and-advanced",
                },
            )
        except (
            ConnectionError,
            OSError,
            TimeoutError,
            TypeError,
            ValueError,
            KeyError,
        ) as exc:
            return self._mutation_ack(
                operation_id=operation_id,
                status="unknown",
                source_content=canonical_json_bytes(
                    {
                        "adapter": "cassi-cosmos-seed-7599",
                        "error": str(exc),
                        "phase": "transport-unknown",
                    }
                ),
                context={
                    "authorization_reason": self.authorization.reason,
                    "error": str(exc),
                    "phase": "transport-unknown",
                },
            )

    def _wire_command(
        self,
        command: Mapping[str, Any],
    ) -> tuple[bytes, Mapping[str, Any]]:
        wire = canonical_json_bytes(dict(command)) + b"\n"
        with socket.create_connection(
            (self.host, self.port),
            timeout=self.timeout,
        ) as sock:
            sock.settimeout(self.timeout)
            sock.sendall(wire)
            with sock.makefile("rb") as response_file:
                raw = response_file.readline(self.max_response_bytes + 1)
        if not raw:
            raise ConnectionError("CassiCosmos bridge returned no mutation response")
        if len(raw) > self.max_response_bytes:
            raise ValueError("CassiCosmos mutation response exceeds byte limit")
        raw = raw.rstrip(b"\r\n")
        try:
            response = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("CassiCosmos mutation response is not JSON") from exc
        if not isinstance(response, Mapping):
            raise ValueError("CassiCosmos mutation response is not an object")
        return raw, response

    def _mutation_ack(
        self,
        *,
        operation_id: str,
        status: str,
        source_content: bytes,
        context: Mapping[str, Any],
        observed_values: Mapping[str, float] | None = None,
    ) -> WorldAcknowledgment:
        acknowledgment_id = (
            "ack:cosmos-seed:"
            + sha256_value(
                {
                    "operation_id": operation_id,
                    "source_sha256": hashlib.sha256(source_content).hexdigest(),
                    "status": status,
                }
            )
        )
        return WorldAcknowledgment(
            acknowledgment_id=acknowledgment_id,
            operation_id=operation_id,
            status=status,
            observed_values=dict(observed_values or {}),
            context=dict(context),
            source_content=source_content,
        )


class CassiCosmosWorldFactoryController(CassiCosmosSeedController):
    """Authorized fresh-world episodes with exact stepped observations.

    This controller is intentionally separate from both the read-only adapter
    and the additive seed controller.  Every episode clears the canonical
    field, applies bounded initial or time-dependent deposits, advances only
    through explicit step commands, and journals the complete mutation and
    observation transcript.
    """

    def __init__(
        self,
        *,
        authorization: CassiCosmosSeedAuthorization,
        host: str = "127.0.0.1",
        port: int = 7599,
        timeout: float = 30.0,
        max_response_bytes: int = 16 * 1024 * 1024,
    ) -> None:
        super().__init__(
            authorization=authorization,
            host=host,
            port=port,
            timeout=timeout,
            max_response_bytes=max_response_bytes,
        )
        self._journal = DeterministicWorldAdapter(
            self._transition,
            adapter_id="cassi-cosmos-world-factory-7599",
        )

    def execute_world(
        self,
        *,
        operation_id: str,
        deposits: Sequence[Mapping[str, Any]],
        horizons: Sequence[int],
        projection_k: int = 8,
        phase_profile_bins: int = 0,
        phase_topology_bins: int = 0,
        phase_winding_probe: int = 0,
    ) -> WorldAcknowledgment:
        payload = self._normalize_world(
            deposits,
            horizons,
            projection_k,
            phase_profile_bins,
            phase_topology_bins,
            phase_winding_probe,
        )
        return self._execute_world_plan(
            operation_id=operation_id,
            action="reset-seed-observe",
            payload=payload,
        )
    def execute_scheduled_world(
        self,
        *,
        operation_id: str,
        segments: Sequence[Mapping[str, Any]],
        projection_k: int = 8,
        phase_profile_bins: int = 0,
        phase_topology_bins: int = 0,
        phase_winding_probe: int = 0,
    ) -> WorldAcknowledgment:
        """Run deposits at segment boundaries and observe after each advance."""

        payload = self._normalize_schedule(
            segments,
            projection_k,
            phase_profile_bins,
            phase_topology_bins,
            phase_winding_probe,
        )
        return self._execute_world_plan(
            operation_id=operation_id,
            action="reset-schedule-observe",
            payload=payload,
        )

    def _execute_world_plan(
        self,
        *,
        operation_id: str,
        action: str,
        payload: Mapping[str, Any],
    ) -> WorldAcknowledgment:
        with self._lock:
            if self._active_operation_id is not None:
                raise FieldIntelligenceError(
                    "SEED_AUTHORIZATION",
                    "CassiCosmos world factory does not support nested runs",
                )
            self._active_operation_id = operation_id
            try:
                return self._journal.execute_once(
                    operation_id=operation_id,
                    action=action,
                    target="cassi-cosmos:7599",
                    payload=payload,
                )
            finally:
                self._active_operation_id = None

    @staticmethod
    def _normalize_deposits(
        deposits: Sequence[Mapping[str, Any]],
        *,
        limit: int,
    ) -> list[dict[str, float]]:
        if (
            not isinstance(deposits, Sequence)
            or isinstance(deposits, (str, bytes))
            or len(deposits) > limit
        ):
            raise FieldIntelligenceError(
                "SEED_REQUEST",
                f"CassiCosmos world requires zero to {limit} deposits",
            )
        normalized_deposits: list[dict[str, float]] = []
        required = {"x", "y", "z", "cy", "ci", "sigma"}
        for deposit in deposits:
            if not isinstance(deposit, Mapping) or set(deposit) != required:
                raise FieldIntelligenceError(
                    "SEED_REQUEST",
                    "CassiCosmos world deposit shape is invalid",
                )
            normalized: dict[str, float] = {}
            for name in sorted(required):
                value = deposit[name]
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise FieldIntelligenceError(
                        "SEED_REQUEST",
                        "CassiCosmos world values must be numeric",
                        details={"field": name},
                    )
                numeric = float(value)
                if not math.isfinite(numeric):
                    raise FieldIntelligenceError(
                        "SEED_REQUEST",
                        "CassiCosmos world values must be finite",
                        details={"field": name},
                    )
                normalized[name] = numeric
            if normalized["sigma"] <= 0.0:
                raise FieldIntelligenceError(
                    "SEED_REQUEST",
                    "CassiCosmos world sigma must be positive",
                )
            normalized_deposits.append(normalized)
        return normalized_deposits

    @staticmethod
    def _normalize_phase_profile_bins(phase_profile_bins: int) -> int:
        if (
            isinstance(phase_profile_bins, bool)
            or not isinstance(phase_profile_bins, int)
            or phase_profile_bins not in {0, _PHASE_PROFILE_BIN_COUNT}
        ):
            raise FieldIntelligenceError(
                "SEED_REQUEST",
                "CassiCosmos phase profile must be disabled or use 16 bins",
            )
        return phase_profile_bins

    @staticmethod
    def _normalize_phase_topology_bins(phase_topology_bins: int) -> int:
        if (
            isinstance(phase_topology_bins, bool)
            or not isinstance(phase_topology_bins, int)
            or phase_topology_bins not in {0, _PHASE_TOPOLOGY_BIN_COUNT}
        ):
            raise FieldIntelligenceError(
                "SEED_REQUEST",
                "CassiCosmos phase topology must be disabled or use 4x4x4 bins",
            )
        return phase_topology_bins
    @staticmethod
    def _normalize_phase_winding_probe(phase_winding_probe: int) -> int:
        if (
            isinstance(phase_winding_probe, bool)
            or not isinstance(phase_winding_probe, int)
            or phase_winding_probe not in {0, 1}
        ):
            raise FieldIntelligenceError(
                "SEED_REQUEST",
                "CassiCosmos native phase winding must be disabled or enabled with 1",
            )
        return phase_winding_probe


    @classmethod
    def _normalize_schedule(
        cls,
        segments: Sequence[Mapping[str, Any]],
        projection_k: int,
        phase_profile_bins: int,
        phase_topology_bins: int,
        phase_winding_probe: int,
    ) -> Mapping[str, Any]:
        if (
            not isinstance(segments, Sequence)
            or isinstance(segments, (str, bytes))
            or not segments
            or len(segments) > 16
        ):
            raise FieldIntelligenceError(
                "SEED_REQUEST",
                "CassiCosmos schedule requires one to 16 segments",
            )
        normalized_segments: list[dict[str, Any]] = []
        horizons: list[int] = []
        total_steps = 0
        total_deposits = 0
        for index, segment in enumerate(segments):
            if not isinstance(segment, Mapping) or set(segment) != {
                "deposits",
                "steps",
            }:
                raise FieldIntelligenceError(
                    "SEED_REQUEST",
                    "CassiCosmos schedule segment shape is invalid",
                    details={"segment": index},
                )
            steps = segment["steps"]
            if (
                isinstance(steps, bool)
                or not isinstance(steps, int)
                or not 1 <= steps <= 100_000
            ):
                raise FieldIntelligenceError(
                    "SEED_REQUEST",
                    "CassiCosmos schedule segment steps are outside their bound",
                    details={"segment": index},
                )
            deposits = cls._normalize_deposits(segment["deposits"], limit=64)
            total_steps += steps
            total_deposits += len(deposits)
            if total_steps > 100_000 or total_deposits > 128:
                raise FieldIntelligenceError(
                    "SEED_REQUEST",
                    "CassiCosmos schedule exceeds its episode bounds",
                )
            horizons.append(total_steps)
            normalized_segments.append({"deposits": deposits, "steps": steps})
        if (
            isinstance(projection_k, bool)
            or not isinstance(projection_k, int)
            or not 1 <= projection_k <= 4096
        ):
            raise FieldIntelligenceError(
                "SEED_REQUEST",
                "CassiCosmos world projection size is outside its bound",
            )
        return {
            "horizons": horizons,
            "phase_profile_bins": cls._normalize_phase_profile_bins(
                phase_profile_bins
            ),
            "phase_topology_bins": cls._normalize_phase_topology_bins(
                phase_topology_bins
            ),
            "projection_k": projection_k,
            "segments": normalized_segments,
            "phase_winding_probe": cls._normalize_phase_winding_probe(
                phase_winding_probe
            ),
        }

    @staticmethod
    def _normalize_world(
        deposits: Sequence[Mapping[str, Any]],
        horizons: Sequence[int],
        projection_k: int,
        phase_profile_bins: int,
        phase_topology_bins: int,
        phase_winding_probe: int,
    ) -> Mapping[str, Any]:
        normalized_deposits = CassiCosmosWorldFactoryController._normalize_deposits(
            deposits,
            limit=64,
        )
        if (
            not isinstance(horizons, Sequence)
            or isinstance(horizons, (str, bytes))
            or not horizons
            or len(horizons) > 16
            or any(
                isinstance(item, bool)
                or not isinstance(item, int)
                or not 1 <= item <= 100_000
                for item in horizons
            )
        ):
            raise FieldIntelligenceError(
                "SEED_REQUEST",
                "CassiCosmos world horizons must contain one to 16 bounded steps",
            )
        normalized_horizons = list(horizons)
        if normalized_horizons != sorted(set(normalized_horizons)):
            raise FieldIntelligenceError(
                "SEED_REQUEST",
                "CassiCosmos world horizons must be strictly increasing",
            )
        if (
            isinstance(projection_k, bool)
            or not isinstance(projection_k, int)
            or not 1 <= projection_k <= 4096
        ):
            raise FieldIntelligenceError(
                "SEED_REQUEST",
                "CassiCosmos world projection size is outside its bound",
            )
        return {
            "deposits": normalized_deposits,
            "horizons": normalized_horizons,
            "phase_profile_bins": (
                CassiCosmosWorldFactoryController._normalize_phase_profile_bins(
                    phase_profile_bins
                )
            ),
            "phase_topology_bins": (
                CassiCosmosWorldFactoryController._normalize_phase_topology_bins(
                    phase_topology_bins
                )
            ),
            "phase_winding_probe": (
                CassiCosmosWorldFactoryController._normalize_phase_winding_probe(
                    phase_winding_probe
                )
            ),
            "projection_k": projection_k,
        }

    def _transition(
        self,
        action: str,
        target: str,
        payload: Mapping[str, Any],
    ) -> WorldAcknowledgment:
        operation_id = self._active_operation_id
        if operation_id is None:
            raise FieldIntelligenceError(
                "SEED_AUTHORIZATION",
                "CassiCosmos world factory has no active operation identity",
            )
        if (
            action not in {"reset-seed-observe", "reset-schedule-observe"}
            or target != "cassi-cosmos:7599"
        ):
            raise FieldIntelligenceError(
                "SEED_AUTHORIZATION",
                "CassiCosmos world factory received an invalid mutation request",
            )
        horizons = payload["horizons"]
        projection_k = int(payload["projection_k"])
        phase_profile_bins = int(payload["phase_profile_bins"])
        phase_topology_bins = int(payload["phase_topology_bins"])
        phase_winding_probe = int(payload["phase_winding_probe"])
        commands: list[tuple[dict[str, Any], int | None]] = [
            ({"cmd": "clear"}, None)
        ]
        if action == "reset-seed-observe":
            deposits = payload["deposits"]
            commands.extend(
                ({"cmd": "deposit", **deposit}, None) for deposit in deposits
            )
            previous = 0
            for horizon in horizons:
                commands.extend(
                    (
                        ({"cmd": "step", "n": int(horizon) - previous}, int(horizon)),
                        ({"cmd": "state"}, int(horizon)),
                        (
                            {
                                "cmd": "project",
                                "k": projection_k,
                                "phase_bins": phase_profile_bins,
                                "topology_bins": phase_topology_bins,
                                "winding_probe": phase_winding_probe,
                            },
                            int(horizon),
                        ),
                    )
                )
                previous = int(horizon)
            deposit_count = len(deposits)
            phase = "fresh-world-observed"
        else:
            segments = payload["segments"]
            deposit_count = sum(len(segment["deposits"]) for segment in segments)
            current = 0
            for segment in segments:
                commands.extend(
                    ({"cmd": "deposit", **deposit}, None)
                    for deposit in segment["deposits"]
                )
                current += int(segment["steps"])
                commands.extend(
                    (
                        ({"cmd": "step", "n": int(segment["steps"])}, current),
                        ({"cmd": "state"}, current),
                        (
                            {
                                "cmd": "project",
                                "k": projection_k,
                                "phase_bins": phase_profile_bins,
                                "topology_bins": phase_topology_bins,
                                "winding_probe": phase_winding_probe,
                            },
                            current,
                        ),
                    )
                )
            phase = "scheduled-world-observed"
        raw_lines: list[bytes] = []
        observed: dict[str, float] = {}
        current_horizon: int | None = None
        try:
            for command, expected_horizon in commands:
                raw, response = self._wire_command(command)
                raw_lines.append(raw)
                response_command = response.get("cmd")
                if (
                    response.get("ok") is not True
                    or response_command != command["cmd"]
                ):
                    return self._world_ack(
                        operation_id=operation_id,
                        status="unknown",
                        source_content=b"\n".join(raw_lines),
                        context={
                            "authorization_reason": self.authorization.reason,
                            "command": command["cmd"],
                            "engine_error": str(
                                response.get("error", "partition-or-rejected-mutation")
                            ),
                            "phase": "ambiguous-world-mutation",
                        },
                    )
                if command["cmd"] == "step":
                    current_horizon = int(
                        CassiCosmos7599Adapter._finite_number(response["step"])
                    )
                    if expected_horizon is None:
                        raise RuntimeError("stepped command lacks an expected horizon")
                    if current_horizon != expected_horizon:
                        return self._world_ack(
                            operation_id=operation_id,
                            status="unknown",
                            source_content=b"\n".join(raw_lines),
                            context={
                                "authorization_reason": self.authorization.reason,
                                "expected_step": expected_horizon,
                                "observed_step": current_horizon,
                                "phase": "non-deterministic-world-clock",
                            },
                        )
                elif command["cmd"] == "state":
                    if current_horizon is None or current_horizon != expected_horizon:
                        raise RuntimeError("state arrived before its stepped horizon")
                    values = CassiCosmos7599Adapter._extract_values(
                        "state",
                        sorted(_DIRECT_FIELDS["state"]),
                        response,
                    )
                    prefix = f"h{current_horizon}"
                    observed.update(
                        {f"{prefix}_{name}": value for name, value in values.items()}
                    )
                elif command["cmd"] == "project":
                    if current_horizon is None or current_horizon != expected_horizon:
                        raise RuntimeError("projection arrived before its stepped horizon")
                    projection_fields = set(_PROJECT_FIELDS)
                    if phase_profile_bins:
                        projection_fields.update(_PHASE_PROFILE_FIELDS)
                    if phase_topology_bins:
                        projection_fields.update(_PHASE_TOPOLOGY_FIELDS)
                    if phase_winding_probe:
                        projection_fields.update(_PHASE_WINDING_FIELDS)
                    values = CassiCosmos7599Adapter._extract_values(
                        "project",
                        sorted(projection_fields),
                        response,
                    )
                    prefix = f"h{current_horizon}"
                    observed.update(
                        {f"{prefix}_{name}": value for name, value in values.items()}
                    )
            return self._world_ack(
                operation_id=operation_id,
                status="succeeded",
                observed_values=observed,
                source_content=b"\n".join(raw_lines),
                context={
                    "authorization_reason": self.authorization.reason,
                    "deposit_count": deposit_count,
                    "horizons": list(horizons),
                    "phase": phase,
                    "projection_k": projection_k,
                    "phase_profile_bins": phase_profile_bins,
                    "phase_topology_bins": phase_topology_bins,
                    "phase_winding_probe": phase_winding_probe,
                },
            )
        except (ConnectionError, OSError, TimeoutError, ValueError, KeyError) as exc:
            return self._world_ack(
                operation_id=operation_id,
                status="unknown",
                source_content=(
                    b"\n".join(raw_lines)
                    + canonical_json_bytes(
                        {
                            "adapter": "cassi-cosmos-world-factory-7599",
                            "error": str(exc),
                            "phase": "transport-unknown",
                        }
                    )
                ),
                context={
                    "authorization_reason": self.authorization.reason,
                    "error": str(exc),
                    "phase": "transport-unknown",
                },
            )

    @staticmethod
    def _world_ack(
        *,
        operation_id: str,
        status: str,
        source_content: bytes,
        context: Mapping[str, Any],
        observed_values: Mapping[str, float] | None = None,
    ) -> WorldAcknowledgment:
        acknowledgment_id = (
            "ack:cosmos-world:"
            + sha256_value(
                {
                    "operation_id": operation_id,
                    "source_sha256": hashlib.sha256(source_content).hexdigest(),
                    "status": status,
                }
            )
        )
        return WorldAcknowledgment(
            acknowledgment_id=acknowledgment_id,
            operation_id=operation_id,
            status=status,
            observed_values=dict(observed_values or {}),
            context=dict(context),
            source_content=source_content,
        )
