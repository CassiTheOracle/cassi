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
from contextlib import contextmanager, nullcontext
from types import MappingProxyType
from typing import Any, Iterator, Mapping, Sequence

import numpy as np
import torch
import cassi_field_regions as field_regions
from scipy.sparse.linalg import LinearOperator, gmres


SCHEMA = "cassifi.resonant-workspace.v1"
LAYOUT = "mode-major-9M-1:f64le"
PARENT_SUMMARY_PATH = "L"
PARENT_SUMMARY_LAYOUT = "parent-summary-L-level-zero-v1:f64le"
PARENT_SUMMARY_WIDTH = 4
PARENT_SUMMARY_METADATA_KEY = "parent_summary_register"
PARENT_SUMMARY_REGISTER_SCHEMA = "cassifi.resonant-parent-summary-register.v1"
PARENT_REGISTER_PATHS = ("L", "LL")
PARENT_REGISTER_LAYOUT = "parent-register-map-v1:f64le"
PARENT_REGISTER_SCHEMA = "cassifi.resonant-parent-register-map.v1"
PARENT_REGISTER_SLOT_WIDTH = PARENT_SUMMARY_WIDTH + 2
PARENT_REGISTER_METADATA_KEY = PARENT_SUMMARY_METADATA_KEY
FROZEN_PARENT_METADATA_KEY = "frozen_parent"
FROZEN_PARENT_SCHEMA = "cassifi.frozen-parent.v1"
FROZEN_PARENT_COUPLING_GAIN = 1.0
LIVE_CHILD_DETAIL_TO_PARENT_SCHEMA = "cassifi.live-child-detail-to-parent.v1"
LIVE_CHILD_DETAIL_MODE_INDEX = 1
LIVE_CHILD_DETAIL_CHANNEL_SLICE = (2, 4)
SQRT2 = math.sqrt(2.0)
HELICAL_PACKET_SCHEMA = "cassifi.dual-helical-packet.v1"
HELICAL_PACKET_BASIS = "balanced-contiguous-haar-phase-space-v1"
HELICAL_PACKET_CHANNELS = (
    "position-common",
    "position-counterflow",
    "momentum-common",
    "momentum-counterflow",
)
_FIELD_EVENT_KINDS = frozenset({
    "formation",
    "withdrawal",
    "goal-observation",
    "forbidden-observation",
    "context-observation",
    "mismatch-observation",
    "reasoning-work",
})


class ResonantNumericalError(ValueError):
    """Invalid numerical state or unsupported operation."""


class ResonantDeviceUnavailableError(RuntimeError):
    """Requested GPU arithmetic is unavailable."""


def _resource_manager(resources: Any) -> Any:
    """Resolve a caller-owned residency policy without importing it at module load."""
    if resources is None:
        return None
    if hasattr(resources, "reserve") and hasattr(resources, "available"):
        return resources
    try:
        from cassi_field_residency import ResidencyManager
    except ImportError as exc:
        raise ResonantNumericalError(
            "GPU resource limits require cassi_field_residency.ResidencyManager"
        ) from exc
    if isinstance(resources, Mapping):
        return ResidencyManager(resources)
    if hasattr(resources, "as_dict"):
        return ResidencyManager(resources)
    raise TypeError("resources must be a ResidencyManager, ResourceLimits, or mapping")


@contextmanager
def _gpu_residency(resources: Any, *, state_bytes: int, scratch_bytes: int) -> Iterator[Any]:
    """Charge device state, solver scratch, and transfers before allocating tensors."""
    manager = _resource_manager(resources)
    if manager is None:
        yield None
        return
    # Transfer is deliberately charged on both sides of the staging boundary.
    transfer_bytes = max(1, state_bytes)
    with manager.reserve("vram", max(1, state_bytes), kind="resident"):
        with manager.reserve("vram", max(1, scratch_bytes), kind="scratch"):
            with manager.reserve("vram", transfer_bytes, kind="transfer"):
                with manager.reserve("ram", transfer_bytes, kind="transfer"):
                    yield manager


def _torch_gmres(
    matvec: Any,
    rhs: torch.Tensor,
    *,
    tolerance: float,
    restart: int = 8,
    max_restarts: int = 8,
) -> tuple[torch.Tensor, float, int]:
    """Restarted matrix-free GMRES with O(restart*state) device storage.

    The old GPU path formed an explicit identity and then a dense Jacobian.  This
    implementation keeps only Krylov vectors and a tiny Hessenberg matrix; every
    Jacobian action remains the admitted nonlinear flow, including projections and
    rail reductions.
    """
    if rhs.ndim != 1:
        raise ResonantNumericalError("GPU GMRES expects a vector right-hand side")
    norm_rhs = float(torch.linalg.vector_norm(rhs).item())
    target = max(float(tolerance) * 0.05, 64.0 * torch.finfo(rhs.dtype).eps * max(1.0, norm_rhs))
    if norm_rhs <= target:
        return torch.zeros_like(rhs), norm_rhs, 0
    dimension = int(rhs.numel())
    restart = max(1, min(int(restart), dimension))
    solution = torch.zeros_like(rhs)
    applications = 0
    residual_norm = norm_rhs
    for _ in range(max(1, int(max_restarts))):
        residual = rhs - matvec(solution)
        applications += 1
        beta = torch.linalg.vector_norm(residual)
        residual_norm = float(beta.item())
        if residual_norm <= target:
            return solution, residual_norm, applications
        basis = [residual / beta]
        hessenberg = torch.zeros(
            (restart + 1, restart), dtype=rhs.dtype, device=rhs.device
        )
        projected_rhs = torch.zeros((restart + 1,), dtype=rhs.dtype, device=rhs.device)
        projected_rhs[0] = beta
        best = solution
        best_norm = residual_norm
        for column in range(restart):
            candidate = matvec(basis[column])
            applications += 1
            for row in range(column + 1):
                coefficient = torch.dot(basis[row], candidate)
                hessenberg[row, column] = coefficient
                candidate = candidate - coefficient * basis[row]
            next_norm = torch.linalg.vector_norm(candidate)
            hessenberg[column + 1, column] = next_norm
            if float(next_norm.item()) > 0.0 and column + 1 < restart:
                basis.append(candidate / next_norm)
            solve_rows = column + 2
            try:
                coeffs = torch.linalg.lstsq(
                    hessenberg[:solve_rows, : column + 1],
                    projected_rhs[:solve_rows],
                ).solution
            except RuntimeError as exc:
                raise ResonantNumericalError("GPU matrix-free least-squares solve failed") from exc
            trial = solution + torch.stack(basis[: column + 1], dim=1) @ coeffs
            trial_residual = rhs - matvec(trial)
            applications += 1
            trial_norm = float(torch.linalg.vector_norm(trial_residual).item())
            if trial_norm < best_norm:
                best, best_norm = trial, trial_norm
            if trial_norm <= target:
                return trial, trial_norm, applications
            if float(next_norm.item()) <= target:
                break
        solution = best
        residual_norm = best_norm
        if residual_norm <= target:
            return solution, residual_norm, applications
    return solution, residual_norm, applications


def _torch_gmres_batch(
    matvec: Any,
    rhs: torch.Tensor,
    *,
    tolerance: float,
    restart: int = 8,
    max_restarts: int = 8,
) -> tuple[torch.Tensor, torch.Tensor, int]:
    """Restarted matrix-free GMRES for independent column right-hand sides."""
    if rhs.ndim != 2:
        raise ResonantNumericalError("batched GPU GMRES expects a matrix of column right-hand sides")
    dimension, count = rhs.shape
    norm_rhs = torch.linalg.vector_norm(rhs, dim=0)
    target = torch.maximum(
        torch.full_like(norm_rhs, float(tolerance) * 0.05),
        64.0 * torch.finfo(rhs.dtype).eps * torch.maximum(torch.ones_like(norm_rhs), norm_rhs),
    )
    solution = torch.zeros_like(rhs)
    residual_norm = norm_rhs.clone()
    applications = 0
    restart = max(1, min(int(restart), dimension))
    for _ in range(max(1, int(max_restarts))):
        residual = rhs - matvec(solution)
        applications += 1
        beta = torch.linalg.vector_norm(residual, dim=0)
        residual_norm = beta
        basis = [residual / torch.clamp(beta, min=torch.finfo(rhs.dtype).tiny)[None, :]]
        basis[0] = torch.where((beta > target)[None, :], basis[0], torch.zeros_like(basis[0]))
        hessenberg = torch.zeros((restart + 1, restart, count), dtype=rhs.dtype, device=rhs.device)
        projected_rhs = torch.zeros((restart + 1, count), dtype=rhs.dtype, device=rhs.device)
        projected_rhs[0] = beta
        best = solution.clone()
        best_norm = residual_norm.clone()
        for column in range(restart):
            candidate = matvec(basis[column])
            applications += 1
            for row in range(column + 1):
                coefficient = (basis[row] * candidate).sum(dim=0)
                hessenberg[row, column] = coefficient
                candidate = candidate - basis[row] * coefficient[None, :]
            next_norm = torch.linalg.vector_norm(candidate, dim=0)
            hessenberg[column + 1, column] = next_norm
            if column + 1 < restart:
                basis.append(candidate / torch.clamp(next_norm, min=torch.finfo(rhs.dtype).tiny)[None, :])
            rows = column + 2
            matrices = hessenberg[:rows, :column + 1].permute(2, 0, 1)
            vectors = projected_rhs[:rows].T.unsqueeze(-1)
            gram = matrices.transpose(1, 2) @ matrices
            scale = matrices.abs().amax(dim=(1, 2)).clamp_min(1.0)
            regularizer = 64.0 * torch.finfo(rhs.dtype).eps * scale.square()
            gram = gram + regularizer[:, None, None] * torch.eye(
                column + 1, dtype=rhs.dtype, device=rhs.device,
            )[None, :, :]
            coefficients = torch.linalg.solve(
                gram, matrices.transpose(1, 2) @ vectors,
            ).squeeze(-1)
            vectors_basis = torch.stack(basis[:column + 1], dim=1).permute(2, 0, 1)
            trial = solution + torch.bmm(vectors_basis, coefficients.unsqueeze(-1)).squeeze(-1).T
            trial_residual = rhs - matvec(trial)
            applications += 1
            trial_norm = torch.linalg.vector_norm(trial_residual, dim=0)
            improve = trial_norm < best_norm
            best = torch.where(improve[None, :], trial, best)
            best_norm = torch.minimum(best_norm, trial_norm)
            solved = trial_norm <= target
            best = torch.where(solved[None, :], trial, best)
            best_norm = torch.where(solved, trial_norm, best_norm)
            if bool(solved.all().item()):
                return trial, trial_norm, applications
            active = (next_norm > target) & (beta > target)
            if not bool(active.any().item()):
                break
        solution = best
        residual_norm = best_norm
        if bool((residual_norm <= target).all().item()):
            return solution, residual_norm, applications
    return solution, residual_norm, applications


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
        self.ledger = MappingProxyType({"positive_heartbeat_work": 0.0, "extracted_heartbeat_work": 0.0, "dissipated_work": 0.0, "interface_transfer_work": 0.0, "residual_work": 0.0, "parameter_work": 0.0, "balance_defect": 0.0, **{str(k): float(v) for k, v in (ledger or {}).items()}})
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
        flat = self._field.reshape(-1)
        ll_positions = set(_parent_register_positions(n, "LL"))
        for index, value in enumerate(flat[:9*n]):
            if index % 9 >= 4 and index not in ll_positions and value != 0.0:
                raise ResonantNumericalError("unused per-port lanes must be canonical zero")
        registers, _relations = _parent_register_transition(
            self._field, n, self.layout_transition
        )
        _frozen_parent_transition(self._field, n, self.layout_transition)
        l_values = _parent_register_values(self._field, n, "L")
        if l_values is None and np.any(flat[9*n+3:9*m] != 0):
            raise ResonantNumericalError("unused clock lanes must be canonical zero")
        if l_values is not None and "L" not in registers:
            raise ResonantNumericalError("parent summary provenance is missing")
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
    n = workspace.profile.port_count
    page = workspace._field.copy().reshape(-1)
    register_values = {
        path: _parent_register_values(page, n, path)
        for path in PARENT_REGISTER_PATHS
    }
    for lane, values in enumerate(np.split(z, 4)):
        page[lane:9*n:9] = values
    m = workspace.profile.mode_count
    page[9*n] = workspace.heartbeat_phase if heartbeat_phase is None else heartbeat_phase
    page[9*n + 1] = workspace.breath_phase if breath_phase is None else breath_phase
    page[9*n + 2] = workspace.activity if activity is None else activity
    page[9*n + 3:9*m] = 0.0
    for path, values in register_values.items():
        if values is not None:
            page = _parent_register_page_write(page, n, path, values).reshape(-1)
    return page.reshape(workspace.profile.page_shape)


import hashlib
import json
from functools import partial

_json_dumps = partial(
    json.dumps,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False,
    allow_nan=False,
)

def _canonical_sha256(value: Any) -> str:
    encoded = _json_dumps(value).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

def _validate_parent_register_path(path: Any) -> str:
    if not isinstance(path, str) or path not in PARENT_REGISTER_PATHS:
        raise ResonantNumericalError(
            f"parent register path must be one of {PARENT_REGISTER_PATHS!r}"
        )
    return path


def _parent_register_offsets(port_count: int, path: str) -> tuple[int, int, int]:
    _validate_parent_register_path(path)
    if path == PARENT_SUMMARY_PATH:
        start = 9 * int(port_count) + 3
        return start, start + PARENT_SUMMARY_WIDTH, start + PARENT_SUMMARY_WIDTH + 1
    # The LL bank occupies otherwise-unused per-mode lanes.  Its positions are
    # fixed in the canonical page and are independent of resolution.
    start = 4
    return start, start + PARENT_SUMMARY_WIDTH, 13


def _parent_register_positions(port_count: int, path: str) -> tuple[int, ...]:
    start, marker_offset, spare_offset = _parent_register_offsets(port_count, path)
    if path == PARENT_SUMMARY_PATH:
        return tuple(range(start, marker_offset)) + (marker_offset, spare_offset)
    return (4, 5, 6, 7, 8, 13)


def _parent_register_values(page: Any, port_count: int, path: str) -> np.ndarray | None:
    positions = _parent_register_positions(port_count, path)
    flat = np.asarray(page, dtype=np.float64).reshape(-1)
    values = flat[list(positions[:PARENT_SUMMARY_WIDTH])]
    marker = float(flat[positions[PARENT_SUMMARY_WIDTH]])
    spare = float(flat[positions[PARENT_SUMMARY_WIDTH + 1]])
    if not np.all(np.isfinite(values)) or not math.isfinite(marker) or not math.isfinite(spare):
        raise ResonantNumericalError(f"parent register {path} is non-finite")
    if spare != 0.0:
        raise ResonantNumericalError(f"parent register {path} spare lane must be zero")
    if marker == 0.0:
        if np.any(values != 0.0):
            raise ResonantNumericalError(f"absent parent register {path} has nonzero values")
        return None
    if marker != 1.0:
        raise ResonantNumericalError(f"parent register {path} marker is invalid")
    return values.copy()


def _parent_summary_offsets(port_count: int) -> tuple[int, int, int]:
    return _parent_register_offsets(port_count, PARENT_SUMMARY_PATH)


def _parent_summary_values(page: Any, port_count: int) -> np.ndarray | None:
    return _parent_register_values(page, port_count, PARENT_SUMMARY_PATH)


def _parent_register_digest(metadata: Mapping[str, Any], values: Sequence[float]) -> str:
    return _canonical_sha256({
        "layout": metadata["layout"],
        "path": metadata["path"],
        "basis": metadata["basis"],
        "basis_sha256": metadata["basis_sha256"],
        "support": metadata["support"],
        "source_state_sha256": metadata["source_state_sha256"],
        "source_packet_sha256": metadata["source_packet_sha256"],
        "values": [float(value) for value in values],
    })


def _parent_summary_digest(metadata: Mapping[str, Any], values: Sequence[float]) -> str:
    return _parent_register_digest(metadata, values)


def _parent_register_metadata(
    metadata: Mapping[str, Any], *, port_count: int, values: Sequence[float],
) -> None:
    required = {
        "schema", "layout", "path", "basis", "basis_sha256", "support",
        "source_state_sha256", "source_packet_sha256", "summary_sha256",
    }
    if set(metadata) != required:
        raise ResonantNumericalError("parent register provenance is noncanonical")
    path = _validate_parent_register_path(metadata["path"])
    if metadata["schema"] != PARENT_REGISTER_SCHEMA or metadata["layout"] != PARENT_REGISTER_LAYOUT:
        raise ResonantNumericalError("parent register schema or layout is invalid")
    if metadata["basis"] != HELICAL_PACKET_BASIS:
        raise ResonantNumericalError("parent register basis is invalid")
    start, stop = _packet_support(port_count, path)
    if metadata["support"] != {"start": start, "stop": stop}:
        raise ResonantNumericalError("parent register support is invalid")
    for name in ("basis_sha256", "source_state_sha256", "source_packet_sha256", "summary_sha256"):
        value = metadata[name]
        if not isinstance(value, str) or len(value) != 64 or any(
            char not in "0123456789abcdef" for char in value
        ):
            raise ResonantNumericalError(f"parent register {name} is invalid")
    if metadata["summary_sha256"] != _parent_register_digest(metadata, values):
        raise ResonantNumericalError("parent register digest mismatch")


def _parent_summary_metadata(
    metadata: Mapping[str, Any], *, port_count: int, values: Sequence[float],
) -> None:
    if set(metadata) != {
        "schema", "layout", "path", "basis", "basis_sha256", "support",
        "source_state_sha256", "source_packet_sha256", "summary_sha256",
    }:
        raise ResonantNumericalError("parent summary provenance is noncanonical")
    if metadata["schema"] != PARENT_SUMMARY_REGISTER_SCHEMA:
        raise ResonantNumericalError("parent summary register schema is invalid")
    if metadata["layout"] != PARENT_SUMMARY_LAYOUT or metadata["path"] != PARENT_SUMMARY_PATH:
        raise ResonantNumericalError("parent summary register layout is invalid")
    if metadata["basis"] != HELICAL_PACKET_BASIS:
        raise ResonantNumericalError("parent summary basis is invalid")
    if metadata["support"] != {"start": 0, "stop": port_count // 2}:
        raise ResonantNumericalError("parent summary support is invalid")
    for name in ("basis_sha256", "source_state_sha256", "source_packet_sha256", "summary_sha256"):
        value = metadata[name]
        if not isinstance(value, str) or len(value) != 64 or any(
            char not in "0123456789abcdef" for char in value
        ):
            raise ResonantNumericalError(f"parent summary {name} is invalid")
    if metadata["summary_sha256"] != _parent_summary_digest(metadata, values):
        raise ResonantNumericalError("parent summary digest mismatch")


def _parent_register_page_write(
    page: Any, port_count: int, path: str, values: Sequence[float],
) -> np.ndarray:
    summary = _as_f64(values, (PARENT_SUMMARY_WIDTH,), f"parent register {path} values")
    if not np.all(np.isfinite(summary)):
        raise ResonantNumericalError(f"parent register {path} values are non-finite")
    result = np.asarray(page, dtype=np.float64).copy().reshape(-1)
    positions = _parent_register_positions(port_count, path)
    result[list(positions[:PARENT_SUMMARY_WIDTH])] = summary
    result[positions[PARENT_SUMMARY_WIDTH]] = 1.0
    result[positions[PARENT_SUMMARY_WIDTH + 1]] = 0.0
    return result.reshape(np.asarray(page).shape)


def _parent_summary_page_write(
    page: Any, port_count: int, values: Sequence[float],
) -> np.ndarray:
    return _parent_register_page_write(page, port_count, PARENT_SUMMARY_PATH, values)
def _parent_register_transition(
    page: Any, port_count: int, transition: Mapping[str, Any],
) -> tuple[dict[str, Mapping[str, Any]], list[Mapping[str, Any]]]:
    values_by_path = {
        path: _parent_register_values(page, port_count, path)
        for path in PARENT_REGISTER_PATHS
    }
    metadata = transition.get(PARENT_REGISTER_METADATA_KEY)
    if metadata is None:
        if any(value is not None for value in values_by_path.values()):
            raise ResonantNumericalError("parent register provenance is missing")
        return {}, []
    # The legacy flat L envelope is retained solely so the frozen direct
    # retention receipt remains byte-for-byte compatible.
    if set(metadata) == {
        "schema", "layout", "path", "basis", "basis_sha256", "support",
        "source_state_sha256", "source_packet_sha256", "summary_sha256",
    }:
        if values_by_path["L"] is None or values_by_path["LL"] is not None:
            raise ResonantNumericalError("legacy parent summary map is inconsistent")
        _parent_summary_metadata(metadata, port_count=port_count, values=values_by_path["L"])
        return {"L": metadata}, []
    if not isinstance(metadata, Mapping) or set(metadata) != {"schema", "layout", "slots", "relations"}:
        raise ResonantNumericalError("parent register map is noncanonical")
    if metadata["schema"] != PARENT_REGISTER_SCHEMA or metadata["layout"] != PARENT_REGISTER_LAYOUT:
        raise ResonantNumericalError("parent register map schema or layout is invalid")
    slots = metadata["slots"]
    if not isinstance(slots, Mapping) or any(path not in PARENT_REGISTER_PATHS for path in slots):
        raise ResonantNumericalError("parent register map paths are invalid")
    if set(slots) != {path for path, value in values_by_path.items() if value is not None}:
        raise ResonantNumericalError("parent register map slots do not match page markers")
    normalized: dict[str, Mapping[str, Any]] = {}
    for path, item in slots.items():
        if not isinstance(item, Mapping):
            raise ResonantNumericalError("parent register map slot is invalid")
        _parent_register_metadata(item, port_count=port_count, values=values_by_path[path])
        normalized[path] = item
    relations = metadata["relations"]
    if not isinstance(relations, list):
        raise ResonantNumericalError("parent register map relations are invalid")
    for relation in relations:
        if not isinstance(relation, Mapping) or set(relation) != {
            "parent_path", "child_path", "source_state_sha256",
            "capture_group_sha256", "parent_support", "child_support",
            "support_contained", "path_prefix", "relation_sha256",
        }:
            raise ResonantNumericalError("parent register relation is noncanonical")
        if relation["parent_path"] != "L" or relation["child_path"] != "LL":
            raise ResonantNumericalError("unsupported parent register relation")
        if relation["parent_path"] not in normalized or relation["child_path"] not in normalized:
            raise ResonantNumericalError("parent register relation references absent slot")
        parent = normalized["L"]; child = normalized["LL"]
        if relation["source_state_sha256"] != parent["source_state_sha256"] or relation["source_state_sha256"] != child["source_state_sha256"]:
            raise ResonantNumericalError("parent register relation source digest mismatch")
        if relation["parent_support"] != parent["support"] or relation["child_support"] != child["support"]:
            raise ResonantNumericalError("parent register relation support mismatch")
        if relation["support_contained"] is not True or relation["path_prefix"] is not True:
            raise ResonantNumericalError("parent register relation containment is unproven")
        expected_digest = _canonical_sha256({
            key: relation[key] for key in (
                "parent_path", "child_path", "source_state_sha256",
                "capture_group_sha256", "parent_support", "child_support",
                "support_contained", "path_prefix",
            )
        })
        if relation["relation_sha256"] != expected_digest:
            raise ResonantNumericalError("parent register relation digest mismatch")
    return normalized, list(relations)
def _frozen_parent_transition(
    page: Any,
    port_count: int,
    transition: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    metadata = transition.get(FROZEN_PARENT_METADATA_KEY)
    if metadata is None:
        return None
    required = {
        "schema", "status", "freeze_id", "parent_path", "child_path",
        "summary_sha256", "source_state_sha256", "source_packet_sha256",
        "basis", "basis_sha256", "support", "relation_sha256",
        "capture_group_sha256",
    }
    if not isinstance(metadata, Mapping) or set(metadata) != required:
        raise ResonantNumericalError("frozen parent descriptor is noncanonical")
    if metadata["schema"] != FROZEN_PARENT_SCHEMA or metadata["status"] != "active":
        raise ResonantNumericalError("frozen parent descriptor is invalid")
    if metadata["parent_path"] != "L" or metadata["child_path"] != "LL":
        raise ResonantNumericalError("frozen parent path is unsupported")
    registers, relations = _parent_register_transition(page, port_count, transition)
    parent = registers.get("L")
    if parent is None:
        raise ResonantNumericalError("frozen parent requires an active L register")
    for name in (
        "summary_sha256", "source_state_sha256", "source_packet_sha256",
        "basis", "basis_sha256", "support",
    ):
        if metadata[name] != parent[name]:
            raise ResonantNumericalError("frozen parent provenance does not match L register")
    relation = next(
        (
            item for item in relations
            if item.get("parent_path") == "L" and item.get("child_path") == "LL"
        ),
        None,
    )
    if relation is None:
        raise ResonantNumericalError("frozen parent requires an active L to LL relation")
    if metadata["relation_sha256"] != relation["relation_sha256"]:
        raise ResonantNumericalError("frozen parent relation digest mismatch")
    if metadata["capture_group_sha256"] != relation["capture_group_sha256"]:
        raise ResonantNumericalError("frozen parent capture group mismatch")
    if not all(
        isinstance(metadata[name], str)
        and len(metadata[name]) == 64
        and all(char in "0123456789abcdef" for char in metadata[name])
        for name in (
            "freeze_id", "summary_sha256", "source_state_sha256",
            "source_packet_sha256", "basis_sha256", "relation_sha256",
            "capture_group_sha256",
        )
    ):
        raise ResonantNumericalError("frozen parent digest is invalid")
    expected_freeze_id = _frozen_parent_id(metadata)
    if metadata["freeze_id"] != expected_freeze_id:
        raise ResonantNumericalError("frozen parent identity digest mismatch")
    return metadata


def _frozen_parent_id(metadata: Mapping[str, Any]) -> str:
    return _canonical_sha256({
        "schema": FROZEN_PARENT_SCHEMA,
        "parent_path": metadata["parent_path"],
        "child_path": metadata["child_path"],
        "summary_sha256": metadata["summary_sha256"],
        "source_state_sha256": metadata["source_state_sha256"],
        "source_packet_sha256": metadata["source_packet_sha256"],
        "relation_sha256": metadata["relation_sha256"],
    })


def freeze_parent(
    workspace: ResonantWorkspace,
    *,
    parent_path: str = "L",
    child_path: str = "LL",
    expected_state_sha256: str | None = None,
    expected_relation_sha256: str | None = None,
) -> tuple[ResonantWorkspace, Mapping[str, Any]]:
    """Lock the canonical L register as a retained parent for later LL writes."""
    if not isinstance(workspace, ResonantWorkspace):
        raise TypeError("workspace must be ResonantWorkspace")
    if parent_path != "L" or child_path != "LL":
        raise ResonantNumericalError("only the declared L to LL relation is supported")
    if expected_state_sha256 is not None and expected_state_sha256 != workspace.state_sha256:
        raise ResonantNumericalError("freeze parent source state digest is stale")
    registers, relations = _parent_register_transition(
        workspace._field, workspace.profile.port_count, workspace.layout_transition
    )
    parent = registers.get("L")
    if parent is None:
        raise ResonantNumericalError("freeze parent requires an active L register")
    relation = next(
        (
            item for item in relations
            if item.get("parent_path") == "L" and item.get("child_path") == "LL"
        ),
        None,
    )
    if relation is None:
        raise ResonantNumericalError("freeze parent requires an active L to LL relation")
    if expected_relation_sha256 is not None and expected_relation_sha256 != relation["relation_sha256"]:
        raise ResonantNumericalError("freeze parent relation digest is stale")
    existing = _frozen_parent_transition(
        workspace._field, workspace.profile.port_count, workspace.layout_transition
    )
    freeze_id = _frozen_parent_id({
        "parent_path": parent_path,
        "child_path": child_path,
        **parent,
        "relation_sha256": relation["relation_sha256"],
    })
    if existing is not None:
        if existing["freeze_id"] != freeze_id:
            raise ResonantNumericalError("a different frozen parent is already active")
        return workspace, {
            "schema": FROZEN_PARENT_SCHEMA,
            "accepted": True,
            "replayed": True,
            "freeze_id": freeze_id,
            "source_state_sha256": parent["source_state_sha256"],
            "summary_sha256": parent["summary_sha256"],
            "relation_sha256": relation["relation_sha256"],
            "state_sha256": workspace.state_sha256,
        }
    descriptor = {
        "schema": FROZEN_PARENT_SCHEMA,
        "status": "active",
        "freeze_id": freeze_id,
        "parent_path": parent_path,
        "child_path": child_path,
        "summary_sha256": parent["summary_sha256"],
        "source_state_sha256": parent["source_state_sha256"],
        "source_packet_sha256": parent["source_packet_sha256"],
        "basis": parent["basis"],
        "basis_sha256": parent["basis_sha256"],
        "support": dict(parent["support"]),
        "relation_sha256": relation["relation_sha256"],
        "capture_group_sha256": relation["capture_group_sha256"],
    }
    transition = dict(workspace.layout_transition)
    transition[FROZEN_PARENT_METADATA_KEY] = descriptor
    successor = workspace._copy(layout_transition=transition)
    return successor, {
        "schema": FROZEN_PARENT_SCHEMA,
        "accepted": True,
        "replayed": False,
        "freeze_id": freeze_id,
        "source_state_sha256": parent["source_state_sha256"],
        "source_packet_sha256": parent["source_packet_sha256"],
        "summary_sha256": parent["summary_sha256"],
        "relation_sha256": relation["relation_sha256"],
        "capture_group_sha256": relation["capture_group_sha256"],
        "summary": _parent_register_values(
            workspace._field, workspace.profile.port_count, "L"
        ).tolist(),
        "successor_state_sha256": successor.state_sha256,
        "successor_is_distinct": successor.state_sha256 != workspace.state_sha256,
    }


def read_frozen_parent(workspace: ResonantWorkspace) -> Mapping[str, Any]:
    """Read the locked canonical L register without live packet analysis."""
    if not isinstance(workspace, ResonantWorkspace):
        raise TypeError("workspace must be ResonantWorkspace")
    metadata = _frozen_parent_transition(
        workspace._field, workspace.profile.port_count, workspace.layout_transition
    )
    if metadata is None:
        return {
            "schema": FROZEN_PARENT_SCHEMA,
            "present": False,
            "status": "absent",
            "freeze_id": None,
            "values": None,
        }
    values = _parent_register_values(workspace._field, workspace.profile.port_count, "L")
    if values is None:
        raise ResonantNumericalError("frozen parent register is absent")
    return {
        **dict(metadata),
        "present": True,
        "values": values.tolist(),
        "state_sha256": workspace.state_sha256,
    }


def apply_frozen_parent_to_child(
    workspace: ResonantWorkspace,
    *,
    freeze_id: str,
    base_flow_signal: Sequence[float],
    work_budget: float,
    child_path: str = "LL",
    component: str = "scale",
    parent_enabled: bool = True,
    expected_parent_summary_sha256: str | None = None,
    expected_parent_source_state_sha256: str | None = None,
    expected_relation_sha256: str | None = None,
    expected_child_source_state_sha256: str | None = None,
    event_kind: str = "reasoning-work",
    consume: bool = False,
) -> tuple[ResonantWorkspace, Mapping[str, Any]]:
    """Apply the locked L momentum channels through the native LL impulse path."""
    if not isinstance(workspace, ResonantWorkspace):
        raise TypeError("workspace must be ResonantWorkspace")
    if child_path != "LL":
        raise ResonantNumericalError("frozen parent child path must be LL")
    if not isinstance(freeze_id, str) or len(freeze_id) != 64:
        raise ResonantNumericalError("frozen parent identity is invalid")
    if expected_child_source_state_sha256 is not None and expected_child_source_state_sha256 != workspace.state_sha256:
        raise ResonantNumericalError("frozen parent child predecessor digest is stale")
    metadata = _frozen_parent_transition(
        workspace._field, workspace.profile.port_count, workspace.layout_transition
    )
    if metadata is None or metadata["freeze_id"] != freeze_id:
        raise ResonantNumericalError("frozen parent identity is stale")
    if expected_parent_summary_sha256 is not None and expected_parent_summary_sha256 != metadata["summary_sha256"]:
        raise ResonantNumericalError("frozen parent summary digest is stale")
    if expected_parent_source_state_sha256 is not None and expected_parent_source_state_sha256 != metadata["source_state_sha256"]:
        raise ResonantNumericalError("frozen parent source digest is stale")
    if expected_relation_sha256 is not None and expected_relation_sha256 != metadata["relation_sha256"]:
        raise ResonantNumericalError("frozen parent relation digest is stale")
    signal = _as_f64(base_flow_signal, (2,), "base_flow_signal")
    if not np.all(np.isfinite(signal)):
        raise ResonantNumericalError("base_flow_signal must be finite")
    budget = float(work_budget)
    if not math.isfinite(budget) or not 0.0 <= budget <= 1.0:
        raise ResonantNumericalError("work_budget must be finite and in [0,1]")
    values = _parent_register_values(workspace._field, workspace.profile.port_count, "L")
    if values is None:
        raise ResonantNumericalError("frozen parent register is absent")
    parent_flow = values[2:4].copy()
    effective = signal + FROZEN_PARENT_COUPLING_GAIN * parent_flow if parent_enabled else signal
    successor, impulse = apply_helical_packet_impulse(
        workspace,
        path=child_path,
        component=component,
        flow_signal=effective.tolist(),
        work_budget=budget,
        evidence_tick=workspace.evidence_tick,
        event_kind=event_kind,
    )
    if consume:
        transition = dict(successor.layout_transition)
        transition.pop(FROZEN_PARENT_METADATA_KEY, None)
        successor = successor._copy(layout_transition=transition)
    receipt = {
        "schema": "cassifi.frozen-parent-application.v1",
        "accepted": bool(impulse["accepted"]),
        "freeze_id": freeze_id,
        "parent_path": "L",
        "child_path": child_path,
        "component": component,
        "parent_enabled": bool(parent_enabled),
        "coupling_gain": FROZEN_PARENT_COUPLING_GAIN,
        "base_flow_signal": signal.tolist(),
        "parent_flow_signal": parent_flow.tolist(),
        "effective_flow_signal": effective.tolist(),
        "prolongation": "L momentum common/counterflow values[2:4] as native LL flow_signal",
        "parent_summary_sha256": metadata["summary_sha256"],
        "parent_source_state_sha256": metadata["source_state_sha256"],
        "relation_sha256": metadata["relation_sha256"],
        "child_source_state_sha256": workspace.state_sha256,
        "consume": bool(consume),
        "impulse": dict(impulse),
        "state_sha256": successor.state_sha256,
    }
    return successor, receipt


def release_frozen_parent(
    workspace: ResonantWorkspace,
    *,
    freeze_id: str,
) -> tuple[ResonantWorkspace, Mapping[str, Any]]:
    """Release the lock while preserving the ordinary canonical L register."""
    metadata = _frozen_parent_transition(
        workspace._field, workspace.profile.port_count, workspace.layout_transition
    )
    if metadata is None or metadata["freeze_id"] != freeze_id:
        raise ResonantNumericalError("frozen parent identity is stale")
    transition = dict(workspace.layout_transition)
    transition.pop(FROZEN_PARENT_METADATA_KEY, None)
    successor = workspace._copy(layout_transition=transition)
    return successor, {
        "schema": FROZEN_PARENT_SCHEMA,
        "released": True,
        "freeze_id": freeze_id,
        "state_sha256": successor.state_sha256,
    }

def _active_parent_register_paths(page: Any, port_count: int) -> tuple[str, ...]:
    return tuple(
        path for path in PARENT_REGISTER_PATHS
        if _parent_register_values(page, port_count, path) is not None
    )

def _profile_sha256(profile: ResonantProfile | Mapping[str, Any]) -> str:
    return _canonical_sha256(
        profile.as_dict() if isinstance(profile, ResonantProfile) else dict(profile)
    )


def _packet_support(port_count: int, path: str) -> tuple[int, int]:
    if (
        isinstance(port_count, bool)
        or not isinstance(port_count, int)
        or port_count < 1
    ):
        raise ResonantNumericalError("packet port_count must be a positive integer")
    if not isinstance(path, str) or any(branch not in "LR" for branch in path):
        raise ResonantNumericalError("packet path must contain only L and R")
    start, stop = 0, port_count
    for branch in path:
        if stop - start <= 1:
            raise ResonantNumericalError("packet path descends beyond a leaf")
        middle = start + (stop - start) // 2
        if branch == "L":
            stop = middle
        else:
            start = middle
    return start, stop


def _packet_mode_descriptors(
    start: int,
    stop: int,
    path: str,
) -> list[dict[str, Any]]:
    modes: list[dict[str, Any]] = [{
        "kind": "scale",
        "path": path,
        "start": start,
        "stop": stop,
    }]

    def visit(left: int, right: int, node_path: str) -> None:
        if right - left <= 1:
            return
        middle = left + (right - left) // 2
        modes.append({
            "kind": "detail",
            "path": node_path,
            "start": left,
            "middle": middle,
            "stop": right,
        })
        visit(left, middle, node_path + "L")
        visit(middle, right, node_path + "R")

    visit(start, stop, path)
    return modes


def _packet_analyze(values: np.ndarray) -> np.ndarray:
    channels = _as_f64(values, name="helical packet channels")
    if channels.ndim != 2 or channels.shape[0] != len(HELICAL_PACKET_CHANNELS):
        raise ResonantNumericalError("helical packet channels must have shape [4,N]")
    if channels.shape[1] < 1:
        raise ResonantNumericalError("helical packet cannot have empty support")

    def visit(left: int, right: int) -> tuple[np.ndarray, list[np.ndarray]]:
        size = right - left
        if size == 1:
            return channels[:, left].copy(), []
        middle = left + size // 2
        left_scale, left_details = visit(left, middle)
        right_scale, right_details = visit(middle, right)
        left_size, right_size = middle - left, right - middle
        left_weight = math.sqrt(left_size / size)
        right_weight = math.sqrt(right_size / size)
        scale = left_weight * left_scale + right_weight * right_scale
        detail = right_weight * left_scale - left_weight * right_scale
        return scale, [detail, *left_details, *right_details]

    scale, details = visit(0, channels.shape[1])
    return np.stack([scale, *details], axis=0)


def _packet_synthesize(coefficients: np.ndarray) -> np.ndarray:
    values = _as_f64(coefficients, name="helical packet coefficients")
    if values.ndim != 2 or values.shape[1] != len(HELICAL_PACKET_CHANNELS):
        raise ResonantNumericalError("helical packet coefficients must have shape [N,4]")
    if values.shape[0] < 1:
        raise ResonantNumericalError("helical packet cannot have empty support")
    cursor = 1

    def visit(scale: np.ndarray, size: int) -> np.ndarray:
        nonlocal cursor
        if size == 1:
            return scale.reshape((len(HELICAL_PACKET_CHANNELS), 1))
        if cursor >= values.shape[0]:
            raise ResonantNumericalError("helical packet is missing detail coefficients")
        detail = values[cursor]
        cursor += 1
        left_size, right_size = size // 2, size - size // 2
        left_weight = math.sqrt(left_size / size)
        right_weight = math.sqrt(right_size / size)
        left_scale = left_weight * scale + right_weight * detail
        right_scale = right_weight * scale - left_weight * detail
        return np.concatenate(
            (visit(left_scale, left_size), visit(right_scale, right_size)),
            axis=1,
        )

    reconstructed = visit(values[0], values.shape[0])
    if cursor != values.shape[0]:
        raise ResonantNumericalError("helical packet has unused detail coefficients")
    return reconstructed


def _packet_roundoff_allowance(
    coefficients: np.ndarray,
    reconstructed: np.ndarray,
) -> float:
    depth = max(1, math.ceil(math.log2(max(1, coefficients.shape[0]))))
    scale = max(
        1.0,
        float(np.max(np.abs(coefficients), initial=0.0)),
        float(np.max(np.abs(reconstructed), initial=0.0)),
    )
    return float(128.0 * np.finfo(float).eps * depth * scale)


def _helical_channels(vector: np.ndarray, port_count: int) -> np.ndarray:
    q_y, q_i, p_y, p_i = _as_f64(
        vector,
        (4 * port_count,),
        "helical phase-space vector",
    ).reshape((4, port_count))
    return np.stack((
        (q_y + q_i) / SQRT2,
        (q_y - q_i) / SQRT2,
        (p_y + p_i) / SQRT2,
        (p_y - p_i) / SQRT2,
    ))


def _packet_basis_sha256(
    *,
    layout_identity: str,
    profile_sha256: str,
    port_count: int,
    path: str,
) -> str:
    start, stop = _packet_support(port_count, path)
    return _canonical_sha256({
        "schema": HELICAL_PACKET_SCHEMA,
        "basis": HELICAL_PACKET_BASIS,
        "layout_identity": layout_identity,
        "profile_sha256": profile_sha256,
        "port_count": port_count,
        "path": path,
        "support": {"start": start, "stop": stop},
        "channels": list(HELICAL_PACKET_CHANNELS),
        "modes": _packet_mode_descriptors(start, stop, path),
    })


def _packet_from_channels(
    channels: np.ndarray,
    *,
    layout_identity: str,
    profile_sha256: str,
    port_count: int,
    source_state_sha256: str,
    path: str,
) -> dict[str, Any]:
    start, stop = _packet_support(port_count, path)
    values = _as_f64(
        channels,
        (len(HELICAL_PACKET_CHANNELS), stop - start),
        "helical packet channels",
    )
    coefficients = _packet_analyze(values)
    reconstructed = _packet_synthesize(coefficients)
    round_trip_allowance = _packet_roundoff_allowance(
        coefficients,
        reconstructed,
    )
    payload: dict[str, Any] = {
        "schema": HELICAL_PACKET_SCHEMA,
        "basis": HELICAL_PACKET_BASIS,
        "layout_identity": str(layout_identity),
        "profile_sha256": str(profile_sha256),
        "port_count": int(port_count),
        "source_state_sha256": str(source_state_sha256),
        "path": path,
        "support": {"start": start, "stop": stop},
        "channels": list(HELICAL_PACKET_CHANNELS),
        "modes": _packet_mode_descriptors(start, stop, path),
        "coefficients": coefficients.tolist(),
        "basis_sha256": _packet_basis_sha256(
            layout_identity=str(layout_identity),
            profile_sha256=str(profile_sha256),
            port_count=port_count,
            path=path,
        ),
        "round_trip_error": float(np.max(np.abs(values - reconstructed), initial=0.0)),
        "round_trip_allowance": round_trip_allowance,
        "coefficient_squared_norm": float(np.sum(coefficients * coefficients)),
    }
    payload["packet_sha256"] = _canonical_sha256(payload)
    return payload


def _validated_helical_packet(
    packet: Mapping[str, Any],
) -> tuple[dict[str, Any], np.ndarray]:
    if not isinstance(packet, Mapping):
        raise ResonantNumericalError("helical packet must be a mapping")
    expected_keys = {
        "schema", "basis", "layout_identity", "profile_sha256", "port_count",
        "source_state_sha256", "path", "support", "channels", "modes",
        "coefficients", "basis_sha256", "round_trip_error",
        "round_trip_allowance", "coefficient_squared_norm", "packet_sha256",
    }
    if set(packet) != expected_keys:
        raise ResonantNumericalError("helical packet keys are invalid")
    if packet["schema"] != HELICAL_PACKET_SCHEMA or packet["basis"] != HELICAL_PACKET_BASIS:
        raise ResonantNumericalError("helical packet basis is unsupported")
    for name in ("profile_sha256", "source_state_sha256", "basis_sha256", "packet_sha256"):
        value = packet[name]
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(char not in "0123456789abcdef" for char in value)
        ):
            raise ResonantNumericalError(f"helical packet {name} is invalid")
    if not isinstance(packet["layout_identity"], str) or not packet["layout_identity"]:
        raise ResonantNumericalError("helical packet layout identity is invalid")
    port_count = packet["port_count"]
    path = packet["path"]
    start, stop = _packet_support(port_count, path)
    if (
        not isinstance(packet["support"], dict)
        or packet["support"] != {"start": start, "stop": stop}
    ):
        raise ResonantNumericalError("helical packet support does not match its path")
    if (
        not isinstance(packet["channels"], list)
        or packet["channels"] != list(HELICAL_PACKET_CHANNELS)
    ):
        raise ResonantNumericalError("helical packet channels are incompatible")
    modes = _packet_mode_descriptors(start, stop, path)
    if not isinstance(packet["modes"], list) or packet["modes"] != modes:
        raise ResonantNumericalError("helical packet mode table is invalid")
    coefficients = _as_f64(
        packet["coefficients"],
        (stop - start, len(HELICAL_PACKET_CHANNELS)),
        "helical packet coefficients",
    )
    expected_basis = _packet_basis_sha256(
        layout_identity=packet["layout_identity"],
        profile_sha256=packet["profile_sha256"],
        port_count=port_count,
        path=path,
    )
    if packet["basis_sha256"] != expected_basis:
        raise ResonantNumericalError("helical packet basis digest mismatch")
    try:
        normalized = json.loads(json.dumps(
            dict(packet),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ))
    except (TypeError, ValueError, OverflowError) as exc:
        raise ResonantNumericalError(
            "helical packet must contain canonical JSON values"
        ) from exc
    claimed_packet = normalized.pop("packet_sha256")
    if claimed_packet != _canonical_sha256(normalized):
        raise ResonantNumericalError("helical packet digest mismatch")
    reconstructed = _packet_synthesize(coefficients)
    reanalyzed = _packet_analyze(reconstructed)
    round_trip = float(np.max(np.abs(coefficients - reanalyzed), initial=0.0))
    try:
        claimed_round_trip = float(packet["round_trip_error"])
        claimed_allowance = float(packet["round_trip_allowance"])
        claimed_norm = float(packet["coefficient_squared_norm"])
    except (TypeError, ValueError, OverflowError) as exc:
        raise ResonantNumericalError(
            "helical packet numerical certificate is invalid"
        ) from exc
    expected_allowance = _packet_roundoff_allowance(
        coefficients,
        reconstructed,
    )
    if (
        not math.isfinite(claimed_round_trip)
        or claimed_round_trip < 0.0
        or not math.isfinite(claimed_allowance)
        or claimed_allowance != expected_allowance
        or claimed_round_trip > claimed_allowance
        or round_trip > claimed_allowance
        or not math.isfinite(claimed_norm)
        or abs(claimed_norm - float(np.sum(coefficients * coefficients)))
        > 32 * np.finfo(float).eps * max(1.0, abs(claimed_norm))
    ):
        raise ResonantNumericalError("helical packet numerical certificate is invalid")
    return dict(packet), coefficients


def analyze_helical_packet(
    workspace: ResonantWorkspace,
    *,
    path: str = "",
) -> Mapping[str, Any]:
    """Return a disposable localized multiresolution view of the live field."""
    if not isinstance(workspace, ResonantWorkspace):
        raise TypeError("workspace must be ResonantWorkspace")
    start, stop = _packet_support(workspace.profile.port_count, path)
    channels = _helical_channels(
        _state_vector(workspace),
        workspace.profile.port_count,
    )[:, start:stop]
    return _packet_from_channels(
        channels,
        layout_identity=workspace.profile.layout_identity,
        profile_sha256=_profile_sha256(workspace.profile),
        port_count=workspace.profile.port_count,
        source_state_sha256=workspace.state_sha256,
        path=path,
    )

def _parent_slot_metadata(
    workspace: ResonantWorkspace, path: str, packet: Mapping[str, Any],
) -> tuple[dict[str, Any], np.ndarray]:
    coefficients = _as_f64(packet["coefficients"], name=f"parent register {path} coefficients")
    if coefficients.ndim != 2 or coefficients.shape[1] != PARENT_SUMMARY_WIDTH:
        raise ResonantNumericalError(f"parent register {path} has the wrong shape")
    values = coefficients[0].copy()
    metadata: dict[str, Any] = {
        "schema": PARENT_REGISTER_SCHEMA,
        "layout": PARENT_REGISTER_LAYOUT,
        "path": path,
        "basis": HELICAL_PACKET_BASIS,
        "basis_sha256": str(packet["basis_sha256"]),
        "support": dict(packet["support"]),
        "source_state_sha256": workspace.state_sha256,
        "source_packet_sha256": str(packet["packet_sha256"]),
    }
    metadata["summary_sha256"] = _parent_register_digest(metadata, values)
    return metadata, values


def _parent_relation(
    source_state_sha256: str,
    captures: Mapping[str, tuple[Mapping[str, Any], np.ndarray]],
    parent_path: str,
    child_path: str,
) -> dict[str, Any]:
    if parent_path != "L" or child_path != "LL":
        raise ResonantNumericalError("only the declared L to LL relation is supported")
    if parent_path not in captures or child_path not in captures:
        raise ResonantNumericalError("an ancestry relation requires both same-source captures")
    parent, child = captures[parent_path][0], captures[child_path][0]
    parent_support, child_support = parent["support"], child["support"]
    path_prefix = child_path.startswith(parent_path)
    support_contained = (
        int(parent_support["start"]) <= int(child_support["start"])
        and int(child_support["stop"]) <= int(parent_support["stop"])
    )
    if parent["source_state_sha256"] != source_state_sha256 or child["source_state_sha256"] != source_state_sha256:
        raise ResonantNumericalError("ancestry captures do not share the pre-write source digest")
    if not path_prefix or not support_contained:
        raise ResonantNumericalError("ancestry path prefix/support containment is not proven")
    capture_group = _canonical_sha256({
        "source_state_sha256": source_state_sha256,
        "captures": {
            path: {"source_packet_sha256": captures[path][0]["source_packet_sha256"], "support": captures[path][0]["support"]}
            for path in sorted(captures)
        },
    })
    relation = {
        "parent_path": parent_path,
        "child_path": child_path,
        "source_state_sha256": source_state_sha256,
        "capture_group_sha256": capture_group,
        "parent_support": dict(parent_support),
        "child_support": dict(child_support),
        "support_contained": True,
        "path_prefix": True,
    }
    relation["relation_sha256"] = _canonical_sha256({
        key: relation[key] for key in (
            "parent_path", "child_path", "source_state_sha256",
            "capture_group_sha256", "parent_support", "child_support",
            "support_contained", "path_prefix",
        )
    })
    return relation


def write_parent_registers(
    workspace: ResonantWorkspace,
    *,
    paths: Sequence[str] = PARENT_REGISTER_PATHS,
    ancestry_pairs: Sequence[Sequence[str]] = (),
) -> tuple[ResonantWorkspace, Mapping[str, Any]]:
    """Atomically capture bounded L/LL registers from one pre-write field state."""
    if not isinstance(workspace, ResonantWorkspace):
        raise TypeError("workspace must be ResonantWorkspace")
    if _frozen_parent_transition(
        workspace._field, workspace.profile.port_count, workspace.layout_transition
    ) is not None:
        raise ResonantNumericalError(
            "parent register write is locked while a frozen parent is active"
        )
    if isinstance(paths, (str, bytes)):
        raise ResonantNumericalError("parent register paths must be a sequence")
    requested = tuple(_validate_parent_register_path(path) for path in paths)
    if not requested or len(set(requested)) != len(requested):
        raise ResonantNumericalError("parent register paths must be nonempty and unique")
    existing, existing_relations = _parent_register_transition(
        workspace._field, workspace.profile.port_count, workspace.layout_transition
    )
    if any(path in existing for path in requested):
        raise ResonantNumericalError("parent register path is already active")
    source_state_sha256 = workspace.state_sha256
    captures: dict[str, tuple[Mapping[str, Any], np.ndarray]] = {}
    for path in requested:
        packet = analyze_helical_packet(workspace, path=path)
        captures[path] = _parent_slot_metadata(workspace, path, packet)
    relations: list[Mapping[str, Any]] = list(existing_relations)
    for pair in ancestry_pairs:
        if isinstance(pair, (str, bytes)) or len(pair) != 2:
            raise ResonantNumericalError("ancestry pair must contain exactly two paths")
        parent_path, child_path = (_validate_parent_register_path(value) for value in pair)
        if parent_path not in requested or child_path not in requested:
            raise ResonantNumericalError("ancestry pair paths must be captured in this write")
        relations.append(_parent_relation(source_state_sha256, captures, parent_path, child_path))
    slots: dict[str, Mapping[str, Any]] = {}
    for path, metadata in existing.items():
        if metadata["layout"] == PARENT_REGISTER_LAYOUT:
            slots[path] = metadata
        else:
            values = _parent_register_values(workspace._field, workspace.profile.port_count, path)
            if values is None:
                raise ResonantNumericalError("active parent register has no values")
            converted = dict(metadata)
            converted["schema"] = PARENT_REGISTER_SCHEMA
            converted["layout"] = PARENT_REGISTER_LAYOUT
            converted["summary_sha256"] = _parent_register_digest(converted, values)
            slots[path] = converted
    page = workspace._field
    for path in requested:
        metadata, values = captures[path]
        slots[path] = metadata
        page = _parent_register_page_write(page, workspace.profile.port_count, path, values)
    transition = dict(workspace.layout_transition)
    transition[PARENT_REGISTER_METADATA_KEY] = {
        "schema": PARENT_REGISTER_SCHEMA,
        "layout": PARENT_REGISTER_LAYOUT,
        "slots": {path: slots[path] for path in sorted(slots)},
        "relations": [dict(relation) for relation in relations],
    }
    successor = workspace._copy(field_page=page, layout_transition=transition)
    return successor, {
        "schema": "cassifi.parent-register-write.v1",
        "paths": list(requested),
        "source_state_sha256": source_state_sha256,
        "successor_state_sha256": successor.state_sha256,
        "slots": {
            path: {
                "source_packet_sha256": captures[path][0]["source_packet_sha256"],
                "summary_sha256": captures[path][0]["summary_sha256"],
                "values": captures[path][1].tolist(),
            }
            for path in requested
        },
        "relations": [dict(relation) for relation in relations if relation not in existing_relations],
        "successor_is_distinct": workspace.state_sha256 != successor.state_sha256,
    }
def recompute_parent_summary_from_child(
    workspace: ResonantWorkspace,
    *,
    expected_source_state_sha256: str | None = None,
    expected_relation_sha256: str | None = None,
    expected_child_packet_sha256: str | None = None,
) -> tuple[ResonantWorkspace, Mapping[str, Any]]:
    """Recompute canonical L summary from the live LL child state."""
    if not isinstance(workspace, ResonantWorkspace):
        raise TypeError("workspace must be ResonantWorkspace")
    if _frozen_parent_transition(
        workspace._field, workspace.profile.port_count, workspace.layout_transition
    ) is not None:
        raise ResonantNumericalError(
            "parent recompute is locked while a frozen parent is active"
        )
    registers, relations = _parent_register_transition(
        workspace._field, workspace.profile.port_count, workspace.layout_transition
    )
    if set(registers) != set(PARENT_REGISTER_PATHS) or not any(
        relation.get("parent_path") == "L" and relation.get("child_path") == "LL"
        for relation in relations
    ):
        raise ResonantNumericalError(
            "parent recompute requires an active L to LL relation"
        )
    source_state_sha256 = workspace.state_sha256
    if expected_source_state_sha256 is not None and expected_source_state_sha256 != source_state_sha256:
        raise ResonantNumericalError("parent recompute source state digest is stale")
    current_relation = next(
        relation for relation in relations
        if relation.get("parent_path") == "L" and relation.get("child_path") == "LL"
    )
    if expected_relation_sha256 is not None and expected_relation_sha256 != current_relation["relation_sha256"]:
        raise ResonantNumericalError("parent recompute relation digest is stale")
    captures: dict[str, tuple[dict[str, Any], np.ndarray]] = {}
    for path in PARENT_REGISTER_PATHS:
        packet = analyze_helical_packet(workspace, path=path)
        if path == "LL" and expected_child_packet_sha256 is not None and expected_child_packet_sha256 != packet["packet_sha256"]:
            raise ResonantNumericalError("parent recompute child packet digest is stale")
        captures[path] = _parent_slot_metadata(workspace, path, packet)
    relation = _parent_relation(source_state_sha256, captures, "L", "LL")
    page = workspace._field
    slots: dict[str, Mapping[str, Any]] = {}
    for path in PARENT_REGISTER_PATHS:
        metadata, values = captures[path]
        slots[path] = metadata
        page = _parent_register_page_write(page, workspace.profile.port_count, path, values)
    transition = dict(workspace.layout_transition)
    transition[PARENT_REGISTER_METADATA_KEY] = {
        "schema": PARENT_REGISTER_SCHEMA,
        "layout": PARENT_REGISTER_LAYOUT,
        "slots": {path: slots[path] for path in sorted(slots)},
        "relations": [dict(item) for item in relations if item != current_relation]
        + [relation],
    }
    successor = workspace._copy(field_page=page, layout_transition=transition)
    return successor, {
        "schema": "cassifi.parent-child-summary-recompute.v1",
        "parent_path": "L",
        "child_path": "LL",
        "source_state_sha256": source_state_sha256,
        "previous_source_state_sha256": current_relation["source_state_sha256"],
        "source_packet_sha256": slots["L"]["source_packet_sha256"],
        "child_packet_sha256": slots["LL"]["source_packet_sha256"],
        "relation_sha256": relation["relation_sha256"],
        "previous_relation_sha256": current_relation["relation_sha256"],
        "summary_sha256": slots["L"]["summary_sha256"],
        "summary": [float(value) for value in captures["L"][1]],
        "child": [float(value) for value in captures["LL"][1]],
        "successor_state_sha256": successor.state_sha256,
        "successor_is_distinct": successor.state_sha256 != workspace.state_sha256,
    }


def read_parent_register(workspace: ResonantWorkspace, path: str) -> Mapping[str, Any]:
    """Read one canonical register without recomputing its live packet."""
    if not isinstance(workspace, ResonantWorkspace):
        raise TypeError("workspace must be ResonantWorkspace")
    path = _validate_parent_register_path(path)
    values = _parent_register_values(workspace._field, workspace.profile.port_count, path)
    metadata = workspace.layout_transition.get(PARENT_REGISTER_METADATA_KEY)
    if values is None:
        if isinstance(metadata, Mapping) and (
            path == "L" and set(metadata) == {
                "schema", "layout", "path", "basis", "basis_sha256", "support",
                "source_state_sha256", "source_packet_sha256", "summary_sha256",
            }
        ):
            raise ResonantNumericalError("parent summary provenance has no register")
        return {
            "schema": "cassifi.parent-register-read.v1",
            "present": False, "path": path, "layout": PARENT_REGISTER_LAYOUT,
            "values": None, "summary_sha256": None,
        }
    registers, _relations = _parent_register_transition(
        workspace._field, workspace.profile.port_count, workspace.layout_transition
    )
    if path not in registers:
        raise ResonantNumericalError("parent register provenance is missing")
    item = registers[path]
    return {
        "schema": "cassifi.parent-register-read.v1",
        "present": True, "path": path, "layout": item["layout"],
        "basis": item["basis"], "basis_sha256": item["basis_sha256"],
        "support": dict(item["support"]),
        "source_state_sha256": item["source_state_sha256"],
        "source_packet_sha256": item["source_packet_sha256"],
        "summary_sha256": item["summary_sha256"], "values": values.tolist(),
    }


def read_parent_registers(workspace: ResonantWorkspace) -> Mapping[str, Any]:
    """Read the bounded canonical map, including only active slots."""
    if not isinstance(workspace, ResonantWorkspace):
        raise TypeError("workspace must be ResonantWorkspace")
    _registers, relations = _parent_register_transition(
        workspace._field, workspace.profile.port_count, workspace.layout_transition
    )
    return {
        "schema": "cassifi.parent-register-map-read.v1",
        "layout": PARENT_REGISTER_LAYOUT,
        "slots": {path: dict(read_parent_register(workspace, path)) for path in PARENT_REGISTER_PATHS
                  if _parent_register_values(workspace._field, workspace.profile.port_count, path) is not None},
        "relations": [dict(relation) for relation in relations],
    }


def write_parent_summary(
    workspace: ResonantWorkspace,
) -> tuple[ResonantWorkspace, Mapping[str, Any]]:
    """Compatibility adapter retaining the frozen legacy L-register contract."""
    if not isinstance(workspace, ResonantWorkspace):
        raise TypeError("workspace must be ResonantWorkspace")
    if _frozen_parent_transition(
        workspace._field, workspace.profile.port_count, workspace.layout_transition
    ) is not None:
        raise ResonantNumericalError(
            "parent summary write is locked while a frozen parent is active"
        )
    if _parent_summary_values(workspace._field, workspace.profile.port_count) is not None:
        raise ResonantNumericalError("parent summary register is already active")
    packet = analyze_helical_packet(workspace, path=PARENT_SUMMARY_PATH)
    coefficients = _as_f64(packet["coefficients"], name="parent summary packet coefficients")
    if coefficients.ndim != 2 or coefficients.shape[1] != PARENT_SUMMARY_WIDTH:
        raise ResonantNumericalError("level-zero parent summary has the wrong shape")
    values = coefficients[0].copy()
    metadata: dict[str, Any] = {
        "schema": PARENT_SUMMARY_REGISTER_SCHEMA, "layout": PARENT_SUMMARY_LAYOUT,
        "path": PARENT_SUMMARY_PATH, "basis": HELICAL_PACKET_BASIS,
        "basis_sha256": str(packet["basis_sha256"]), "support": dict(packet["support"]),
        "source_state_sha256": workspace.state_sha256,
        "source_packet_sha256": str(packet["packet_sha256"]),
    }
    metadata["summary_sha256"] = _parent_summary_digest(metadata, values)
    transition = dict(workspace.layout_transition)
    transition[PARENT_SUMMARY_METADATA_KEY] = metadata
    successor = workspace._copy(
        field_page=_parent_summary_page_write(workspace._field, workspace.profile.port_count, values),
        layout_transition=transition,
    )
    active_digest = _canonical_sha256(_state_vector(workspace).tolist())
    return successor, {
        "schema": "cassifi.parent-summary-write.v1", "path": PARENT_SUMMARY_PATH,
        "layout": PARENT_SUMMARY_LAYOUT, "source_state_sha256": workspace.state_sha256,
        "successor_state_sha256": successor.state_sha256,
        "source_packet_sha256": metadata["source_packet_sha256"],
        "summary_sha256": metadata["summary_sha256"], "summary": values.tolist(),
        "active_vector_sha256_before": active_digest,
        "active_vector_sha256_after": _canonical_sha256(_state_vector(successor).tolist()),
        "successor_is_distinct": workspace.state_sha256 != successor.state_sha256,
    }


def read_parent_summary(workspace: ResonantWorkspace) -> Mapping[str, Any]:
    """Read only the stored legacy-compatible L register."""
    if not isinstance(workspace, ResonantWorkspace):
        raise TypeError("workspace must be ResonantWorkspace")
    values = _parent_summary_values(workspace._field, workspace.profile.port_count)
    metadata = workspace.layout_transition.get(PARENT_SUMMARY_METADATA_KEY)
    if values is None:
        if metadata is not None:
            raise ResonantNumericalError("parent summary provenance has no register")
        return {"schema": "cassifi.parent-summary-read.v1", "present": False,
                "path": PARENT_SUMMARY_PATH, "layout": PARENT_SUMMARY_LAYOUT,
                "values": None, "summary_sha256": None}
    if isinstance(metadata, Mapping) and set(metadata) == {
        "schema", "layout", "slots", "relations",
    }:
        item = metadata["slots"].get(PARENT_SUMMARY_PATH)
        if item is None:
            raise ResonantNumericalError("parent summary provenance is missing")
        _parent_register_metadata(item, port_count=workspace.profile.port_count, values=values)
    else:
        if not isinstance(metadata, Mapping):
            raise ResonantNumericalError("parent summary provenance is missing")
        _parent_summary_metadata(metadata, port_count=workspace.profile.port_count, values=values)
        item = metadata
    return {"schema": "cassifi.parent-summary-read.v1", "present": True,
            "path": PARENT_SUMMARY_PATH, "layout": PARENT_SUMMARY_LAYOUT,
            "basis": item["basis"], "basis_sha256": item["basis_sha256"],
            "support": dict(item["support"]), "source_state_sha256": item["source_state_sha256"],
            "source_packet_sha256": item["source_packet_sha256"],
            "summary_sha256": item["summary_sha256"], "values": values.tolist()}


def helical_packet_channels(packet: Mapping[str, Any]) -> np.ndarray:
    """Reconstruct the four declared phase-space channels for one packet."""
    _normalized, coefficients = _validated_helical_packet(packet)
    return _packet_synthesize(coefficients)


def split_helical_packet(
    packet: Mapping[str, Any],
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    """Split one packet into exact sibling views without creating new state."""
    normalized, coefficients = _validated_helical_packet(packet)
    channels = _packet_synthesize(coefficients)
    size = channels.shape[1]
    if size <= 1:
        raise ResonantNumericalError("a leaf packet cannot be split")
    left_size = size // 2
    common = {
        "layout_identity": normalized["layout_identity"],
        "profile_sha256": normalized["profile_sha256"],
        "port_count": normalized["port_count"],
        "source_state_sha256": normalized["source_state_sha256"],
    }
    return (
        _packet_from_channels(
            channels[:, :left_size],
            path=normalized["path"] + "L",
            **common,
        ),
        _packet_from_channels(
            channels[:, left_size:],
            path=normalized["path"] + "R",
            **common,
        ),
    )


def compose_helical_packets(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> Mapping[str, Any]:
    """Compose sibling views of the same field state into their parent packet."""
    left_packet, left_coefficients = _validated_helical_packet(left)
    right_packet, right_coefficients = _validated_helical_packet(right)
    shared = (
        "layout_identity",
        "profile_sha256",
        "port_count",
        "source_state_sha256",
    )
    if any(left_packet[key] != right_packet[key] for key in shared):
        raise ResonantNumericalError(
            "helical packet composition requires one profile and source state"
        )
    left_path, right_path = left_packet["path"], right_packet["path"]
    if (
        not left_path.endswith("L")
        or not right_path.endswith("R")
        or left_path[:-1] != right_path[:-1]
    ):
        raise ResonantNumericalError("helical packet composition requires ordered siblings")
    parent_path = left_path[:-1]
    parent_start, parent_stop = _packet_support(left_packet["port_count"], parent_path)
    if (
        left_packet["support"]["start"] != parent_start
        or left_packet["support"]["stop"] != right_packet["support"]["start"]
        or right_packet["support"]["stop"] != parent_stop
    ):
        raise ResonantNumericalError("helical packet sibling supports are not contiguous")
    channels = np.concatenate((
        _packet_synthesize(left_coefficients),
        _packet_synthesize(right_coefficients),
    ), axis=1)
    return _packet_from_channels(
        channels,
        layout_identity=left_packet["layout_identity"],
        profile_sha256=left_packet["profile_sha256"],
        port_count=left_packet["port_count"],
        source_state_sha256=left_packet["source_state_sha256"],
        path=parent_path,
    )


def _packet_spatial_mode(
    port_count: int,
    path: str,
    component: str,
) -> tuple[np.ndarray, dict[str, Any]]:
    start, stop = _packet_support(port_count, path)
    size = stop - start
    mode = np.zeros(port_count, dtype=np.float64)
    if component == "scale":
        mode[start:stop] = 1.0 / math.sqrt(size)
        descriptor = {
            "kind": "scale",
            "path": path,
            "start": start,
            "stop": stop,
        }
    elif component == "detail":
        if size <= 1:
            raise ResonantNumericalError("a leaf packet has no detail mode")
        middle = start + size // 2
        left_size, right_size = middle - start, stop - middle
        mode[start:middle] = math.sqrt(right_size / (left_size * size))
        mode[middle:stop] = -math.sqrt(left_size / (right_size * size))
        descriptor = {
            "kind": "detail",
            "path": path,
            "start": start,
            "middle": middle,
            "stop": stop,
        }
    else:
        raise ResonantNumericalError("packet component must be scale or detail")
    return mode, descriptor


def _packet_momentum_direction(
    port_count: int,
    path: str,
    component: str,
    flow_signal: Sequence[float],
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    signal = _as_f64(flow_signal, (2,), "packet flow_signal")
    spatial, descriptor = _packet_spatial_mode(port_count, path, component)
    norm = float(np.linalg.norm(signal))
    unit = signal if norm == 0.0 else signal / norm
    common, counterflow = unit
    p_y = spatial * (common + counterflow) / SQRT2
    p_i = spatial * (common - counterflow) / SQRT2
    direction = np.zeros(4 * port_count, dtype=np.float64)
    direction[2 * port_count:] = np.concatenate((p_y, p_i))
    return direction, unit, descriptor


class _WaveOperator:
    """One batch-local operator; only scoped matrices and sparse rail edges persist here."""

    def __init__(
        self,
        workspace: ResonantWorkspace,
        problem: ResonantProblem | None,
        *,
        device: str | None = None,
        resources: Any = None,
    ) -> None:
        self.profile = workspace.profile
        self.n = workspace.profile.port_count
        self.device = device
        self.resources = resources
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
        mass = 1 / inv_mass if inv_mass.ndim == 1 else np.linalg.inv(inv_mass)
        self.mass = self.array(mass)
        self.inv_mass = self.array(inv_mass)
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
        constraint_inverse = np.linalg.pinv(matrix)
        self.constraints = self.array(matrix)
        self.targets = self.array(targets)
        self.constraint_inverse = self.array(constraint_inverse)
        rail_sums = np.zeros(2 * n)
        for source, destination, weight, _ in self.edges:
            rail_sums[source] += abs(weight)
            rail_sums[destination] += abs(weight)
        rail_bound = float(rail_sums.max(initial=0))
        if workspace.profile.projected_transport is not None:
            rail_bound = float(np.linalg.norm(workspace.profile.projected_transport, ord=np.inf))
        projection_bound = (
            1 + float(np.linalg.norm(constraint_inverse, ord=np.inf) * np.linalg.norm(matrix, ord=np.inf))
            if len(targets) else 1.0
        )
        mass_bound = float(np.max(mass)) if inv_mass.ndim == 1 else float(np.linalg.norm(mass, ord=np.inf))
        conditioner_bound = float(np.linalg.norm(conditioner, ord=np.inf)) if problem is not None else 1.0
        damping_bound = max(
            self.profile.damping,
            2 * self.profile.quiet_damping * max(conditioner_bound, mass_bound, 1 / max(self.profile.relative_stiffness, 1e-6)),
        )
        self.flow_roundoff_gain = projection_bound ** 2 * (1 + rail_bound + damping_bound)
        self.absolute_k = abs(self.k)
        self.absolute_b = abs(self.b)
        self.absolute_inv_mass = abs(self.inv_mass)

    def array(self, value: Any, *, integer: bool = False) -> Any:
        if self.device is None:
            return np.array(value, dtype=np.int64 if integer else np.float64)
        return torch.as_tensor(
            np.asarray(value), dtype=torch.int64 if integer else torch.float64, device=self.device
        )

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
                result[self.ports] -= self.b[:, None] if value.ndim > 1 else self.b
        return result

    def project(self, value: Any) -> Any:
        if not len(self.targets):
            return value
        residual = self.constraints @ value
        if value.ndim > 1:
            return value - self.constraint_inverse @ residual
        return value - self.constraint_inverse @ residual

    def boundary(self, value: Any, tolerance: float) -> Any:
        if not len(self.targets):
            return value
        target = self.targets[:, None] if value.ndim > 1 else self.targets
        result = value + self.constraint_inverse @ (target - self.constraints @ value)
        if self.norm(self.constraints @ result - target) > tolerance:
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

    def energy_gradient(self, value: Any) -> tuple[Any, Any]:
        batch = value.ndim > 1
        qy, qi, py, pi = value.reshape((4, self.n) + value.shape[1:])
        x, d = (qy + qi) / SQRT2, (qy - qi) / SQRT2
        kx = self.semantic(x, force=False)
        semantic = self.semantic(x)
        relative = self.profile.relative_stiffness * d + self.beta.reshape((-1,) + (1,) * (d.ndim - 1)) * d ** 3
        p = self.cat((py, pi))
        gp = self.mass_apply(p)
        if batch:
            energy = 0.5 * ((x * kx).sum(dim=0) + self.profile.relative_stiffness * (d * d).sum(dim=0) + (p * gp).sum(dim=0))
            energy += (self.beta.reshape((-1, 1)) * d ** 4).sum(dim=0) / 4
            if len(self.ports):
                energy -= (self.b[:, None] * x[self.ports]).sum(dim=0)
        else:
            energy = 0.5 * (x @ kx + self.profile.relative_stiffness * (d @ d) + p @ gp)
            energy += (self.beta * d ** 4).sum() / 4
            if len(self.ports):
                energy -= self.b @ x[self.ports]
            energy = float(energy)
        return energy, self.cat(((semantic + relative) / SQRT2, (semantic - relative) / SQRT2, gp))

    def roundoff_scales(self, value: Any) -> tuple[Any, Any]:
        """Absolute-product bounds retain cancellation hidden by a small energy."""
        batch = value.ndim > 1
        qy, qi, py, pi = abs(value).reshape((4, self.n) + value.shape[1:])
        common = (qy + qi) / SQRT2
        semantic = self.clone(common)
        if len(self.ports):
            semantic[self.ports] = self.absolute_k @ common[self.ports]
            if batch:
                semantic[self.ports] += self.absolute_b[:, None]
            else:
                semantic[self.ports] += self.absolute_b
        beta = self.beta.reshape((-1,) + (1,) * (common.ndim - 1))
        relative = self.profile.relative_stiffness * common + beta * common ** 3
        momentum = self.cat((py, pi))
        kinetic = (
            self.multiply(self.absolute_inv_mass, momentum)
            if self.absolute_inv_mass.ndim == 1 else self.absolute_inv_mass @ momentum
        )
        position = (semantic + relative) / SQRT2
        magnitude = self.cat((position, position, kinetic))
        if batch:
            return magnitude.abs().amax(dim=0), (abs(value) * magnitude).sum(dim=0)
        return self.norm(magnitude), float(abs(value) @ magnitude)

    def step_batch(
        self, before: Any, duration: Any, *, quiet: bool,
        max_iterations: int, tolerance: float,
    ) -> tuple[Any, list[dict[str, float]]]:
        """Batched GPU Newton updates with independently retiring columns."""
        if self.device is None or before.ndim != 2:
            raise ResonantNumericalError("batched stepping requires a column-major GPU state batch")
        count = int(before.shape[1])
        durations = duration if isinstance(duration, torch.Tensor) else torch.full(
            (count,), float(duration), dtype=before.dtype, device=before.device,
        )
        durations = durations.reshape(-1)
        candidate = self.clone(before)
        residual = torch.zeros_like(candidate)
        gradient = torch.zeros_like(candidate)
        converged = torch.zeros((count,), dtype=torch.bool, device=before.device)
        iterations = torch.zeros((count,), dtype=torch.int64, device=before.device)
        for iteration in range(max_iterations):
            gradient = self.energy_gradient(candidate)[1] if quiet else self.discrete_gradient(before, candidate)
            flow = self.flow(gradient, quiet)
            residual = candidate - before - durations[None, :] * flow
            residual_norm = residual.abs().amax(dim=0)
            candidate_norm = candidate.abs().amax(dim=0)
            before_norm = before.abs().amax(dim=0)
            flow_norm = flow.abs().amax(dim=0)
            round_scale = self.roundoff_scales(candidate)[0]
            rounding = 64 * np.finfo(float).eps * (
                candidate_norm + before_norm
                + durations * torch.maximum(flow_norm, self.flow_roundoff_gain * round_scale)
            )
            converged = residual_norm <= torch.maximum(torch.full_like(rounding, tolerance), rounding)
            iterations = torch.where(converged & (iterations == 0), iteration + 1, iterations)
            if bool(converged.all().item()):
                break
            def jacobian(value: Any) -> Any:
                return value - durations[None, :] * self.flow(
                    self.derivative(before, candidate, value, quiet), quiet,
                )
            delta, gmres_residual, _ = _torch_gmres_batch(
                jacobian, residual, tolerance=tolerance,
                restart=min(8, int(before.shape[0])), max_restarts=8,
            )
            if bool((gmres_residual[~converged] > max(tolerance * 0.05, 1e-11)).any().item()):
                raise ResonantNumericalError("bounded GPU batched matrix-free Newton solve exhausted")
            candidate = candidate - torch.where(converged[None, :], torch.zeros_like(delta), delta)
        else:
            raise ResonantNumericalError("bounded nonlinear solve exhausted")
        starts, ends = self.energy_gradient(before)[0], self.energy_gradient(candidate)[0]
        receipts: list[dict[str, float]] = []
        for column in range(count):
            before_column, candidate_column = before[:, column], candidate[:, column]
            gradient_column, residual_column = gradient[:, column], residual[:, column]
            projected = self.project(gradient_column)
            step_duration = float(durations[column].item())
            dissipated = float(step_duration * (projected @ self.dissipation(projected, quiet)))
            numerical = float((gradient_column - self.discrete_gradient(before_column, candidate_column)) @ (candidate_column - before_column)) if quiet else 0.0
            residual_work = float(gradient_column @ residual_column)
            defect = float(ends[column] - starts[column]) + dissipated + numerical - residual_work
            allowance = max(1e-10, 64 * np.finfo(float).eps * max(
                1.0, self.roundoff_scales(before_column)[1], self.roundoff_scales(candidate_column)[1],
            ))
            if not math.isfinite(defect) or abs(defect) > allowance or numerical < -allowance:
                raise ResonantNumericalError("transition violates the discrete work balance")
            receipts.append({
                "dissipated_work": dissipated,
                "numerical_dissipated_work": max(0.0, numerical),
                "energy_roundoff_allowance": allowance,
                "residual_work": residual_work,
                "balance_defect": defect,
                "residual_norm": float(residual_column.abs().max().item()),
                "iterations": int(iterations[column].item()),
            })
        return candidate, receipts

    def derivative(self, before: Any, after: Any, value: Any, quiet: bool) -> Any:
        qy, qi, py, pi = value.reshape((4, self.n) + value.shape[1:])
        x, d = (qy + qi) / SQRT2, (qy - qi) / SQRT2
        q0, i0 = before[:self.n], before[self.n:2 * self.n]
        q1, i1 = after[:self.n], after[self.n:2 * self.n]
        d0, d1 = (q0 - i0) / SQRT2, (q1 - i1) / SQRT2
        beta = self.beta.reshape((-1,) + (1,) * (d.ndim - 1))
        if quiet:
            factor = 1.0
            relative = self.profile.relative_stiffness + 3 * beta * d1 ** 2
        else:
            factor = 0.5
            relative = self.profile.relative_stiffness / 2 + beta * (3 * d1 ** 2 + 2 * d1 * d0 + d0 ** 2) / 4
        semantic = factor * self.semantic(x, force=False)
        relative = relative * d
        return self.cat(((semantic + relative) / SQRT2, (semantic - relative) / SQRT2,
                         factor * self.mass_apply(self.cat((py, pi)))))


    def discrete_gradient(self, before: Any, after: Any) -> Any:
        shape = (4, self.n) + before.shape[1:]
        qy0, qi0, py0, pi0 = before.reshape(shape)
        qy1, qi1, py1, pi1 = after.reshape(shape)
        x = (qy0 + qi0 + qy1 + qi1) / (2 * SQRT2)
        d0, d1 = (qy0 - qi0) / SQRT2, (qy1 - qi1) / SQRT2
        semantic = self.semantic(x)
        beta = self.beta.reshape((-1,) + (1,) * (d1.ndim - 1))
        relative = self.profile.relative_stiffness * (d0 + d1) / 2
        relative += beta * (d1 ** 3 + d1 ** 2 * d0 + d1 * d0 ** 2 + d0 ** 3) / 4
        return self.cat(((semantic + relative) / SQRT2, (semantic - relative) / SQRT2,
                         self.mass_apply(self.cat((py0 + py1, pi0 + pi1))) / 2))


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
                return value - duration * self.flow(
                    self.derivative(before, candidate, value, quiet), quiet
                )
            if self.device is None:
                operator = LinearOperator((len(before), len(before)), matvec=jacobian, dtype=np.float64)
                delta, info = gmres(operator, residual, atol=tolerance * 0.05, rtol=1e-10,
                                    restart=min(32, len(before)), maxiter=8)
                if info != 0:
                    raise ResonantNumericalError("bounded matrix-free Newton solve exhausted")
            else:
                delta, gmres_residual, _applications = _torch_gmres(
                    jacobian,
                    residual,
                    tolerance=tolerance,
                    restart=min(8, len(before)),
                    max_restarts=8,
                )
                if gmres_residual > max(tolerance * 0.05, 1e-11):
                    raise ResonantNumericalError("bounded GPU matrix-free Newton solve exhausted")
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
    if event_kind not in _FIELD_EVENT_KINDS:
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


def _energy_bounded_packet_step(
    operator: Any,
    before: np.ndarray,
    direction: np.ndarray,
    work_budget: float,
) -> tuple[np.ndarray, float, float, float, float, float]:
    start_energy = float(operator.energy_gradient(before)[0])
    if work_budget == 0.0:
        return before.copy(), start_energy, start_energy, 0.0, 0.0, 1e-12
    port_count = before.size // 4
    mass_direction = operator.mass_apply(direction[2 * port_count:])
    linear = float(before[2 * port_count:] @ mass_direction)
    quadratic = float(direction[2 * port_count:] @ mass_direction)
    if not math.isfinite(quadratic) or quadratic <= 0.0:
        raise ResonantNumericalError("helical packet impulse has no positive kinetic metric")
    discriminant = linear * linear + 2.0 * quadratic * work_budget
    if not math.isfinite(discriminant) or discriminant < 0.0:
        raise ResonantNumericalError("helical packet impulse amplitude is not finite")
    root = math.sqrt(discriminant)
    amount = (
        2.0 * work_budget / (root + linear)
        if linear >= 0.0
        else (root - linear) / quadratic
    )
    after = before + amount * direction
    end_energy = float(operator.energy_gradient(after)[0])
    if not math.isfinite(end_energy) or end_energy > 1e12:
        raise ResonantNumericalError("helical packet impulse exceeds the field energy ceiling")
    applied_work = end_energy - start_energy
    allowance = max(
        1e-12,
        256.0 * np.finfo(float).eps * max(
            1.0,
            abs(start_energy),
            abs(end_energy),
            abs(work_budget),
        ),
    )
    if (
        not math.isfinite(applied_work)
        or abs(applied_work - work_budget) > allowance
    ):
        raise ResonantNumericalError("helical packet impulse violates its work balance")
    return after, start_energy, end_energy, applied_work, amount, allowance


def apply_helical_packet_impulse(
    workspace: ResonantWorkspace,
    *,
    path: str,
    component: str,
    flow_signal: Sequence[float],
    work_budget: float,
    evidence_tick: int,
    event_kind: str,
) -> tuple[ResonantWorkspace, dict[str, Any]]:
    """Deposit bounded common/counterflow momentum in one packet basis mode."""
    if not isinstance(workspace, ResonantWorkspace):
        raise TypeError("workspace must be ResonantWorkspace")
    if (
        isinstance(work_budget, bool)
        or not isinstance(work_budget, (int, float))
        or not math.isfinite(float(work_budget))
        or not 0.0 <= float(work_budget) <= 1.0
    ):
        raise ResonantNumericalError("work_budget must be finite and in [0,1]")
    budget = float(work_budget)
    if (
        isinstance(evidence_tick, bool)
        or not isinstance(evidence_tick, int)
        or evidence_tick < workspace.evidence_tick
    ):
        raise ResonantNumericalError(
            "evidence_tick cannot precede the workspace evidence clock"
        )
    if event_kind not in _FIELD_EVENT_KINDS:
        raise ResonantNumericalError("event_kind is not a supported field event")
    direction, unit_signal, mode = _packet_momentum_direction(
        workspace.profile.port_count,
        path,
        component,
        flow_signal,
    )
    signal_norm = float(np.linalg.norm(unit_signal))
    if signal_norm == 0.0 and budget:
        raise ResonantNumericalError(
            "positive packet work requires a nonzero flow signal"
        )
    if workspace.paused and budget:
        raise ResonantNumericalError(
            "paused workspace cannot accept a helical packet impulse"
        )
    operator = _WaveOperator(workspace, None)
    before = _state_vector(workspace)
    recorded_start = float(workspace.ledger.get(
        "stored_energy",
        operator.energy_gradient(before)[0],
    ))
    if budget and signal_norm:
        (
            after,
            start_energy,
            end_energy,
            applied_work,
            amount,
            allowance,
        ) = _energy_bounded_packet_step(operator, before, direction, budget)
        parameter_work = start_energy - recorded_start
        balance_defect = (
            end_energy - recorded_start - parameter_work - applied_work
        )
        if abs(balance_defect) > allowance:
            raise ResonantNumericalError(
                "helical packet impulse violates its recorded energy balance"
            )
        ledger = dict(workspace.ledger)
        increments = {
            "parameter_work": parameter_work,
            "helical_packet_work": applied_work,
            f"helical_packet_{event_kind}_work": applied_work,
            "balance_defect": balance_defect,
        }
        if event_kind.endswith("-observation"):
            increments["helical_packet_outcome_work"] = applied_work
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
        accepted = True
    else:
        result = workspace
        start_energy = end_energy = float(operator.energy_gradient(before)[0])
        applied_work = amount = parameter_work = balance_defect = 0.0
        allowance = 1e-12
        accepted = False
    profile_sha256 = _profile_sha256(workspace.profile)
    return result, {
        "schema": "cassifi.resonant-helical-packet-impulse.v1",
        "accepted": accepted,
        "event_kind": event_kind,
        "basis": HELICAL_PACKET_BASIS,
        "basis_sha256": _packet_basis_sha256(
            layout_identity=workspace.profile.layout_identity,
            profile_sha256=profile_sha256,
            port_count=workspace.profile.port_count,
            path=path,
        ),
        "profile_sha256": profile_sha256,
        "path": path,
        "component": component,
        "support": {"start": mode["start"], "stop": mode["stop"]},
        "mode": mode,
        "flow_channels": ["common", "counterflow"],
        "flow_signal": unit_signal.tolist(),
        "requested_work": budget,
        "applied_work": float(applied_work),
        "impulse_amount": float(amount),
        "recorded_start_energy": recorded_start,
        "start_energy": float(start_energy),
        "end_energy": float(end_energy),
        "parameter_work": float(parameter_work),
        "balance_defect": float(balance_defect),
        "energy_roundoff_allowance": float(allowance),
        "field_ticks": result.field_ticks,
        "evidence_tick": result.evidence_tick,
        "source_state_sha256": workspace.state_sha256,
        "state_sha256": result.state_sha256,
    }
def apply_live_child_detail_to_parent(
    workspace: ResonantWorkspace,
    *,
    work_budget: float,
    parent_enabled: bool = True,
    expected_child_source_state_sha256: str | None = None,
    expected_child_packet_sha256: str | None = None,
    expected_relation_sha256: str | None = None,
    event_kind: str = "reasoning-work",
) -> tuple[ResonantWorkspace, Mapping[str, Any]]:
    """Apply the live LL top-detail momentum to the native L scale mode.

    The child detail is read from the current field at invocation time.  It is
    deliberately not retained as a frozen descriptor, and this transition
    never rewrites the canonical parent register; callers may explicitly use
    :func:`recompute_parent_summary_from_child` afterward.
    """
    if not isinstance(workspace, ResonantWorkspace):
        raise TypeError("workspace must be ResonantWorkspace")
    if _frozen_parent_transition(
        workspace._field, workspace.profile.port_count, workspace.layout_transition
    ) is not None:
        raise ResonantNumericalError(
            "child detail to parent transition is locked while a frozen parent is active"
        )
    registers, relations = _parent_register_transition(
        workspace._field, workspace.profile.port_count, workspace.layout_transition
    )
    if set(registers) != set(PARENT_REGISTER_PATHS):
        raise ResonantNumericalError(
            "child detail to parent requires active L and LL registers"
        )
    relation = next(
        (
            item for item in relations
            if item.get("parent_path") == "L" and item.get("child_path") == "LL"
        ),
        None,
    )
    if relation is None:
        raise ResonantNumericalError(
            "child detail to parent requires an active L to LL relation"
        )
    source_state_sha256 = workspace.state_sha256
    if (
        expected_child_source_state_sha256 is not None
        and expected_child_source_state_sha256 != source_state_sha256
    ):
        raise ResonantNumericalError("child detail source state digest is stale")
    if (
        expected_relation_sha256 is not None
        and expected_relation_sha256 != relation["relation_sha256"]
    ):
        raise ResonantNumericalError("child detail relation digest is stale")
    packet = analyze_helical_packet(workspace, path="LL")
    if (
        expected_child_packet_sha256 is not None
        and expected_child_packet_sha256 != packet["packet_sha256"]
    ):
        raise ResonantNumericalError("child detail packet digest is stale")
    coefficients = _as_f64(packet["coefficients"], name="LL child packet coefficients")
    if coefficients.ndim != 2 or coefficients.shape[0] <= LIVE_CHILD_DETAIL_MODE_INDEX:
        raise ResonantNumericalError("LL child packet has no top detail mode")
    channel_start, channel_stop = LIVE_CHILD_DETAIL_CHANNEL_SLICE
    feedback_signal = coefficients[
        LIVE_CHILD_DETAIL_MODE_INDEX, channel_start:channel_stop
    ].copy()
    _finite(feedback_signal, "LL child detail momentum channels")
    budget = float(work_budget)
    if (
        isinstance(work_budget, bool)
        or not isinstance(work_budget, (int, float))
        or not math.isfinite(budget)
        or not 0.0 <= budget <= 1.0
    ):
        raise ResonantNumericalError("work_budget must be finite and in [0,1]")
    if event_kind not in _FIELD_EVENT_KINDS:
        raise ResonantNumericalError("event_kind is not a supported field event")
    if parent_enabled:
        successor, impulse = apply_helical_packet_impulse(
            workspace,
            path="L",
            component="scale",
            flow_signal=feedback_signal.tolist(),
            work_budget=budget,
            evidence_tick=workspace.evidence_tick,
            event_kind=event_kind,
        )
    else:
        successor = workspace
        operator = _WaveOperator(workspace, None)
        energy = float(operator.energy_gradient(_state_vector(workspace))[0])
        impulse = {
            "schema": "cassifi.resonant-helical-packet-impulse.v1",
            "accepted": False,
            "requested_work": budget,
            "applied_work": 0.0,
            "start_energy": energy,
            "end_energy": energy,
            "balance_defect": 0.0,
            "energy_roundoff_allowance": 1e-12,
            "source_state_sha256": workspace.state_sha256,
            "state_sha256": workspace.state_sha256,
        }
    return successor, {
        "schema": LIVE_CHILD_DETAIL_TO_PARENT_SCHEMA,
        "accepted": bool(parent_enabled and impulse["accepted"]),
        "parent_enabled": bool(parent_enabled),
        "parent_path": "L",
        "child_path": "LL",
        "restriction": {
            "child_mode_index": LIVE_CHILD_DETAIL_MODE_INDEX,
            "child_mode": "LL:detail",
            "child_channels": ["momentum-common", "momentum-counterflow"],
            "parent_component": "L:scale",
        },
        "child_source_state_sha256": source_state_sha256,
        "child_packet_sha256": str(packet["packet_sha256"]),
        "relation_sha256": str(relation["relation_sha256"]),
        "feedback_signal": feedback_signal.tolist(),
        "requested_work": budget,
        "applied_work": float(impulse["applied_work"]),
        "balance_defect": float(impulse["balance_defect"]),
        "energy_roundoff_allowance": float(impulse["energy_roundoff_allowance"]),
        "start_energy": float(impulse["start_energy"]),
        "end_energy": float(impulse["end_energy"]),
        "impulse": dict(impulse),
        "source_state_sha256": workspace.state_sha256,
        "state_sha256": successor.state_sha256,
        "successor_is_distinct": successor.state_sha256 != workspace.state_sha256,
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
        "reference_norm": reference_norm,
        "scores": rows,
        "workspace_unchanged": True,
    }



def _advance(workspace: ResonantWorkspace, *, problem: ResonantProblem | None, ticks: int, demand: float,
             source_enabled: bool, quiet: bool, max_iterations: int, tolerance: float | None,
             device: str | None = None, resources: Any = None) -> tuple[ResonantWorkspace, dict[str, Any]]:
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
    operator = _WaveOperator(workspace, problem, device=device, resources=resources)
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
               "arithmetic": "numpy-matrix-free-float64" if device is None else "torch-matrix-free-float64",
               "device": "cpu" if device is None else device, "state_sha256": result.state_sha256}
    return result, receipt


def advance_workspace(workspace: ResonantWorkspace, *, problem: ResonantProblem | None = None, ticks: int = 1,
                      demand: float = 0.0, source_enabled: bool = True, quiet: bool = False,
                      max_iterations: int = 32, tolerance: float | None = None,
                      resources: Any = None) -> tuple[ResonantWorkspace, dict[str, Any]]:
    return _advance(workspace, problem=problem, ticks=ticks, demand=demand, source_enabled=source_enabled,
                    quiet=quiet, max_iterations=max_iterations, tolerance=tolerance, resources=resources)

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
    if _active_parent_register_paths(workspace._field, workspace.profile.port_count):
        raise ResonantNumericalError(
            "resolution change rejects an active parent register map"
        )
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
                          quiet: bool = False, device: str = "cuda",
                          resources: Any = None) -> tuple[ResonantWorkspace, dict[str, Any]]:
    if not isinstance(workspace, ResonantWorkspace):
        raise TypeError("workspace must be ResonantWorkspace")
    requested_device = str(device)
    if requested_device == "auto":
        if not torch.cuda.is_available():
            result, receipt = advance_workspace(
                workspace, problem=problem, ticks=ticks, demand=demand,
                source_enabled=source_enabled, quiet=quiet, resources=resources,
            )
            receipt["device_requested"] = "auto"
            receipt["device_fallback_reason"] = "CUDA unavailable; selected CPU"
            receipt["device_reason"] = receipt["device_fallback_reason"]
            return result, receipt
        requested_device = "cuda"
    # gpu_profile intentionally raises for an unavailable explicit CUDA request.
    workspace.profile.gpu_profile(requested_device)
    state_bytes = 4 * workspace.profile.port_count * np.dtype(np.float64).itemsize
    # Eight Krylov vectors plus flow/derivative scratch; no N-by-N allocation.
    scratch_bytes = state_bytes * 10
    policy = _resource_manager(resources)
    with _gpu_residency(policy, state_bytes=state_bytes, scratch_bytes=scratch_bytes) as manager:
        result, receipt = _advance(
            workspace, problem=problem, ticks=ticks, demand=demand,
            source_enabled=source_enabled, quiet=quiet, max_iterations=32,
            tolerance=None, device=requested_device, resources=manager,
        )
    receipt["device_requested"] = str(device)
    receipt["device_fallback_reason"] = None
    receipt["working_set_bytes"] = state_bytes + scratch_bytes
    receipt["solver"] = "restarted-matrix-free-gmres-float64"
    receipt["reservation"] = {
        "resident_bytes": state_bytes,
        "scratch_bytes": scratch_bytes,
        "transfer_bytes": state_bytes,
        "ram_transfer_bytes": state_bytes,
    }
    if manager is not None:
        receipt["resource_report"] = manager.report()
    return result, receipt


def advance_workspace_gpu_cohort(
    workspaces: Sequence[ResonantWorkspace],
    *,
    problem: ResonantProblem | None = None,
    ticks: int = 1,
    demand: float = 0.0,
    source_enabled: bool = True,
    quiet: bool = False,
    device: str = "cuda",
    resources: Any = None,
) -> tuple[tuple[ResonantWorkspace, ...], dict[str, Any]]:
    """Advance 1..8 compatible independent workspaces with column-batched GPU arithmetic.

    A cohort shares only fixed operator data. Dynamic state, clocks, activity,
    work ledgers, convergence and output pages remain per field. If the shared
    nonlinear transition cannot be accepted, the cohort is retried through the
    existing exact single-field GPU path and receipts identify that fallback.
    """
    if not isinstance(workspaces, Sequence) or isinstance(workspaces, (str, bytes)):
        raise TypeError("workspaces must be a sequence of ResonantWorkspace values")
    cohort = tuple(workspaces)
    if not 1 <= len(cohort) <= 8:
        raise ResonantNumericalError("GPU cohort capacity is [1,8] fields")
    if any(not isinstance(item, ResonantWorkspace) for item in cohort):
        raise TypeError("every cohort member must be ResonantWorkspace")
    if isinstance(ticks, bool) or not isinstance(ticks, int) or not 0 <= ticks <= 4096:
        raise ResonantNumericalError("ticks must be an integer in [0,4096]")
    if not math.isfinite(demand) or not 0 <= demand <= 1:
        raise ResonantNumericalError("ready demand must be finite and in [0,1]")
    if any(item.paused and ticks for item in cohort):
        raise ResonantNumericalError("paused workspace cannot advance")
    if device == "auto":
        raise ResonantNumericalError("GPU cohorts require an explicit GPU device; auto fallback is unsupported")
    try:
        if torch.device(device).type != "cuda":
            raise ResonantNumericalError("GPU cohorts require a CUDA-compatible device")
    except (TypeError, RuntimeError) as exc:
        raise ResonantNumericalError(f"invalid GPU device {device!r}") from exc
    first = bind_workspace(cohort[0], problem) if problem is not None else cohort[0]
    cohort = tuple(bind_workspace(item, problem) for item in cohort) if problem is not None else cohort
    signature = json.dumps(
        {"profile": first.profile.as_dict(), "bindings": _jsonable(first.bindings)},
        sort_keys=True, separators=(",", ":"), allow_nan=False,
    )
    if any(
        json.dumps({"profile": item.profile.as_dict(), "bindings": _jsonable(item.bindings)},
                   sort_keys=True, separators=(",", ":"), allow_nan=False) != signature
        for item in cohort
    ):
        raise ResonantNumericalError("GPU cohort fields must share profile, bindings, and operator")
    first.profile.gpu_profile(device)
    profile = first.profile
    tolerance = profile.tolerance
    state_bytes = 4 * profile.port_count * np.dtype(np.float64).itemsize * len(cohort)
    scratch_bytes = state_bytes * 10
    manager = _resource_manager(resources)
    # A one-field cohort deliberately uses the established single-field implementation.
    if len(cohort) == 1:
        result, receipt = advance_workspace_gpu(
            cohort[0], problem=None, ticks=ticks, demand=demand,
            source_enabled=source_enabled, quiet=quiet, device=device, resources=resources,
        )
        return (result,), {
            "schema": "cassifi.resonant-gpu-cohort-receipt.v1", "accepted": True,
            "capacity": 8, "field_count": 1, "device": str(torch.device(device)),
            "execution": "single-field-reference", "field_receipts": [receipt],
            "state_sha256": [result.state_sha256],
        }
    with _gpu_residency(manager, state_bytes=state_bytes, scratch_bytes=scratch_bytes):
        operator = _WaveOperator(first, problem, device=device, resources=manager)
        z = torch.as_tensor(
            np.stack([_state_vector(item) for item in cohort]).T,
            dtype=torch.float64, device=device,
        )
        batch_count = len(cohort)
        energies = operator.energy_gradient(z)[0]
        stored = [item.ledger.get("stored_energy") for item in cohort]
        stored_mask = torch.as_tensor([value is not None for value in stored], dtype=torch.bool, device=device)
        stored_values = torch.as_tensor([0.0 if value is None else float(value) for value in stored], dtype=torch.float64, device=device)
        start_energy = torch.where(stored_mask, stored_values, energies)
        parameter_work = energies - start_energy
        projected = operator.boundary(z, max(tolerance, 1e-10))
        boundary_work = operator.energy_gradient(projected)[0] - energies
        z = projected
        positive = torch.zeros(batch_count, dtype=torch.float64, device=device)
        extracted = torch.zeros_like(positive)
        dissipated = torch.zeros_like(positive)
        numerical = torch.zeros_like(positive)
        residual_work = torch.zeros_like(positive)
        max_residual = torch.zeros_like(positive)
        subdivisions = [0] * batch_count
        iterations = [0] * batch_count
        phases_h = [item.heartbeat_phase for item in cohort]
        phases_b = [item.breath_phase for item in cohort]
        heartbeat_cycles = [item.heartbeat_cycles for item in cohort]
        breath_cycles = [item.breath_cycles for item in cohort]
        activities = [item.activity for item in cohort]
        try:
            for _tick in range(ticks):
                rates = [0.5 + 1.5 * activities[i] + 0.25 * (1 + math.cos(phases_b[i])) for i in range(batch_count)]
                accepted = False
                for level in range(profile.max_subdivisions + 1):
                    parts = 2 ** level
                    trial = operator.clone(z)
                    local_positive = torch.zeros_like(positive)
                    local_extracted = torch.zeros_like(positive)
                    local_dissipated = torch.zeros_like(positive)
                    local_numerical = torch.zeros_like(positive)
                    local_residual = torch.zeros_like(positive)
                    local_max = torch.zeros_like(positive)
                    local_iterations = [0] * batch_count
                    sub_h = profile.time_step / parts
                    for sub in range(parts):
                        mids = [phases_h[i] + (sub + 0.5) * sub_h * profile.heartbeat_frequency for i in range(batch_count)]
                        phase1 = [phases_h[i] + (sub + 1) * sub_h * profile.heartbeat_frequency for i in range(batch_count)]
                        phase0 = [phases_h[i] + sub * sub_h * profile.heartbeat_frequency for i in range(batch_count)]
                        allowances = [
                            profile.heartbeat_work * (pulse_primitive(phase1[i]) - pulse_primitive(phase0[i]))
                            if source_enabled and not quiet else 0.0
                            for i in range(batch_count)
                        ]
                        trial_energy = operator.energy_gradient(trial)[0]
                        allowances = torch.minimum(
                            torch.as_tensor(allowances, dtype=torch.float64, device=device),
                            torch.clamp(1e12 - trial_energy, min=0.0),
                        )
                        requested = torch.as_tensor(
                            [sub_h * profile.heartbeat_amplitude * math.sin(mids[i]) ** 2 for i in range(batch_count)],
                            dtype=torch.float64, device=device,
                        )
                        directions = np.zeros((4 * profile.port_count, batch_count), dtype=np.float64)
                        n = profile.port_count
                        for i, midpoint in enumerate(mids):
                            directions[2*n, i] = directions[3*n-1, i] = math.cos(midpoint) / SQRT2
                            directions[2*n+1, i] = directions[3*n-2, i] = -math.sin(midpoint) / SQRT2
                        motor = operator.project(torch.as_tensor(directions, dtype=torch.float64, device=device))
                        mass_motor = operator.mass_apply(motor[2*n:])
                        momentum = trial[2*n:]
                        linear = (momentum * mass_motor).sum(dim=0)
                        quadratic = (motor[2*n:] * mass_motor).sum(dim=0)
                        root = torch.sqrt(torch.clamp(linear * linear + 2 * quadratic * allowances, min=0.0))
                        denom = torch.clamp(root + linear, min=torch.finfo(torch.float64).tiny)
                        limit = torch.where(linear >= 0, 2 * allowances / denom,
                                            (root - linear) / torch.clamp(quadratic, min=torch.finfo(torch.float64).tiny))
                        amount = torch.minimum(requested, torch.clamp(limit, min=0.0))
                        amount = torch.where((allowances > 0) & (quadratic > 0), amount, torch.zeros_like(amount))
                        work = linear * amount + 0.5 * quadratic * amount * amount
                        trial = trial + amount[None, :] * motor
                        local_positive += torch.clamp(work, min=0.0)
                        local_extracted += torch.clamp(-work, min=0.0)
                        durations = torch.as_tensor([sub_h * rates[i] for i in range(batch_count)], dtype=torch.float64, device=device)
                        trial, step_receipts = operator.step_batch(
                            trial, durations, quiet=quiet, max_iterations=32, tolerance=tolerance,
                        )
                        for i, step_receipt in enumerate(step_receipts):
                            local_dissipated[i] += step_receipt["dissipated_work"]
                            local_numerical[i] += step_receipt["numerical_dissipated_work"]
                            local_residual[i] += step_receipt["residual_work"]
                            local_max[i] = max(float(local_max[i].item()), step_receipt["residual_norm"])
                            local_iterations[i] += step_receipt["iterations"]
                    z = trial
                    positive += local_positive
                    extracted += local_extracted
                    dissipated += local_dissipated
                    numerical += local_numerical
                    residual_work += local_residual
                    max_residual = torch.maximum(max_residual, local_max)
                    for i in range(batch_count):
                        subdivisions[i] += parts - 1
                        iterations[i] += local_iterations[i]
                    accepted = True
                    break
                if not accepted:
                    raise ResonantNumericalError("unresolved numerical work after bounded subdivision rollback")
                h = profile.time_step
                for i in range(batch_count):
                    phases_h[i] += h * profile.heartbeat_frequency
                    phases_b[i] += h * profile.heartbeat_frequency * (1 / 16 + 3 * activities[i] / 16)
                    wraps_h, wraps_b = math.floor(phases_h[i] / (2 * math.pi)), math.floor(phases_b[i] / (2 * math.pi))
                    phases_h[i] -= wraps_h * 2 * math.pi
                    phases_b[i] -= wraps_b * 2 * math.pi
                    heartbeat_cycles[i] += wraps_h
                    breath_cycles[i] += wraps_b
                    activities[i] = demand + (activities[i] - demand) * math.exp(-h / profile.activity_tau)
        except (ResonantNumericalError, RuntimeError, np.linalg.LinAlgError):
            # A cohort that needs divergent rollback uses the established
            # single-field subdivision policy, never suppressing a failure.
            fallback_results, fallback_receipts = [], []
            for item in cohort:
                result, receipt = advance_workspace_gpu(
                    item, problem=None, ticks=ticks, demand=demand,
                    source_enabled=source_enabled, quiet=quiet, device=device, resources=None,
                )
                fallback_results.append(result)
                fallback_receipts.append(receipt)
            return tuple(fallback_results), {
                "schema": "cassifi.resonant-gpu-cohort-receipt.v1",
                "accepted": True, "capacity": 8, "field_count": batch_count,
                "device": str(torch.device(device)), "execution": "per-field-fallback",
                "fallback_reason": "cohort nonlinear solve or subdivision was not jointly admissible",
                "field_receipts": fallback_receipts,
                "state_sha256": [item.state_sha256 for item in fallback_results],
            }
        end_energy = operator.energy_gradient(z)[0]
        results: list[ResonantWorkspace] = []
        field_receipts: list[dict[str, Any]] = []
        scalar_arrays = [
            parameter_work.detach().cpu().tolist(), boundary_work.detach().cpu().tolist(),
            positive.detach().cpu().tolist(), extracted.detach().cpu().tolist(),
            dissipated.detach().cpu().tolist(), numerical.detach().cpu().tolist(),
            residual_work.detach().cpu().tolist(), max_residual.detach().cpu().tolist(),
            end_energy.detach().cpu().tolist(), z.detach().cpu().numpy(),
        ]
        for i, workspace in enumerate(cohort):
            parameter_i, boundary_i, pos_i, ext_i, diss_i, num_i, residual_i, max_i, end_i, _ = scalar_arrays
            defect = end_i[i] - float(start_energy[i].item()) - parameter_i[i] - boundary_i[i] - pos_i[i] + ext_i[i] + diss_i[i] + num_i[i] - residual_i[i]
            ledger = dict(workspace.ledger)
            increments = {
                "positive_heartbeat_work": pos_i[i], "extracted_heartbeat_work": ext_i[i],
                "dissipated_work": diss_i[i], "numerical_dissipated_work": num_i[i],
                "residual_work": residual_i[i], "parameter_work": parameter_i[i],
                "boundary_work": boundary_i[i], "balance_defect": defect,
            }
            ledger.update({key: ledger.get(key, 0.0) + value for key, value in increments.items()})
            ledger["stored_energy"] = end_i[i]
            page = _page_from_state(
                workspace, scalar_arrays[-1][:, i], heartbeat_phase=phases_h[i],
                breath_phase=phases_b[i], activity=activities[i],
            )
            result = workspace._copy(
                field_page=page, field_ticks=workspace.field_ticks + ticks,
                heartbeat_phase=phases_h[i], heartbeat_cycles=heartbeat_cycles[i],
                breath_phase=phases_b[i], breath_cycles=breath_cycles[i],
                activity=activities[i], ledger=ledger,
                subdivision_ticks=workspace.subdivision_ticks + subdivisions[i],
            )
            results.append(result)
            field_receipts.append({
                "schema": "cassifi.resonant-advance-receipt.v1", "accepted": True,
                "ticks": ticks, "field_ticks": result.field_ticks, "evidence_tick": result.evidence_tick,
                "start_energy": float(start_energy[i].item()), "end_energy": end_i[i],
                **increments, "maximum_residual_norm": max_i, "subdivisions": subdivisions[i],
                "nonlinear_iterations": iterations[i], "operator_applications": operator.applications,
                "arithmetic": "torch-batched-matrix-free-float64", "device": str(device),
                "state_sha256": result.state_sha256,
            })
    return tuple(results), {
        "schema": "cassifi.resonant-gpu-cohort-receipt.v1", "accepted": True,
        "capacity": 8, "field_count": len(cohort), "device": str(torch.device(device)),
        "execution": "column-batched-newton-gmres", "state_batch_shape": [4 * profile.port_count, len(cohort)],
        "successor_tolerance": {"absolute": 2e-12, "relative": 2e-12},
        "field_receipts": field_receipts, "state_sha256": [item.state_sha256 for item in results],
    }





 
# The regional lowering below intentionally does not decode or invoke
# ``ResonantWorkspace``.  It contains a disposable arithmetic view over the
# typed task words, and every cursor and accumulator that can affect a future
# result is part of that task.
REGIONAL_KERNEL_NAME = "numerical.resonant"
REGIONAL_KERNEL_MAX_WORK = 4096
REGIONAL_STATE_SCHEMA = "cassifi.regional-resonant-state.v1"
REGIONAL_RESULT_SCHEMA = "cassifi.regional-resonant-result.v1"

_REGIONAL_STATE_KEYS = frozenset({
    "schema", "profile", "wave_words", "bindings", "phases", "local_ticks",
    "subdivisions", "activity", "objective", "request", "continuation",
    "ledger", "paused", "phase", "result",
})
# The circulation segment is an optional overlay: a state that omits it stays
# byte-identical to the pre-circulation regional state.
_REGIONAL_OPTIONAL_STATE_KEYS = frozenset({"circulation"})
_REGIONAL_TOTAL_KEYS = (
    "positive_heartbeat_work", "extracted_heartbeat_work",
    "dissipated_work", "numerical_dissipated_work", "residual_work",
    "parameter_work", "boundary_work", "balance_defect",
    "interface_transfer_work", "circulation_parameter_work",
)
_REGIONAL_LOCAL_KEYS = (
    "positive_heartbeat_work", "extracted_heartbeat_work",
    "dissipated_work", "numerical_dissipated_work", "residual_work",
    "maximum_residual_norm", "nonlinear_iterations", "operator_applications",
    "parameter_work", "interface_transfer_work",
)


def _regional_canonical(value: Any) -> bytes:
    if isinstance(value, dict):
        sorted_dict = {k: value[k] for k in sorted(value.keys())}
        try:
            return json.dumps(sorted_dict, sort_keys=False, separators=(",", ":"),
                              ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (TypeError, ValueError, OverflowError, RecursionError) as exc:
            raise ResonantNumericalError("regional resonant state is not canonical JSON") from exc
    else:
        try:
            return json.dumps(value, sort_keys=True, separators=(",", ":"),
                              ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (TypeError, ValueError, OverflowError, RecursionError) as exc:
            raise ResonantNumericalError("regional resonant state is not canonical JSON") from exc


def _regional_integer(value: Any, name: str, *, minimum: int = 0,
                      maximum: int = 2**53 - 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ResonantNumericalError(f"{name} must be an exact integer")
    if value < minimum or value > maximum:
        raise ResonantNumericalError(f"{name} is outside its bounded range")
    return int(value)


def _regional_number(value: Any, name: str, *, minimum: float | None = None,
                     maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ResonantNumericalError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ResonantNumericalError(f"{name} must be finite")
    if minimum is not None and result < minimum:
        raise ResonantNumericalError(f"{name} is below its lower bound")
    if maximum is not None and result > maximum:
        raise ResonantNumericalError(f"{name} is above its upper bound")
    return result


def _regional_profile_data(value: Any = None) -> dict[str, Any]:
    if value is None:
        return ResonantProfile().as_dict()
    if isinstance(value, ResonantProfile):
        return value.as_dict()
    if not isinstance(value, Mapping):
        raise ResonantNumericalError("regional profile must be a ResonantProfile or mapping")
    fields = ResonantProfile.__dataclass_fields__
    try:
        profile = ResonantProfile(**{
            key: value[key] for key in fields if key in value and key != "layout_identity"
        })
    except (TypeError, ValueError) as exc:
        raise ResonantNumericalError("regional profile is invalid") from exc
    return profile.as_dict()


def _regional_objective_data(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, ResonantProblem):
        raw = {
            "variable_ids": list(value.variable_ids),
            "precision": value.precision.tolist(),
            "linear_b": value.linear_b.tolist(),
            "observed": dict(value.observed),
            "affine_constraints": None if value.affine_constraints is None else {
                "matrix": value.affine_constraints[0].tolist(),
                "rhs": value.affine_constraints[1].tolist(),
            },
            "dependency_sha256": value.dependency_sha256,
        }
    elif isinstance(value, Mapping):
        raw = dict(value)
    else:
        raise ResonantNumericalError("regional objective must be a ResonantProblem or mapping")
    allowed = {"variable_ids", "precision", "linear_b", "observed",
               "affine_constraints", "dependency_sha256"}
    if set(raw) - allowed:
        raise ResonantNumericalError("regional objective has unknown keys")
    ids = raw.get("variable_ids")
    if isinstance(ids, (str, bytes)) or not isinstance(ids, Sequence) or not ids:
        raise ResonantNumericalError("regional objective variable_ids are invalid")
    names = [str(item) for item in ids]
    if len(set(names)) != len(names):
        raise ResonantNumericalError("regional objective variable_ids are not unique")
    matrix = _as_f64(raw.get("precision"), (len(names), len(names)), "regional precision")
    if not np.allclose(matrix, matrix.T, atol=1e-12, rtol=0) or float(np.linalg.eigvalsh(matrix).min()) <= 0:
        raise ResonantNumericalError("regional precision must be positive definite")
    linear = _as_f64(raw.get("linear_b", np.zeros(len(names))), (len(names),), "regional linear_b")
    observed = raw.get("observed", {})
    if not isinstance(observed, Mapping):
        raise ResonantNumericalError("regional observed objective values are invalid")
    observed_value = {
        str(key): _regional_number(item, f"observed[{key}]")
        for key, item in observed.items()
    }
    constraints = raw.get("affine_constraints")
    if constraints is not None:
        if isinstance(constraints, Mapping):
            c_matrix = constraints.get("matrix", constraints.get("A"))
            c_rhs = constraints.get("rhs", constraints.get("b", []))
        elif isinstance(constraints, (tuple, list)) and len(constraints) == 2:
            c_matrix, c_rhs = constraints
        else:
            raise ResonantNumericalError("regional affine constraints are invalid")
        c_matrix = _as_f64(c_matrix, name="regional constraint matrix")
        c_rhs = _as_f64(c_rhs, name="regional constraint rhs").reshape(-1)
        if c_matrix.ndim != 2 or c_matrix.shape[1] != len(names) or c_matrix.shape[0] != len(c_rhs):
            raise ResonantNumericalError("regional affine constraints have incompatible shape")
        constraints = {"matrix": c_matrix.tolist(), "rhs": c_rhs.tolist()}
    dependency = raw.get("dependency_sha256", "")
    if dependency and (
        not isinstance(dependency, str) or len(dependency) != 64
        or any(char not in "0123456789abcdefABCDEF" for char in dependency)
    ):
        raise ResonantNumericalError("regional objective dependency digest is invalid")
    return {
        "variable_ids": names,
        "precision": matrix.tolist(),
        "linear_b": linear.tolist(),
        "observed": observed_value,
        "affine_constraints": constraints,
        "dependency_sha256": str(dependency),
    }


def _regional_bindings(value: Any, objective: Mapping[str, Any] | None,
                       profile: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    if value is None:
        result: dict[str, dict[str, Any]] = {}
    elif not isinstance(value, Mapping):
        raise ResonantNumericalError("regional bindings must be a mapping")
    else:
        result = {}
        for name, binding in value.items():
            if not isinstance(name, str) or not name or not isinstance(binding, Mapping):
                raise ResonantNumericalError("regional binding is invalid")
            result[name] = dict(binding)
    count = int(profile["pools"]) * int(profile["ports_per_pool"])
    occupied: set[int] = set()
    for name, binding in result.items():
        port = _regional_integer(binding.get("port"), f"binding {name}.port",
                                 maximum=count - 1)
        binding["port"] = port
        binding["pool"] = _regional_integer(
            binding.get("pool", port // int(profile["ports_per_pool"])),
            f"binding {name}.pool", maximum=int(profile["pools"]) - 1,
        )
        if port in occupied:
            raise ResonantNumericalError("regional bindings reuse a port")
        occupied.add(port)
        binding.setdefault("component", "common")
        binding.setdefault("binding_id", f"regional:{name}:common")
    if objective is not None:
        ports_per_pool = int(profile["ports_per_pool"])
        observed = objective["observed"]
        for name in objective["variable_ids"]:
            if name in result:
                continue
            hint = observed.get(f"{name}.__pool")
            preferred = (
                int(hint) if isinstance(hint, (int, float)) and not isinstance(hint, bool)
                and float(hint).is_integer() and 0 <= int(hint) < int(profile["pools"])
                else None
            )
            pools = list(range(int(profile["pools"])))
            if preferred is not None:
                pools.remove(preferred)
                pools.insert(0, preferred)
            pool = min(pools, key=lambda candidate: (
                sum(1 for port in occupied if candidate * ports_per_pool <= port < (candidate + 1) * ports_per_pool),
                candidate,
            ))
            choices = [
                pool * ports_per_pool + local
                for local in range(ports_per_pool)
                if pool * ports_per_pool + local not in occupied
            ]
            if not choices:
                raise ResonantNumericalError("regional objective has no free binding port")
            port = choices[0]
            occupied.add(port)
            result[name] = {
                "pool": pool, "port": port, "component": "common",
                "binding_id": f"regional:{name}:common",
            }
    return result


def _regional_coordinates(profile: Mapping[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    pools = int(profile["pools"])
    ports = int(profile["ports_per_pool"])
    rows: list[tuple[float, float, float]] = []
    for pool in range(pools):
        for local in range(ports):
            t = (pool + (local + 0.5) / ports) / pools
            angle = 2.0 * math.pi * t
            radius = 1.0 + 0.08 * math.sin(math.pi * t)
            rows.append((t, radius * math.cos(angle), radius * math.sin(angle)))
    original_rows = tuple(rows)
    rows.extend((t, -x, -y) for t, x, y in original_rows)
    coordinates = np.asarray(rows, dtype=np.float64)
    if profile["topology"] == "undivided":
        volumes = np.ones(2 * pools * ports, dtype=np.float64)
    else:
        base = np.asarray(
            [1.0 + 0.05 * ((i % ports) / max(1, ports - 1))
             for i in range(pools * ports)], dtype=np.float64
        )
        volumes = np.concatenate((base, base))
    return coordinates, volumes


def _regional_transport(profile: Mapping[str, Any]) -> np.ndarray:
    count = int(profile["pools"]) * int(profile["ports_per_pool"])
    full = 2 * count
    projected = profile.get("projected_transport")
    if projected is not None:
        return _as_f64(projected, (full, full), "regional transport").copy()
    coordinates, volumes = _regional_coordinates(profile)
    pools, ports = int(profile["pools"]), int(profile["ports_per_pool"])
    circuit = list(range(count)) + list(range(2 * count - 1, count - 1, -1))
    edges: list[tuple[int, int, float, str]] = []
    seen: set[tuple[int, int, str]] = set()
    coupling = float(profile["coupling"])
    topology = profile["topology"]

    def add(source: int, destination: int, kind: str, scale: float = 1.0) -> None:
        key = (source, destination, kind)
        if source == destination or key in seen:
            return
        seen.add(key)
        distance = max(float(np.linalg.norm(coordinates[destination] - coordinates[source])), 1e-12)
        weight = coupling * scale / (distance * math.sqrt(volumes[source] * volumes[destination]))
        edges.append((source, destination, weight, kind))

    if topology != "isolated":
        for source, destination in zip(circuit, circuit[1:] + circuit[:1]):
            add(source, destination, "circuit")
    for pool in range(pools):
        start = pool * ports
        for local in range(ports - 1):
            add(start + local, start + local + 1, "intra", 0.5)
        add(start, start + ports - 1, "intra", 0.35)
    if topology != "isolated":
        for pool in range(pools - 1):
            add(pool * ports + ports - 1, (pool + 1) * ports, "neck", 0.7)
    if topology == "rewired":
        circuit_edges = [row for row in edges if row[3] == "circuit"]
        others = [row for row in edges if row[3] != "circuit"]
        destinations = [row[1] for row in circuit_edges]
        edges = others + [
            (source, destinations[(index + 7) % len(destinations)], weight, kind)
            for index, (source, _destination, weight, kind) in enumerate(circuit_edges)
        ]
        edges = [row for row in edges if row[0] != row[1]]
    transport = np.zeros((full, full), dtype=np.float64)
    for source, destination, weight, _kind in edges:
        transport[destination, source] += weight
        transport[source, destination] -= weight
    return transport


class _RegionalWaveOperator:
    """Disposable direct arithmetic view used by one regional kernel call."""

    def __init__(self, profile: Mapping[str, Any], bindings: Mapping[str, Any],
                 objective: Mapping[str, Any] | None, *, device: str | None = None,
                 resources: Any = None) -> None:
        self.device = device
        self.resources = resources
        if device is not None:
            try:
                if str(device).startswith("cuda") and not torch.cuda.is_available():
                    raise ResonantDeviceUnavailableError(
                        f"requested device {device!r} is unavailable"
                    )
                torch.empty((1,), dtype=torch.float64, device=device)
            except ResonantDeviceUnavailableError:
                raise
            except Exception as exc:
                raise ResonantDeviceUnavailableError(
                    f"requested device {device!r} is unavailable"
                ) from exc
        self._resource_tokens: list[Any] = []
        if device is not None and str(device).startswith("cuda") and resources is not None:
            manager = _resource_manager(resources)
            state_bytes = 4 * int(profile["pools"]) * int(profile["ports_per_pool"]) * 8
            for tier, amount, kind in (
                ("vram", state_bytes, "resident"),
                ("vram", state_bytes * 2, "scratch"),
                ("vram", state_bytes, "transfer"),
                ("ram", state_bytes, "transfer"),
            ):
                token = manager.reserve(tier, max(1, amount), kind=kind)
                token.__enter__()
                self._resource_tokens.append(token)
        self.profile = profile
        self.n = int(profile["pools"]) * int(profile["ports_per_pool"])
        self.transport = _regional_transport(profile)
        raw_mass = profile.get("projected_inv_mass")
        if raw_mass is None:
            if profile["topology"] == "undivided":
                inertances = np.ones(2 * self.n, dtype=np.float64)
            else:
                p = int(profile["ports_per_pool"])
                inertances = np.asarray(
                    [1.3 ** pool for pool in range(int(profile["pools"])) for _ in range(p)] * 2,
                    dtype=np.float64,
                )
            self.inv_mass = 1.0 / inertances
        else:
            self.inv_mass = _as_f64(raw_mass, name="regional inverse mass")
        if self.inv_mass.ndim == 2:
            self.mass = np.linalg.inv(self.inv_mass)
        else:
            if self.inv_mass.shape != (2 * self.n,):
                raise ResonantNumericalError("regional inverse mass has invalid shape")
            self.mass = 1.0 / self.inv_mass
        weights = profile.get("projected_quartic_weights")
        self.beta = float(profile["beta"]) * (
            np.ones(self.n, dtype=np.float64)
            if weights is None else _as_f64(weights, (self.n,), "regional quartic weights")
        )
        self.bindings = bindings
        self.objective = objective
        self.ports = np.empty(0, dtype=np.int64)
        self.k = np.empty((0, 0), dtype=np.float64)
        self.b = np.empty(0, dtype=np.float64)
        self.conditioner = np.empty((0, 0), dtype=np.float64)
        self.constraints = np.empty((0, 4 * self.n), dtype=np.float64)
        self.targets = np.empty(0, dtype=np.float64)
        if objective is not None:
            self.ports = np.asarray(
                [int(bindings[name]["port"]) for name in objective["variable_ids"]],
                dtype=np.int64,
            )
            self.k = _as_f64(objective["precision"], (len(self.ports), len(self.ports)),
                             "regional objective precision")
            self.b = _as_f64(objective["linear_b"], (len(self.ports),), "regional objective linear_b")
            common_rows: list[np.ndarray] = []
            targets: list[float] = []
            names = objective["variable_ids"]
            for name, target in objective["observed"].items():
                if name not in names:
                    continue
                row = np.zeros(len(names), dtype=np.float64)
                row[names.index(name)] = 1.0
                common_rows.append(row)
                targets.append(float(target))
            affine = objective.get("affine_constraints")
            if affine is not None:
                matrix = _as_f64(affine["matrix"], name="regional constraint matrix")
                common_rows.extend(matrix)
                targets.extend(_as_f64(affine["rhs"], name="regional constraint rhs").tolist())
            rows: list[np.ndarray] = []
            for row in common_rows:
                full_row = np.zeros(4 * self.n, dtype=np.float64)
                full_row[self.ports] = row / SQRT2
                full_row[self.ports + self.n] = row / SQRT2
                rows.append(full_row)
            if common_rows:
                common = np.asarray(common_rows, dtype=np.float64)
                _, singular, vh = np.linalg.svd(common, full_matrices=True)
                threshold = max(common.shape) * np.finfo(float).eps * float(singular.max(initial=0.0))
                rank = int(np.count_nonzero(singular > threshold))
                tangent = vh[rank:].T
                reduced = tangent.T @ self.k @ tangent
                self.conditioner = (
                    tangent @ np.linalg.solve(reduced, tangent.T)
                    if tangent.shape[1] else np.zeros_like(self.k)
                )
                rows.extend([
                    np.concatenate((np.zeros(2 * self.n), row[:2 * self.n]))
                    for row in rows
                ])
                targets.extend([0.0] * len(common_rows))
            else:
                self.conditioner = np.linalg.solve(self.k, np.eye(len(self.ports)))
            self.constraints = np.asarray(rows, dtype=np.float64).reshape((-1, 4 * self.n))
            self.targets = np.asarray(targets, dtype=np.float64)
        self.constraint_inverse = (
            np.linalg.pinv(self.constraints)
            if len(self.targets) else np.zeros((4 * self.n, 0), dtype=np.float64)
        )
        rail_bound = float(np.linalg.norm(self.transport, ord=np.inf))
        condition_bound = float(np.linalg.norm(self.conditioner, ord=np.inf)) if objective is not None else 1.0
        mass_bound = float(np.linalg.norm(self.mass, ord=np.inf)) if self.mass.ndim == 2 else float(np.max(self.mass))
        damping_bound = max(
            float(profile["damping"]),
            2 * float(profile["quiet_damping"]) * max(
                condition_bound, mass_bound, 1.0 / max(float(profile["relative_stiffness"]), 1e-6)
            ),
        )
        projection_bound = (
            1.0 + float(np.linalg.norm(self.constraint_inverse, ord=np.inf)
                        * np.linalg.norm(self.constraints, ord=np.inf))
            if len(self.targets) else 1.0
        )
        self.flow_roundoff_gain = projection_bound ** 2 * (1.0 + rail_bound + damping_bound)
        self.absolute_k = abs(self.k)
        self.absolute_b = abs(self.b)
        self.absolute_inv_mass = abs(self.inv_mass)
        self.applications = 0

    def close(self) -> None:
        for token in reversed(self._resource_tokens):
            token.__exit__(None, None, None)
        self._resource_tokens.clear()

    @staticmethod
    def _multiply(matrix: np.ndarray, value: np.ndarray) -> np.ndarray:
        return matrix.reshape((-1,) + (1,) * (value.ndim - 1)) * value if matrix.ndim == 1 else matrix @ value

    def mass_apply(self, value: np.ndarray, *, inverse: bool = True) -> np.ndarray:
        return self._multiply(self.inv_mass if inverse else self.mass, value)

    def semantic(self, value: np.ndarray, *, force: bool = True) -> np.ndarray:
        result = value.copy()
        if len(self.ports):
            result[self.ports] = self.k @ value[self.ports]
            if force:
                result[self.ports] -= self.b
        return result

    def project(self, value: np.ndarray) -> np.ndarray:
        if not len(self.targets):
            return value
        return value - self.constraint_inverse @ (self.constraints @ value)

    def boundary(self, value: np.ndarray, tolerance: float) -> np.ndarray:
        if not len(self.targets):
            return value
        result = value + self.constraint_inverse @ (self.targets - self.constraints @ value)
        if float(np.max(np.abs(self.constraints @ result - self.targets), initial=0.0)) > tolerance:
            raise ResonantNumericalError("regional constraints are inconsistent")
        return result

    def rail(self, value: np.ndarray) -> np.ndarray:
        return self.transport @ value

    def circulation(self, gradient: np.ndarray) -> np.ndarray:
        q, p = gradient[:2 * self.n], gradient[2 * self.n:]
        return np.concatenate((self.rail(q) + p, -q + self.rail(p)))

    def dissipation(self, gradient: np.ndarray, quiet: bool) -> np.ndarray:
        if not quiet:
            return float(self.profile["damping"]) * gradient
        qy, qi, py, pi = gradient.reshape(4, self.n)
        common, relative = (qy + qi) / SQRT2, (qy - qi) / SQRT2
        if len(self.ports):
            common = common.copy()
            common[self.ports] = self.conditioner @ common[self.ports]
        relative = relative / max(float(self.profile["relative_stiffness"]), 1e-6)
        return float(self.profile["quiet_damping"]) * np.concatenate((
            (common + relative) / SQRT2,
            (common - relative) / SQRT2,
            self.mass_apply(np.concatenate((py, pi)), inverse=False),
        ))

    def flow(self, gradient: np.ndarray, quiet: bool) -> np.ndarray:
        self.applications += 1
        return self.project(self.circulation(self.project(gradient)) - self.dissipation(self.project(gradient), quiet))

    def energy_gradient(self, value: np.ndarray) -> tuple[float, np.ndarray]:
        qy, qi, py, pi = value.reshape(4, self.n)
        common, relative_coordinate = (qy + qi) / SQRT2, (qy - qi) / SQRT2
        semantic = self.semantic(common)
        relative = float(self.profile["relative_stiffness"]) * relative_coordinate + self.beta * relative_coordinate ** 3
        momentum = np.concatenate((py, pi))
        kinetic_gradient = self.mass_apply(momentum)
        energy = 0.5 * float(common @ self.semantic(common, force=False))
        energy += 0.5 * float(self.profile["relative_stiffness"]) * float(relative_coordinate @ relative_coordinate)
        energy += float((self.beta * relative_coordinate ** 4).sum()) / 4.0
        energy += 0.5 * float(momentum @ kinetic_gradient)
        if len(self.ports):
            energy -= float(self.b @ common[self.ports])
        return energy, np.concatenate(((semantic + relative) / SQRT2, (semantic - relative) / SQRT2, kinetic_gradient))

    def roundoff_scales(self, value: np.ndarray) -> tuple[float, float]:
        qy, qi, py, pi = abs(value).reshape(4, self.n)
        common = (qy + qi) / SQRT2
        semantic = common.copy()
        if len(self.ports):
            semantic[self.ports] = self.absolute_k @ common[self.ports] + self.absolute_b
        relative = float(self.profile["relative_stiffness"]) * common + self.beta * common ** 3
        momentum = np.concatenate((py, pi))
        kinetic = self._multiply(self.absolute_inv_mass, momentum)
        magnitude = np.concatenate(((semantic + relative) / SQRT2,
                                    (semantic + relative) / SQRT2, kinetic))
        return float(np.max(np.abs(magnitude), initial=0.0)), float(abs(value) @ magnitude)

    def discrete_gradient(self, before: np.ndarray, after: np.ndarray) -> np.ndarray:
        qy0, qi0, py0, pi0 = before.reshape(4, self.n)
        qy1, qi1, py1, pi1 = after.reshape(4, self.n)
        common = (qy0 + qi0 + qy1 + qi1) / (2 * SQRT2)
        d0, d1 = (qy0 - qi0) / SQRT2, (qy1 - qi1) / SQRT2
        semantic = self.semantic(common)
        relative = float(self.profile["relative_stiffness"]) * (d0 + d1) / 2.0
        relative += self.beta * (d1 ** 3 + d1 ** 2 * d0 + d1 * d0 ** 2 + d0 ** 3) / 4.0
        return np.concatenate(((semantic + relative) / SQRT2,
                               (semantic - relative) / SQRT2,
                               self.mass_apply(np.concatenate((py0 + py1, pi0 + pi1))) / 2.0))

    def derivative(self, before: np.ndarray, after: np.ndarray, value: np.ndarray,
                   quiet: bool) -> np.ndarray:
        qy, qi, py, pi = value.reshape((4, self.n))
        common, relative_coordinate = (qy + qi) / SQRT2, (qy - qi) / SQRT2
        qy0, qi0 = before[:self.n], before[self.n:2 * self.n]
        qy1, qi1 = after[:self.n], after[self.n:2 * self.n]
        d0, d1 = (qy0 - qi0) / SQRT2, (qy1 - qi1) / SQRT2
        if quiet:
            factor = 1.0
            relative = float(self.profile["relative_stiffness"]) + 3 * self.beta * d1 ** 2
        else:
            factor = 0.5
            relative = float(self.profile["relative_stiffness"]) / 2.0 + self.beta * (
                3 * d1 ** 2 + 2 * d1 * d0 + d0 ** 2
            ) / 4.0
        semantic = factor * self.semantic(common, force=False)
        return np.concatenate(((semantic + self._multiply(relative, relative_coordinate)) / SQRT2,
                               (semantic - self._multiply(relative, relative_coordinate)) / SQRT2,
                               factor * self.mass_apply(np.concatenate((py, pi)))))

    def step(self, before: np.ndarray, duration: float, *, quiet: bool,
             max_iterations: int, tolerance: float) -> tuple[np.ndarray, dict[str, float]]:
        candidate = before.copy()
        eps = np.finfo(float).eps
        atol_inner = tolerance * 0.05
        rtol_inner = 1e-10
        sqrt2 = math.sqrt(2.0)

        # Precompute scalar bounds for residual check (done once per outer iteration)
        before_max = float(np.max(np.abs(before), initial=0.0))
        duration_max = float(duration)

        for iteration in range(max_iterations):
            # Compute gradient: avoid tuple unpacking overhead
            if quiet:
                gradient = self.energy_gradient(candidate)[1]
            else:
                gradient = self.discrete_gradient(before, candidate)

            flow = self.flow(gradient, quiet)

            # Vectorized residual calculation
            residual = candidate - before - duration * flow

            # Compute rounding threshold efficiently using precomputed scalars
            cand_max = float(np.max(np.abs(candidate), initial=0.0))
            flow_max = float(np.max(np.abs(flow), initial=0.0))
            flow_roundoff = self.flow_roundoff_gain * self.roundoff_scales(candidate)[0]
            rounding = 64.0 * eps * (cand_max + before_max + duration_max * max(flow_max, flow_roundoff))

            # Early exit if converged
            if float(np.max(np.abs(residual), initial=0.0)) <= max(tolerance, rounding):
                break

            # Define Jacobian application directly
            def jacobian(value):
                return value - duration * self.flow(self.derivative(before, candidate, value, quiet), quiet)

            if self.device is None:
                operator = LinearOperator((len(before), len(before)), matvec=jacobian, dtype=np.float64)
                delta, info = gmres(operator, residual, atol=atol_inner, rtol=rtol_inner,
                                    restart=min(32, len(before)), maxiter=8)
                if info != 0:
                    raise ResonantNumericalError("regional nonlinear solve exhausted")
            else:
                # GPU
                def gpu_jacobian(value):
                    cpu_value = value.detach().cpu().numpy()
                    return torch.as_tensor(jacobian(cpu_value), dtype=torch.float64, device=self.device)
                delta_device, gmres_residual, _applications = _torch_gmres(
                    gpu_jacobian,
                    torch.as_tensor(residual, dtype=torch.float64, device=self.device),
                    tolerance=tolerance, restart=min(8, len(before)), max_restarts=8,
                )
                if gmres_residual > max(tolerance * 0.05, 1e-11):
                    raise ResonantNumericalError("regional GPU matrix-free Newton solve exhausted")
                delta = delta_device.cpu().numpy()

            candidate -= delta

        else:
            raise ResonantNumericalError("regional nonlinear solve exhausted")

        start_energy = self.energy_gradient(before)[0]
        end_energy = self.energy_gradient(candidate)[0]
        projected_gradient = self.project(gradient)
        dissipated = float(duration * (projected_gradient @ self.dissipation(projected_gradient, quiet)))
        numerical = float((gradient - self.discrete_gradient(before, candidate)) @ (candidate - before)) if quiet else 0.0
        residual_work = float(gradient @ residual)
        defect = end_energy - start_energy + dissipated + numerical - residual_work
        allowance = max(
            1e-10,
            64 * np.finfo(float).eps * max(
                1.0, self.roundoff_scales(before)[1], self.roundoff_scales(candidate)[1]
            ),
        )
        if not math.isfinite(defect) or abs(defect) > allowance or numerical < -allowance:
            raise ResonantNumericalError("regional transition violates its work balance")
        return candidate, {
            "dissipated_work": dissipated,
            "numerical_dissipated_work": max(0.0, numerical),
            "energy_roundoff_allowance": allowance,
            "residual_work": residual_work,
            "balance_defect": defect,
            "residual_norm": float(np.max(np.abs(residual), initial=0.0)),
            "iterations": float(iteration + 1),
            "operator_applications": float(self.applications),
        }

    def kick(self, before: np.ndarray, phase: float, requested: float,
             allowance: float) -> tuple[np.ndarray, float]:
        if allowance <= 0.0 or requested <= 0.0:
            return before.copy(), 0.0
        direction = np.zeros(4 * self.n, dtype=np.float64)
        direction[2 * self.n] = direction[3 * self.n - 1] = math.cos(phase) / SQRT2
        direction[2 * self.n + 1] = direction[3 * self.n - 2] = -math.sin(phase) / SQRT2
        direction = self.project(direction)
        mass_direction = self.mass_apply(direction[2 * self.n:])
        linear = float(before[2 * self.n:] @ mass_direction)
        quadratic = float(direction[2 * self.n:] @ mass_direction)
        if quadratic <= 0.0:
            return before.copy(), 0.0
        root = math.sqrt(linear * linear + 2.0 * quadratic * allowance)
        amount = (
            2.0 * allowance / (root + linear)
            if linear >= 0.0 else (root - linear) / quadratic
        )
        return before + amount * direction, linear * amount + 0.5 * quadratic * amount * amount


def _regional_zero_accumulator() -> dict[str, float]:
    return {key: 0.0 for key in _REGIONAL_LOCAL_KEYS}


def _regional_validate_state(state: Any) -> None:
    if not isinstance(state, Mapping) or not (
        _REGIONAL_STATE_KEYS <= set(state) <= _REGIONAL_STATE_KEYS | _REGIONAL_OPTIONAL_STATE_KEYS
    ):
        raise ResonantNumericalError("regional resonant state keys are invalid")
    if state["schema"] != REGIONAL_STATE_SCHEMA:
        raise ResonantNumericalError("regional resonant state schema is invalid")
    _regional_canonical(state)
    profile = _regional_profile_data(state["profile"])
    count = int(profile["pools"]) * int(profile["ports_per_pool"])
    words = state["wave_words"]
    if not isinstance(words, Mapping) or set(words) != {"layout", "values"} or words["layout"] != "qY,qI,pY,pI:f64":
        raise ResonantNumericalError("regional wave words are invalid")
    values = _as_f64(words["values"], (4 * count,), "regional wave words")
    del values
    bindings = _regional_bindings(state["bindings"], _regional_objective_data(state["objective"]), profile)
    del bindings
    phases = state["phases"]
    if not isinstance(phases, Mapping) or set(phases) != {"heartbeat", "breath", "heartbeat_cycles", "breath_cycles"}:
        raise ResonantNumericalError("regional resonant phases are invalid")
    _regional_number(phases["heartbeat"], "heartbeat phase")
    _regional_number(phases["breath"], "breath phase")
    _regional_integer(phases["heartbeat_cycles"], "heartbeat cycles")
    _regional_integer(phases["breath_cycles"], "breath cycles")
    ticks = state["local_ticks"]
    if not isinstance(ticks, Mapping) or set(ticks) != {"field", "evidence"}:
        raise ResonantNumericalError("regional local ticks are invalid")
    _regional_integer(ticks["field"], "field tick")
    _regional_integer(ticks["evidence"], "evidence tick")
    _regional_integer(state["subdivisions"], "subdivision ticks")
    _regional_number(state["activity"], "activity", minimum=0.0, maximum=1.0)
    request = state["request"]
    if not isinstance(request, Mapping) or set(request) != {
        "operation", "ticks", "demand", "source_enabled", "quiet",
        "max_iterations", "tolerance", "impulse",
    }:
        raise ResonantNumericalError("regional resonant request is invalid")
    if request["operation"] not in {"advance", "impulse", "packet-impulse", "circulate"}:
        raise ResonantNumericalError("regional resonant request operation is invalid")
    _regional_integer(request["ticks"], "requested ticks", maximum=4096)
    _regional_number(request["demand"], "requested demand", minimum=0.0, maximum=1.0)
    _regional_integer(request["max_iterations"], "regional nonlinear iterations", minimum=1, maximum=512)
    if request["tolerance"] is not None:
        tolerance_value = _regional_number(request["tolerance"], "regional tolerance")
        if tolerance_value <= 0.0:
            raise ResonantNumericalError("regional tolerance must be positive")
    if not isinstance(request["source_enabled"], bool) or not isinstance(request["quiet"], bool):
        raise ResonantNumericalError("regional request flags are invalid")
    objective = _regional_objective_data(state["objective"])
    if objective is not None:
        for name in objective["observed"]:
            if name.endswith(".__pool"):
                continue
            if name not in objective["variable_ids"]:
                raise ResonantNumericalError("regional observed objective has an unknown variable")
    continuation = state["continuation"]
    if not isinstance(continuation, Mapping) or set(continuation) != {
        "tick", "level", "parts", "substep", "operation", "initialized",
        "base_wave_words", "trial_wave_words", "local", "totals",
        "start_energy", "recorded_start_energy",
    }:
        raise ResonantNumericalError("regional integration continuation is invalid")
    _regional_integer(continuation["tick"], "regional tick cursor", maximum=4096)
    _regional_integer(continuation["level"], "regional subdivision level", maximum=20)
    _regional_integer(continuation["parts"], "regional subdivision parts", minimum=1, maximum=2**20)
    _regional_integer(continuation["substep"], "regional substep cursor", maximum=2**20)
    if continuation["operation"] not in {"prepare", "kick", "step"}:
        raise ResonantNumericalError("regional integration operation is invalid")
    if not isinstance(continuation["initialized"], bool):
        raise ResonantNumericalError("regional integration initialization flag is invalid")
    for key in ("base_wave_words", "trial_wave_words"):
        raw = continuation[key]
        if raw is not None:
            _as_f64(raw, (4 * count,), f"regional {key}")
    for name in ("local", "totals"):
        value = continuation[name]
        if not isinstance(value, Mapping):
            raise ResonantNumericalError(f"regional {name} accumulator is invalid")
        expected = set(_REGIONAL_LOCAL_KEYS) if name == "local" else set(_REGIONAL_TOTAL_KEYS) | {"subdivisions", "operator_applications", "failed_attempts", "maximum_residual_norm", "nonlinear_iterations"}
        if set(value) != expected:
            raise ResonantNumericalError(f"regional {name} accumulator keys are invalid")
        nonnegative = {
            "positive_heartbeat_work", "extracted_heartbeat_work",
            "dissipated_work", "numerical_dissipated_work",
            "maximum_residual_norm", "nonlinear_iterations",
            "operator_applications", "subdivisions", "failed_attempts",
        }
        for key, number in value.items():
            _regional_number(
                number,
                f"{name}.{key}",
                minimum=0.0 if key in nonnegative else None,
            )
    if not isinstance(state["ledger"], Mapping):
        raise ResonantNumericalError("regional resonant ledger is invalid")
    for key, number in state["ledger"].items():
        _regional_number(number, f"ledger.{key}")
    if not isinstance(state["paused"], bool):
        raise ResonantNumericalError("regional paused flag is invalid")
    if state["phase"] not in {"running", "done", "fault"}:
        raise ResonantNumericalError("regional resonant phase is invalid")
    if state["phase"] == "running" and state["result"] is not None:
        raise ResonantNumericalError("running regional state has a result")
    if state["phase"] in {"done", "fault"} and not isinstance(state["result"], Mapping):
        raise ResonantNumericalError("terminal regional state has no result")
    if "circulation" in state:
        from cassi_circulation import validate_circulation
        validate_circulation(state["circulation"])


def regional_state(
    source: ResonantWorkspace | ResonantProfile | Mapping[str, Any] | None = None,
    *,
    profile: ResonantProfile | Mapping[str, Any] | None = None,
    problem: ResonantProblem | Mapping[str, Any] | None = None,
    objective: ResonantProblem | Mapping[str, Any] | None = None,
    bindings: Mapping[str, Any] | None = None,
    ticks: int = 1,
    demand: float = 0.0,
    source_enabled: bool = True,
    quiet: bool = False,
    max_iterations: int = 32,
    tolerance: float | None = None,
    impulse: Mapping[str, Any] | None = None,
    packet_impulse: Mapping[str, Any] | None = None,
    circulation: bool | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Lower one resonant task into JSON-safe regional data.

    ``circulation`` declares the optional circulation overlay.  ``None`` (the
    default) leaves the state byte-identical to a state without it; ``True``
    builds a fresh enabled segment over this state's wave words, so the field
    machine runs one bounded circulation unit as each tick completes;
    a mapping is carried as the caller's own segment after validation.
    """
    workspace: ResonantWorkspace | None = source if isinstance(source, ResonantWorkspace) else None
    if workspace is not None:
        selected_profile = _regional_profile_data(workspace.profile)
        if _active_parent_register_paths(workspace._field, workspace.profile.port_count):
            raise ResonantNumericalError(
                "regional serialization rejects an active parent register map"
            )
        words = _state_vector(workspace).tolist()
        selected_bindings = _jsonable(workspace.bindings)
        phases = {
            "heartbeat": workspace.heartbeat_phase,
            "breath": workspace.breath_phase,
            "heartbeat_cycles": workspace.heartbeat_cycles,
            "breath_cycles": workspace.breath_cycles,
        }
        local_ticks = {"field": workspace.field_ticks, "evidence": workspace.evidence_tick}
        selected_subdivisions = workspace.subdivision_ticks
        selected_activity = workspace.activity
        selected_ledger = dict(workspace.ledger)
        paused = workspace.paused
    else:
        selected_profile = _regional_profile_data(
            profile if profile is not None else (
                source if isinstance(source, (ResonantProfile, Mapping)) else None
            )
        )
        count = int(selected_profile["pools"]) * int(selected_profile["ports_per_pool"])
        words = [0.0] * (4 * count)
        selected_bindings = {}
        phases = {"heartbeat": 0.0, "breath": 0.0, "heartbeat_cycles": 0, "breath_cycles": 0}
        local_ticks = {"field": 0, "evidence": 0}
        selected_subdivisions = 0
        selected_activity = 0.0
        selected_ledger = {}
        paused = False
    selected_objective = _regional_objective_data(
        problem if problem is not None else objective
    )
    selected_bindings = _regional_bindings(bindings if bindings is not None else selected_bindings,
                                           selected_objective, selected_profile)
    selected_ticks = _regional_integer(ticks, "ticks", maximum=4096)
    selected_demand = _regional_number(demand, "demand", minimum=0.0, maximum=1.0)
    selected_iterations = _regional_integer(max_iterations, "max_iterations", minimum=1, maximum=512)
    selected_tolerance = (
        None if tolerance is None else _regional_number(tolerance, "tolerance", minimum=0.0)
    )
    if impulse is not None and packet_impulse is not None:
        raise ResonantNumericalError(
            "regional state accepts either a pool impulse or a packet impulse"
        )
    request_operation = (
        "packet-impulse"
        if packet_impulse is not None
        else "impulse" if impulse is not None else "advance"
    )
    selected_impulse = (
        dict(packet_impulse)
        if packet_impulse is not None
        else None if impulse is None else dict(impulse)
    )
    operator = _RegionalWaveOperator(selected_profile, selected_bindings, selected_objective)
    current_energy = operator.energy_gradient(np.asarray(words, dtype=np.float64))[0]
    ledger = {
        "positive_heartbeat_work": 0.0,
        "extracted_heartbeat_work": 0.0,
        "dissipated_work": 0.0,
        "interface_transfer_work": 0.0,
        "numerical_dissipated_work": 0.0,
        "residual_work": 0.0,
        "parameter_work": 0.0,
        "boundary_work": 0.0,
        "balance_defect": 0.0,
        "logical_work": 0.0,
        "operator_applications": 0.0,
        "stored_energy": 0.0,
        **{str(key): float(value) for key, value in selected_ledger.items()},
    }
    if "stored_energy" not in selected_ledger:
        ledger["stored_energy"] = float(current_energy)
    continuation = {
        "tick": 0, "level": 0, "parts": 1, "substep": 0, "operation": "prepare",
        "initialized": False, "base_wave_words": None, "trial_wave_words": None,
        "local": _regional_zero_accumulator(),
        "totals": {
            **{key: 0.0 for key in _REGIONAL_TOTAL_KEYS},
            "subdivisions": 0.0, "operator_applications": 0.0,
            "failed_attempts": 0.0, "maximum_residual_norm": 0.0,
            "nonlinear_iterations": 0.0,
        },
        "start_energy": 0.0, "recorded_start_energy": 0.0,
    }
    state = {
        "schema": REGIONAL_STATE_SCHEMA,
        "profile": selected_profile,
        "wave_words": {"layout": "qY,qI,pY,pI:f64", "values": words},
        "bindings": selected_bindings,
        "phases": phases,
        "local_ticks": local_ticks,
        "subdivisions": int(selected_subdivisions),
        "activity": float(selected_activity),
        "objective": selected_objective,
        "request": {
            "operation": request_operation, "ticks": selected_ticks,
            "demand": selected_demand, "source_enabled": bool(source_enabled),
            "quiet": bool(quiet), "max_iterations": selected_iterations,
            "tolerance": selected_tolerance, "impulse": selected_impulse,
        },
        "continuation": continuation, "ledger": ledger, "paused": bool(paused),
        "phase": "running", "result": None,
    }
    if circulation is not None:
        if isinstance(circulation, bool):
            if circulation:
                from cassi_circulation import initial_circulation
                state["circulation"] = initial_circulation(
                    selected_profile, enabled=True, words=list(words),
                )
        else:
            from cassi_circulation import validate_circulation
            segment = json.loads(_regional_canonical(dict(circulation)).decode("utf-8"))
            validate_circulation(segment)
            state["circulation"] = segment
    state = json.loads(_regional_canonical(state).decode("utf-8"))
    _regional_validate_state(state)
    return state


def workspace_from_regional_state(
    source: Mapping[str, Any],
    *,
    require_complete: bool = False,
) -> ResonantWorkspace:
    """Decode the complete owned workspace carried by a regional task."""

    if not isinstance(source, Mapping):
        raise ResonantNumericalError("regional successor must be a mapping")
    current = json.loads(_regional_canonical(dict(source)).decode("utf-8"))
    _regional_validate_state(current)
    if require_complete and current["phase"] != "done":
        raise ResonantNumericalError(
            "regional successor has not completed its current operation"
        )
    profile_data = dict(current["profile"])
    profile_data.pop("layout_identity", None)
    profile = ResonantProfile(
        **{
            name: profile_data[name]
            for name in ResonantProfile.__dataclass_fields__
            if name in profile_data
        }
    )
    seed = ResonantWorkspace(profile=profile)
    words = _as_f64(
        current["wave_words"]["values"],
        (4 * profile.port_count,),
        "regional successor wave words",
    )
    page = _page_from_state(
        seed,
        words,
        heartbeat_phase=float(current["phases"]["heartbeat"]),
        breath_phase=float(current["phases"]["breath"]),
        activity=float(current["activity"]),
    )
    return ResonantWorkspace(
        profile=profile,
        field_page=page,
        bindings=current["bindings"],
        field_ticks=int(current["local_ticks"]["field"]),
        heartbeat_phase=float(current["phases"]["heartbeat"]),
        heartbeat_cycles=int(current["phases"]["heartbeat_cycles"]),
        breath_phase=float(current["phases"]["breath"]),
        breath_cycles=int(current["phases"]["breath_cycles"]),
        activity=float(current["activity"]),
        evidence_tick=int(current["local_ticks"]["evidence"]),
        subdivision_ticks=int(current["subdivisions"]),
        paused=bool(current["paused"]),
        ledger=current["ledger"],
    )
def resume_regional_state(
    source: Mapping[str, Any],
    *,
    ticks: int = 1,
    demand: float = 0.0,
    source_enabled: bool = True,
    quiet: bool = False,
    max_iterations: int = 32,
    tolerance: float | None = None,
    impulse: Mapping[str, Any] | None = None,
    packet_impulse: Mapping[str, Any] | None = None,
    circulation: bool | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Start one operation from a validated owned regional successor.

    ``circulation`` defaults to carrying the source's segment, so a continuing
    task keeps its interfaces; ``False`` drops it and ``True`` rebuilds it.
    """

    current = json.loads(_regional_canonical(dict(source)).decode("utf-8"))
    workspace = workspace_from_regional_state(
        current, require_complete=True
    )
    carried = current.get("circulation") if circulation is None else (
        None if circulation is False else circulation
    )
    return regional_state(
        workspace,
        objective=current["objective"],
        bindings=current["bindings"],
        ticks=ticks,
        demand=demand,
        source_enabled=source_enabled,
        quiet=quiet,
        max_iterations=max_iterations,
        tolerance=tolerance,
        impulse=impulse,
        packet_impulse=packet_impulse,
        circulation=carried,
    )


def _regional_fault(state: dict[str, Any], message: str, work: int) -> field_regions.KernelResult:
    result = {
        "schema": REGIONAL_RESULT_SCHEMA, "family": REGIONAL_KERNEL_NAME,
        "status": "fault", "error_type": "ResonantNumericalError",
        "message": str(message), "logical_work": int(work),
    }
    state["phase"] = "fault"
    state["result"] = result
    return field_regions.KernelResult(state=state, status="fault", work=max(0, int(work)), output=result)


def _regional_record_ledger(state: dict[str, Any], executed: int) -> None:
    ledger = dict(state["ledger"])
    ledger["logical_work"] = float(ledger.get("logical_work", 0.0) + executed)
    state["ledger"] = ledger


def _regional_prepare(state: dict[str, Any], operator: _RegionalWaveOperator) -> None:
    continuation = dict(state["continuation"])
    values = np.asarray(state["wave_words"]["values"], dtype=np.float64)
    if not continuation["initialized"]:
        current_energy = operator.energy_gradient(values)[0]
        recorded = float(state["ledger"].get("stored_energy", current_energy))
        projected = operator.boundary(values, max(
            float(state["request"]["tolerance"] or state["profile"]["tolerance"]), 1e-10
        ))
        boundary_work = operator.energy_gradient(projected)[0] - current_energy
        state["wave_words"] = {"layout": "qY,qI,pI,pY:f64", "values": projected.tolist()}
        state["wave_words"]["layout"] = "qY,qI,pY,pI:f64"
        continuation["initialized"] = True
        continuation["start_energy"] = float(current_energy)
        continuation["recorded_start_energy"] = recorded
        continuation["totals"]["parameter_work"] = current_energy - recorded
        continuation["totals"]["boundary_work"] = boundary_work
        values = projected
    continuation["base_wave_words"] = list(state["wave_words"]["values"])
    continuation["trial_wave_words"] = list(state["wave_words"]["values"])
    continuation["level"] = 0
    continuation["parts"] = 1
    continuation["substep"] = 0
    continuation["local"] = _regional_zero_accumulator()
    continuation["operation"] = "kick"
    state["continuation"] = continuation


def _regional_rebase_trial(state: dict[str, Any]) -> None:
    """Re-base the in-tick working state onto the owned field words.

    A circulation unit transforms the field itself, so the integration that
    follows must start from the exchanged words rather than from the words the
    tick was prepared with; otherwise the exchange is integrated away.
    """

    continuation = dict(state["continuation"])
    values = list(state["wave_words"]["values"])
    continuation["base_wave_words"] = list(values)
    continuation["trial_wave_words"] = list(values)
    state["continuation"] = continuation


def _regional_finish_tick(state: dict[str, Any], profile: Mapping[str, Any]) -> None:
    continuation = dict(state["continuation"])
    phases = dict(state["phases"])
    h = float(profile["time_step"])
    heartbeat = float(phases["heartbeat"]) + h * float(profile["heartbeat_frequency"])
    breath = float(phases["breath"]) + h * float(profile["heartbeat_frequency"]) * (
        1.0 / 16.0 + 3.0 * float(state["activity"]) / 16.0
    )
    wraps_h, wraps_b = math.floor(heartbeat / (2.0 * math.pi)), math.floor(breath / (2.0 * math.pi))
    phases["heartbeat"] = heartbeat - wraps_h * 2.0 * math.pi
    phases["breath"] = breath - wraps_b * 2.0 * math.pi
    phases["heartbeat_cycles"] = int(phases["heartbeat_cycles"]) + wraps_h
    phases["breath_cycles"] = int(phases["breath_cycles"]) + wraps_b
    state["phases"] = phases
    state["activity"] = float(state["request"]["demand"]) + (
        float(state["activity"]) - float(state["request"]["demand"])
    ) * math.exp(-h / float(profile["activity_tau"]))
    state["local_ticks"] = {
        "field": int(state["local_ticks"]["field"]) + 1,
        "evidence": int(state["local_ticks"]["evidence"]),
    }
    state["subdivisions"] = int(state["subdivisions"]) + int(continuation["parts"]) - 1
    continuation["tick"] = int(continuation["tick"]) + 1
    continuation["totals"]["subdivisions"] += int(continuation["parts"]) - 1
    continuation["base_wave_words"] = None
    continuation["trial_wave_words"] = None
    continuation["local"] = _regional_zero_accumulator()
    continuation["operation"] = "prepare"
    state["continuation"] = continuation


def _regional_circulation_stage(state: dict[str, Any], operator: _RegionalWaveOperator,
                                *, passes: int, quantum: int = 1) -> dict[str, Any] | None:
    """Run bounded circulation units and roll their work into the task ledger.

    Returns ``None`` when the state declares no circulation segment.  Every
    accepted exchange charges its *measured* energy change to
    ``interface_transfer_work``, so the regional balance closes on the same
    identity that covers the integration itself; the second-order remainder of
    the exchange's linearisation is a quality measure of that measurement, not
    a further energy, and stays visible on the segment ledger and in each unit
    receipt instead of being charged a second time.
    """
    segment = state.get("circulation")
    if segment is None or not bool(segment["enabled"]):
        return None
    from cassi_circulation import circulation_stage
    continuation = dict(state["continuation"])
    totals = dict(continuation["totals"])
    transfer_before = float(segment["ledger"]["interface_transfer_work"])
    parameter_before = float(segment["ledger"]["parameter_work"])
    applications_before = int(operator.applications)
    report = circulation_stage(state, quantum=quantum, passes=int(passes), operator=operator)
    ledger = segment["ledger"]
    totals["interface_transfer_work"] += float(ledger["interface_transfer_work"]) - transfer_before
    totals["circulation_parameter_work"] += float(ledger["parameter_work"]) - parameter_before
    totals["operator_applications"] += max(0, int(operator.applications) - applications_before)
    continuation["totals"] = totals
    state["continuation"] = continuation
    return report


def _regional_finalize(state: dict[str, Any], operator: _RegionalWaveOperator,
                       executed: int) -> field_regions.KernelResult:
    continuation = state["continuation"]
    values = np.asarray(state["wave_words"]["values"], dtype=np.float64)
    end_energy = operator.energy_gradient(values)[0]
    totals = continuation["totals"]
    defect = (
        end_energy - continuation["recorded_start_energy"] - totals["parameter_work"]
        - totals["boundary_work"] - totals["interface_transfer_work"]
        - totals["positive_heartbeat_work"]
        + totals["extracted_heartbeat_work"] + totals["dissipated_work"]
        + totals["numerical_dissipated_work"] - totals["residual_work"]
    )
    allowance = max(
        1e-10,
        64 * np.finfo(float).eps * max(
            1.0, operator.roundoff_scales(values)[1],
            abs(float(continuation["start_energy"])),
        ),
    )
    ledger = dict(state["ledger"])
    for key in _REGIONAL_TOTAL_KEYS:
        ledger[key] = float(ledger.get(key, 0.0) + totals[key])
    ledger["balance_defect"] = float(ledger.get("balance_defect", 0.0) + defect)
    ledger["operator_applications"] = float(
        ledger.get("operator_applications", 0.0) + totals["operator_applications"]
    )
    ledger["stored_energy"] = float(end_energy)
    state["ledger"] = ledger
    result = {
        "schema": REGIONAL_RESULT_SCHEMA, "family": REGIONAL_KERNEL_NAME,
        "status": "done", "ticks": int(state["request"]["ticks"]),
        "field_ticks": int(state["local_ticks"]["field"]),
        "evidence_tick": int(state["local_ticks"]["evidence"]),
        "start_energy": float(continuation["start_energy"]),
        "end_energy": float(end_energy),
        "positive_heartbeat_work": float(totals["positive_heartbeat_work"]),
        "extracted_heartbeat_work": float(totals["extracted_heartbeat_work"]),
        "dissipated_work": float(totals["dissipated_work"]),
        "numerical_dissipated_work": float(totals["numerical_dissipated_work"]),
        "residual_work": float(totals["residual_work"]),
        "boundary_work": float(totals["boundary_work"]),
        "parameter_work": float(totals["parameter_work"]),
        "interface_transfer_work": float(totals["interface_transfer_work"]),
        "circulation_parameter_work": float(totals["circulation_parameter_work"]),
        "balance_defect": float(defect),
        "energy_roundoff_allowance": float(allowance),
        "output_allowance": float(allowance),
        "logical_work": int(state["ledger"].get("logical_work", 0.0)),
        "subdivisions": int(totals["subdivisions"]),
        "nonlinear_iterations": int(totals["nonlinear_iterations"]),
        "operator_applications": int(totals["operator_applications"]),
        "maximum_residual_norm": float(totals["maximum_residual_norm"]),
        "source_enabled": bool(state["request"]["source_enabled"] and not state["request"]["quiet"]),
        "integration": "projected-backward-euler-quiet-v1" if state["request"]["quiet"] else str(state["profile"]["integration"]),
        "arithmetic": "torch-regional-float64" if operator.device is not None else "numpy-matrix-free-float64",
        "device": "cpu" if operator.device is None else str(operator.device),
        "reason": "completed",
    }
    if "circulation" in state:
        from cassi_circulation import circulation_readout
        result["circulation"] = circulation_readout(state["circulation"])
    state["phase"] = "done"
    state["result"] = result
    return field_regions.KernelResult(state=state, status="done", work=max(0, executed), output=result)


def _regional_impulse(state: dict[str, Any], impulse: Mapping[str, Any]) -> field_regions.KernelResult:
    if state["continuation"]["operation"] != "prepare" or state["continuation"]["initialized"]:
        return _regional_fault(state, "regional impulse cannot interrupt an integration", 0)
    if not isinstance(impulse, Mapping) or set(impulse) != {
        "pool_signal", "work_budget", "evidence_tick", "event_kind",
    }:
        return _regional_fault(state, "regional impulse payload is invalid", 0)
    profile, objective = state["profile"], _regional_objective_data(state["objective"])
    operator = _RegionalWaveOperator(profile, state["bindings"], objective)
    count = int(profile["pools"]) * int(profile["ports_per_pool"])
    signal = _as_f64(impulse["pool_signal"], (int(profile["pools"]),), "regional pool signal")
    budget = _regional_number(impulse["work_budget"], "regional work budget", minimum=0.0, maximum=1.0)
    evidence_tick = _regional_integer(impulse["evidence_tick"], "regional evidence tick")
    if evidence_tick < int(state["local_ticks"]["evidence"]):
        return _regional_fault(state, "regional evidence tick moved backwards", 0)
    if impulse["event_kind"] not in _FIELD_EVENT_KINDS:
        return _regional_fault(state, "regional impulse event kind is invalid", 0)
    norm = float(np.linalg.norm(signal))
    if norm == 0.0:
        if budget:
            return _regional_fault(state, "positive regional work requires a nonzero signal", 0)
        accepted = False
        unit_signal = signal
        applied = amount = 0.0
        start_energy = end_energy = operator.energy_gradient(np.asarray(state["wave_words"]["values"]))[0]
        parameter = 0.0
    else:
        if state["paused"] and budget:
            return _regional_fault(state, "paused regional task cannot accept an impulse", 0)
        unit_signal = signal / norm
        ports = int(profile["ports_per_pool"])
        one_strand = np.repeat(unit_signal, ports) / math.sqrt(ports)
        direction = np.zeros(4 * count, dtype=np.float64)
        direction[2 * count:] = np.concatenate((one_strand, one_strand)) / SQRT2
        before = np.asarray(state["wave_words"]["values"], dtype=np.float64)
        start_energy = operator.energy_gradient(before)[0]
        recorded = float(state["ledger"].get("stored_energy", start_energy))
        parameter = start_energy - recorded
        mass_direction = operator.mass_apply(direction[2 * count:])
        linear = float(before[2 * count:] @ mass_direction)
        quadratic = float(direction[2 * count:] @ mass_direction)
        if quadratic <= 0.0:
            return _regional_fault(state, "regional impulse has no positive kinetic metric", 0)
        root = math.sqrt(linear * linear + 2.0 * quadratic * budget)
        amount = 2.0 * budget / (root + linear) if linear >= 0 else (root - linear) / quadratic
        after = before + amount * direction
        end_energy = operator.energy_gradient(after)[0]
        applied = end_energy - start_energy
        allowance = max(1e-12, 256 * np.finfo(float).eps * max(
            1.0, abs(recorded), abs(start_energy), abs(end_energy), abs(budget)
        ))
        if not math.isfinite(applied) or abs(applied - budget) > allowance:
            return _regional_fault(state, "regional impulse violates its work balance", 0)
        state["wave_words"] = {"layout": "qY,qI,pY,pI:f64", "values": after.tolist()}
        accepted = True
    ledger = dict(state["ledger"])
    ledger["parameter_work"] = float(ledger.get("parameter_work", 0.0) + parameter)
    ledger["temporal_coupling_work"] = float(ledger.get("temporal_coupling_work", 0.0) + applied)
    ledger[f"temporal_{impulse['event_kind']}_work"] = float(
        ledger.get(f"temporal_{impulse['event_kind']}_work", 0.0) + applied
    )
    ledger["stored_energy"] = float(end_energy)
    state["ledger"] = ledger
    state["local_ticks"] = {"field": int(state["local_ticks"]["field"]), "evidence": evidence_tick}
    state["phase"] = "done"
    result = {
        "schema": REGIONAL_RESULT_SCHEMA, "family": REGIONAL_KERNEL_NAME,
        "status": "done", "accepted": accepted, "event_kind": impulse["event_kind"],
        "pool_signal": unit_signal.tolist(), "requested_work": budget,
        "applied_work": float(applied), "impulse_amount": float(amount),
        "start_energy": float(start_energy), "end_energy": float(end_energy),
        "parameter_work": float(parameter), "balance_defect": 0.0,
        "field_ticks": int(state["local_ticks"]["field"]),
        "evidence_tick": int(evidence_tick), "logical_work": 1,
        "reason": "completed",
    }
    state["result"] = result
    _regional_record_ledger(state, 1)
    return field_regions.KernelResult(state=state, status="done", work=1, output=result)


def _regional_packet_impulse(
    state: dict[str, Any],
    impulse: Mapping[str, Any],
) -> field_regions.KernelResult:
    if (
        state["continuation"]["operation"] != "prepare"
        or state["continuation"]["initialized"]
    ):
        return _regional_fault(
            state,
            "regional packet impulse cannot interrupt an integration",
            0,
        )
    if not isinstance(impulse, Mapping) or set(impulse) != {
        "path", "component", "flow_signal", "work_budget", "evidence_tick",
        "event_kind",
    }:
        return _regional_fault(state, "regional packet impulse payload is invalid", 0)
    profile = state["profile"]
    objective = _regional_objective_data(state["objective"])
    operator = _RegionalWaveOperator(profile, state["bindings"], objective)
    count = int(profile["pools"]) * int(profile["ports_per_pool"])
    budget = _regional_number(
        impulse["work_budget"],
        "regional packet work budget",
        minimum=0.0,
        maximum=1.0,
    )
    evidence_tick = _regional_integer(
        impulse["evidence_tick"],
        "regional packet evidence tick",
    )
    if evidence_tick < int(state["local_ticks"]["evidence"]):
        return _regional_fault(
            state,
            "regional packet evidence tick moved backwards",
            0,
        )
    if impulse["event_kind"] not in _FIELD_EVENT_KINDS:
        return _regional_fault(
            state,
            "regional packet impulse event kind is invalid",
            0,
        )
    try:
        direction, unit_signal, mode = _packet_momentum_direction(
            count,
            impulse["path"],
            impulse["component"],
            impulse["flow_signal"],
        )
    except (ResonantNumericalError, TypeError, ValueError) as exc:
        return _regional_fault(state, str(exc), 0)
    signal_norm = float(np.linalg.norm(unit_signal))
    if signal_norm == 0.0 and budget:
        return _regional_fault(
            state,
            "positive regional packet work requires a nonzero flow signal",
            0,
        )
    if state["paused"] and budget:
        return _regional_fault(
            state,
            "paused regional task cannot accept a packet impulse",
            0,
        )
    before = np.asarray(state["wave_words"]["values"], dtype=np.float64)
    recorded = float(state["ledger"].get(
        "stored_energy",
        operator.energy_gradient(before)[0],
    ))
    if budget and signal_norm:
        try:
            (
                after,
                start_energy,
                end_energy,
                applied,
                amount,
                allowance,
            ) = _energy_bounded_packet_step(operator, before, direction, budget)
        except ResonantNumericalError as exc:
            return _regional_fault(state, str(exc), 0)
        parameter = start_energy - recorded
        balance_defect = end_energy - recorded - parameter - applied
        if abs(balance_defect) > allowance:
            return _regional_fault(
                state,
                "regional packet impulse violates its recorded energy balance",
                0,
            )
        state["wave_words"] = {
            "layout": "qY,qI,pY,pI:f64",
            "values": after.tolist(),
        }
        ledger = dict(state["ledger"])
        increments = {
            "parameter_work": parameter,
            "helical_packet_work": applied,
            f"helical_packet_{impulse['event_kind']}_work": applied,
            "balance_defect": balance_defect,
        }
        if str(impulse["event_kind"]).endswith("-observation"):
            increments["helical_packet_outcome_work"] = applied
        ledger.update({
            key: float(ledger.get(key, 0.0) + value)
            for key, value in increments.items()
        })
        ledger["stored_energy"] = float(end_energy)
        state["ledger"] = ledger
        state["local_ticks"] = {
            "field": int(state["local_ticks"]["field"]),
            "evidence": evidence_tick,
        }
        accepted = True
    else:
        start_energy = end_energy = float(operator.energy_gradient(before)[0])
        applied = amount = parameter = balance_defect = 0.0
        allowance = 1e-12
        accepted = False
    profile_sha256 = _profile_sha256(profile)
    state["phase"] = "done"
    result = {
        "schema": REGIONAL_RESULT_SCHEMA,
        "family": REGIONAL_KERNEL_NAME,
        "status": "done",
        "operation": "packet-impulse",
        "accepted": accepted,
        "event_kind": impulse["event_kind"],
        "basis": HELICAL_PACKET_BASIS,
        "basis_sha256": _packet_basis_sha256(
            layout_identity=str(profile["layout_identity"]),
            profile_sha256=profile_sha256,
            port_count=count,
            path=impulse["path"],
        ),
        "profile_sha256": profile_sha256,
        "path": impulse["path"],
        "component": impulse["component"],
        "support": {"start": mode["start"], "stop": mode["stop"]},
        "mode": mode,
        "flow_channels": ["common", "counterflow"],
        "flow_signal": unit_signal.tolist(),
        "requested_work": float(budget),
        "applied_work": float(applied),
        "impulse_amount": float(amount),
        "start_energy": float(start_energy),
        "end_energy": float(end_energy),
        "parameter_work": float(parameter),
        "balance_defect": float(balance_defect),
        "energy_roundoff_allowance": float(allowance),
        "field_ticks": int(state["local_ticks"]["field"]),
        "evidence_tick": int(state["local_ticks"]["evidence"]),
        "logical_work": 1,
        "reason": "completed",
    }
    state["result"] = result
    _regional_record_ledger(state, 1)
    return field_regions.KernelResult(
        state=state,
        status="done",
        work=1,
        output=result,
    )


def regional_kernel(state: Any, arguments: Mapping[str, Any], quantum: int) -> field_regions.KernelResult:
    """Advance at most ``quantum`` direct resonant task operations."""
    _regional_validate_state(state)
    bound = _regional_integer(quantum, "regional resonant quantum", minimum=1,
                              maximum=REGIONAL_KERNEL_MAX_WORK)
    current = json.loads(_regional_canonical(state).decode("utf-8"))
    operation = (
        arguments.get("operation", arguments.get("op"))
        if isinstance(arguments, Mapping) else None
    )
    if operation == "spectral-feedback":
        if not isinstance(arguments, Mapping):
            raise ResonantNumericalError("spectral feedback arguments must be a mapping")
        if set(arguments) - {
                "operation", "op", "interface", "appraisal_ref", "progress",
                "expected_exchange_sha256", "concern_ref", "appraisal_basis",
                "device", "resource_limits", "resources"}:
            raise ResonantNumericalError("spectral feedback arguments contain unknown fields")
        if current["phase"] == "fault":
            return field_regions.KernelResult(
                state=current, status="fault", work=0, output=current["result"]
            )
        if current["paused"]:
            return _regional_fault(current, "paused regional task cannot apply spectral feedback", 0)
        from cassi_circulation import circulation_spectral_feedback

        segment = current.get("circulation")
        if segment is None:
            receipt = {
                "schema": "cassifi.resonant-spectral-feedback.v1",
                "status": "unavailable",
                "reason": "regional task has no declared circulation segment",
                "interface": arguments.get("interface"),
                "admitted": False, "parameter_work": 0.0,
            }
        else:
            feedback_operator = _RegionalWaveOperator(
                current["profile"], current["bindings"],
                _regional_objective_data(current["objective"]),
            )
            try:
                receipt = circulation_spectral_feedback(
                    segment,
                    interface=arguments.get("interface"),
                    appraisal_ref=arguments.get("appraisal_ref"),
                    progress=arguments.get("progress"),
                    expected_exchange_sha256=arguments.get("expected_exchange_sha256"),
                    concern_ref=arguments.get("concern_ref"),
                    appraisal_basis=arguments.get("appraisal_basis"),
                    operator=feedback_operator,
                    words=current["wave_words"]["values"],
                    quiet=bool(current["request"]["quiet"]),
                )
            finally:
                operator_applications = int(feedback_operator.applications)
                feedback_operator.close()
                if operator_applications:
                    ledger = dict(current["ledger"])
                    ledger["operator_applications"] = float(
                        ledger.get("operator_applications", 0.0)
                    ) + operator_applications
                    current["ledger"] = ledger
        _regional_validate_state(current)
        return field_regions.KernelResult(
            state=current,
            status="done" if current["phase"] == "done" else "yield",
            work=0, output=receipt,
        )
    if current["phase"] == "done":
        return field_regions.KernelResult(state=current, status="done", work=0, output=current["result"])
    if current["phase"] == "fault":
        return field_regions.KernelResult(state=current, status="fault", work=0, output=current["result"])
    if not isinstance(arguments, Mapping):
        raise ResonantNumericalError("regional resonant arguments must be a mapping")
    request = dict(current["request"])
    requested_device = arguments.get("device")
    resource_limits = arguments.get("resource_limits", arguments.get("resources"))
    if requested_device == "auto":
        requested_device = "cuda" if torch.cuda.is_available() else None
    if requested_device is not None and requested_device != "cpu":
        if not str(requested_device).startswith("cuda"):
            raise ResonantNumericalError("regional device must be 'cpu', 'cuda', or 'auto'")
        if not torch.cuda.is_available():
            raise ResonantDeviceUnavailableError(
                f"requested device {requested_device!r} is unavailable"
            )
    if arguments:
        operation = arguments.get("operation", arguments.get("op"))
        if operation not in {"impulse", "packet-impulse", "circulate"}:
            raise ResonantNumericalError(
                "regional resonant kernel accepts impulse and circulate operations only"
            )
        if operation == "circulate":
            current["request"] = {
                **request,
                "operation": "circulate",
                "impulse": None,
                "ticks": _regional_integer(
                    arguments.get("ticks", arguments.get("passes", request["ticks"])),
                    "circulation passes", maximum=4096,
                ),
            }
            request = current["request"]
        else:
            keys = (
                ("pool_signal", "work_budget", "evidence_tick", "event_kind")
                if operation == "impulse"
                else (
                    "path", "component", "flow_signal", "work_budget",
                    "evidence_tick", "event_kind",
                )
            )
            impulse = {key: arguments[key] for key in keys if key in arguments}
            current["request"] = {
                **request,
                "operation": operation,
                "impulse": impulse,
            }
            request = current["request"]
    if request["operation"] == "impulse":
        return _regional_impulse(current, request["impulse"])
    if request["operation"] == "packet-impulse":
        return _regional_packet_impulse(current, request["impulse"])
    if request["operation"] == "circulate" and "circulation" not in current:
        return _regional_fault(current, "circulate requires a declared circulation segment", 0)
    if request["operation"] == "circulate" and not bool(current["circulation"]["enabled"]):
        return _regional_fault(current, "circulate requires an enabled circulation segment", 0)
    if current["paused"] and int(request["ticks"]) > 0:
        return _regional_fault(current, "paused regional task cannot advance", 0)
    operator = _RegionalWaveOperator(
        current["profile"], current["bindings"],
        _regional_objective_data(current["objective"]),
        device=requested_device,
        resources=resource_limits,
    )
    executed = 0
    try:
        while executed < bound and current["phase"] == "running":
            continuation = current["continuation"]
            if request["operation"] == "circulate":
                if continuation["operation"] == "prepare":
                    _regional_prepare(current, operator)
                    continue
                stage = _regional_circulation_stage(
                    current, operator, passes=int(request["ticks"]),
                )
                executed += 1
                if bool(stage["complete"]):
                    _regional_record_ledger(current, executed)
                    return _regional_finalize(current, operator, executed)
                continue
            if continuation["operation"] == "prepare":
                _regional_prepare(current, operator)
                continue
            segment = current.get("circulation")
            if (segment is not None and bool(segment["enabled"])
                    and int(segment["continuation"]["pending"]) > 0
                    and continuation["operation"] == "kick"
                    and int(continuation["substep"]) == 0):
                from cassi_circulation import circulation_take_pending

                report = _regional_circulation_stage(
                    current, operator,
                    passes=int(segment["continuation"]["pass"]) + 1,
                )
                circulation_take_pending(segment)
                if int(report["units"]) > 0:
                    _regional_rebase_trial(current)
                executed += 1
                continue
            if continuation["tick"] >= request["ticks"]:
                _regional_record_ledger(current, executed)
                return _regional_finalize(current, operator, executed)
            profile = current["profile"]
            h = float(profile["time_step"])
            parts = int(continuation["parts"])
            sub_h = h / parts
            substep = int(continuation["substep"])
            phase0 = float(current["phases"]["heartbeat"]) + substep * sub_h * float(profile["heartbeat_frequency"])
            phase1 = phase0 + sub_h * float(profile["heartbeat_frequency"])
            midpoint = (phase0 + phase1) / 2.0
            trial = np.asarray(continuation["trial_wave_words"], dtype=np.float64)
            if continuation["operation"] == "kick":
                allowance = float(profile["heartbeat_work"]) * (
                    pulse_primitive(phase1) - pulse_primitive(phase0)
                )
                energy_now = operator.energy_gradient(trial)[0]
                if request["source_enabled"] and not request["quiet"]:
                    allowance = min(allowance, max(0.0, 1e12 - energy_now))
                else:
                    allowance = 0.0
                trial, work = operator.kick(
                    trial, midpoint, sub_h * float(profile["heartbeat_amplitude"]) * math.sin(midpoint) ** 2,
                    allowance,
                )
                local = dict(continuation["local"])
                local["positive_heartbeat_work"] += max(work, 0.0)
                local["extracted_heartbeat_work"] += max(-work, 0.0)
                continuation["trial_wave_words"] = trial.tolist()
                continuation["local"] = local
                continuation["operation"] = "step"
                executed += 1
                continue
            applications_before = operator.applications
            try:
                updated, receipt = operator.step(
                    trial, sub_h * (
                        0.5 + 1.5 * float(current["activity"])
                        + 0.25 * (1.0 + math.cos(float(current["phases"]["breath"])))
                    ),
                    quiet=bool(request["quiet"]),
                    max_iterations=int(request["max_iterations"]),
                    tolerance=float(request["tolerance"] or profile["tolerance"]),
                )
            except (ResonantNumericalError, np.linalg.LinAlgError):
                if int(continuation["level"]) >= int(profile["max_subdivisions"]):
                    executed += 1
                    _regional_record_ledger(current, executed)
                    return _regional_fault(current, "regional subdivision bound exhausted", executed)
                continuation["level"] = int(continuation["level"]) + 1
                continuation["parts"] = 2 ** int(continuation["level"])
                continuation["substep"] = 0
                continuation["trial_wave_words"] = list(continuation["base_wave_words"])
                continuation["local"] = _regional_zero_accumulator()
                continuation["totals"]["failed_attempts"] += 1.0
                continuation["operation"] = "kick"
                executed += 1
                continue
            local = dict(continuation["local"])
            local["dissipated_work"] += float(receipt["dissipated_work"])
            local["numerical_dissipated_work"] += float(receipt["numerical_dissipated_work"])
            local["residual_work"] += float(receipt["residual_work"])
            local["maximum_residual_norm"] = max(local["maximum_residual_norm"], float(receipt["residual_norm"]))
            local["nonlinear_iterations"] += float(receipt["iterations"])
            local["operator_applications"] += float(operator.applications - applications_before)
            continuation["trial_wave_words"] = updated.tolist()
            continuation["local"] = local
            continuation["substep"] = substep + 1
            continuation["operation"] = "kick"
            executed += 1
            if continuation["substep"] >= int(continuation["parts"]):
                for key in _REGIONAL_LOCAL_KEYS:
                    continuation["totals"][key] += local[key]
                continuation["totals"]["maximum_residual_norm"] = max(
                    continuation["totals"]["maximum_residual_norm"], local["maximum_residual_norm"]
                )

                current["wave_words"] = {"layout": "qY,qI,pY,pI:f64", "values": updated.tolist()}
                _regional_finish_tick(current, profile)
                segment = current.get("circulation")
                if segment is not None and bool(segment["enabled"]):
                    from cassi_circulation import circulation_defer_unit

                    circulation_defer_unit(segment)
    except (ResonantNumericalError, np.linalg.LinAlgError, TypeError, ValueError) as exc:
        _regional_record_ledger(current, executed)
        return _regional_fault(current, str(exc), executed)
    finally:
        operator.close()
    _regional_record_ledger(current, executed)
    return field_regions.KernelResult(state=current, status="yield", work=executed, output=None)



# ---------------------------------------------------------------------------
# Section 18: canonical multiscale state, reciprocal exchange, and geometry.
# These records are immutable-by-convention numerical views.  They never own
# an adaptive relation table or a second memory representation.


class ResonantStageMismatchError(ResonantNumericalError):
    """A reciprocal exchange attempted to combine unlike numerical stages."""


def _metric_vector(metric: Any, size: int, name: str = "metric") -> np.ndarray:
    values = _as_f64(metric, (size,), name)
    if np.any(values <= 0.0):
        raise ResonantNumericalError(f"{name} must be strictly positive")
    return values


@dataclass(frozen=True)
class ResonantMetricTransform:
    """A reversible change of coordinates in a diagonal numerical metric.

    ``matrix`` is a metric-orthogonal map: ``A.T M A = M``.  The inverse is
    therefore the metric adjoint, not an unweighted transpose.
    """

    metric: Any
    matrix: Any = None
    version: str = "metric-transform-v1"

    def __post_init__(self) -> None:
        m = _metric_vector(self.metric, len(np.asarray(self.metric).reshape(-1)))
        n = len(m)
        if self.matrix is None:
            q = np.eye(n, dtype=np.float64)
            if n > 1:
                q[0, 0] = q[0, 1] = q[1, 0] = 1.0 / SQRT2
                q[1, 1] = -1.0 / SQRT2
        else:
            q = _as_f64(self.matrix, (n, n), "metric transform matrix")
        # Interpret a supplied matrix as an ordinary orthogonal basis map.
        if not np.allclose(q.T @ q, np.eye(n), atol=2e-12, rtol=0):
            raise ResonantNumericalError("metric transform basis must be orthogonal")
        d = np.sqrt(m)
        a = (q * d[np.newaxis, :]) / d[:, np.newaxis]
        ai = (q.T * d[np.newaxis, :]) / d[:, np.newaxis]
        object.__setattr__(self, "metric", m.copy())
        object.__setattr__(self, "matrix", a)
        object.__setattr__(self, "_inverse", ai)
        object.__setattr__(self, "roundoff_bound", float(64 * np.finfo(float).eps * max(1.0, np.linalg.norm(a, ord=2))))

    @property
    def size(self) -> int:
        return len(self.metric)

    def restrict(self, values: Any) -> np.ndarray:
        return self.matrix @ _as_f64(values, (self.size,), "fine coordinates")

    def prolongate(self, coefficients: Any) -> np.ndarray:
        return self._inverse @ _as_f64(coefficients, (self.size,), "coarse/detail coordinates")

    def roundtrip(self, values: Any) -> tuple[np.ndarray, float]:
        source = _as_f64(values, (self.size,), "fine coordinates")
        restored = self.prolongate(self.restrict(source))
        return restored, float(np.max(np.abs(restored - source), initial=0.0))

    def as_dict(self) -> dict[str, Any]:
        return {"version": self.version, "metric": self.metric.tolist(), "matrix": self.matrix.tolist(),
                "roundoff_bound": self.roundoff_bound}


def metric_weighted_transform(values: Any, metric: Any, *, matrix: Any = None) -> dict[str, Any]:
    """Restrict and prolongate one complete coordinate vector."""
    transform = ResonantMetricTransform(metric, matrix)
    source = _as_f64(values, (transform.size,), "values")
    coefficients = transform.restrict(source)
    restored = transform.prolongate(coefficients)
    return {"coefficients": coefficients, "restored": restored,
            "roundtrip_error": float(np.max(np.abs(restored - source), initial=0.0)),
            "roundoff_bound": transform.roundoff_bound, "transform": transform}


def unweighted_transform_error(values: Any, metric: Any, *, matrix: Any = None) -> float:
    """Negative control: use an unweighted transpose under a nonuniform metric."""
    source = _as_f64(values, name="values")
    m = _metric_vector(metric, source.size)
    if matrix is None:
        q = np.eye(source.size, dtype=np.float64)
        if source.size > 1:
            q[0, 0] = q[0, 1] = q[1, 0] = 1.0 / SQRT2
            q[1, 1] = -1.0 / SQRT2
    else:
        q = _as_f64(matrix, (source.size, source.size), "matrix")
    restricted = q @ source
    # The metric adjoint of the unweighted restriction is not its transpose.
    restored = np.diag(1.0 / m) @ q.T @ np.diag(m) @ restricted
    return float(np.max(np.abs(restored - source), initial=0.0))


@dataclass(frozen=True)
class ResonantRegionRecord:
    identity: str
    owner_scope: str = "resonant"
    parent_id: str | None = None
    basis_ref: str = "canonical"
    content_version: int = 0
    coarse_coordinates: Any = field(default_factory=lambda: np.zeros(0))
    detail_coordinates: Any = field(default_factory=lambda: np.zeros(0))
    coarse_momenta: Any = field(default_factory=lambda: np.zeros(0))
    detail_momenta: Any = field(default_factory=lambda: np.zeros(0))
    axial_frame: Any = field(default_factory=lambda: np.eye(3))
    signed_current: float = 0.0
    handedness: int = 0
    relative_phases: Any = field(default_factory=dict)
    geometric_parameters: Any = field(default_factory=dict)
    coupling_ports: Any = field(default_factory=tuple)
    endpoint_turnarounds: Any = field(default_factory=tuple)
    interface_dependencies: Any = field(default_factory=tuple)
    arithmetic_profile: str = "numpy-cpu-float64"
    numerical_time: float = 0.0
    integration_phase: str = "idle"
    unfinished_work: Any = field(default_factory=dict)
    resource_accounts: Any = field(default_factory=dict)
    interface_work: float = 0.0
    stale: bool = False

    def __post_init__(self) -> None:
        if not self.identity:
            raise ResonantNumericalError("region identity must be nonempty")
        if self.parent_id == self.identity:
            raise ResonantNumericalError("a region cannot be its own parent")
        if self.content_version < 0 or self.numerical_time < 0.0 or not math.isfinite(self.numerical_time):
            raise ResonantNumericalError("region versions and numerical time must be bounded")

        # Cache the identity matrix to avoid repeated creation if called multiple times
        # However, since we cannot cache across calls with different arguments (though here it's constant),
        # we just create it locally. np.eye(3) is very fast, but avoiding np.allclose is the key.
        _I3 = np.eye(3, dtype=np.float64)

        for name in ("coarse_coordinates", "detail_coordinates", "coarse_momenta", "detail_momenta"):
            array = _as_f64(getattr(self, name), name=name).reshape(-1)
            array.setflags(write=False)
            object.__setattr__(self, name, array)

        frame = _as_f64(self.axial_frame, (3, 3), "axial_frame")

        # Optimized orthogonality and determinant check
        # np.allclose(frame.T @ frame, np.eye(3), atol=2e-10, rtol=0) is slow due to overhead
        # We compute the product and check element-wise equality with tolerance
        frame_T_frame = frame.T @ frame
        # Check if frame_T_frame is close to identity
        # np.allclose with rtol=0 is equivalent to: abs(a - b) <= atol
        # So we check: abs(frame_T_frame - I) <= 2e-10
        if not np.all(np.abs(frame_T_frame - _I3) <= 2e-10):
            raise ResonantNumericalError("axial_frame must be a proper rotation")

        # Check determinant
        det = np.linalg.det(frame)
        if det <= 0.0:
            raise ResonantNumericalError("axial_frame must be a proper rotation")

        object.__setattr__(self, "axial_frame", frame)

        if not math.isfinite(float(self.signed_current)) or not math.isfinite(float(self.interface_work)):
            raise ResonantNumericalError("region flow accounts must be finite")
        if self.handedness not in (-1, 0, 1):
            raise ResonantNumericalError("handedness must be -1, 0, or +1")

    @property
    def version(self) -> str:
        return f"{self.identity}@{self.content_version}"

    def as_dict(self) -> dict[str, Any]:
        return _jsonable({name: getattr(self, name) for name in self.__dataclass_fields__})


@dataclass(frozen=True)
class ResonantHierarchySpec:
    max_nodes: int = 64
    max_depth: int = 16
    coverage_limit: int = 64
    basis_version: str = "metric-haar-v1"
    parent_map: Mapping[str, str | None] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 1 <= int(self.max_nodes) <= 1_000_000 or not 0 <= int(self.max_depth) <= 1024:
            raise ResonantNumericalError("hierarchy bounds are invalid")
        if not 1 <= int(self.coverage_limit) <= int(self.max_nodes):
            raise ResonantNumericalError("coverage_limit exceeds hierarchy bound")
        object.__setattr__(self, "max_nodes", int(self.max_nodes))
        object.__setattr__(self, "max_depth", int(self.max_depth))
        object.__setattr__(self, "coverage_limit", int(self.coverage_limit))
        object.__setattr__(self, "parent_map", MappingProxyType(dict(self.parent_map)))


def _axis_projection(directions: Any, weights: Any = None, *, signed_current: float = 0.0,
                     prior_frame: Any = None, degeneracy_tolerance: float = 1e-12) -> dict[str, Any]:
    vectors = _as_f64(directions, name="directions")
    if vectors.size == 0:
        vectors = np.zeros((0, 3), dtype=np.float64)
    if vectors.ndim != 2 or vectors.shape[1] != 3:
        raise ResonantNumericalError("directions must have shape (N,3)")
    norms = np.linalg.norm(vectors, axis=1)
    usable = norms > degeneracy_tolerance
    if weights is None:
        weight = np.ones(len(vectors), dtype=np.float64)
    else:
        weight = _metric_vector(weights, len(vectors), "direction weights")
    if not np.any(usable):
        eigvals = np.zeros(3)
        unresolved = np.eye(3)
        return {"axis": None, "eigenvalues": eigvals.tolist(), "unresolved_eigenspace": unresolved.tolist(),
                "resolved": False, "signed_current": float(signed_current), "coverage": 0.0}
    unit = vectors[usable] / norms[usable, None]
    w = weight[usable]
    moment = (unit * w[:, None]).T @ unit / float(w.sum())
    eigenvalues, eigenvectors = np.linalg.eigh(moment)
    order = np.argsort(eigenvalues)[::-1]
    eigenvalues, eigenvectors = eigenvalues[order], eigenvectors[:, order]
    gap = float(eigenvalues[0] - eigenvalues[1])
    scale = max(1.0, float(abs(eigenvalues[0])))
    if gap <= degeneracy_tolerance * scale:
        unresolved = eigenvectors[:, eigenvalues >= eigenvalues[0] - degeneracy_tolerance * scale]
        return {"axis": None, "eigenvalues": eigenvalues.tolist(), "unresolved_eigenspace": unresolved.tolist(),
                "resolved": False, "signed_current": float(signed_current), "coverage": float(w.sum() / weight.sum())}
    axis = eigenvectors[:, 0]
    if prior_frame is not None:
        prior = _as_f64(prior_frame, (3, 3), "prior_frame")[:, 0]
        if float(axis @ prior) < 0.0:
            axis = -axis
    return {"axis": axis.tolist(), "eigenvalues": eigenvalues.tolist(), "unresolved_eigenspace": [],
            "resolved": True, "signed_current": float(signed_current), "coverage": float(w.sum() / weight.sum())}


class ResonantHierarchy:
    """Bounded ancestry over one workspace with no duplicated learned state."""

    def __init__(self, workspace: ResonantWorkspace | ResonantProfile | None = None, *,
                 spec: ResonantHierarchySpec | None = None,
                 regions: Mapping[str, ResonantRegionRecord | Mapping[str, Any]] | None = None,
                 parent_map: Mapping[str, str | None] | None = None,
                 max_nodes: int = 64) -> None:
        self.workspace = workspace if isinstance(workspace, ResonantWorkspace) else initial_workspace(workspace if isinstance(workspace, ResonantProfile) else None)
        self.spec = spec or ResonantHierarchySpec(max_nodes=max_nodes, parent_map=parent_map or {})
        self._regions: dict[str, ResonantRegionRecord] = {}
        root = ResonantRegionRecord(
            identity="root", owner_scope="workspace", basis_ref=self.workspace.profile.layout_identity,
            coarse_coordinates=self.workspace.common_coordinates(), detail_coordinates=self.workspace.relative_coordinates(),
            coarse_momenta=self.workspace.momentum()[:self.workspace.profile.port_count],
            detail_momenta=self.workspace.momentum()[self.workspace.profile.port_count:],
            geometric_parameters={"profile": self.workspace.profile.layout_identity},
        )
        self._regions["root"] = root
        for identity, record in (regions or {}).items():
            self.add_region(record if isinstance(record, ResonantRegionRecord) else ResonantRegionRecord(identity=identity, **dict(record)))
        self._validate_ancestry()

    @property
    def regions(self) -> Mapping[str, ResonantRegionRecord]:
        return MappingProxyType(dict(self._regions))

    def _validate_ancestry(self) -> None:
        parent_map = dict(self.spec.parent_map)
        parent_map.update({key: value.parent_id for key, value in self._regions.items()})
        if len(self._regions) > self.spec.max_nodes:
            raise ResonantNumericalError("hierarchy node bound exceeded")
        identities = set(self._regions) | set(parent_map)
        for identity in identities:
            seen: set[str] = set()
            cursor: str | None = identity
            depth = 0
            while cursor is not None:
                if cursor in seen:
                    raise ResonantNumericalError("representation ancestry contains a cycle")
                seen.add(cursor)
                depth += 1
                if depth > self.spec.max_depth + 1:
                    raise ResonantNumericalError("hierarchy depth bound exceeded")
                cursor = parent_map.get(cursor)
                if cursor is not None and cursor not in identities and cursor != "root":
                    raise ResonantNumericalError(f"unknown region parent {cursor!r}")

    def add_region(self, record: ResonantRegionRecord) -> None:
        if not isinstance(record, ResonantRegionRecord):
            raise TypeError("record must be ResonantRegionRecord")
        if record.identity in self._regions:
            raise ResonantNumericalError("duplicate region identity")
        if len(self._regions) >= self.spec.max_nodes:
            raise ResonantNumericalError("hierarchy allocation bound exceeded")
        self._regions[record.identity] = record
        try:
            self._validate_ancestry()
        except Exception:
            del self._regions[record.identity]
            raise

    def restrict(self, values: Any, metric: Any = None, *, matrix: Any = None) -> ResonantMetricTransform:
        source = np.asarray(values, dtype=np.float64).reshape(-1)
        selected_metric = self.workspace.profile.volumes[:source.size] if metric is None else metric
        transform = ResonantMetricTransform(selected_metric, matrix)
        transform.restrict(source)
        return transform

    def prolongate(self, transform: ResonantMetricTransform, coefficients: Any) -> np.ndarray:
        if not isinstance(transform, ResonantMetricTransform):
            raise TypeError("transform must be ResonantMetricTransform")
        return transform.prolongate(coefficients)

    def coarse_working_set(self, *, max_regions: int | None = None) -> dict[str, Any]:
        limit = self.spec.coverage_limit if max_regions is None else min(int(max_regions), self.spec.coverage_limit)
        selected = list(self._regions.values())[:limit]
        directions = np.asarray([record.axial_frame[:, 0] for record in selected], dtype=np.float64)
        currents = float(sum(record.signed_current for record in selected))
        projection = _axis_projection(directions, signed_current=currents)
        stale = [record.identity for record in selected if record.stale]
        coverage = 0.0 if not selected else sum(not r.stale for r in selected) / len(selected)
        projection["coverage"] = float(projection["coverage"] * coverage)
        return {"schema": "cassifi.resonant-coarse-working-set.v1", "version": max((r.content_version for r in selected), default=0),
                "signed_current": currents, "axial_order": projection, "region_ids": [r.identity for r in selected],
                "coverage": coverage, "coverage_limit": limit, "stale_regions": stale}

    def activity_values(self, events: Sequence[Mapping[str, Any]], *,
                        flow: ResonantGeometryRecord | Mapping[str, Any] | None = None,
                        scale: float = 1.0) -> dict[int, float]:
        """Produce bounded eligible-work modulation from canonical geometry.

        For event sequence ``k``, let ``C`` be the non-stale coverage and
        ``I`` the signed-current sum of the selected regions.  The producer
        uses the declared bounded reading
        ``v_k = clip(tanh(scale)*C*tanh(I_r/(1+abs(I_r)))*
        (1/2 + kappa/(2*(omega+kappa))) *
        cos(pi*k/2 + pi*handedness/2), -1, 1)``.
        ``I_r`` is the event's region current (or ``I``), and
        ``kappa >= 0, omega > 0`` come from the supplied geometry or the
        hierarchy's declared flow fallback.  Thus every returned value is in
        ``[-1,1]``; no eligibility or fairness decision is made here.
        """
        if not events:
            return {}
        selected = list(self._regions.values())[:self.spec.coverage_limit]
        coverage = 0.0 if not selected else sum(not region.stale for region in selected) / len(selected)
        total_current = float(sum(region.signed_current for region in selected))
        if isinstance(flow, ResonantGeometryRecord):
            kappa, omega, flow_handedness = float(flow.kappa), float(flow.omega), int(flow.handedness)
        elif isinstance(flow, Mapping):
            kappa = float(flow.get("kappa", 0.0))
            omega = float(flow.get("omega", 1.0))
            flow_handedness = int(flow.get("handedness", 0))
        else:
            kappa, omega, flow_handedness = abs(total_current) / (1.0 + abs(total_current)), 1.0, 0
        from cassi_circulation import _modulation_values
        return _modulation_values(
            selected, events, coverage=coverage, total_current=total_current,
            kappa=kappa, omega=omega, flow_handedness=flow_handedness, scale=scale,
        )

    def as_dict(self) -> dict[str, Any]:
        spec = {
            "max_nodes": self.spec.max_nodes, "max_depth": self.spec.max_depth,
            "coverage_limit": self.spec.coverage_limit, "basis_version": self.spec.basis_version,
            "parent_map": dict(self.spec.parent_map),
        }
        return {"schema": "cassifi.resonant-hierarchy.v1", "spec": spec,
                "workspace_state_sha256": self.workspace.state_sha256,
                "regions": {key: value.as_dict() for key, value in self._regions.items()}}

    def regional_state(self, *, interface_work: float | None = None) -> dict[str, Any]:
        payload = self.as_dict()
        payload["interface_work"] = float(sum(r.interface_work for r in self._regions.values()) if interface_work is None else interface_work)
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any], workspace: ResonantWorkspace) -> "ResonantHierarchy":
        if payload.get("schema") != "cassifi.resonant-hierarchy.v1":
            raise ResonantNumericalError("unsupported resonant hierarchy schema")
        raw_spec = dict(payload.get("spec", {}))
        regions = dict(payload.get("regions", {}))
        regions.pop("root", None)
        parsed = {key: ResonantRegionRecord(identity=key, **{k: v for k, v in value.items() if k != "identity"})
                  for key, value in regions.items()}
        return cls(workspace, spec=ResonantHierarchySpec(**raw_spec), regions=parsed)


def metric_weighted_restrict(values: Any, metric: Any, *, matrix: Any = None) -> np.ndarray:
    """Apply the metric-weighted restriction half of a reversible transform."""
    transform = ResonantMetricTransform(metric, matrix)
    return transform.restrict(values)


def metric_weighted_prolongate(coefficients: Any, metric: Any, *, matrix: Any = None) -> np.ndarray:
    """Apply the exact metric-weighted prolongation half of a reversible transform."""
    transform = ResonantMetricTransform(metric, matrix)
    return transform.prolongate(coefficients)


@dataclass(frozen=True)
class ResonantExchangeStage:
    version: str
    parent_version: str
    child_version: str
    digest: str

    @classmethod
    def bind(cls, parent: Any, child: Any, *, version: str = "stage-0") -> "ResonantExchangeStage":
        parent_version = str(parent.version if isinstance(parent, ResonantRegionRecord) else parent)
        child_version = str(child.version if isinstance(child, ResonantRegionRecord) else child)
        digest = _canonical_sha256({"version": version, "parent": parent_version, "child": child_version})
        return cls(str(version), parent_version, child_version, digest)


def reciprocal_exchange(parent_gradient: Any, child_gradient: Any, transfer: Any, *,
                        stage: ResonantExchangeStage | None = None,
                        expected_stage: ResonantExchangeStage | None = None) -> dict[str, Any]:
    gp = _as_f64(parent_gradient, name="parent gradient").reshape(-1)
    gc = _as_f64(child_gradient, name="child gradient").reshape(-1)
    t = _as_f64(transfer, (gp.size, gc.size), "exchange transfer")
    if stage is None:
        stage = ResonantExchangeStage.bind("parent", "child")
    if expected_stage is not None and stage.digest != expected_stage.digest:
        raise ResonantStageMismatchError("parent and child signals do not share a version-bound stage")
    parent_delta, child_delta = t @ gc, -t.T @ gp
    parent_power = float(gp @ parent_delta)
    child_power = float(gc @ child_delta)
    return {"stage": stage, "parent_delta": parent_delta, "child_delta": child_delta,
            "parent_power": parent_power, "child_power": child_power,
            "interface_transfer_work": parent_power + child_power,
            "power_imbalance": parent_power + child_power}


def reciprocal_exchange_power(parent_gradient: Any, child_gradient: Any, transfer: Any) -> float:
    result = reciprocal_exchange(parent_gradient, child_gradient, transfer)
    return float(result["power_imbalance"])


def apply_reciprocal_exchange(workspace: ResonantWorkspace, parent_gradient: Any, child_gradient: Any,
                              transfer: Any, *, stage: ResonantExchangeStage,
                              expected_stage: ResonantExchangeStage | None = None) -> tuple[ResonantWorkspace, dict[str, Any]]:
    result = reciprocal_exchange(parent_gradient, child_gradient, transfer, stage=stage, expected_stage=expected_stage)
    ledger = dict(workspace.ledger)
    ledger["interface_transfer_work"] = ledger.get("interface_transfer_work", 0.0) + float(result["interface_transfer_work"])
    result["workspace_state_sha256"] = workspace.state_sha256
    return workspace._copy(ledger=ledger), result


def transported_phase_mismatch(phase_parent: float, phase_child: float, preferred_offset: float = 0.0,
                              frame_offset: float = 0.0) -> float:
    return float(phase_child - phase_parent - preferred_offset + frame_offset)


def constraint_tangent_gradient(axis: Any, gradient: Any) -> np.ndarray:
    n = _as_f64(axis, (3,), "axis")
    norm = float(np.linalg.norm(n))
    if norm == 0.0:
        raise ResonantNumericalError("axis cannot be zero")
    n = n / norm
    g = _as_f64(gradient, (3,), "axis gradient")
    return g - float(g @ n) * n


def alignment_energy(axis_parent: Any, axis_child: Any, *, a: float = 1.0, b: float = 1.0,
                     rotation: Any = None, phase_parent: float = 0.0, phase_child: float = 0.0,
                     preferred_offset: float = 0.0, frame_offset: float = 0.0) -> float:
    import numpy as np
    from cassi_resonant_field import ResonantNumericalError

    # Inline _as_f64 logic with explicit checks and shape validation
    parent_arr = np.asarray(axis_parent, dtype=np.float64)
    if parent_arr.shape != (3,):
        raise ResonantNumericalError("parent axis must have shape (3,)")
    child_arr = np.asarray(axis_child, dtype=np.float64)
    if child_arr.shape != (3,):
        raise ResonantNumericalError("child axis must have shape (3,)")

    # Manual norm computation to avoid function call overhead
    parent_norm = math.sqrt(parent_arr[0]**2 + parent_arr[1]**2 + parent_arr[2]**2)
    child_norm = math.sqrt(child_arr[0]**2 + child_arr[1]**2 + child_arr[2]**2)

    if parent_norm == 0.0 or child_norm == 0.0:
        raise ResonantNumericalError("axis norms must be non-zero")

    # Normalize in-place conceptually (we create new arrays for clarity but could optimize further)
    np_ = parent_arr / parent_norm
    nc = child_arr / child_norm

    # Handle rotation matrix
    if rotation is None:
        q = np.eye(3)
    else:
        q = np.asarray(rotation, dtype=np.float64)
        if q.shape != (3, 3):
            raise ResonantNumericalError("frame rotation must have shape (3, 3)")

    # Manual matrix multiplication and orthogonality check
    # q.T @ q should be identity
    q00, q01, q02 = q[0]
    q10, q11, q12 = q[1]
    q20, q21, q22 = q[2]

    # Compute q.T @ q elements
    qTq00 = q00*q00 + q10*q10 + q20*q20
    qTq01 = q00*q01 + q10*q11 + q20*q21
    qTq02 = q00*q02 + q10*q12 + q20*q22
    qTq11 = q01*q01 + q11*q11 + q21*q21
    qTq12 = q01*q02 + q11*q12 + q21*q22
    qTq22 = q02*q02 + q12*q12 + q22*q22

    # Check orthogonality with explicit tolerance
    if abs(qTq00 - 1.0) > 2e-10 or abs(qTq11 - 1.0) > 2e-10 or abs(qTq22 - 1.0) > 2e-10:
        raise ResonantNumericalError("alignment rotation must be proper")
    if abs(qTq01) > 2e-10 or abs(qTq02) > 2e-10 or abs(qTq12) > 2e-10:
        raise ResonantNumericalError("alignment rotation must be proper")

    # Check determinant (proper rotation means det > 0)
    det = (q00*(q11*q22 - q12*q21) - q01*(q10*q22 - q12*q20) + q02*(q10*q21 - q11*q20))
    if det <= 0.0:
        raise ResonantNumericalError("alignment rotation must be proper")

    if a < 0.0 or b < 0.0:
        raise ResonantNumericalError("alignment weights must be nonnegative")

    # Compute dot product manually
    # nc @ q @ np_
    # First compute q @ np_
    q_np_0 = q00*np_[0] + q01*np_[1] + q02*np_[2]
    q_np_1 = q10*np_[0] + q11*np_[1] + q12*np_[2]
    q_np_2 = q20*np_[0] + q21*np_[1] + q22*np_[2]

    # Then nc @ (q @ np_)
    dot = nc[0]*q_np_0 + nc[1]*q_np_1 + nc[2]*q_np_2

    # Compute phase mismatch
    delta = phase_child - phase_parent - preferred_offset + frame_offset

    # Compute final energy
    return 0.5 * a * (1.0 - dot * dot) + b * (1.0 - math.cos(delta))


def alignment_gradients(axis_parent: Any, axis_child: Any, *, a: float = 1.0, b: float = 1.0,
                        rotation: Any = None, phase_parent: float = 0.0, phase_child: float = 0.0,
                        preferred_offset: float = 0.0, frame_offset: float = 0.0) -> dict[str, Any]:
    np_ = _as_f64(axis_parent, (3,), "parent axis"); nc = _as_f64(axis_child, (3,), "child axis")
    np_ /= np.linalg.norm(np_); nc /= np.linalg.norm(nc)
    q = np.eye(3) if rotation is None else _as_f64(rotation, (3, 3), "frame rotation")
    dot = float(nc @ q @ np_)
    gp = constraint_tangent_gradient(np_, -float(a) * dot * (q.T @ nc))
    gc = constraint_tangent_gradient(nc, -float(a) * dot * (q @ np_))
    delta = transported_phase_mismatch(phase_parent, phase_child, preferred_offset, frame_offset)
    return {"parent_axis": gp, "child_axis": gc, "parent_phase": -float(b) * math.sin(delta),
            "child_phase": float(b) * math.sin(delta), "dot": dot,
            "tangent_residual": max(abs(float(np_ @ gp)), abs(float(nc @ gc)))}


def alignment_step(axis: Any, gradient: Any, step: float = 0.1) -> tuple[np.ndarray, float]:
    n = _as_f64(axis, (3,), "axis"); n /= np.linalg.norm(n)
    projected = constraint_tangent_gradient(n, gradient)
    updated = n - float(step) * projected
    updated /= np.linalg.norm(updated)
    residual = constraint_tangent_gradient(updated, projected)
    return updated, abs(float(updated @ residual))


@dataclass(frozen=True)
class ResonantGeometryRecord:
    longitudinal_direction: Any
    signed_current: float = 0.0
    handedness: int = 0
    kappa: float = 0.0
    omega: float = 1.0
    axial_speed: float = 0.0
    angular_convention: str = "declared"
    divergence: float = 0.0

    def __post_init__(self) -> None:
        direction = _as_f64(self.longitudinal_direction, (3,), "longitudinal_direction")
        norm = float(np.linalg.norm(direction))
        if norm == 0.0:
            raise ResonantNumericalError("longitudinal direction cannot be zero")
        object.__setattr__(self, "longitudinal_direction", direction / norm)
        if self.kappa < 0.0 or self.omega <= 0.0:
            raise ResonantNumericalError("geometry requires kappa >= 0 and omega > 0")
        if self.handedness not in (-1, 0, 1):
            raise ResonantNumericalError("handedness must be -1, 0, or +1")


def flow_line(r0: float, s0: float, theta: Any, *, theta0: float = 0.0,
              kappa: float = 0.0, omega: float = 1.0, axial_speed: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    angles = _as_f64(theta, name="theta")
    if kappa < 0.0 or omega <= 0.0:
        raise ResonantNumericalError("flow-line rates are invalid")
    delta = angles - float(theta0)
    return float(r0) * np.exp(-(float(kappa) / float(omega)) * delta), float(s0) + (float(axial_speed) / float(omega)) * delta


def contraction_rate_ratio(contraction: float, delta_theta: float, *, omega: float = 1.0) -> float:
    if not 0.0 < contraction <= 1.0 or delta_theta <= 0.0 or omega <= 0.0:
        raise ResonantNumericalError("contraction and angular interval are invalid")
    return float(omega * math.log(1.0 / contraction) / delta_theta)


def uniform_axial_divergence(kappa: float) -> float:
    if kappa < 0.0:
        raise ResonantNumericalError("kappa must be nonnegative")
    return -2.0 * float(kappa)


def geometry_from_flow(flow: Any, *, signed_current: float = 0.0, handedness: int = 0,
                       kappa: float = 0.0, omega: float = 1.0, axial_speed: float = 0.0,
                       angular_convention: str = "declared") -> ResonantGeometryRecord:
    return ResonantGeometryRecord(flow, signed_current, handedness, kappa, omega, axial_speed,
                                  angular_convention, uniform_axial_divergence(kappa))


def metric_edge_weights(coordinates: Any, edges: Sequence[Sequence[int]], volumes: Any, *, scale: float = 1.0) -> np.ndarray:
    from numpy import asarray, finfo, sqrt, float64, array
    from math import sqrt as math_sqrt

    points = asarray(coordinates, dtype=float64)
    if points.ndim != 2:
        raise ResonantNumericalError("coordinates must be a matrix")

    volume = _metric_vector(volumes, len(points), "volumes")
    tiny = finfo(float64).tiny

    result = []
    n_points = len(points)

    # Pre-lookup points and volume arrays to avoid repeated attribute access in loop
    # This is a micro-optimization for tight loops, ensuring we access local variables

    for edge in edges:
        if len(edge) != 2:
            raise ResonantNumericalError("edges must be endpoint pairs")
        source, destination = int(edge[0]), int(edge[1])

        if not (0 <= source < n_points) or not (0 <= destination < n_points) or source == destination:
            raise ResonantNumericalError("invalid metric edge")

        # Manual dot product is faster than np.linalg.norm for single vector in tight loops
        dx = points[destination, 0] - points[source, 0]
        dy = points[destination, 1] - points[source, 1]
        dz = points[destination, 2] - points[source, 2]
        length = math_sqrt(dx*dx + dy*dy + dz*dz)

        if length == 0.0:
            length = tiny

        vol_src = volume[source]
        vol_dst = volume[destination]
        weight = scale / (length * math_sqrt(vol_src * vol_dst))
        result.append(weight)

    return array(result, dtype=float64)


def basis_change(q: Any, p: Any, basis: Any, *, operators: Mapping[str, Any] | None = None,
                 readouts: Mapping[str, Any] | None = None, suspended_view: Mapping[str, Any] | None = None) -> dict[str, Any]:
    coordinates = _as_f64(q, name="coordinates").reshape(-1)
    momenta = _as_f64(p, coordinates.shape, "momenta")
    s = _as_f64(basis, (coordinates.size, coordinates.size), "basis")
    if abs(float(np.linalg.det(s))) <= 1e-14:
        raise ResonantNumericalError("basis change must be invertible")
    inverse = np.linalg.inv(s)
    inverse_transpose = inverse.T
    result: dict[str, Any] = {"q": s @ coordinates, "p": inverse_transpose @ momenta,
                              "mapping": {"S": s.tolist(), "S_inverse_transpose": inverse_transpose.tolist()},
                              "frame_lineage": {"from": "canonical", "to": _canonical_sha256(s.tolist())},
                              "invalidated": []}
    if operators is not None:
        result["operators"] = {key: s @ _as_f64(value, (coordinates.size, coordinates.size), key) @ inverse
                               for key, value in operators.items()}
    if readouts is not None:
        result["readouts"] = {key: inverse_transpose @ _as_f64(value, (coordinates.size,), key)
                              for key, value in readouts.items()}
    if suspended_view is not None:
        result["suspended_view"] = None
        result["invalidated"].append("suspended_view")
    result["invalidated"] += ["solver_iterates", "boundary_responses"]
    return result


def moving_frame_rhs(y: Any, rotation: Any, rotation_rate: Any, force: Any, *,
                     include_frame_motion: bool = True) -> np.ndarray:
    vec = _as_f64(y, name="frame coordinates").reshape(-1)
    r = _as_f64(rotation, (vec.size, vec.size), "rotation")
    rd = _as_f64(rotation_rate, (vec.size, vec.size), "rotation_rate")
    f = _as_f64(force, vec.shape, "force")
    result = r.T @ f
    if include_frame_motion:
        result = result - r.T @ rd @ vec
    return result


def passive_rotation_check(y: Any, rotation: Any, rotation_rate: Any, *, force: Any = None) -> dict[str, float]:
    vec = _as_f64(y, name="frame coordinates").reshape(-1)
    f = np.zeros_like(vec) if force is None else _as_f64(force, vec.shape, "force")
    full = moving_frame_rhs(vec, rotation, rotation_rate, f, include_frame_motion=True)
    r = _as_f64(rotation, (vec.size, vec.size), "rotation")
    rd = _as_f64(rotation_rate, (vec.size, vec.size), "rotation_rate")
    expected_motion = -r.T @ rd @ vec
    omission_error = omitted - (r.T @ f + expected_motion)
    return {"with_frame_motion_norm": float(np.linalg.norm(full)), "omitted_term_norm": float(np.linalg.norm(omission_error)),
            "passive_work_with_term": float(vec @ full), "omitted_work": float(vec @ omission_error)}


# Descriptive aliases keep the mathematical operation discoverable to callers
# that use the Section 18 terminology rather than the implementation names.
alignment_hamiltonian = alignment_energy
reciprocal_exchange_block = reciprocal_exchange
ResonantNumericalStage = ResonantExchangeStage
ResonantGeometry = ResonantGeometryRecord
moving_frame_flow = moving_frame_rhs
axial_order_projection = _axis_projection

def reverse_axis_representative(axis: Any, handedness: int) -> tuple[np.ndarray, int]:
    n = _as_f64(axis, (3,), "axis")
    if handedness not in (-1, 0, 1):
        raise ResonantNumericalError("handedness must be -1, 0, or +1")
    return -n, int(handedness)
# Explicit descriptive aliases make the lowering discoverable without adding
# another implementation or another state owner.
__all__ = [
    "SCHEMA", "LAYOUT", "HELICAL_PACKET_SCHEMA", "HELICAL_PACKET_BASIS",
    "HELICAL_PACKET_CHANNELS", "PARENT_SUMMARY_PATH", "PARENT_REGISTER_PATHS",
    "PARENT_SUMMARY_LAYOUT", "PARENT_SUMMARY_REGISTER_SCHEMA",
    "PARENT_REGISTER_LAYOUT", "PARENT_REGISTER_SCHEMA",
    "REGIONAL_KERNEL_NAME", "REGIONAL_KERNEL_MAX_WORK",
    "REGIONAL_STATE_SCHEMA", "REGIONAL_RESULT_SCHEMA",
    "ResonantNumericalError", "ResonantDeviceUnavailableError",
    "ResonantStageMismatchError", "ResonantMetricTransform",
    "ResonantRegionRecord", "ResonantHierarchySpec", "ResonantHierarchy",
    "ResonantExchangeStage", "ResonantGeometryRecord",
    "ResonantProfile", "ResonantProblem", "ResonantWorkspace",
    "initial_workspace", "bind_workspace", "apply_pool_impulse",
    "advance_workspace_gpu_cohort",
    "metric_weighted_transform", "unweighted_transform_error",
    "reciprocal_exchange", "reciprocal_exchange_power", "apply_reciprocal_exchange",
    "transported_phase_mismatch", "constraint_tangent_gradient",
    "alignment_energy", "alignment_hamiltonian", "alignment_gradients", "alignment_step",
    "flow_line", "contraction_rate_ratio", "uniform_axial_divergence",
    "geometry_from_flow", "ResonantGeometry", "metric_edge_weights", "basis_change",
    "moving_frame_rhs", "moving_frame_flow", "passive_rotation_check", "reverse_axis_representative",
    "reciprocal_exchange_block", "ResonantNumericalStage",
    "metric_weighted_restrict", "metric_weighted_prolongate",
    "axial_order_projection",
]
