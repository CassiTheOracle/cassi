"""Production numerical operator for the seven-pool resonant field.

The module deliberately owns only fixed geometry, numerical profiles, and pure
state transitions. Learned relation matrices are supplied in ``ResonantProblem``
and are never retained as an adaptive side table by a workspace.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any, Mapping, Sequence

import numpy as np
import torch
from scipy.sparse.linalg import LinearOperator, gmres


SCHEMA = "cassifi.resonant-workspace.v1"
LAYOUT = "mode-major-9M-1:f64le"
SQRT2 = math.sqrt(2.0)


class ResonantNumericalError(ValueError):
    """Invalid numerical state or unsupported operation."""


class ResonantDeviceUnavailableError(RuntimeError):
    """Requested GPU arithmetic is unavailable."""


def _finite(a: np.ndarray, name: str) -> None:
    if not np.isfinite(a).all():
        raise ResonantNumericalError(f"{name} contains non-finite values")


def _as_f64(a: Any, shape: tuple[int, ...] | None = None, name: str = "array") -> np.ndarray:
    out = np.asarray(a, dtype=np.float64)
    if shape is not None and out.shape != shape:
        raise ResonantNumericalError(f"{name} must have shape {shape}, got {out.shape}")
    _finite(out, name)
    return out


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, tuple):
        return [_jsonable(v) for v in value]
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    return value


def pulse_primitive(phase: float) -> float:
    """Unwrapped integral of ``sin(theta)^2/pi`` (one unit per beat)."""
    return (float(phase) - 0.5 * math.sin(2.0 * float(phase))) / (2.0 * math.pi)


@dataclass(frozen=True)
class ResonantProfile:
    """Fixed seven-pool geometry and integration constants.

    ``ports_per_pool`` is a resolution setting, not a number of models.  Four
    is the minimum production resolution; expansion creates passive ports.
    """

    pools: int = 7
    ports_per_pool: int = 4
    coupling: float = 0.006
    beta: float = 0.08
    relative_stiffness: float = 1.0
    damping: float = 0.012
    heartbeat_frequency: float = 0.75
    heartbeat_work: float = 0.006
    heartbeat_amplitude: float = 0.018
    time_step: float = 0.08
    activity_tau: float = 4.0
    quiet_damping: float = 16.0
    tolerance: float = 2e-12
    max_subdivisions: int = 8
    topology: str = "meaningful-helix"
    arithmetic: str = "numpy-cpu-float64"
    integration: str = "average-vector-field-discrete-gradient-v1"
    projected_transport: Any = None
    projected_inv_mass: Any = None

    projected_quartic_weights: Any = None
    def __post_init__(self) -> None:
        if self.pools != 7:
            raise ResonantNumericalError("the resonant architecture has exactly seven pools")
        if isinstance(self.ports_per_pool, bool) or not isinstance(self.ports_per_pool, int) or not 4 <= self.ports_per_pool <= 4096:
            raise ResonantNumericalError("ports_per_pool must be an integer between 4 and 4096")
        for name in ("coupling", "beta", "relative_stiffness", "damping", "heartbeat_frequency", "heartbeat_work", "heartbeat_amplitude", "time_step", "activity_tau", "quiet_damping", "tolerance"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0.0:
                raise ResonantNumericalError(f"{name} must be finite and nonnegative")
        if self.time_step <= 0 or self.activity_tau <= 0 or self.quiet_damping <= 0 or self.tolerance <= 0:
            raise ResonantNumericalError("time_step, activity_tau, quiet_damping and tolerance must be positive")
        if isinstance(self.max_subdivisions, bool) or not isinstance(self.max_subdivisions, int) or not 0 <= self.max_subdivisions <= 20:
            raise ResonantNumericalError("invalid subdivision bound")
        if self.projected_transport is not None:
            pt = _as_f64(self.projected_transport, (2*self.port_count, 2*self.port_count), "projected_transport")
            if not np.allclose(pt, -pt.T, atol=1e-12, rtol=0): raise ResonantNumericalError("projected transport must be antisymmetric")
            pt = pt.copy(); pt.setflags(write=False); object.__setattr__(self, "projected_transport", pt)
        if self.projected_inv_mass is not None:
            raw = _as_f64(self.projected_inv_mass, name="projected inverse mass")
            if raw.shape not in {(2*self.port_count,), (2*self.port_count, 2*self.port_count)}:
                raise ResonantNumericalError("projected inverse mass must be positive vector or matrix")
            if raw.ndim == 1 and np.any(raw <= 0):
                raise ResonantNumericalError("projected inverse mass vector must be positive")
            if raw.ndim == 2 and (not np.allclose(raw, raw.T, atol=1e-12, rtol=0) or np.any(np.linalg.eigvalsh(raw) <= 0)):
                raise ResonantNumericalError("projected inverse mass matrix must be symmetric positive definite")
            pim = raw.copy(); pim.setflags(write=False); object.__setattr__(self, "projected_inv_mass", pim)
        if self.projected_quartic_weights is not None:
            weights = _as_f64(self.projected_quartic_weights, (self.port_count,), "quartic weights")
            if np.any(weights < 0):
                raise ResonantNumericalError("quartic weights must be nonnegative")
            weights.setflags(write=False)
            object.__setattr__(self, "projected_quartic_weights", weights)
        if self.topology not in {"meaningful-helix", "undivided", "isolated", "rewired"}:
            raise ResonantNumericalError("topology must be meaningful-helix, undivided, isolated, or rewired")

    @property
    def port_count(self) -> int:
        return self.pools * self.ports_per_pool

    @property
    def mode_count(self) -> int:
        return self.port_count + 1

    @property
    def page_shape(self) -> tuple[int, int, int]:
        return (1, 9 * self.mode_count, 1)

    @property
    def layout_identity(self) -> str:
        return f"{LAYOUT}:N={self.port_count}:pools={self.pools}:ports={self.ports_per_pool}"

    @property
    def coordinates(self) -> tuple[tuple[float, float, float], ...]:
        # Two strands make one complete turn over the longitudinal extent.
        rows: list[tuple[float, float, float]] = []
        for pool in range(self.pools):
            for local in range(self.ports_per_pool):
                t = (pool + (local + 0.5) / self.ports_per_pool) / self.pools
                angle = 2.0 * math.pi * t
                radius = 1.0 + 0.08 * math.sin(math.pi * t)
                rows.append((t, radius * math.cos(angle), radius * math.sin(angle)))
        return tuple(rows + [(t, -x, -y) for t, x, y in rows])

    @property
    def volumes(self) -> tuple[float, ...]:
        base = tuple(1.0 + 0.05 * ((i % self.ports_per_pool) / max(1, self.ports_per_pool - 1)) for i in range(self.port_count))
        return (tuple(1.0 for _ in base) * 2) if self.topology == "undivided" else base * 2
    @property
    def inertances(self) -> tuple[float, ...]:
        if self.projected_inv_mass is not None:
            pim = np.asarray(self.projected_inv_mass, dtype=np.float64)
            return tuple((1.0/np.diag(pim) if pim.ndim == 2 else 1.0/pim).tolist())
        if self.topology == "undivided":
            return tuple(1.0 for _ in range(2 * self.port_count))
        return tuple(1.3 ** pool for pool in range(self.pools) for _ in range(self.ports_per_pool)) * 2

    @property
    def edges(self) -> tuple[tuple[int, int, float, str], ...]:
        """Oriented circuit and local exchange edges (source,destination,weight,kind)."""
        n = self.port_count
        p = self.ports_per_pool
        circuit = list(range(n)) + list(range(2 * n - 1, n - 1, -1))
        result: list[tuple[int, int, float, str]] = []
        coordinates = np.asarray(self.coordinates)
        volumes = np.asarray(self.volumes)
        seen: set[tuple[int, int, str]] = set()
        def add(source: int, destination: int, kind: str, scale: float = 1.0) -> None:
            key = (source, destination, kind)
            if source == destination or key in seen:
                return
            seen.add(key)
            dx = coordinates[destination] - coordinates[source]
            length = max(float(np.linalg.norm(dx)), 1e-12)
            weight = self.coupling * scale / (length * math.sqrt(volumes[source] * volumes[destination]))
            result.append((source, destination, weight, kind))
        if self.topology != "isolated":
            for source, destination in zip(circuit, circuit[1:] + circuit[:1]):
                add(source, destination, "circuit")
        for pool in range(self.pools):
            start = pool * p
            for local in range(p - 1):
                add(start + local, start + local + 1, "intra", 0.5)
            add(start, start + p - 1, "intra", 0.35)
        if self.topology != "isolated":
            for pool in range(self.pools - 1):
                add(pool * p + p - 1, (pool + 1) * p, "neck", 0.7)
        if self.topology == "rewired":
            circuit_edges = [row for row in result if row[3] == "circuit"]
            others = [row for row in result if row[3] != "circuit"]
            destinations = [row[1] for row in circuit_edges]
            rewired = [(src, destinations[(i + 7) % len(destinations)], weight, kind)
                       for i, (src, _dst, weight, kind) in enumerate(circuit_edges)]
            result = others + [row for row in rewired if row[0] != row[1]]
        return tuple(result)

    @property
    def transport_matrix(self) -> np.ndarray:
        n = 2*self.port_count
        if self.projected_transport is not None:
            return np.asarray(self.projected_transport, dtype=np.float64).copy()
        matrix = np.zeros((n, n), dtype=np.float64)
        for source, destination, weight, _kind in self.edges:
            matrix[destination, source] += weight
            matrix[source, destination] -= weight
        return matrix

    def as_dict(self) -> dict[str, Any]:
        return {
            "pools": self.pools, "ports_per_pool": self.ports_per_pool,
            "coupling": self.coupling, "beta": self.beta,
            "relative_stiffness": self.relative_stiffness, "damping": self.damping,
            "heartbeat_frequency": self.heartbeat_frequency, "heartbeat_work": self.heartbeat_work,
            "heartbeat_amplitude": self.heartbeat_amplitude, "time_step": self.time_step,
            "activity_tau": self.activity_tau, "quiet_damping": self.quiet_damping,
            "tolerance": self.tolerance, "max_subdivisions": self.max_subdivisions,
            "topology": self.topology, "arithmetic": self.arithmetic,
            "integration": self.integration, "layout_identity": self.layout_identity,
            "projected_transport": None if self.projected_transport is None else self.projected_transport.tolist(),
            "projected_inv_mass": None if self.projected_inv_mass is None else self.projected_inv_mass.tolist(),
            "projected_quartic_weights": None if self.projected_quartic_weights is None else self.projected_quartic_weights.tolist(),
        }


    def gpu_profile(self, device: str = "cuda") -> dict[str, Any]:

        if device.startswith("cuda") and not torch.cuda.is_available():
            raise ResonantDeviceUnavailableError(f"requested device {device!r} is unavailable")
        try:
            dev = torch.device(device)
            if dev.type == "cuda":
                torch.empty((1,), device=dev)
        except Exception as exc:
            raise ResonantDeviceUnavailableError(f"requested device {device!r} is unavailable") from exc
        return {"device": str(dev), "dtype": "torch.float64", "batched": True, "layout": self.layout_identity, "arithmetic": "torch-batched-float64"}


@dataclass(frozen=True)
class ResonantProblem:
    """Disposable learned objective and admissible fixed constraints."""

    variable_ids: tuple[str, ...]
    precision: Any
    linear_b: Any = None
    observed: Mapping[str, float] = field(default_factory=dict)
    affine_constraints: Any = None
    dependency_sha256: str = ""

    def __post_init__(self) -> None:
        ids = tuple(str(v) for v in self.variable_ids)
        if len(ids) == 0 or len(set(ids)) != len(ids):
            raise ResonantNumericalError("variable_ids must be nonempty and unique")
        k = _as_f64(self.precision, (len(ids), len(ids)), "precision")
        if not np.allclose(k, k.T, atol=1e-12, rtol=0):
            raise ResonantNumericalError("precision must be symmetric")
        eig = np.linalg.eigvalsh(k)
        if float(eig.min()) <= 0:
            raise ResonantNumericalError("precision must be positive definite")
        if self.linear_b is None:
            linear_b = np.zeros(len(ids), dtype=np.float64)
        else:
            linear_b = _as_f64(self.linear_b, (len(ids),), "linear_b")
        obs = {str(name): float(value) for name, value in dict(self.observed).items()}
        if any(not math.isfinite(v) for v in obs.values()):
            raise ResonantNumericalError("observed values must be finite")
        object.__setattr__(self, "variable_ids", ids)
        object.__setattr__(self, "precision", k.copy())
        object.__setattr__(self, "linear_b", linear_b.copy())
        object.__setattr__(self, "observed", MappingProxyType(obs))
        if self.affine_constraints is not None:
            c = self.affine_constraints
            if isinstance(c, Mapping):
                rows = c.get("matrix", c.get("A"))
                rhs = c.get("rhs", c.get("b", []))
                c = (_as_f64(rows, name="constraint matrix"), _as_f64(rhs, name="constraint rhs").reshape(-1))
            elif isinstance(c, (tuple, list)) and len(c) == 2:
                c = (_as_f64(c[0], name="constraint matrix"), _as_f64(c[1], name="constraint rhs").reshape(-1))
            else:
                c = (_as_f64(c, name="constraint matrix"), np.zeros(len(np.asarray(c)), dtype=np.float64))
            if c[0].ndim != 2 or c[0].shape[0] != len(c[1]):
                raise ResonantNumericalError("affine constraints must be (matrix,rhs)")
            object.__setattr__(self, "affine_constraints", c)
        if self.dependency_sha256 and (len(self.dependency_sha256) != 64 or any(ch not in "0123456789abcdefABCDEF" for ch in self.dependency_sha256)):
            raise ResonantNumericalError("dependency_sha256 must be a hexadecimal digest")

    @property
    def linear(self) -> tuple[np.ndarray, np.ndarray]:
        return self.precision.copy(), self.linear_b.copy()


class ResonantWorkspace:
    """Canonical numerical field page plus reconstructible diagnostics."""

    def __init__(self, *, profile: ResonantProfile | None = None, field_page: Any = None,
                 bindings: Mapping[str, Any] | None = None, field_ticks: int = 0,
                 heartbeat_phase: float = 0.0, heartbeat_cycles: int = 0,
                 breath_phase: float = 0.0, breath_cycles: int = 0, activity: float = 0.0,
                 evidence_tick: int = 0, subdivision_ticks: int = 0, paused: bool = False,
                 ledger: Mapping[str, float] | None = None, layout_transition: Mapping[str, Any] | None = None) -> None:
        self.profile = profile or ResonantProfile()
        page = np.zeros(self.profile.page_shape, dtype=np.float64) if field_page is None else _as_f64(field_page, self.profile.page_shape, "field_page").copy()
        self._field = page
        self.bindings = MappingProxyType({str(k): MappingProxyType(dict(v)) if isinstance(v, Mapping) else v for k, v in (bindings or {}).items()})
        self.field_ticks = int(field_ticks); self.heartbeat_phase = float(heartbeat_phase); self.heartbeat_cycles = int(heartbeat_cycles)
        self.breath_phase = float(breath_phase); self.breath_cycles = int(breath_cycles); self.activity = float(activity)
        self.evidence_tick = int(evidence_tick); self.subdivision_ticks = int(subdivision_ticks); self.paused = bool(paused)
        self.ledger = MappingProxyType({"positive_heartbeat_work": 0.0, "extracted_heartbeat_work": 0.0, "dissipated_work": 0.0, "residual_work": 0.0, "parameter_work": 0.0, "balance_defect": 0.0, **{str(k): float(v) for k, v in (ledger or {}).items()}})
        self.layout_transition = MappingProxyType(dict(layout_transition or {}))
        self._validate()
        self._sealed = True

    def __setattr__(self, name: str, value: Any) -> None:
        if getattr(self, "_sealed", False):
            raise AttributeError("ResonantWorkspace is immutable; use a state transition")
        object.__setattr__(self, name, value)
    @property
    def field(self) -> np.ndarray:
        return self._field.copy()

    def common_coordinates(self) -> np.ndarray:
        n = self.profile.port_count
        return (self._field[0, 0:9*n:9, 0] + self._field[0, 1:9*n:9, 0]) / SQRT2

    def relative_coordinates(self) -> np.ndarray:
        n = self.profile.port_count
        return (self._field[0, 0:9*n:9, 0] - self._field[0, 1:9*n:9, 0]) / SQRT2

    def momentum(self) -> np.ndarray:
        n = self.profile.port_count
        return np.concatenate((self._field[0, 2:9*n:9, 0], self._field[0, 3:9*n:9, 0])).copy()

    @property
    def state_sha256(self) -> str:
        descriptor = self._descriptor(include_page=False)
        h = hashlib.sha256()
        h.update(self._field.astype("<f8", copy=False).tobytes(order="C"))
        h.update(json.dumps(descriptor, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())
        return h.hexdigest()

    @property
    def page_bytes(self) -> bytes:
        return self._field.astype("<f8", copy=False).tobytes(order="C")

    def _descriptor(self, *, include_page: bool = True) -> dict[str, Any]:
        d: dict[str, Any] = {"schema": SCHEMA, "profile": self.profile.as_dict(), "layout": self.profile.layout_identity,
            "bindings": _jsonable(self.bindings), "field_ticks": self.field_ticks,
            "heartbeat_phase": self.heartbeat_phase, "heartbeat_cycles": self.heartbeat_cycles,
            "breath_phase": self.breath_phase, "breath_cycles": self.breath_cycles, "activity": self.activity,
            "evidence_tick": self.evidence_tick, "subdivision_ticks": self.subdivision_ticks, "paused": self.paused,
            "ledger": dict(self.ledger), "layout_transition": dict(self.layout_transition)}
        if include_page:
            d["field"] = self._field.reshape(-1).tolist()
        return d

    def as_dict(self) -> dict[str, Any]:
        out = self._descriptor()
        out["state_sha256"] = self.state_sha256
        out["field_b64"] = base64.b64encode(self.page_bytes).decode("ascii")
        return out

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ResonantWorkspace":
        allowed = {"schema", "profile", "layout", "bindings", "field_ticks", "heartbeat_phase", "heartbeat_cycles", "breath_phase", "breath_cycles", "activity", "evidence_tick", "subdivision_ticks", "paused", "ledger", "layout_transition", "field", "field_b64", "state_sha256"}
        unknown = set(payload) - allowed
        if unknown:
            raise ResonantNumericalError(f"unknown workspace descriptor keys: {sorted(unknown)}")
        if payload.get("schema") != SCHEMA:
            raise ResonantNumericalError("unsupported resonant workspace schema")
        profile_data = dict(payload["profile"])
        profile_data.pop("layout_identity", None)
        profile = ResonantProfile(**{k: v for k, v in profile_data.items() if k in ResonantProfile.__dataclass_fields__})
        if "field_b64" in payload and "field" in payload:
            raw_check = base64.b64decode(str(payload["field_b64"]), validate=True)
            list_check = np.asarray(payload["field"], dtype="<f8").reshape(profile.page_shape).tobytes()
            if raw_check != list_check:
                raise ResonantNumericalError("mismatched duplicate field encodings")
        if "field_b64" in payload:
            raw = base64.b64decode(str(payload["field_b64"]), validate=True)
            if len(raw) != int(np.prod(profile.page_shape)) * 8:
                raise ResonantNumericalError("invalid field byte length")
            page = np.frombuffer(raw, dtype="<f8").reshape(profile.page_shape).copy()
        elif "field" in payload:
            page = np.asarray(payload["field"], dtype=np.float64).reshape(profile.page_shape)
        else:
            raise ResonantNumericalError("workspace descriptor has no field page")
        ws = cls(profile=profile, field_page=page, bindings=payload.get("bindings"), field_ticks=payload.get("field_ticks", 0),
                  heartbeat_phase=payload.get("heartbeat_phase", 0.0), heartbeat_cycles=payload.get("heartbeat_cycles", 0),
                  breath_phase=payload.get("breath_phase", 0.0), breath_cycles=payload.get("breath_cycles", 0), activity=payload.get("activity", 0.0),
                  evidence_tick=payload.get("evidence_tick", 0), subdivision_ticks=payload.get("subdivision_ticks", 0), paused=payload.get("paused", False),
                  ledger=payload.get("ledger"), layout_transition=payload.get("layout_transition"))
        expected = payload.get("state_sha256")
        if expected is not None and expected != ws.state_sha256:
            raise ResonantNumericalError("workspace state digest mismatch")
        return ws

    def _validate(self) -> None:
        _finite(self._field, "field page")
        if self._field.shape != self.profile.page_shape or self._field.dtype != np.float64:
            raise ResonantNumericalError("invalid canonical field page")
        n = self.profile.port_count; m = self.profile.mode_count
        modes = self._field.reshape(-1)[:9*n].reshape(n, 9)
        if np.any(modes[:, 4:] != 0):
            raise ResonantNumericalError("unused per-port lanes must be canonical zero")
        if np.any(self._field[0, 9*n+3:9*m, 0] != 0):
            raise ResonantNumericalError("unused clock lanes must be canonical zero")
        if not (0.0 <= self.activity <= 1.0):
            raise ResonantNumericalError("activity must lie in [0,1]")
        if self._field[0, 9*n, 0] != self.heartbeat_phase or self._field[0, 9*n+1, 0] != self.breath_phase or self._field[0, 9*n+2, 0] != self.activity:
            raise ResonantNumericalError("clock metadata does not match canonical field lanes")
        for value in (self.heartbeat_phase, self.breath_phase):
            if not math.isfinite(value):
                raise ResonantNumericalError("invalid phase")
        if self.field_ticks < 0 or self.evidence_tick < 0 or self.heartbeat_cycles < 0 or self.breath_cycles < 0:
            raise ResonantNumericalError("clock counters cannot be negative")

    def _copy(self, *, field_page: Any = None, **changes: Any) -> "ResonantWorkspace":
        data = {"profile": self.profile, "field_page": self._field if field_page is None else field_page,
                "bindings": self.bindings, "field_ticks": self.field_ticks, "heartbeat_phase": self.heartbeat_phase, "heartbeat_cycles": self.heartbeat_cycles,
                "breath_phase": self.breath_phase, "breath_cycles": self.breath_cycles, "activity": self.activity, "evidence_tick": self.evidence_tick,
                "subdivision_ticks": self.subdivision_ticks, "paused": self.paused, "ledger": self.ledger, "layout_transition": self.layout_transition}
        data.update(changes)
        return ResonantWorkspace(**data)


def initial_workspace(profile: ResonantProfile | Mapping[str, Any] | None = None) -> ResonantWorkspace:
    if isinstance(profile, Mapping): profile = ResonantProfile(**dict(profile))
    return ResonantWorkspace(profile=profile)


def _allocate_bindings(workspace: ResonantWorkspace, problem: ResonantProblem) -> dict[str, dict[str, Any]]:
    p = workspace.profile.ports_per_pool
    existing = dict(workspace.bindings)
    occupied = {int(v["port"]) for v in existing.values() if isinstance(v, Mapping) and "port" in v}
    for var in problem.variable_ids:
        if var in existing: continue
        # The admitted scope hint is deterministic if present; otherwise pool
        # occupancy and then port identity decide.
        hint = problem.observed.get(f"{var}.__pool", None)
        preferred = int(hint) if hint is not None and float(hint).is_integer() and 0 <= int(hint) < 7 else None
        pools = list(range(7))
        if preferred is not None: pools.remove(preferred); pools.insert(0, preferred)
        chosen_pool = min(pools, key=lambda pool: (sum(1 for x in occupied if pool*p <= x < (pool+1)*p), sum(1 for x in occupied if pool*p <= x < (pool+1)*p), pool))
        candidates = [chosen_pool*p + local for local in range(p) if chosen_pool*p + local not in occupied]
        if not candidates:
            # Capacity expansion is explicit, not an accidental overwrite.
            raise ResonantNumericalError("no unoccupied paired port; expand resolution before binding")
        port = candidates[0]; occupied.add(port)
        existing[var] = {"pool": chosen_pool, "port": port, "component": "common", "binding_id": f"default:{var}:common"}
    return existing


def bind_workspace(workspace: ResonantWorkspace, problem: ResonantProblem) -> ResonantWorkspace:
    if not isinstance(workspace, ResonantWorkspace) or not isinstance(problem, ResonantProblem): raise TypeError("workspace and problem types are required")
    bindings = _allocate_bindings(workspace, problem)
    # Binding is metadata only; it never writes a target or exact solution into
    # the candidate field.  Existing phase-space coordinates remain untouched.
    return workspace._copy(bindings=bindings)

def _matrices(profile: ResonantProfile) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    n = 2*profile.port_count
    if profile.projected_transport is not None:
        s = profile.transport_matrix
    else:
        s = np.zeros((n, n), dtype=np.float64)
        for source, destination, weight, _ in profile.edges:
            s[destination, source] += weight
            s[source, destination] -= weight
    if profile.projected_inv_mass is not None and np.asarray(profile.projected_inv_mass).ndim == 2:
        inv_mass = np.asarray(profile.projected_inv_mass, dtype=np.float64)
    else:
        inv_mass = np.diag(1.0 / np.asarray(profile.inertances, dtype=np.float64))
    j = np.block([[s, np.eye(n)], [-np.eye(n), s]])
    gamma = np.eye(2*n, dtype=np.float64) * profile.damping
    return s, inv_mass, j, gamma

def _inverse_mass(profile: ResonantProfile) -> np.ndarray:
    if profile.projected_inv_mass is not None:
        raw = np.asarray(profile.projected_inv_mass, dtype=np.float64)
        return raw if raw.ndim == 2 else np.diag(raw)
    return np.diag(1.0 / np.asarray(profile.inertances, dtype=np.float64))
def _coordinates(workspace: ResonantWorkspace) -> tuple[np.ndarray, np.ndarray]:
    n = workspace.profile.port_count
    page = workspace._field.reshape(-1)
    return page[0:9*n:9].copy(), page[1:9*n:9].copy()  # qY, qI


def _state_vector(workspace: ResonantWorkspace) -> np.ndarray:
    n = workspace.profile.port_count; page = workspace._field.reshape(-1)
    return np.concatenate((page[0:9*n:9], page[1:9*n:9], page[2:9*n:9], page[3:9*n:9]))


def _page_from_state(workspace: ResonantWorkspace, z: np.ndarray, *, heartbeat_phase: float | None = None, breath_phase: float | None = None, activity: float | None = None) -> np.ndarray:
    n = workspace.profile.port_count; page = workspace._field.copy().reshape(-1)
    for lane, values in enumerate(np.split(z, 4)):
        page[lane:9*n:9] = values
    m = workspace.profile.mode_count
    page[9*n] = workspace.heartbeat_phase if heartbeat_phase is None else heartbeat_phase
    page[9*n + 1] = workspace.breath_phase if breath_phase is None else breath_phase
    page[9*n + 2] = workspace.activity if activity is None else activity
    page[9*n + 3:9*m] = 0.0
    return page.reshape(workspace.profile.page_shape)


class _WaveOperator:
    """One batch-local operator; only scoped matrices and sparse rail edges persist here."""

    def __init__(self, workspace: ResonantWorkspace, problem: ResonantProblem | None, *, device: str | None = None) -> None:
        self.profile = workspace.profile
        self.n = workspace.profile.port_count
        self.device = device
        self.applications = 0
        n = self.n
        self.edges = workspace.profile.edges
        self.sources = self.array([row[0] for row in self.edges], integer=True)
        self.destinations = self.array([row[1] for row in self.edges], integer=True)
        self.weights = self.array([row[2] for row in self.edges])
        self.transport = None if workspace.profile.projected_transport is None else self.array(workspace.profile.projected_transport)
        inv_mass = workspace.profile.projected_inv_mass
        if inv_mass is None:
            inv_mass = 1 / np.asarray(workspace.profile.inertances)
        inv_mass = np.asarray(inv_mass)
        self.inv_mass = self.array(inv_mass)
        self.mass = self.array(1 / inv_mass if inv_mass.ndim == 1 else np.linalg.inv(inv_mass))
        weights = workspace.profile.projected_quartic_weights
        self.beta = self.array(workspace.profile.beta * (np.ones(n) if weights is None else weights))
        self.ports = self.array([], integer=True)
        self.k = self.array(np.zeros((0, 0)))
        self.b = self.array([])
        self.conditioner = self.array(np.zeros((0, 0)))
        rows: list[np.ndarray] = []
        targets: list[float] = []
        if problem is not None:
            ports = [int(workspace.bindings[name]["port"]) for name in problem.variable_ids]
            self.ports = self.array(ports, integer=True)
            self.k = self.array(problem.precision)
            self.b = self.array(problem.linear_b)
            common_rows: list[np.ndarray] = []
            for name, value in problem.observed.items():
                row = np.zeros(len(ports))
                row[problem.variable_ids.index(name)] = 1
                common_rows.append(row)
                targets.append(value)
            if problem.affine_constraints is not None:
                matrix, rhs = problem.affine_constraints
                if matrix.shape[1] != len(ports):
                    raise ResonantNumericalError("constraints must address declared common variables")
                common_rows.extend(matrix)
                targets.extend(rhs)
            for common_row in common_rows:
                row = np.zeros(4 * n)
                row[ports] = common_row / SQRT2
                row[np.asarray(ports) + n] = common_row / SQRT2
                rows.append(row)
            if common_rows:
                common_matrix = np.asarray(common_rows)
                _, singular, vh = np.linalg.svd(common_matrix, full_matrices=True)
                threshold = max(common_matrix.shape) * np.finfo(float).eps * float(singular.max(initial=0))
                rank = int(np.count_nonzero(singular > threshold))
                tangent = vh[rank:].T
                reduced = tangent.T @ problem.precision @ tangent
                conditioner = tangent @ np.linalg.solve(reduced, tangent.T) if tangent.shape[1] else np.zeros_like(problem.precision)
                # A fixed boundary has zero normal momentum; relative strand motion remains free.
                momentum_rows = [np.concatenate((np.zeros(2 * n), row[:2 * n])) for row in rows]
                rows.extend(momentum_rows)
                targets.extend([0.0] * len(momentum_rows))
            else:
                conditioner = np.linalg.solve(problem.precision, np.eye(len(ports)))
            self.conditioner = self.array(conditioner)
        matrix = np.asarray(rows).reshape((-1, 4 * n))
        self.constraints = self.array(matrix)
        self.targets = self.array(targets)
        self.constraint_inverse = self.array(np.linalg.pinv(matrix))
        rail_sums = np.zeros(2 * n)
        for source, destination, weight, _ in self.edges:
            rail_sums[source] += abs(weight)
            rail_sums[destination] += abs(weight)
        rail_bound = float(rail_sums.max(initial=0))
        if workspace.profile.projected_transport is not None:
            rail_bound = float(np.linalg.norm(workspace.profile.projected_transport, ord=np.inf))
        projection_bound = (
            1 + float(np.linalg.norm(np.linalg.pinv(matrix), ord=np.inf) * np.linalg.norm(matrix, ord=np.inf))
            if len(targets) else 1.0
        )
        mass_bound = float(np.max(1 / inv_mass)) if inv_mass.ndim == 1 else float(np.linalg.norm(np.linalg.inv(inv_mass), ord=np.inf))
        conditioner_bound = float(np.linalg.norm(conditioner, ord=np.inf)) if problem is not None else 1.0
        damping_bound = max(
            self.profile.damping,
            2 * self.profile.quiet_damping * max(conditioner_bound, mass_bound, 1 / max(self.profile.relative_stiffness, 1e-6)),
        )
        self.flow_roundoff_gain = projection_bound ** 2 * (1 + rail_bound + damping_bound)
        self.absolute_k = abs(self.k)
        self.absolute_b = abs(self.b)
        self.absolute_inv_mass = abs(self.inv_mass)
        if device is not None:
            # Device Newton solves batch the whole field; bound their explicit Jacobian storage.
            if (4 * n) ** 2 * 8 * 4 > 128 * 1024 * 1024:
                raise ResonantNumericalError("GPU Newton matrix exceeds the declared 128 MiB working allowance")
            self.identity = torch.eye(4 * n, dtype=torch.float64, device=device)

    def array(self, value: Any, *, integer: bool = False) -> Any:
        if self.device is None:
            return np.array(value, dtype=np.int64 if integer else np.float64)
        return torch.tensor(np.asarray(value), dtype=torch.int64 if integer else torch.float64, device=self.device)

    def cat(self, values: Sequence[Any]) -> Any:
        return np.concatenate(values) if self.device is None else torch.cat(tuple(values))

    def clone(self, value: Any) -> Any:
        return value.copy() if self.device is None else value.clone()

    def norm(self, value: Any) -> float:
        return float(np.max(np.abs(value), initial=0)) if self.device is None else float(torch.max(torch.abs(value))) if value.numel() else 0.0

    @staticmethod
    def multiply(coefficient: Any, value: Any) -> Any:
        return coefficient.reshape((-1,) + (1,) * (value.ndim - 1)) * value

    def mass_apply(self, value: Any, *, inverse: bool = True) -> Any:
        matrix = self.inv_mass if inverse else self.mass
        return self.multiply(matrix, value) if matrix.ndim == 1 else matrix @ value

    def semantic(self, value: Any, *, force: bool = True) -> Any:
        result = self.clone(value)
        if len(self.ports):
            result[self.ports] = self.k @ value[self.ports]
            if force:
                result[self.ports] -= self.b
        return result

    def project(self, value: Any) -> Any:
        return value - self.constraint_inverse @ (self.constraints @ value) if len(self.targets) else value

    def boundary(self, value: Any, tolerance: float) -> Any:
        result = value + self.constraint_inverse @ (self.targets - self.constraints @ value) if len(self.targets) else value
        if self.norm(self.constraints @ result - self.targets) > tolerance:
            raise ResonantNumericalError("inconsistent common-coordinate constraints")
        return result

    def rail(self, value: Any) -> Any:
        if self.transport is not None:
            return self.transport @ value
        if self.device is None:
            result = np.zeros_like(value)
            np.add.at(result, self.destinations, self.multiply(self.weights, value[self.sources]))
            np.add.at(result, self.sources, -self.multiply(self.weights, value[self.destinations]))
        else:
            result = torch.zeros_like(value)
            result.index_add_(0, self.destinations, self.multiply(self.weights, value[self.sources]))
            result.index_add_(0, self.sources, -self.multiply(self.weights, value[self.destinations]))
        return result

    def circulation(self, gradient: Any) -> Any:
        q, p = gradient[:2 * self.n], gradient[2 * self.n:]
        return self.cat((self.rail(q) + p, -q + self.rail(p)))

    def dissipation(self, gradient: Any, quiet: bool) -> Any:
        if not quiet:
            return self.profile.damping * gradient
        qy, qi, py, pi = gradient.reshape((4, self.n) + gradient.shape[1:])
        common, relative = (qy + qi) / SQRT2, (qy - qi) / SQRT2
        common = self.clone(common)
        if len(self.ports):
            common[self.ports] = self.conditioner @ common[self.ports]
        relative = relative / max(self.profile.relative_stiffness, 1e-6)
        return self.profile.quiet_damping * self.cat((
            (common + relative) / SQRT2,
            (common - relative) / SQRT2,
            self.mass_apply(self.cat((py, pi)), inverse=False),
        ))

    def flow(self, gradient: Any, quiet: bool) -> Any:
        self.applications += 1
        gradient = self.project(gradient)
        return self.project(self.circulation(gradient) - self.dissipation(gradient, quiet))

    def energy_gradient(self, value: Any) -> tuple[float, Any]:
        qy, qi, py, pi = value.reshape(4, self.n)
        x, d = (qy + qi) / SQRT2, (qy - qi) / SQRT2
        kx = self.semantic(x, force=False)
        semantic = self.semantic(x)
        relative = self.profile.relative_stiffness * d + self.beta * d ** 3
        p = self.cat((py, pi))
        gp = self.mass_apply(p)
        energy = 0.5 * (x @ kx + self.profile.relative_stiffness * (d @ d) + p @ gp)
        energy += (self.beta * d ** 4).sum() / 4
        if len(self.ports):
            energy -= self.b @ x[self.ports]
        return float(energy), self.cat(((semantic + relative) / SQRT2, (semantic - relative) / SQRT2, gp))

    def roundoff_scales(self, value: Any) -> tuple[float, float]:
        """Absolute-product bounds retain cancellation hidden by a small energy."""
        qy, qi, py, pi = abs(value).reshape(4, self.n)
        common = (qy + qi) / SQRT2
        semantic = self.clone(common)
        if len(self.ports):
            semantic[self.ports] = self.absolute_k @ common[self.ports] + self.absolute_b
        relative = self.profile.relative_stiffness * common + self.beta * common ** 3
        momentum = self.cat((py, pi))
        kinetic = (
            self.multiply(self.absolute_inv_mass, momentum)
            if self.absolute_inv_mass.ndim == 1 else self.absolute_inv_mass @ momentum
        )
        position = (semantic + relative) / SQRT2
        magnitude = self.cat((position, position, kinetic))
        return self.norm(magnitude), float(abs(value) @ magnitude)

    def discrete_gradient(self, before: Any, after: Any) -> Any:
        qy0, qi0, py0, pi0 = before.reshape(4, self.n)
        qy1, qi1, py1, pi1 = after.reshape(4, self.n)
        x = (qy0 + qi0 + qy1 + qi1) / (2 * SQRT2)
        d0, d1 = (qy0 - qi0) / SQRT2, (qy1 - qi1) / SQRT2
        semantic = self.semantic(x)
        relative = self.profile.relative_stiffness * (d0 + d1) / 2
        relative += self.beta * (d1 ** 3 + d1 ** 2 * d0 + d1 * d0 ** 2 + d0 ** 3) / 4
        return self.cat(((semantic + relative) / SQRT2, (semantic - relative) / SQRT2,
                         self.mass_apply(self.cat((py0 + py1, pi0 + pi1))) / 2))

    def derivative(self, before: Any, after: Any, value: Any, quiet: bool) -> Any:
        qy, qi, py, pi = value.reshape((4, self.n) + value.shape[1:])
        x, d = (qy + qi) / SQRT2, (qy - qi) / SQRT2
        q0, i0 = before[:self.n], before[self.n:2 * self.n]
        q1, i1 = after[:self.n], after[self.n:2 * self.n]
        d0, d1 = (q0 - i0) / SQRT2, (q1 - i1) / SQRT2
        if quiet:
            factor = 1.0
            relative = self.profile.relative_stiffness + 3 * self.beta * d1 ** 2
        else:
            factor = 0.5
            relative = self.profile.relative_stiffness / 2 + self.beta * (3 * d1 ** 2 + 2 * d1 * d0 + d0 ** 2) / 4
        semantic = factor * self.semantic(x, force=False)
        relative = self.multiply(relative, d)
        return self.cat(((semantic + relative) / SQRT2, (semantic - relative) / SQRT2,
                         factor * self.mass_apply(self.cat((py, pi)))))

    def step(self, before: Any, duration: float, *, quiet: bool, max_iterations: int, tolerance: float) -> tuple[Any, dict[str, float]]:
        candidate = self.clone(before)
        for iteration in range(max_iterations):
            gradient = self.energy_gradient(candidate)[1] if quiet else self.discrete_gradient(before, candidate)
            flow = self.flow(gradient, quiet)
            residual = candidate - before - duration * flow
            # Absolute residuals below projected force roundoff cannot be
            # resolved by further Newton iterations. The separate common-
            # coordinate certificate still determines whether a readout settles.
            rounding = 64 * np.finfo(float).eps * (
                self.norm(candidate) + self.norm(before)
                + duration * max(self.norm(flow), self.flow_roundoff_gain * self.roundoff_scales(candidate)[0])
            )
            if self.norm(residual) <= max(tolerance, rounding):
                break
            def jacobian(value: Any) -> Any:
                return value - duration * self.flow(self.derivative(before, candidate, value, quiet), quiet)
            if self.device is None:
                operator = LinearOperator((len(before), len(before)), matvec=jacobian, dtype=np.float64)
                delta, info = gmres(operator, residual, atol=tolerance * 0.05, rtol=1e-10,
                                    restart=min(32, len(before)), maxiter=8)
                if info != 0:
                    raise ResonantNumericalError("bounded matrix-free Newton solve exhausted")
            else:
                delta = torch.linalg.solve(jacobian(self.identity), residual)
            candidate -= delta
        else:
            raise ResonantNumericalError("bounded nonlinear solve exhausted")
        start_energy = self.energy_gradient(before)[0]
        end_energy = self.energy_gradient(candidate)[0]
        projected_gradient = self.project(gradient)
        dissipated = float(duration * (projected_gradient @ self.dissipation(projected_gradient, quiet)))
        numerical_dissipation = float((gradient - self.discrete_gradient(before, candidate)) @ (candidate - before)) if quiet else 0.0
        residual_work = float(gradient @ residual)
        defect = end_energy - start_energy + dissipated + numerical_dissipation - residual_work
        allowance = max(
            1e-10,
            64 * np.finfo(float).eps * max(
                1.0, self.roundoff_scales(before)[1], self.roundoff_scales(candidate)[1]
            ),
        )
        if not math.isfinite(defect) or abs(defect) > allowance or numerical_dissipation < -allowance:
            raise ResonantNumericalError("transition violates the discrete work balance")
        return candidate, {"dissipated_work": dissipated, "numerical_dissipated_work": max(0.0, numerical_dissipation),
                           "energy_roundoff_allowance": allowance,
                           "residual_work": residual_work, "balance_defect": defect,
                           "residual_norm": self.norm(residual), "iterations": iteration + 1}

    def kick(self, before: Any, phase: float, requested: float, allowance: float) -> tuple[Any, float]:
        if allowance <= 0 or requested <= 0:
            return before, 0.0
        direction = np.zeros(4 * self.n)
        direction[2 * self.n] = direction[3 * self.n - 1] = math.cos(phase) / SQRT2
        direction[2 * self.n + 1] = direction[3 * self.n - 2] = -math.sin(phase) / SQRT2
        motor = self.project(self.array(direction))
        mass_motor = self.mass_apply(motor[2 * self.n:])
        linear = float(before[2 * self.n:] @ mass_motor)
        quadratic = float(motor[2 * self.n:] @ mass_motor)
        if quadratic <= 0:
            return before, 0.0
        root = math.sqrt(linear * linear + 2 * quadratic * allowance)
        limit = 2 * allowance / (root + linear) if linear >= 0 else (root - linear) / quadratic
        amount = min(requested, limit)
        return before + amount * motor, linear * amount + 0.5 * quadratic * amount * amount


def apply_pool_impulse(
    workspace: ResonantWorkspace,
    *,
    pool_signal: Sequence[float],
    work_budget: float,
    evidence_tick: int,
    event_kind: str,
) -> tuple[ResonantWorkspace, dict[str, Any]]:
    """Apply one energy-bounded common-mode impulse across the seven pools."""
    if not isinstance(workspace, ResonantWorkspace):
        raise TypeError("workspace must be ResonantWorkspace")
    signal = _as_f64(pool_signal, (workspace.profile.pools,), "pool_signal")
    if not math.isfinite(work_budget) or not 0.0 <= work_budget <= 1.0:
        raise ResonantNumericalError("work_budget must be finite and in [0,1]")
    if (
        isinstance(evidence_tick, bool)
        or not isinstance(evidence_tick, int)
        or evidence_tick < workspace.evidence_tick
    ):
        raise ResonantNumericalError("evidence_tick cannot precede the workspace evidence clock")
    if event_kind not in {
        "formation",
        "withdrawal",
        "goal-observation",
        "forbidden-observation",
        "context-observation",
        "mismatch-observation",
    }:
        raise ResonantNumericalError("event_kind is not a supported field event")
    norm = float(np.linalg.norm(signal))
    if norm == 0.0:
        if work_budget:
            raise ResonantNumericalError("a positive work budget requires a nonzero pool signal")
        return workspace, {
            "schema": "cassifi.resonant-pool-impulse-receipt.v2",
            "accepted": False,
            "event_kind": event_kind,
            "pool_signal": signal.tolist(),
            "requested_work": 0.0,
            "applied_work": 0.0,
            "evidence_tick": evidence_tick,
            "state_sha256": workspace.state_sha256,
        }
    if workspace.paused and work_budget:
        raise ResonantNumericalError("paused workspace cannot accept a pool impulse")

    unit_signal = signal / norm
    ports_per_pool = workspace.profile.ports_per_pool
    one_strand = np.repeat(unit_signal, ports_per_pool) / math.sqrt(ports_per_pool)
    momentum_direction = np.concatenate((one_strand, one_strand)) / SQRT2
    n = workspace.profile.port_count
    direction = np.zeros(4 * n, dtype=np.float64)
    direction[2 * n:] = momentum_direction

    operator = _WaveOperator(workspace, None)
    before = _state_vector(workspace)
    start_energy = operator.energy_gradient(before)[0]
    recorded_start = float(workspace.ledger.get("stored_energy", start_energy))
    parameter_work = start_energy - recorded_start
    mass_direction = operator.mass_apply(direction[2 * n:])
    linear = float(before[2 * n:] @ mass_direction)
    quadratic = float(direction[2 * n:] @ mass_direction)
    if quadratic <= 0.0:
        raise ResonantNumericalError("pool impulse has no positive kinetic metric")
    root = math.sqrt(linear * linear + 2.0 * quadratic * work_budget)
    amount = (
        2.0 * work_budget / (root + linear)
        if linear >= 0.0
        else (root - linear) / quadratic
    )
    after = before + amount * direction
    end_energy = operator.energy_gradient(after)[0]
    if end_energy > 1e12:
        raise ResonantNumericalError("pool impulse exceeds the field energy ceiling")
    applied_work = end_energy - start_energy
    balance_defect = end_energy - recorded_start - parameter_work - applied_work
    allowance = max(
        1e-12,
        256.0 * np.finfo(float).eps * max(
            1.0,
            abs(recorded_start),
            abs(start_energy),
            abs(end_energy),
            abs(work_budget),
        ),
    )
    if (
        not math.isfinite(applied_work)
        or abs(applied_work - work_budget) > allowance
        or abs(balance_defect) > allowance
    ):
        raise ResonantNumericalError("pool impulse violates its bounded work balance")

    ledger = dict(workspace.ledger)
    increments = {
        "parameter_work": parameter_work,
        "temporal_coupling_work": applied_work,
        f"temporal_{event_kind}_work": applied_work,
        "balance_defect": balance_defect,
    }
    if event_kind.endswith("-observation"):
        increments["temporal_outcome_work"] = applied_work
    ledger.update({
        key: ledger.get(key, 0.0) + value
        for key, value in increments.items()
    })
    ledger["stored_energy"] = end_energy
    result = workspace._copy(
        field_page=_page_from_state(workspace, after),
        evidence_tick=evidence_tick,
        ledger=ledger,
    )
    return result, {
        "schema": "cassifi.resonant-pool-impulse-receipt.v2",
        "accepted": True,
        "event_kind": event_kind,
        "pool_signal": unit_signal.tolist(),
        "requested_work": work_budget,
        "applied_work": applied_work,
        "impulse_amount": amount,
        "recorded_start_energy": recorded_start,
        "start_energy": start_energy,
        "end_energy": end_energy,
        "parameter_work": parameter_work,
        "balance_defect": balance_defect,
        "energy_roundoff_allowance": allowance,
        "field_ticks": result.field_ticks,
        "evidence_tick": result.evidence_tick,
        "state_sha256": result.state_sha256,
    }


def score_pool_probes(
    workspace: ResonantWorkspace,
    probes: Mapping[str, Sequence[float]],
) -> Mapping[str, Any]:
    """Read the phase-bearing compatibility of fixed seven-pool probes.

    The workspace is never advanced or copied.  Each probe is normalized in
    the same common-mode geometry used by :func:`apply_pool_impulse`; its
    signed score is the projection of the current common position and velocity
    onto the workspace heartbeat phase.
    """
    if not isinstance(workspace, ResonantWorkspace):
        raise TypeError("workspace must be ResonantWorkspace")
    if not isinstance(probes, Mapping) or len(probes) > 4096:
        raise ResonantNumericalError("probes must be a bounded mapping")
    before_sha256 = workspace.state_sha256
    n = workspace.profile.port_count
    page = workspace._field.reshape(-1)
    q_common = (page[0:9*n:9] + page[1:9*n:9]) / SQRT2
    momentum = np.concatenate((page[2:9*n:9], page[3:9*n:9]))
    inverse_mass = (
        1.0 / np.asarray(workspace.profile.inertances, dtype=np.float64)
        if workspace.profile.projected_inv_mass is None
        else np.asarray(workspace.profile.projected_inv_mass, dtype=np.float64)
    )
    metric_momentum = (
        inverse_mass * momentum
        if inverse_mass.ndim == 1
        else inverse_mass @ momentum
    )
    kinetic_norm_squared = float(momentum @ metric_momentum)
    if kinetic_norm_squared < -1e-12:
        raise ResonantNumericalError("resonant inverse-mass metric is not positive")
    reference_norm = math.sqrt(
        float(q_common @ q_common) + max(0.0, kinetic_norm_squared)
    )
    phase = workspace.heartbeat_phase
    cosine, sine = math.cos(phase), math.sin(phase)
    rows: list[Mapping[str, Any]] = []
    for probe_id, raw_signal in sorted(probes.items()):
        if (
            not isinstance(probe_id, str)
            or not probe_id
            or len(probe_id.encode("utf-8")) > 512
        ):
            raise ResonantNumericalError("probe identifiers must be bounded text")
        signal = _as_f64(
            raw_signal, (workspace.profile.pools,), f"probe {probe_id}"
        )
        signal_norm = float(np.linalg.norm(signal))
        if signal_norm == 0.0:
            unit_signal = signal
            in_phase = quadrature = 0.0
        else:
            unit_signal = signal / signal_norm
            coordinate_probe = np.repeat(
                unit_signal, workspace.profile.ports_per_pool
            ) / math.sqrt(workspace.profile.ports_per_pool)
            momentum_probe = np.concatenate(
                (coordinate_probe, coordinate_probe)
            ) / SQRT2
            metric_probe = (
                inverse_mass * momentum_probe
                if inverse_mass.ndim == 1
                else inverse_mass @ momentum_probe
            )
            coordinate_norm_squared = float(
                coordinate_probe @ coordinate_probe
            )
            momentum_norm_squared = float(momentum_probe @ metric_probe)
            q_projection = float(coordinate_probe @ q_common)
            p_projection = float(momentum_probe @ metric_momentum)
            in_phase_probe_norm = math.sqrt(
                sine * sine * coordinate_norm_squared
                + cosine * cosine * momentum_norm_squared
            )
            quadrature_probe_norm = math.sqrt(
                cosine * cosine * coordinate_norm_squared
                + sine * sine * momentum_norm_squared
            )
            in_phase_denominator = reference_norm * in_phase_probe_norm
            quadrature_denominator = reference_norm * quadrature_probe_norm
            in_phase = (
                0.0
                if in_phase_denominator == 0.0
                else (
                    sine * q_projection + cosine * p_projection
                ) / in_phase_denominator
            )
            quadrature = (
                0.0
                if quadrature_denominator == 0.0
                else (
                    cosine * q_projection - sine * p_projection
                ) / quadrature_denominator
            )
        signal_value = unit_signal.tolist()
        rows.append(
            {
                "compatibility": in_phase,
                "in_phase": in_phase,
                "pool_signal": signal_value,
                "probe_id": probe_id,
                "probe_norm": signal_norm,
                "probe_sha256": hashlib.sha256(
                    json.dumps(
                        signal_value,
                        sort_keys=True,
                        separators=(",", ":"),
                        allow_nan=False,
                    ).encode("ascii")
                ).hexdigest(),
                "quadrature": quadrature,
            }
        )
    if workspace.state_sha256 != before_sha256:
        raise ResonantNumericalError("read-only probe scoring mutated the workspace")
    return {
        "schema": "cassifi.resonant-pool-probe-scores.v1",
        "workspace_state_sha256": before_sha256,
        "field_ticks": workspace.field_ticks,
        "evidence_tick": workspace.evidence_tick,
        "heartbeat_phase": phase,
        "metric": "normalized-common-phase-space-energy-projection-v1",
        "reference_norm": reference_norm,
        "scores": rows,
        "workspace_unchanged": True,
    }



def _advance(workspace: ResonantWorkspace, *, problem: ResonantProblem | None, ticks: int, demand: float,
             source_enabled: bool, quiet: bool, max_iterations: int, tolerance: float | None,
             device: str | None = None) -> tuple[ResonantWorkspace, dict[str, Any]]:
    if not isinstance(workspace, ResonantWorkspace):
        raise TypeError("workspace must be ResonantWorkspace")
    if isinstance(ticks, bool) or not isinstance(ticks, int) or not 0 <= ticks <= 4096:
        raise ResonantNumericalError("ticks must be an integer in [0,4096]")
    if isinstance(max_iterations, bool) or not isinstance(max_iterations, int) or not 1 <= max_iterations <= 512:
        raise ResonantNumericalError("nonlinear iterations must be in [1,512]")
    if not math.isfinite(demand) or not 0 <= demand <= 1:
        raise ResonantNumericalError("ready demand must be finite and in [0,1]")
    if workspace.paused and ticks:
        raise ResonantNumericalError("paused workspace cannot advance")
    if problem is not None:
        workspace = bind_workspace(workspace, problem)
    profile = workspace.profile
    tol = profile.tolerance if tolerance is None else min(profile.tolerance, float(tolerance))
    if not math.isfinite(tol) or tol <= 0:
        raise ResonantNumericalError("tolerance must be finite and positive")
    operator = _WaveOperator(workspace, problem, device=device)
    z = operator.array(_state_vector(workspace))
    current_energy = operator.energy_gradient(z)[0]
    start_energy = float(workspace.ledger.get("stored_energy", current_energy))
    parameter_work = current_energy - start_energy
    projected = operator.boundary(z, max(tol, 1e-10))
    boundary_work = operator.energy_gradient(projected)[0] - current_energy
    z = projected
    positive = extracted = dissipated = numerical_dissipated = residual_work = max_residual = 0.0
    subdivisions = iterations = 0
    phase_h, phase_b = workspace.heartbeat_phase, workspace.breath_phase
    heartbeat_cycles, breath_cycles = workspace.heartbeat_cycles, workspace.breath_cycles
    activity = workspace.activity
    for _ in range(ticks):
        h = profile.time_step
        rate = 0.5 + 1.5 * activity + 0.25 * (1 + math.cos(phase_b))
        for level in range(profile.max_subdivisions + 1):
            parts = 2 ** level
            trial = operator.clone(z)
            local_positive = local_extracted = 0.0
            local_dissipation = local_numerical = local_residual = local_max = 0.0
            local_iterations = 0
            try:
                for sub in range(parts):
                    sub_h = h / parts
                    phase0 = phase_h + sub * sub_h * profile.heartbeat_frequency
                    phase1 = phase0 + sub_h * profile.heartbeat_frequency
                    midpoint = (phase0 + phase1) / 2
                    allowance = profile.heartbeat_work * (pulse_primitive(phase1) - pulse_primitive(phase0))
                    energy_now = operator.energy_gradient(trial)[0]
                    allowance = min(allowance, max(0.0, 1e12 - energy_now)) if source_enabled and not quiet else 0.0
                    trial, work = operator.kick(trial, midpoint, sub_h * profile.heartbeat_amplitude * math.sin(midpoint) ** 2, allowance)
                    local_positive += max(work, 0.0)
                    local_extracted += max(-work, 0.0)
                    trial, receipt = operator.step(trial, sub_h * rate, quiet=quiet, max_iterations=max_iterations, tolerance=tol)
                    local_dissipation += receipt["dissipated_work"]
                    local_numerical += receipt["numerical_dissipated_work"]
                    local_residual += receipt["residual_work"]
                    local_max = max(local_max, receipt["residual_norm"])
                    local_iterations += int(receipt["iterations"])
            except (ResonantNumericalError, np.linalg.LinAlgError):
                continue
            z = trial
            positive += local_positive
            extracted += local_extracted
            dissipated += local_dissipation
            numerical_dissipated += local_numerical
            residual_work += local_residual
            max_residual = max(max_residual, local_max)
            subdivisions += parts - 1
            iterations += local_iterations
            break
        else:
            raise ResonantNumericalError("unresolved numerical work after bounded subdivision rollback")
        phase_h += h * profile.heartbeat_frequency
        phase_b += h * profile.heartbeat_frequency * (1 / 16 + 3 * activity / 16)
        wraps_h, wraps_b = math.floor(phase_h / (2 * math.pi)), math.floor(phase_b / (2 * math.pi))
        phase_h -= wraps_h * 2 * math.pi
        phase_b -= wraps_b * 2 * math.pi
        heartbeat_cycles += wraps_h
        breath_cycles += wraps_b
        activity = demand + (activity - demand) * math.exp(-h / profile.activity_tau)
    end_energy = operator.energy_gradient(z)[0]
    defect = end_energy - start_energy - parameter_work - boundary_work - positive + extracted + dissipated + numerical_dissipated - residual_work
    ledger = dict(workspace.ledger)
    increments = {"positive_heartbeat_work": positive, "extracted_heartbeat_work": extracted,
                  "dissipated_work": dissipated, "numerical_dissipated_work": numerical_dissipated,
                  "residual_work": residual_work, "parameter_work": parameter_work,
                  "boundary_work": boundary_work, "balance_defect": defect}
    ledger.update({key: ledger.get(key, 0.0) + value for key, value in increments.items()})
    ledger["stored_energy"] = end_energy
    vector = z if device is None else z.detach().cpu().numpy()
    page = _page_from_state(workspace, vector, heartbeat_phase=phase_h, breath_phase=phase_b, activity=activity)
    result = workspace._copy(field_page=page, field_ticks=workspace.field_ticks + ticks,
                             heartbeat_phase=phase_h, breath_phase=phase_b, heartbeat_cycles=heartbeat_cycles,
                             breath_cycles=breath_cycles, activity=activity, ledger=ledger,
                             subdivision_ticks=workspace.subdivision_ticks + subdivisions)
    receipt = {"schema": "cassifi.resonant-advance-receipt.v1", "accepted": True,
               "ticks": ticks, "field_ticks": result.field_ticks, "evidence_tick": result.evidence_tick,
               "start_energy": start_energy, "end_energy": end_energy, **increments,
               "maximum_residual_norm": max_residual, "subdivisions": subdivisions,
               "nonlinear_iterations": iterations, "operator_applications": operator.applications,
               "source_enabled": bool(source_enabled and not quiet), "pump_energy_ceiling": 1e12,
               "integration": "projected-backward-euler-quiet-v1" if quiet else profile.integration,
               "arithmetic": "numpy-matrix-free-float64" if device is None else "torch-batched-float64",
               "device": "cpu" if device is None else device, "state_sha256": result.state_sha256}
    return result, receipt


def advance_workspace(workspace: ResonantWorkspace, *, problem: ResonantProblem | None = None, ticks: int = 1,
                      demand: float = 0.0, source_enabled: bool = True, quiet: bool = False,
                      max_iterations: int = 32, tolerance: float | None = None) -> tuple[ResonantWorkspace, dict[str, Any]]:
    return _advance(workspace, problem=problem, ticks=ticks, demand=demand, source_enabled=source_enabled,
                    quiet=quiet, max_iterations=max_iterations, tolerance=tolerance)

def _diagnostics(workspace: ResonantWorkspace, problem: ResonantProblem | None = None) -> dict[str, Any]:
    operator = _WaveOperator(workspace, problem)
    z = _state_vector(workspace)
    profile, n = workspace.profile, workspace.profile.port_count
    energy, gradient = operator.energy_gradient(z)
    rate = 0.5 + 1.5 * workspace.activity + 0.25 * (1 + math.cos(workspace.breath_phase))
    velocity = rate * operator.flow(gradient, False)
    q, p = z[:2 * n], z[2 * n:]
    if operator.inv_mass.ndim == 1:
        normalization = np.sqrt(operator.inv_mass)
        normalized_p = normalization * p
        normalized_dp = normalization * velocity[2 * n:]
    else:
        normalization = np.linalg.cholesky(operator.inv_mass).T
        normalized_p = normalization @ p
        normalized_dp = normalization @ velocity[2 * n:]
    power = q * q + normalized_p * normalized_p
    amplitude = np.sqrt(power)
    phase = np.arctan2(normalized_p, q)
    angular_rate = np.divide(q * normalized_dp - normalized_p * velocity[:2 * n], power,
                             out=np.zeros_like(power), where=power > 1e-24)
    rows = []
    coordinates = profile.coordinates
    for port in range(2 * n):
        defined = bool(power[port] > 1e-24)
        rows.append({"port": port % n, "pool": (port % n) // profile.ports_per_pool,
                     "coordinate": list(coordinates[port]), "q": float(q[port]), "p": float(p[port]),
                     "amplitude": float(amplitude[port]), "power": float(power[port]),
                     "phase": float(phase[port]) if defined else None,
                     "phase_rate": float(angular_rate[port]) if defined else None})
    pools = []
    for pool in range(7):
        start = pool * profile.ports_per_pool
        indices = np.concatenate((np.arange(start, start + profile.ports_per_pool),
                                  np.arange(n + start, n + start + profile.ports_per_pool)))
        total_power = float(power[indices].sum())
        resultant = np.sum(power[indices] * np.exp(1j * phase[indices]))
        defined = abs(resultant) > 1e-24
        pools.append({"name": f"pool-{pool + 1}", "pool": pool,
                      "amplitude": math.sqrt(total_power), "power": total_power,
                      "local_phase_rate": float(power[indices] @ angular_rate[indices] / total_power) if total_power > 1e-24 else None,
                      "local_phase": float(np.angle(resultant)) if defined else None,
                      "phase_defined": bool(defined),
                      "sampling": {"ports_per_strand": profile.ports_per_pool, "field_time_step": profile.time_step}})
    edges = profile.edges
    if profile.projected_transport is not None:
        transport = profile.projected_transport
        edges = tuple((s, d, float(transport[d, s]), "projected")
                      for s, d in zip(*np.nonzero(np.tril(transport, -1))))
    qg, pg = gradient[:2 * n], gradient[2 * n:]
    edge_powers = [{"source": s, "destination": d, "weight": w, "kind": kind,
                    "power": float(rate * w * (qg[d] * qg[s] + pg[d] * pg[s]))}
                   for s, d, w, kind in edges]
    circuit = [row["power"] for row in edge_powers if row["kind"] == "circuit"]
    yang = [row["power"] for row in edge_powers if row["kind"] == "circuit" and row["source"] < n and row["destination"] < n]
    yin = [row["power"] for row in edge_powers if row["kind"] == "circuit" and row["source"] >= n and row["destination"] >= n]
    rail_y = float(np.mean(yang)) if yang else 0.0
    rail_i = -float(np.mean(yin)) if yin else 0.0
    semantic = operator.semantic(workspace.common_coordinates())
    return {"energy": energy, "semantic_residual_norm": float(np.linalg.norm(semantic)),
            "semantic_residual": semantic.tolist(), "state_sha256": workspace.state_sha256,
            "field_ticks": workspace.field_ticks, "evidence_tick": workspace.evidence_tick,
            "heartbeat_phase": workspace.heartbeat_phase, "heartbeat_cycles": workspace.heartbeat_cycles,
            "breath_phase": workspace.breath_phase, "breath_cycles": workspace.breath_cycles,
            "activity": workspace.activity, "mobility": rate,
            "rail_power_yang": rail_y, "rail_power_yin": rail_i,
            "common_rail_power": rail_y + rail_i, "counterflow_rail_power": (rail_y - rail_i) / 2,
            "cycle_power": float(np.mean(circuit)) if circuit else 0.0,
            "cycle_power_absolute": float(np.mean(np.abs(circuit))) if circuit else 0.0,
            "pool_sample": pools, "local_phase": [row["local_phase"] for row in pools],
            "local_phase_rates": [row["local_phase_rate"] for row in pools],
            "strands": {"yang": {"samples": rows[:n]}, "yin": {"samples": rows[n:]}},
            "edge_powers": edge_powers, "pool_count": profile.pools,
            "ports_per_pool": profile.ports_per_pool, "port_count": n,
            "oriented_edge_count": len(edges), "edge_strength_l1": sum(abs(row[2]) for row in edges),
            "topology": profile.topology, "bindings": _jsonable(workspace.bindings),
            "ledger": dict(workspace.ledger), "layout": profile.layout_identity, "arithmetic": profile.arithmetic,
            "sampling_limits": {"field_time_step": profile.time_step,
                                "field_step_nyquist_angular": math.pi / profile.time_step,
                                "minimum_squared_amplitude": 1e-24},
            "measurement_assumptions": [
                "phase is arg(q + i sqrt(inv_mass) p); matrix metrics use the Cholesky transpose",
                "phase_rate is the instantaneous signed quadrature derivative, not an eigenfrequency",
                "pool rate is power-weighted; pool phase is a power-weighted circular mean",
                "edge power is generalized energy transfer, not a physical number current",
                "rail powers share increasing-longitudinal sign; cycle power follows the oriented circuit",
                "no spectral fit or eigendecomposition is performed by this snapshot"]}


def inspect_workspace(workspace: ResonantWorkspace, *, problem: ResonantProblem | None = None) -> Mapping[str, Any]:
    if not isinstance(workspace, ResonantWorkspace):
        raise TypeError("workspace must be ResonantWorkspace")
    return _diagnostics(workspace, problem)


def measure_body_response(profile: ResonantProfile) -> Mapping[str, Any]:
    """Bounded, read-only calibration of the unforced body linearized at rest.

    This uses the production operator, with unit mobility and no learned task
    constraints. It is an inspection operation, never part of an advance.
    """
    dimension = 4 * profile.port_count
    profile_sha256 = hashlib.sha256(json.dumps(
        profile.as_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()
    metadata = {
        "profile_sha256": profile_sha256,
        "scope": "unforced body linearization at zero; unit mobility; no learned task constraints",
        "angular_field_time_units": True,
        "maximum_dense_dimension": 256,
        "dimension": dimension,
    }
    if dimension > 256:
        return {**metadata, "available": False, "reason": "inspection dimension limit", "peaks": []}
    operator = _WaveOperator(initial_workspace(replace(profile, beta=0.0)), None)
    identity = np.eye(dimension)
    generator = np.column_stack([
        operator.flow(operator.energy_gradient(identity[:, index])[1], False)
        for index in range(dimension)
    ])
    eigenvalues = np.linalg.eigvals(generator)
    modes: list[dict[str, Any]] = []
    for frequency in sorted(float(value.imag) for value in eigenvalues if value.imag > 1e-9):
        if modes and abs(frequency - modes[-1]["frequency_max"]) <= 1e-7:
            modes[-1]["frequency_max"] = frequency
            modes[-1]["multiplicity"] += 1
        else:
            modes.append({"frequency_min": frequency, "frequency_max": frequency, "multiplicity": 1})
    n = profile.port_count
    inputs = np.zeros((dimension, 7))
    outputs = np.zeros((7, dimension))
    for pool in range(7):
        port = pool * profile.ports_per_pool
        inputs[2 * n + port, pool] = inputs[3 * n + port, pool] = 1 / SQRT2
        outputs[pool, port] = outputs[pool, n + port] = 1 / SQRT2
    frequencies = np.linspace(0.15, 1.25, 241)
    transfer = np.empty((len(frequencies), 7), dtype=np.complex128)
    localization = np.empty((len(frequencies), 7))
    for index, frequency in enumerate(frequencies):
        response = np.linalg.solve(1j * frequency * identity - generator, inputs)
        transfer[index] = np.diag(outputs @ response)
        powers = (np.abs(response.reshape(4, n, 7)) ** 2).sum(axis=0)
        pool_powers = powers.reshape(7, profile.ports_per_pool, 7).sum(axis=1)
        localization[index] = np.diag(pool_powers) / pool_powers.sum(axis=0)
    amplitudes = np.abs(transfer)
    peaks = []
    for pool in range(7):
        peak = int(np.argmax(amplitudes[:, pool]))
        threshold = amplitudes[peak, pool] / SQRT2
        left = right = peak
        while left > 0 and amplitudes[left - 1, pool] >= threshold:
            left -= 1
        while right + 1 < len(frequencies) and amplitudes[right + 1, pool] >= threshold:
            right += 1
        peaks.append({
            "pool": pool, "frequency": float(frequencies[peak]),
            "amplitude": float(amplitudes[peak, pool]),
            "half_power_bandwidth": float(frequencies[right] - frequencies[left]),
            "phase_lag_radians": float(-np.angle(transfer[peak, pool])),
            "localization_fraction": float(localization[peak, pool]),
            "band_touches_scan_boundary": left == 0 or right == len(frequencies) - 1,
        })
    return {
        **metadata, "available": True, "peaks": peaks, "temporal_mode_groups": modes,
        "maximum_mode_growth_rate": float(eigenvalues.real.max()),
        "frequency_interval": [float(frequencies[0]), float(frequencies[-1])],
        "frequency_grid_spacing": float(frequencies[1] - frequencies[0]),
        "ports": "first paired port per pool; common momentum input and common position output",
        "sampling_limits": "grid-resolved transfer peaks, not a claim about the evolving constrained task operator",
    }


def _layout_successor(workspace: ResonantWorkspace, profile: ResonantProfile, vector: np.ndarray,
                      bindings: Mapping[str, Any], transition: Mapping[str, Any]) -> ResonantWorkspace:
    empty = ResonantWorkspace(profile=profile)
    page = _page_from_state(empty, vector, heartbeat_phase=workspace.heartbeat_phase,
                            breath_phase=workspace.breath_phase, activity=workspace.activity)
    result = workspace._copy(profile=profile, field_page=page, bindings=bindings, layout_transition=transition)
    old_energy = _WaveOperator(workspace, None).energy_gradient(_state_vector(workspace))[0]
    new_energy = _WaveOperator(result, None).energy_gradient(vector)[0]
    ledger = dict(workspace.ledger)
    ledger["parameter_work"] = ledger.get("parameter_work", 0.0) + new_energy - old_energy
    if "stored_energy" in ledger:
        ledger["stored_energy"] += new_energy - old_energy
    return result._copy(ledger=ledger)


def expand_resolution(workspace: ResonantWorkspace, *, ports_per_pool: int | None = None,
                      factor: int = 2) -> tuple[ResonantWorkspace, dict[str, Any]]:
    target = workspace.profile.ports_per_pool * factor if ports_per_pool is None else ports_per_pool
    if isinstance(target, bool) or not isinstance(target, int) or target <= workspace.profile.ports_per_pool:
        raise ResonantNumericalError("expansion requires a larger integer resolution")
    old = workspace.profile
    profile = replace(old, ports_per_pool=target, projected_transport=None,
                      projected_inv_mass=None, projected_quartic_weights=None)
    oldn, newn = old.port_count, profile.port_count
    slots = np.asarray([pool * target + local for pool in range(7) for local in range(old.ports_per_pool)])
    vector = np.zeros((4, newn))
    vector[:, slots] = _state_vector(workspace).reshape(4, oldn)
    if old.projected_transport is not None or old.projected_inv_mass is not None:
        if (2 * newn) ** 2 * 8 * 4 > 128 * 1024 * 1024:
            raise ResonantNumericalError("expanded projected matrices exceed 128 MiB working allowance")
        both = np.concatenate((slots, slots + newn))
        transport = profile.transport_matrix
        transport[np.ix_(both, both)] = old.transport_matrix
        inverse_mass = _inverse_mass(profile)
        inverse_mass[np.ix_(both, both)] = _inverse_mass(old)
        profile = replace(profile, projected_transport=transport, projected_inv_mass=inverse_mass)
    if old.projected_quartic_weights is not None:
        weights = np.ones(newn)
        weights[slots] = old.projected_quartic_weights
        profile = replace(profile, projected_quartic_weights=weights)
    bindings = {name: {**dict(value), "port": int(slots[value["port"]])} for name, value in workspace.bindings.items()}
    transition = {"from": old.layout_identity, "to": profile.layout_identity,
                  "kind": "zero-mode-expansion", "old_port_embedding": slots.tolist()}
    result = _layout_successor(workspace, profile, vector.reshape(-1), bindings, transition)
    return result, {"kind": "zero-mode-expansion", "from_ports_per_pool": old.ports_per_pool,
                    "to_ports_per_pool": target, "state_error_norm": 0.0,
                    "new_coordinates_zero": True, "old_port_embedding": slots.tolist()}


def _reduction_certificate(original: ResonantWorkspace, reduced: ResonantWorkspace, embedding: np.ndarray,
                           reconstruction_error: float) -> dict[str, Any]:
    """Passivity gives a uniform frozen-response bound; Gronwall bounds nonlinear free evolution."""
    operators = [_WaveOperator(item, None) for item in (original, reduced)]
    matrices, hessians, generators = [], [], []
    for operator in operators:
        size = 4 * operator.n
        identity = np.eye(size)
        zero = np.zeros(size)
        hessian = operator.derivative(zero, zero, identity, True)
        matrix = operator.flow(identity, False)
        matrices.append(matrix)
        hessians.append(hessian)
        generators.append(matrix @ hessian)
    eigensystems = [np.linalg.eigh(hessian) for hessian in hessians]
    low = [float(values.min()) for values, _ in eigensystems]
    high = [float(values.max()) for values, _ in eigensystems]
    if min(low) <= 0 or original.profile.damping <= 0:
        raise ResonantNumericalError("a strictly positive energy metric and damping are required to certify reduction")
    roots = [(vectors * np.sqrt(values)) @ vectors.T for values, vectors in eigensystems]
    inverse_roots = [(vectors / np.sqrt(values)) @ vectors.T for values, vectors in eigensystems]
    residual = generators[0] @ embedding - embedding @ generators[1]
    normalized_residual = roots[0] @ residual @ inverse_roots[1]
    response_bound = float(np.linalg.norm(normalized_residual, 2)) / (
        original.profile.damping ** 2 * low[0] * low[1])
    energies = [operator.energy_gradient(_state_vector(item))[0] for operator, item in zip(operators, (original, reduced))]
    radius = math.sqrt(2 * max(0.0, *energies) / min(low))
    beta = max(float(np.max(operator.beta, initial=0)) for operator in operators)
    lipschitz = float(np.linalg.norm(matrices[0], 2)) * (high[0] + 3 * beta * radius ** 2)
    nonlinear_residual = float(np.linalg.norm(matrices[0] - embedding @ matrices[1] @ embedding.T, 2)) * beta * radius ** 3
    forcing_bound = float(np.linalg.norm(residual, 2)) * radius + nonlinear_residual
    # Breath is a common positive scalar clock: at most 2.5 per field-time unit.
    horizon = 16 * original.profile.time_step
    exponent = lipschitz * 2.5 * horizon
    if exponent > 700:
        raise ResonantNumericalError("nonlinear reduction error allowance cannot be certified")
    growth = math.exp(exponent)
    trajectory_bound = reconstruction_error * growth + forcing_bound * math.expm1(exponent) / lipschitz if lipschitz else reconstruction_error
    return {"frequency_response_error_bound": response_bound,
            "frequency_domain": "all real angular frequencies, frozen body linearization at zero",
            "response_norm": "induced 2-norm in energy-normalized input and reconstructed output coordinates",
            "nonlinear_trajectory_error_bound": trajectory_bound,
            "field_time_horizon": horizon, "trajectory_conditions": "same breath clock, source off, unchanged body profile",
            "minimum_energy_eigenvalues": low, "passive": True}


def reduce_resolution(workspace: ResonantWorkspace, *, ports_per_pool: int,
                      error_allowance: float = 1.0) -> tuple[ResonantWorkspace, dict[str, Any]]:
    old, target = workspace.profile, ports_per_pool
    if isinstance(target, bool) or not isinstance(target, int) or not 4 <= target < old.ports_per_pool:
        raise ResonantNumericalError("reduction requires an integer resolution >=4 below the current one")
    if not math.isfinite(error_allowance) or error_allowance < 0:
        raise ResonantNumericalError("error_allowance must be finite and nonnegative")
    if old.port_count > 128:
        raise ResonantNumericalError("bounded dense reduction certificate supports at most 128 source ports")
    profile = replace(old, ports_per_pool=target, projected_transport=None,
                      projected_inv_mass=None, projected_quartic_weights=None)
    oldn, newn = old.port_count, profile.port_count
    basis = np.zeros((oldn, newn))
    binding_slots = {}
    for pool in range(7):
        occupied = sorted({value["port"] % old.ports_per_pool for value in workspace.bindings.values() if value["pool"] == pool})
        if len(occupied) > target:
            raise ResonantNumericalError("reduction cannot preserve all occupied semantic ports")
        groups = [np.asarray([local]) for local in occupied]
        remaining = np.asarray([local for local in range(old.ports_per_pool) if local not in occupied])
        slots = target - len(groups)
        if slots:
            groups.extend(np.array_split(remaining, slots))
        for local, group in enumerate(groups):
            basis[pool * old.ports_per_pool + group, pool * target + local] = 1 / math.sqrt(len(group))
        for name, value in workspace.bindings.items():
            if value["pool"] == pool:
                binding_slots[name] = pool * target + occupied.index(value["port"] % old.ports_per_pool)
    both = np.kron(np.eye(2), basis)
    embedding = np.kron(np.eye(4), basis)
    vector = embedding.T @ _state_vector(workspace)
    reconstruction_error = float(np.linalg.norm(_state_vector(workspace) - embedding @ vector))
    old_weights = np.ones(oldn) if old.projected_quartic_weights is None else old.projected_quartic_weights
    profile = replace(profile, projected_transport=both.T @ old.transport_matrix @ both,
                      projected_inv_mass=both.T @ _inverse_mass(old) @ both,
                      projected_quartic_weights=old_weights @ basis ** 4)
    bindings = {name: {**dict(value), "port": binding_slots[name]} for name, value in workspace.bindings.items()}
    transition = {"from": old.layout_identity, "to": profile.layout_identity,
                  "kind": "orthonormal-passive-reduction", "basis": basis.tolist(),
                  "source_state_sha256": workspace.state_sha256}
    result = _layout_successor(workspace, profile, vector, bindings, transition)
    certificate = _reduction_certificate(workspace, result, embedding, reconstruction_error)
    bound = max(reconstruction_error, certificate["frequency_response_error_bound"],
                certificate["nonlinear_trajectory_error_bound"])
    if bound > error_allowance:
        raise ResonantNumericalError(f"dynamic reduction error bound {bound:.6g} exceeds allowance {error_allowance:.6g}")
    before_energy = _WaveOperator(workspace, None).energy_gradient(_state_vector(workspace))[0]
    after_energy = _WaveOperator(result, None).energy_gradient(vector)[0]
    receipt = {"kind": "orthonormal-passive-reduction", "from_ports_per_pool": old.ports_per_pool,
               "to_ports_per_pool": target, "reconstruction_error_bound": reconstruction_error,
               "energy_change": after_energy - before_energy, "error_allowance": error_allowance,
               "occupied_bindings_preserved": True, **certificate}
    result = result._copy(layout_transition={**transition, "certificate": receipt})
    return result, receipt


def advance_workspace_gpu(workspace: ResonantWorkspace, *, problem: ResonantProblem | None = None,
                          ticks: int = 1, demand: float = 0.0, source_enabled: bool = True,
                          quiet: bool = False, device: str = "cuda") -> tuple[ResonantWorkspace, dict[str, Any]]:
    if not isinstance(workspace, ResonantWorkspace):
        raise TypeError("workspace must be ResonantWorkspace")
    workspace.profile.gpu_profile(device)
    return _advance(workspace, problem=problem, ticks=ticks, demand=demand, source_enabled=source_enabled,
                    quiet=quiet, max_iterations=32, tolerance=None, device=device)


def gpu_profile(profile: ResonantProfile | None = None, *, device: str = "cuda") -> Mapping[str, Any]:
    return (profile or ResonantProfile()).gpu_profile(device)


__all__ = ["SCHEMA", "LAYOUT", "ResonantNumericalError", "ResonantDeviceUnavailableError", "ResonantProfile", "ResonantProblem", "ResonantWorkspace", "initial_workspace", "bind_workspace", "apply_pool_impulse", "score_pool_probes", "advance_workspace", "inspect_workspace", "expand_resolution", "reduce_resolution", "advance_workspace_gpu", "gpu_profile", "pulse_primitive"]
