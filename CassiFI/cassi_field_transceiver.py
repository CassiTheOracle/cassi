"""Field-derived temporal input/output realizations of the canonical wave law.

The beta=0 realization uses a Krylov projection of the constrained, energy-
whitened midpoint map. Its residual certificate includes omitted state transport,
not merely the current output residual. Nonlinear dynamics retain the full AVF
operator. These are derived numerical coordinates, never independently learned
weights. The heartbeat is external to this passive, fixed-duration local response.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from copy import deepcopy
from dataclasses import replace
from typing import Any, Mapping, Sequence

import numpy as np

from cassi_field_regions import KernelResult

from cassi_resonant_field import (
    ResonantNumericalError, ResonantProblem, ResonantProfile, ResonantWorkspace,
    _WaveOperator, bind_workspace,
)

REGIONAL_KERNEL_NAME = "numerical.transceiver"
REGIONAL_KERNEL_MAX_WORK = 4_096
REGIONAL_STATE_SCHEMA = "cassifi.regional-transceiver-state.v1"
REGIONAL_RESULT_SCHEMA = "cassifi.regional-kernel-result.v1"
REGIONAL_TASK_SCHEMA = "cassifi.regional-transceiver-task.v1"
_REGIONAL_PANEL_MAX = 256
_REGIONAL_MAX_PANELS = 1_000_000
_REGIONAL_FULL_WORDS = ("base_state", "input_lift", "output_rows", "initial_state")
_REGIONAL_FULL_OPTIONAL_WORDS = ("transition", "drive")
_REGIONAL_REDUCED_WORDS = (
    "transition", "drive", "lift", "output", "direct", "offset",
    "energy", "energy_linear", "residual",
)
_REGIONAL_STATE_KEYS = frozenset({
    "schema", "family", "task", "operation", "phase", "parent_versions",
    "metadata", "recipe", "full_words", "reduced_words", "inputs",
    "input_errors", "previous_inputs", "mode", "coordinates", "ticks",
    "error_radius", "model_error", "state_error", "transport_error",
    "horizon", "force_full", "construction_cursor", "advance_cursor",
    "journal", "ledger", "result",
})
 


SCHEMA = "cassifi.field-transceiver.v1"
_RECEIPT_SCHEMA = "cassifi.field-transceiver-receipt.v1"
_MAX_DENSE_DIM = 512
_MAX_RANK = 64
_MAX_PORTS = 4096
_MAX_TICKS = 4096
_SQRT2 = math.sqrt(2.0)


def _array(value: Any, shape: tuple[int, ...] | None = None, name: str = "array") -> np.ndarray:
    try:
        out = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ResonantNumericalError(f"{name} must be numeric") from exc
    if shape is not None and out.shape != shape:
        raise ResonantNumericalError(f"{name} must have shape {shape}, got {out.shape}")
    if not np.isfinite(out).all():
        raise ResonantNumericalError(f"{name} contains non-finite values")
    return out


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, np.number)):
        raise ResonantNumericalError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ResonantNumericalError(f"{name} must be finite")
    return result


def _int(value: Any, name: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or not low <= value <= high:
        raise ResonantNumericalError(f"{name} must be an integer in [{low},{high}]")
    return int(value)


def _json(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return _json(value.tolist())
    if isinstance(value, (np.integer, np.floating)):
        return _json(value.item())
    if isinstance(value, Mapping):
        return {key: _json(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        raise ResonantNumericalError("non-finite value cannot be serialized")
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise ResonantNumericalError(f"unsupported JSON value: {type(value).__name__}")


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(_json(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _ids(value: Any, name: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)):
        raise ResonantNumericalError(f"{name} must be a sequence")
    result = tuple(value)
    if not result or len(result) > _MAX_RANK or any(not isinstance(item, str) or not item for item in result) or len(result) != len(set(result)):
        raise ResonantNumericalError(f"{name} must contain 1..{_MAX_RANK} unique nonempty strings")
    return result


def _profile(data: Mapping[str, Any]) -> ResonantProfile:
    fields = set(ResonantProfile.__dataclass_fields__)
    if not isinstance(data, Mapping) or set(data) - fields - {"layout_identity"}:
        raise ResonantNumericalError("kernel profile is invalid")
    profile = ResonantProfile(**{key: value for key, value in data.items() if key in fields})
    if data.get("layout_identity", profile.layout_identity) != profile.layout_identity:
        raise ResonantNumericalError("kernel layout identity mismatch")
    if profile.port_count > _MAX_PORTS:
        raise ResonantNumericalError("transceiver port capacity exceeded")
    return profile


def _problem_data(problem: ResonantProblem) -> dict[str, Any]:
    return _json({
        "variable_ids": problem.variable_ids, "precision": problem.precision,
        "linear_b": problem.linear_b, "observed": problem.observed,
        "affine_constraints": problem.affine_constraints,
        "dependency_sha256": problem.dependency_sha256,
    })


def _problem(data: Mapping[str, Any]) -> ResonantProblem:
    if not isinstance(data, Mapping) or set(data) != {"variable_ids", "precision", "linear_b", "observed", "affine_constraints", "dependency_sha256"}:
        raise ResonantNumericalError("kernel problem is invalid")
    return ResonantProblem(**dict(data))


def _workspace(profile: ResonantProfile, bindings: Mapping[str, Any], z: np.ndarray) -> ResonantWorkspace:
    n = profile.port_count
    page = np.zeros(profile.page_shape, dtype=np.float64)
    for lane in range(4):
        page[0, lane:9*n:9, 0] = z[lane*n:(lane+1)*n]
    return ResonantWorkspace(profile=profile, field_page=page, bindings=bindings)


def _vector(workspace: ResonantWorkspace) -> np.ndarray:
    n = workspace.profile.port_count
    return np.concatenate([workspace._field[0, lane:9*n:9, 0] for lane in range(4)])


def _effective(problem: ResonantProblem, input_ids: Sequence[str], values: Mapping[str, float]) -> ResonantProblem:
    observed = {key: value for key, value in problem.observed.items() if key in problem.variable_ids and key not in input_ids}
    observed.update({name: values.get(name, 0.0) for name in input_ids})
    return replace(problem, observed=observed)


def _operator(kernel: Mapping[str, Any], values: Mapping[str, float]) -> _WaveOperator:
    profile = _profile(kernel["profile"])
    problem = _effective(_problem(kernel["problem"]), kernel["input_ids"], values)
    return _WaveOperator(_workspace(profile, kernel["bindings"], np.zeros(4*profile.port_count)), problem)


def _krylov(transition: np.ndarray, seeds: np.ndarray, rank: int) -> np.ndarray:
    columns: list[np.ndarray] = []
    frontier = [seeds[:, index] for index in range(seeds.shape[1])]
    while frontier and len(columns) < rank:
        following = []
        for raw in frontier:
            value = raw.copy()
            for _ in range(2):
                for column in columns:
                    value -= column * float(column @ value)
            norm = float(np.linalg.norm(value))
            if norm > 2e-13 * max(1.0, float(np.linalg.norm(raw))):
                column = value / norm
                columns.append(column)
                following.append(transition @ column)
                if len(columns) == rank:
                    break
        frontier = following
    return np.column_stack(columns) if columns else np.zeros((transition.shape[0], 0))


def _state(
    mode: str,
    coordinates: np.ndarray,
    inputs: np.ndarray,
    ticks: int,
    error: float,
    *,
    transport_error: np.ndarray | None = None,
    model_error: float | None = None,
    state_error: float = 0.0,
) -> dict[str, Any]:
    """Encode a restartable state with output and physical error radii.

    ``model_error`` is an output-space omission bound. ``state_error`` is the
    corresponding physical energy-coordinate radius needed by a later full
    AVF expansion. ``transport_error`` is a componentwise interval in the
    reduced coordinates. Keeping these distinct is necessary when the output
    map has a small or null row.
    """
    if model_error is None:
        model_error = error
    if transport_error is None:
        transport_error = np.zeros(0, dtype=np.float64)
    result = _json({
        "schema": SCHEMA, "mode": mode, "state": coordinates, "inputs": inputs,
        "ticks": ticks, "error_bound": error, "transport_error": transport_error,
        "model_error": model_error, "state_error": state_error,
    })
    result["state_sha256"] = _digest(result)
    return result


def _transport_output(kernel: Mapping[str, Any], transport_error: np.ndarray, input_error: np.ndarray | None = None) -> float:
    """Bound readout uncertainty using the actual compact input/output maps."""
    rom = kernel["rom"]
    if rom is None:
        return 0.0
    q = _array(transport_error)
    e = np.zeros(len(kernel["input_ids"])) if input_error is None else _array(input_error)
    rows = np.abs(_array(rom["output"])) @ np.abs(q)
    rows += np.abs(_array(rom["direct"])) @ np.abs(e)
    return float(np.max(rows, initial=0.0))


def _working_transport(kernel: Mapping[str, Any], working_state: Mapping[str, Any]) -> tuple[np.ndarray, float, float]:
    """Read uncertainty coordinates, safely accepting only legacy full states."""
    rank = int(kernel["rank"])
    if "transport_error" not in working_state:
        if working_state["mode"] == "reduced":
            raise ResonantNumericalError("legacy reduced state lacks physical uncertainty radius")
        return np.zeros(0, dtype=np.float64), float(working_state["error_bound"]), 0.0
    expected = rank if working_state["mode"] == "reduced" else 0
    transport = _array(working_state["transport_error"], (expected,), "transport error")
    if np.any(transport < 0):
        raise ResonantNumericalError("negative transport error")
    model = _number(working_state["model_error"], "model error")
    physical = _number(working_state["state_error"], "state error")
    if model < 0 or model > float(working_state["error_bound"]) + 1e-12 or physical < 0:
        raise ResonantNumericalError("invalid uncertainty decomposition")
    return transport, model, physical


def _validate_state_digest(value: Mapping[str, Any], key: str) -> None:
    if value[key] != _digest({name: item for name, item in value.items() if name != key}):
        raise ResonantNumericalError(f"{key} mismatch")


def _validate_kernel(kernel: Mapping[str, Any]) -> tuple[ResonantProfile, int, int, int]:
    keys = {"schema", "profile", "problem", "bindings", "input_ids", "output_ids", "base_state", "input_lift", "output_rows", "initial_state", "initial_reduced", "initial_error", "rank", "input_bound", "horizon_ticks", "error_allowance", "status", "reason", "certificate", "dimensions", "rom", "bounds", "kernel_sha256"}
    if not isinstance(kernel, Mapping) or set(kernel) != keys or kernel["schema"] != SCHEMA:
        raise ResonantNumericalError("unsupported transceiver kernel")
    profile = _profile(kernel["profile"])
    d = 4*profile.port_count
    inputs, outputs = _ids(kernel["input_ids"], "input_ids"), _ids(kernel["output_ids"], "output_ids")
    if set(inputs).intersection(outputs):
        raise ResonantNumericalError("input and output ports must be distinct")
    ni, no = len(inputs), len(outputs)
    rank = _int(kernel["rank"], "rank", 0, _MAX_RANK)
    for key, shape in (("base_state", (d,)), ("initial_state", (d,)), ("input_lift", (d, ni)), ("output_rows", (no, d)), ("initial_reduced", (rank,))):
        _array(kernel[key], shape, key)
    for key in ("initial_error", "input_bound", "error_allowance"):
        if _number(kernel[key], key) < 0:
            raise ResonantNumericalError(f"{key} must be nonnegative")
    _int(kernel["horizon_ticks"], "horizon_ticks", 1, _MAX_TICKS)
    if kernel["status"] not in {"active", "expanded"}:
        raise ResonantNumericalError("invalid kernel status")
    rom = kernel["rom"]
    if rom is not None:
        if profile.beta != 0.0 or not rank or not isinstance(rom, Mapping):
            raise ResonantNumericalError("invalid compact realization")
        shapes = {"transition": (rank, rank), "drive": (rank, ni+1), "lift": (d, rank),
                  "output": (no, rank), "direct": (no, ni), "offset": (no,),
                  "energy": (rank+ni+1, rank+ni+1), "energy_linear": (rank+ni+1,)}
        for key, shape in shapes.items():
            _array(rom[key], shape, key)
        residual = _array(rom["residual"], name="residual")
        if residual.ndim != 2 or residual.shape[1] != rank+ni+1 or residual.shape[0] > rank+ni+1:
            raise ResonantNumericalError("invalid residual factor")
    elif rank or kernel["status"] == "active":
        raise ResonantNumericalError("compact realization is missing")
    for key in ("growth", "input_gain", "output_gain", "full_output_gain", "roundoff", "state_roundoff", "state_gain", "h_min", "h_max", "linear_norm", "beta_max", "lift_gain"):
        if _number(kernel["bounds"][key], key) < 0:
            raise ResonantNumericalError("invalid numerical bound")
    return profile, d, ni, rank


def validate_transceiver(kernel: Mapping[str, Any], working_state: Mapping[str, Any]) -> None:
    _, d, ni, rank = _validate_kernel(kernel)
    old_keys = {"schema", "mode", "state", "inputs", "ticks", "error_bound", "state_sha256"}
    new_keys = old_keys | {"transport_error", "model_error", "state_error"}
    if not isinstance(working_state, Mapping) or set(working_state) not in (old_keys, new_keys) or working_state["schema"] != SCHEMA:
        raise ResonantNumericalError("unsupported transceiver working state")
    if working_state["mode"] not in {"full", "reduced"} or working_state["mode"] == "reduced" and kernel["rom"] is None:
        raise ResonantNumericalError("invalid working realization")
    _array(working_state["state"], (rank if working_state["mode"] == "reduced" else d,), "working state")
    _array(working_state["inputs"], (ni,), "working inputs")
    _int(working_state["ticks"], "ticks", 0, 2**53-1)
    if _number(working_state["error_bound"], "error bound") < 0:
        raise ResonantNumericalError("negative error bound")
    if set(working_state) == new_keys:
        _working_transport(kernel, working_state)
    _validate_state_digest(working_state, "state_sha256")
    _validate_state_digest(kernel, "kernel_sha256")


def condense_workspace(workspace: ResonantWorkspace, problem: ResonantProblem, *, input_ids: Sequence[str], output_ids: Sequence[str], rank: int = 16, error_allowance: float = 1e-3, input_bound: float = 4.0, horizon_ticks: int = 64) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    started = time.perf_counter()
    input_ids, output_ids = _ids(input_ids, "input_ids"), _ids(output_ids, "output_ids")
    rank = _int(rank, "rank", 0, _MAX_RANK)
    horizon_ticks = _int(horizon_ticks, "horizon_ticks", 1, _MAX_TICKS)
    input_bound, error_allowance = _number(input_bound, "input_bound"), _number(error_allowance, "error_allowance")
    if input_bound < 0 or error_allowance < 0 or set(input_ids).intersection(output_ids):
        raise ResonantNumericalError("invalid input/output envelope")
    if not set((*input_ids, *output_ids)).issubset(problem.variable_ids):
        raise ResonantNumericalError("transceiver ports are outside the supported problem")
    profile = _profile(workspace.profile.as_dict())
    bound_workspace = bind_workspace(workspace, problem)
    n, ni, no = profile.port_count, len(input_ids), len(output_ids)
    d = 4*n
    kernel: dict[str, Any] = {"schema": SCHEMA, "profile": profile.as_dict(), "problem": _problem_data(problem), "bindings": _json(bound_workspace.bindings), "input_ids": list(input_ids), "output_ids": list(output_ids)}
    operator = _operator(kernel, {})
    base = operator.boundary(np.zeros(d), max(profile.tolerance, 1e-10))
    initial = operator.boundary(_vector(bound_workspace), max(profile.tolerance, 1e-10))
    lift = np.column_stack([_operator(kernel, {name: 1.0}).boundary(np.zeros(d), max(profile.tolerance, 1e-10)) - base for name in input_ids])
    output = np.zeros((no, d))
    for row, name in enumerate(output_ids):
        port = int(bound_workspace.bindings[name]["port"])
        output[row, port] = output[row, n+port] = 1.0/_SQRT2
    mass = np.asarray(operator.inv_mass)
    mass_eigen = mass if mass.ndim == 1 else np.linalg.eigvalsh(mass)
    precision_eigen = np.linalg.eigvalsh(problem.precision)
    h_min = min(1.0, profile.relative_stiffness, float(mass_eigen.min()), float(precision_eigen.min()))
    h_max = max(1.0, profile.relative_stiffness, float(mass_eigen.max()), float(precision_eigen.max()))
    bounds = {"growth": math.sqrt(h_max/max(h_min, 1e-300)), "output_gain": 1.0,
              "input_gain": 0.0, "full_output_gain": float(np.linalg.norm(output, 2)),
              "roundoff": 0.0, "state_roundoff": 0.0, "state_gain": 1.0,
              "h_min": h_min, "h_max": h_max,
              "linear_norm": float(np.linalg.norm(problem.linear_b)), "beta_max": float(np.max(operator.beta)),
              "lift_gain": float(np.linalg.norm(lift, 2))}
    rom = None
    reduced = np.zeros(0)
    initial_error = 0.0
    certificate: dict[str, Any] = {"available": False, "passive": True}
    reason = "full nonlinear AVF realization" if profile.beta else "full realization; compact rank or dense allowance unavailable"
    free_dim = d - int(np.linalg.matrix_rank(operator.constraints))
    if profile.beta == 0.0 and d <= _MAX_DENSE_DIM and h_min > 0:
        _, singular, vh = np.linalg.svd(operator.constraints, full_matrices=True)
        tolerance = max(operator.constraints.shape)*np.finfo(float).eps*max(1.0, float(singular.max(initial=0.0)))
        tangent = vh[int(np.count_nonzero(singular > tolerance)):].T
        m = tangent.shape[1]
        if m:
            identity = np.eye(d)
            g0 = operator.energy_gradient(np.zeros(d))[1]
            H = np.column_stack([operator.energy_gradient(identity[:, i])[1] - g0 for i in range(d)])
            Hf = tangent.T @ H @ tangent
            eigenvalues, vectors = np.linalg.eigh((Hf+Hf.T)/2)
            S = (vectors*np.sqrt(eigenvalues)) @ vectors.T
            Sinv = (vectors/np.sqrt(eigenvalues)) @ vectors.T
            physical = tangent @ Sinv
            A = S @ tangent.T @ np.column_stack([operator.flow(H @ physical[:, i], False) for i in range(m)])
            boundary = np.column_stack((lift, base))
            forcing = np.column_stack([operator.flow(H @ boundary[:, i] + (g0 if i == ni else 0.0), False) for i in range(ni+1)])
            lhs = np.eye(m) - 0.5*profile.time_step*A
            D = np.linalg.solve(lhs, np.eye(m) + 0.5*profile.time_step*A)
            P = np.linalg.solve(lhs, profile.time_step*S @ tangent.T @ forcing)
            C = output @ physical
            growth = max(1.0, float(np.linalg.norm(D, 2))) + 64*np.finfo(float).eps
            out_gain = float(np.linalg.norm(C, 2))
            state_roundoff = 64*profile.tolerance*math.sqrt(d)*max(1.0, float(np.linalg.norm(S, 2)))
            roundoff = out_gain*state_roundoff
            bounds.update(growth=growth, output_gain=out_gain,
                          input_gain=out_gain*float(np.linalg.norm(P[:, :ni], 2)) + float(np.linalg.norm(output @ lift, 2)),
                          roundoff=roundoff, state_roundoff=state_roundoff,
                          state_gain=float(np.linalg.norm(physical, 2)))
            if rank:
                y0 = S @ tangent.T @ (initial-base)
                V = _krylov(D, np.column_stack((P, y0, C.T)), min(rank, m))
                r = V.shape[1]
                if r:
                    Dr, Pr = V.T @ D @ V, V.T @ P
                    Rs, Rp = D @ V - V @ Dr, P - V @ Pr
                    # QR avoids subtracting nearly equal terms in a residual Gram form.
                    residual = np.linalg.qr(np.column_stack((Rs, Rp)), mode="r")
                    radius = math.sqrt(ni*input_bound**2+1)
                    drive_bound = float(np.linalg.norm(P, 2))*radius
                    state_radius = float(np.linalg.norm(y0))
                    error = float(np.linalg.norm(y0 - V @ (V.T @ y0)))
                    rs, rp = float(np.linalg.norm(Rs, 2)), float(np.linalg.norm(Rp, 2))
                    for _ in range(horizon_ticks):
                        error = growth*error + rs*state_radius + rp*radius + state_roundoff*(1+state_radius+radius)
                        state_radius = growth*state_radius + drive_bound
                    bound = out_gain*error
                    certificate = {"available": True, "passive": True,
                                   "uniform_unexpanded_output_error_bound": bound,
                                   "horizon_ticks": horizon_ticks, "state_residual_norm": rs,
                                   "input_residual_norm": rp, "transition_norm_bound": growth,
                                   "norm": "constrained quadratic energy",
                                   "scope": "online residual enclosure with pre-step full expansion",
                                   "coordinate_transport": "componentwise |dz| <= |D|q + |P_input|e; |dy| <= |C|q + |D_direct|e",
                                   "physical_state_radius": "retained separately from output-space error for safe full expansion"}
                    if out_gain*float(np.linalg.norm(y0 - V @ (V.T @ y0))) <= error_allowance:
                        reconstruction = physical @ V
                        energy_coordinates = np.column_stack((reconstruction, lift, base))
                        rom = _json({"transition": Dr, "drive": Pr, "lift": reconstruction,
                                     "output": C @ V, "direct": output @ lift, "offset": output @ base,
                                     "residual": residual, "energy": energy_coordinates.T @ H @ energy_coordinates,
                                     "energy_linear": energy_coordinates.T @ g0})
                        reduced = V.T @ y0
                        initial_error = out_gain*float(np.linalg.norm(y0 - V @ reduced))
                        reason = "energy-coordinate Krylov response with per-step error admission"
                    else:
                        reason = "uniform compact trajectory bound exceeds allowance; full AVF retained"
    kernel.update(base_state=base, input_lift=lift, output_rows=output, initial_state=initial,
                  initial_reduced=reduced, initial_error=initial_error, rank=len(reduced),
                  input_bound=input_bound, horizon_ticks=horizon_ticks, error_allowance=error_allowance,
                  status="active" if rom is not None else "expanded", reason=reason, certificate=certificate,
                  dimensions={"full": d, "tangent": free_dim, "reduced": len(reduced), "inputs": ni, "outputs": no},
                  rom=rom, bounds=bounds)
    kernel = _json(kernel)
    kernel["kernel_sha256"] = _digest(kernel)
    working = reset_transceiver(kernel)
    receipt = inspect_transceiver(kernel, working)
    receipt.update(operation="condense_workspace", certificate=certificate, kernel_sha256=kernel["kernel_sha256"],
                   build_operations={"dense_linearization_columns": d if profile.beta == 0 and d <= _MAX_DENSE_DIM else 0, "basis_vectors": len(reduced)},
                   elapsed_seconds=time.perf_counter()-started)
    return kernel, working, receipt

def input_problem(
    variable_ids: Sequence[str],
    *,
    diagonal: float = 1.0,
    coupling: float = 0.0,
) -> ResonantProblem:
    """The declared input relation of one input realization, as an explicit object.

    What decides whether a boundary drive reaches the declared readout is the
    relation the declared problem carries, not the input code path: with the
    shipped declared input (``diagonal`` 1, ``coupling`` 0 -- the identity
    precision) the input lift is supported on the input port's own coordinates
    while the readout row sits on the output port's, so the drive is inert, and
    the same construction carries a signal once the declared precision carries a
    cross term between the declared variables. This helper builds that
    construction as an opt-in object instead of a hand-built matrix: every
    declared variable keeps ``diagonal`` on its own coordinate and every pair
    gains ``coupling`` between them. It is additive and default-off: with no
    coupling the returned problem is the shipped declared input, so no existing
    caller changes.
    """

    ids = _ids(variable_ids, "variable_ids")
    diagonal_value = _number(diagonal, "input diagonal")
    coupling_value = _number(coupling, "input coupling")
    if diagonal_value <= 0.0:
        raise ResonantNumericalError("declared input diagonal must be positive")
    if coupling_value < 0.0:
        raise ResonantNumericalError("declared input coupling must be nonnegative")
    count = len(ids)
    precision = np.full((count, count), coupling_value, dtype=np.float64)
    precision[np.diag_indices(count)] += diagonal_value
    # A declared relation must be a coercive energy: a non-positive-definite
    # precision would make the realization's own energy test meaningless.
    if float(np.linalg.eigvalsh(precision).min()) <= 0.0:
        raise ResonantNumericalError(
            "declared input relation must be positive definite"
        )
    return ResonantProblem(variable_ids=ids, precision=precision)


def condense_input(
    workspace: ResonantWorkspace,
    *,
    input_ids: Sequence[str],
    output_ids: Sequence[str],
    diagonal: float = 1.0,
    coupling: float = 0.0,
    rank: int = 16,
    error_allowance: float = 1e-3,
    input_bound: float = 4.0,
    horizon_ticks: int = 64,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Condense the declared input realization, optionally carrying a coupling.

    This is :func:`condense_workspace` with the declared input relation named
    explicitly by the same two numbers :func:`input_problem` builds it from, so a
    caller can opt into the coupled boundary drive without changing what the
    shipped declared input is. Default-off: ``coupling`` 0 with ``diagonal`` 1
    declares the identity precision, which is exactly the shipped declared input,
    and the realization returned is ``condense_workspace``'s for that problem --
    this function adds a name for the relation, never a second condenser.
    """

    inputs, outputs = _ids(input_ids, "input_ids"), _ids(output_ids, "output_ids")
    return condense_workspace(
        workspace,
        input_problem((*inputs, *outputs), diagonal=diagonal, coupling=coupling),
        input_ids=inputs,
        output_ids=outputs,
        rank=rank,
        error_allowance=error_allowance,
        input_bound=input_bound,
        horizon_ticks=horizon_ticks,
    )


def _initial_state_error(kernel: Mapping[str, Any]) -> float:
    rom = kernel["rom"]
    if rom is None:
        return 0.0
    exact = _array(kernel["initial_state"])
    reconstructed = _array(kernel["base_state"]) + _array(rom["lift"]) @ _array(kernel["initial_reduced"])
    return float(np.linalg.norm(exact-reconstructed))


def reset_transceiver(kernel: Mapping[str, Any]) -> dict[str, Any]:
    _, _, ni, rank = _validate_kernel(kernel)
    reduced = kernel["rom"] is not None
    physical_error = _initial_state_error(kernel) if reduced else 0.0
    return _state(
        "reduced" if reduced else "full",
        _array(kernel["initial_reduced"] if reduced else kernel["initial_state"]),
        np.zeros(ni), 0, float(kernel["initial_error"]),
        transport_error=np.zeros(rank if reduced else 0),
        model_error=float(kernel["initial_error"]),
        state_error=physical_error,
    )


def _lift(kernel: Mapping[str, Any], state: np.ndarray, inputs: np.ndarray) -> np.ndarray:
    return _array(kernel["base_state"]) + _array(kernel["input_lift"]) @ inputs + _array(kernel["rom"]["lift"]) @ state


def _readout(kernel: Mapping[str, Any], mode: str, state: np.ndarray, inputs: np.ndarray) -> np.ndarray:
    if mode == "full":
        return _array(kernel["output_rows"]) @ state
    rom = kernel["rom"]
    return _array(rom["offset"]) + _array(rom["direct"]) @ inputs + _array(rom["output"]) @ state


def advance_transceiver(kernel: Mapping[str, Any], working_state: Mapping[str, Any], *, inputs: Mapping[str, Any], ticks: int = 1, force_full: bool = False, input_errors: Mapping[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    started = time.perf_counter()
    validate_transceiver(kernel, working_state)
    ticks = _int(ticks, "ticks", 1, _MAX_TICKS)
    if not isinstance(force_full, bool) or not isinstance(inputs, Mapping) or set(inputs) - set(kernel["input_ids"]):
        raise ResonantNumericalError("invalid receiving inputs or full-mode flag")
    errors = {} if input_errors is None else input_errors
    if not isinstance(errors, Mapping) or set(errors) - set(kernel["input_ids"]):
        raise ResonantNumericalError("invalid input error channels")
    u = np.array([_number(inputs.get(name, 0.0), name) for name in kernel["input_ids"]])
    uncertainty = np.array([_number(errors.get(name, 0.0), name) for name in kernel["input_ids"]])
    if np.any(uncertainty < 0) or np.any(np.abs(u)+uncertainty > kernel["input_bound"]):
        raise ResonantNumericalError("input uncertainty leaves the declared envelope")
    profile = _profile(kernel["profile"])
    state = _array(working_state["state"]).copy()
    previous = _array(working_state["inputs"])
    mode = working_state["mode"]
    transport, model_error, state_error = _working_transport(kernel, working_state)
    error = float(working_state["error_bound"])
    bounds = kernel["bounds"]
    propagated = local = 0.0
    counts = {"full_steps": 0, "reduced_steps": 0, "operator_applications": 0, "nonlinear_iterations": 0}
    rom = kernel["rom"]
    w = np.concatenate((u, [1.0]))
    operator = None
    for tick in range(ticks):
        if mode == "reduced" and (force_full or working_state["ticks"]+tick >= kernel["horizon_ticks"]):
            # Retain a physical omission radius when expanding; output-space
            # error alone cannot certify a hidden state with a small readout.
            mapped = np.abs(_array(rom["lift"])) @ np.abs(transport)
            mapped += np.abs(_array(kernel["input_lift"])) @ np.abs(uncertainty)
            state_error += float(np.linalg.norm(mapped))
            transport = np.zeros(0, dtype=np.float64)
            state, mode = _lift(kernel, state, previous), "full"
        if mode == "reduced":
            joined = np.concatenate((state, w))
            residual_matrix = _array(rom["residual"])
            residual = float(np.linalg.norm(residual_matrix @ joined))
            roundoff = bounds["roundoff"]*(1+float(np.linalg.norm(state))+float(np.linalg.norm(w)))
            step_local = bounds["output_gain"]*residual + roundoff
            transition_abs = np.abs(_array(rom["transition"]))
            drive_input_abs = np.abs(_array(rom["drive"]))[:, :len(u)]
            transport_next = transition_abs @ np.abs(transport) + drive_input_abs @ np.abs(uncertainty)
            residual_coordinate = (
                np.abs(residual_matrix[:, :len(transport)]) @ np.abs(transport)
                + np.abs(residual_matrix[:, len(transport):len(transport)+len(u)]) @ np.abs(uncertainty)
            )
            residual_uncertainty = float(np.linalg.norm(residual_coordinate))
            model_base = bounds["growth"]*model_error + step_local + bounds["output_gain"]*residual_uncertainty
            state_next = bounds["growth"]*state_error + bounds["state_gain"]*(residual + residual_uncertainty + bounds["state_roundoff"]*(1+float(np.linalg.norm(state))+float(np.linalg.norm(w))))
            # The physical omission radius is independently retained because
            # a small compact readout can hide a large state. It is another
            # sound bound on the same omitted trajectory, so max (not sum)
            # avoids paying twice while still enclosing the output.
            model_next = max(model_base, bounds["full_output_gain"]*state_next)
            output_uncertainty = _transport_output(kernel, transport_next, uncertainty)
            proposed_error = model_next + output_uncertainty
            if proposed_error <= kernel["error_allowance"]:
                state = _array(rom["transition"]) @ state + _array(rom["drive"]) @ w
                transport, model_error, state_error = transport_next, model_next, state_next
                error = proposed_error
                local += step_local
                propagated += bounds["output_gain"]*residual_uncertainty + output_uncertainty
                counts["reduced_steps"] += 1
                previous = u
                continue
            # Refuse compact admission and re-run this tick in the full
            # realization, carrying both coordinate and physical radii.
            mapped = np.abs(_array(rom["lift"])) @ np.abs(transport)
            mapped += np.abs(_array(kernel["input_lift"])) @ np.abs(uncertainty)
            state_error += float(np.linalg.norm(mapped))
            transport = np.zeros(0, dtype=np.float64)
            state, mode = _lift(kernel, state, previous), "full"
        if operator is None:
            operator = _operator(kernel, dict(zip(kernel["input_ids"], u)))
        before = operator.boundary(state, max(profile.tolerance, 1e-10))
        applications_before = operator.applications
        state, metrics = operator.step(before, profile.time_step, quiet=False, max_iterations=32, tolerance=profile.tolerance)
        counts["full_steps"] += 1
        counts["operator_applications"] += operator.applications - applications_before
        counts["nonlinear_iterations"] += int(metrics["iterations"])
        radius = float(np.linalg.norm(uncertainty))
        if profile.beta == 0 and kernel["rom"] is not None:
            step_propagated = bounds["input_gain"]*radius
            model_error = bounds["growth"]*(model_error + bounds["full_output_gain"]*state_error) + step_propagated
            state_error = 0.0
            error = model_error
            propagated += step_propagated
        elif model_error or state_error or radius:
            # An enclosing energy ball is intentionally conservative when no
            # compact incremental certificate exists. Never replace it by a
            # guessed gain or erase incoming uncertainty on expansion.
            if bounds["h_min"] <= 0:
                raise ResonantNumericalError("no coercive energy bound for uncertain full transmission")
            norm = float(np.linalg.norm(before)) + state_error + bounds["lift_gain"]*radius
            energy_upper = 0.5*bounds["h_max"]*norm**2 + bounds["linear_norm"]*norm + 0.25*bounds["beta_max"]*norm**4
            enclosing_radius = 2*math.sqrt((energy_upper + bounds["linear_norm"]**2/bounds["h_min"])/bounds["h_min"])
            new_error = float(np.linalg.norm(state)) + enclosing_radius + model_error
            propagated += max(0.0, new_error-model_error)
            model_error, state_error, error = new_error, 0.0, new_error
        else:
            error = model_error
        previous = u
    if not math.isfinite(error) or not math.isfinite(model_error) or not math.isfinite(state_error) or not np.isfinite(state).all():
        raise ResonantNumericalError("temporal response or its bound is not finite")
    next_state = _state(
        mode, state, u, int(working_state["ticks"])+ticks, error,
        transport_error=transport, model_error=model_error, state_error=state_error,
    )
    output = _readout(kernel, mode, state, u)
    resolved = error <= kernel["error_allowance"]
    receipt = {"schema": _RECEIPT_SCHEMA, "operation": "advance_transceiver", "mode": mode,
               "status": "unresolved" if not resolved else "expanded" if mode == "full" else "active",
               "reason": "uncertainty exceeds output allowance" if not resolved else kernel["reason"],
               "values": dict(zip(kernel["output_ids"], output.tolist())), "error_bound": error,
               "local_error_bound": local, "propagated_input_error_bound": propagated,
               "resolved": resolved, "ticks": ticks, "force_full": force_full, "counts": counts,
               "elapsed_seconds": time.perf_counter()-started}
    return next_state, receipt
def inspect_transceiver(kernel: Mapping[str, Any], working_state: Mapping[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    validate_transceiver(kernel, working_state)
    mode = working_state["mode"]
    state, inputs = _array(working_state["state"]), _array(working_state["inputs"])
    output = _readout(kernel, mode, state, inputs)
    if mode == "reduced":
        joined = np.concatenate((state, inputs, [1.0]))
        energy = 0.5*float(joined @ _array(kernel["rom"]["energy"]) @ joined) + float(_array(kernel["rom"]["energy_linear"]) @ joined)
        transport, model_error, state_error = _working_transport(kernel, working_state)
        error = max(model_error, kernel["bounds"]["full_output_gain"]*state_error) + _transport_output(kernel, transport)
    else:
        energy = _operator(kernel, dict(zip(kernel["input_ids"], inputs))).energy_gradient(state)[0]
        error = float(working_state["error_bound"])
    return {"schema": _RECEIPT_SCHEMA, "operation": "inspect_transceiver", "status": kernel["status"],
            "mode": mode, "values": dict(zip(kernel["output_ids"], output.tolist())), "energy": float(energy),
            "error_bound": error, "resolved": error <= kernel["error_allowance"], "passive": True,
            "dimensions": kernel["dimensions"], "reason": kernel["reason"], "ticks": working_state["ticks"],
            "elapsed_seconds": time.perf_counter()-started}


def _regional_copy(value: Any) -> Any:
    """Copy task data through the same canonical JSON boundary as the field."""
    try:
        return json.loads(json.dumps(_json(value), sort_keys=True, separators=(",", ":"), allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise ResonantNumericalError("regional transceiver data is not canonical") from exc
def _regional_full_word_map(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ResonantNumericalError(f"{name} has invalid word keys")
    allowed = set(_REGIONAL_FULL_WORDS) | set(_REGIONAL_FULL_OPTIONAL_WORDS)
    if not set(_REGIONAL_FULL_WORDS).issubset(value) or set(value) - allowed:
        raise ResonantNumericalError(f"{name} has invalid word keys")
    return {
        key: _regional_copy(value[key])
        for key in (*_REGIONAL_FULL_WORDS, *(_REGIONAL_FULL_OPTIONAL_WORDS))
        if key in value
    }


def _regional_shape(value: Any, name: str) -> tuple[int, ...]:
    array = _array(value, name=name)
    if array.ndim not in (1, 2) or not all(int(size) > 0 for size in array.shape):
        raise ResonantNumericalError(f"{name} must be a nonempty vector or matrix")
    return tuple(int(size) for size in array.shape)


def _regional_word_map(value: Any, names: Sequence[str], name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != set(names):
        raise ResonantNumericalError(f"{name} has invalid word keys")
    return {key: _regional_copy(value[key]) for key in names}


def _regional_parents(value: Any, metadata: Mapping[str, Any]) -> list[list[Any]]:
    if value is None:
        value = metadata.get("parent_versions")
    if value is None:
        digest = metadata.get("kernel_sha256") or metadata.get("source_sha256")
        value = [[digest or "regional-transceiver-source", 1]]
    if isinstance(value, Mapping) or isinstance(value, (str, bytes)):
        raise ResonantNumericalError("parent_versions must be a sequence")
    result: list[list[Any]] = []
    try:
        entries = tuple(value)
    except TypeError as exc:
        raise ResonantNumericalError("parent_versions must be a sequence") from exc
    for entry in entries:
        if isinstance(entry, Mapping):
            if set(entry) != {"id", "version"}:
                raise ResonantNumericalError("parent version entry is invalid")
            identifier, version = entry["id"], entry["version"]
        else:
            try:
                identifier, version = tuple(entry)
            except (TypeError, ValueError) as exc:
                raise ResonantNumericalError("parent version entry is invalid") from exc
        if not isinstance(identifier, str) or not identifier:
            raise ResonantNumericalError("parent version id is invalid")
        version = _int(version, "parent version", 1, 2**53 - 1)
        result.append([identifier, version])
    if not result or len({(row[0], row[1]) for row in result}) != len(result):
        raise ResonantNumericalError("parent_versions must be nonempty and unique")
    return result


def _regional_metadata(source: Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(source.get("metadata"), Mapping):
        metadata = _regional_copy(source["metadata"])
    else:
        metadata = _regional_copy({
            key: source[key]
            for key in (
                "profile", "problem", "bindings", "input_ids", "output_ids",
                "input_bound", "horizon_ticks", "error_allowance", "initial_error",
                "initial_reduced", "reason", "certificate", "dimensions", "bounds",
                "status", "kernel_sha256", "parent_versions",
            )
            if key in source
        })
    if not isinstance(metadata, Mapping):
        raise ResonantNumericalError("regional transceiver metadata is invalid")
    metadata = dict(metadata)
    metadata.setdefault("input_bound", 4.0)
    metadata.setdefault("horizon_ticks", 1)
    metadata.setdefault("error_allowance", 0.0)
    metadata.setdefault("initial_error", 0.0)
    metadata.setdefault("reason", "regional transceiver realization")
    metadata.setdefault("bounds", {})
    if not isinstance(metadata.get("input_ids"), list):
        metadata["input_ids"] = list(metadata.get("input_ids", ()))
    if not isinstance(metadata.get("output_ids"), list):
        metadata["output_ids"] = list(metadata.get("output_ids", ()))
    _ids(metadata["input_ids"], "regional input_ids")
    _ids(metadata["output_ids"], "regional output_ids")
    if set(metadata["input_ids"]).intersection(metadata["output_ids"]):
        raise ResonantNumericalError("regional input and output ports must be distinct")
    for key in ("input_bound", "error_allowance", "initial_error"):
        if _number(metadata[key], f"regional {key}") < 0:
            raise ResonantNumericalError(f"regional {key} must be nonnegative")
    _int(metadata["horizon_ticks"], "regional horizon", 1, _MAX_TICKS)
    if not isinstance(metadata["bounds"], Mapping):
        raise ResonantNumericalError("regional numerical bounds are invalid")
    return metadata


def _regional_material(source: Any) -> dict[str, Any]:
    if not isinstance(source, Mapping):
        raise ResonantNumericalError("regional transceiver source must be a mapping")
    if source.get("schema") == REGIONAL_STATE_SCHEMA:
        if not isinstance(source.get("recipe"), Mapping):
            raise ResonantNumericalError("regional state recipe is missing")
        recipe = source["recipe"]
        metadata = _regional_metadata(recipe)
        full = _regional_full_word_map(recipe.get("full_words"), "regional full words")
        reduced = recipe.get("reduced_words")
        reduced = None if reduced is None else _regional_word_map(reduced, _REGIONAL_REDUCED_WORDS, "regional reduced words")
        return {"metadata": metadata, "full_words": full, "reduced_words": reduced}
    if source.get("schema") == REGIONAL_RESULT_SCHEMA:
        metadata = _regional_metadata(source)
        full = _regional_full_word_map(source.get("full_words"), "regional full words")
        reduced = source.get("reduced_words")
        reduced = None if reduced is None else _regional_word_map(reduced, _REGIONAL_REDUCED_WORDS, "regional reduced words")
        return {"metadata": metadata, "full_words": full, "reduced_words": reduced}
    if source.get("schema") == SCHEMA:
        _validate_kernel(source)
        metadata = _regional_metadata(source)
        full = {key: _regional_copy(source[key]) for key in _REGIONAL_FULL_WORDS}
        reduced_source = source.get("rom")
        reduced = None if reduced_source is None else {
            key: _regional_copy(reduced_source[key]) for key in _REGIONAL_REDUCED_WORDS
        }
        return {"metadata": metadata, "full_words": full, "reduced_words": reduced}
    metadata = _regional_metadata(source)
    if "full_words" not in source:
        raise ResonantNumericalError("regional source has no full words")
    full = _regional_full_word_map(source["full_words"], "regional full words")
    reduced_source = source.get("reduced_words")
    reduced = None if reduced_source is None else _regional_word_map(
        reduced_source, _REGIONAL_REDUCED_WORDS, "regional reduced words"
    )
    return {"metadata": metadata, "full_words": full, "reduced_words": reduced}


def _regional_validate_material(material: Mapping[str, Any]) -> tuple[int, int, int, int]:
    metadata = material["metadata"]
    full = material["full_words"]
    input_count, output_count = len(metadata["input_ids"]), len(metadata["output_ids"])
    base_shape = _regional_shape(full["base_state"], "base_state")
    if len(base_shape) != 1:
        raise ResonantNumericalError("base_state must be a vector")
    dimension = base_shape[0]
    expected = {
        "input_lift": (dimension, input_count),
        "output_rows": (output_count, dimension),
        "initial_state": (dimension,),
    }
    for key, shape in expected.items():
        if _regional_shape(full[key], key) != shape:
            raise ResonantNumericalError(f"{key} has invalid shape")
    for key in _REGIONAL_FULL_OPTIONAL_WORDS:
        if key in full:
            shape = (dimension, dimension) if key == "transition" else (dimension, input_count + 1)
            if _regional_shape(full[key], key) != shape:
                raise ResonantNumericalError(f"{key} has invalid shape")
    reduced = material["reduced_words"]
    rank = 0
    if reduced is not None:
        transition_shape = _regional_shape(reduced["transition"], "transition")
        if len(transition_shape) != 2 or transition_shape[0] != transition_shape[1]:
            raise ResonantNumericalError("reduced transition must be square")
        rank = transition_shape[0]
        expected_reduced = {
            "drive": (rank, input_count + 1), "lift": (dimension, rank),
            "output": (output_count, rank), "direct": (output_count, input_count),
            "offset": (output_count,), "energy": (rank + input_count + 1, rank + input_count + 1),
            "energy_linear": (rank + input_count + 1,),
        }
        for key, shape in expected_reduced.items():
            if _regional_shape(reduced[key], key) != shape:
                raise ResonantNumericalError(f"reduced {key} has invalid shape")
        residual_shape = _regional_shape(reduced["residual"], "residual")
        if len(residual_shape) != 2 or residual_shape[1] != rank + input_count + 1:
            raise ResonantNumericalError("reduced residual has invalid shape")
    return dimension, input_count, output_count, rank
def _regional_panels(
    words: Mapping[str, Any],
    names: Sequence[str],
    panel_size: int = _REGIONAL_PANEL_MAX,
) -> list[tuple[str, str, int, int]]:
    panel_size = _int(panel_size, "regional panel size", 1, _REGIONAL_PANEL_MAX)
    panels: list[tuple[str, str, int, int]] = []
    for name in names:
        shape = _regional_shape(words[name], name)
        size = math.prod(shape)
        for start in range(0, size, panel_size):
            panels.append(("words", name, start, min(size, start + panel_size)))
    return panels


def _regional_set_flat(value: Any, shape: tuple[int, ...], index: int, item: float) -> None:
    if len(shape) == 1:
        value[index] = float(item)
    else:
        columns = shape[1]
        value[index // columns][index % columns] = float(item)


def _regional_get_flat(value: Any, shape: tuple[int, ...], index: int) -> float:
    if len(shape) == 1:
        return float(value[index])
    columns = shape[1]
    return float(value[index // columns][index % columns])


def _regional_parent_and_material(source: Any, parent_versions: Any) -> tuple[dict[str, Any], list[list[Any]]]:
    material = _regional_material(source)
    _regional_validate_material(material)
    return material, _regional_parents(parent_versions, material["metadata"])


def regional_construction_state(
    source: Mapping[str, Any],
    *,
    parent_versions: Sequence[Any] | None = None,
    operation: str = "realization",
    panel_size: int = _REGIONAL_PANEL_MAX,
    horizon: int | None = None,
) -> dict[str, Any]:
    """Create a task that panel-copies immutable realization words.

    The recipe is source data only.  Every matrix element is copied by the
    regional kernel under ``construction_cursor``; no numerical evaluator is
    called by that kernel.
    """
    if operation not in {"realization", "reduction", "condensation", "construction"}:
        raise ResonantNumericalError("invalid regional construction operation")
    panel_size = _int(panel_size, "regional panel size", 1, _REGIONAL_PANEL_MAX)
    material, parents = _regional_parent_and_material(source, parent_versions)
    metadata = dict(material["metadata"])
    if horizon is not None:
        metadata["horizon_ticks"] = _int(horizon, "regional horizon", 1, _MAX_TICKS)
    full_source = material["full_words"]
    reduced_source = material["reduced_words"]
    full_words = {
        key: np.zeros(_regional_shape(value, key), dtype=np.float64).tolist()
        for key, value in full_source.items()
    }
    reduced_words = None if reduced_source is None else {
        key: np.zeros(_regional_shape(value, key), dtype=np.float64).tolist()
        for key, value in reduced_source.items()
    }
    panel_count = len(_regional_panels(full_source, tuple(full_source), panel_size))
    if reduced_source is not None:
        panel_count += len(_regional_panels(reduced_source, _REGIONAL_REDUCED_WORDS, panel_size))
    if panel_count > _REGIONAL_MAX_PANELS:
        raise ResonantNumericalError("regional construction exceeds panel capacity")
    dimension, input_count, _, rank = _regional_validate_material(material)
    return {
        "schema": REGIONAL_STATE_SCHEMA,
        "family": REGIONAL_KERNEL_NAME,
        "task": "construction",
        "operation": operation,
        "phase": "running",
        "parent_versions": parents,
        "metadata": _regional_copy(metadata),
        "recipe": {
            "metadata": _regional_copy(metadata),
            "full_words": _regional_copy(full_source),
            "reduced_words": _regional_copy(reduced_source),
        },
        "full_words": full_words,
        "reduced_words": reduced_words,
        "inputs": [0.0] * input_count,
        "input_errors": [0.0] * input_count,
        "previous_inputs": [0.0] * input_count,
        "mode": "reduced" if rank else "full",
        "coordinates": (
            [0.0] * rank if rank else _regional_copy(full_source["initial_state"])
        ),
        "ticks": 0,
        "error_radius": 0.0,
        "model_error": 0.0,
        "state_error": 0.0,
        "transport_error": [0.0] * rank,
        "horizon": int(metadata["horizon_ticks"]),
        "force_full": False,
        "construction_cursor": {"panel": 0, "panel_count": panel_count, "panel_size": panel_size},
        "advance_cursor": {"tick": 0},
        "journal": [],
        "ledger": {"panels": 0, "matrix_elements": 0, "ticks": 0, "reduced_steps": 0, "full_steps": 0},
        "result": None,
    }


def regional_condensation_state(source: Mapping[str, Any], **kwargs: Any) -> dict[str, Any]:
    kwargs.setdefault("operation", "condensation")
    return regional_construction_state(source, **kwargs)
def regional_advance_state(
    source: Mapping[str, Any],
    *,
    inputs: Mapping[str, Any] | Sequence[Any] | None = None,
    input_errors: Mapping[str, Any] | Sequence[Any] | None = None,
    parent_versions: Sequence[Any] | None = None,
    horizon: int | None = None,
    force_full: bool = False,
) -> dict[str, Any]:
    """Create a bounded execution task from a completed regional result."""
    if not isinstance(force_full, bool):
        raise ResonantNumericalError("regional force_full must be boolean")
    if parent_versions is None and isinstance(source, Mapping):
        if source.get("schema") in {REGIONAL_STATE_SCHEMA, REGIONAL_RESULT_SCHEMA}:
            parent_versions = source.get("parent_versions")
    material, parents = _regional_parent_and_material(source, parent_versions)
    metadata = dict(material["metadata"])
    dimension, input_count, output_count, rank = _regional_validate_material(material)
    source_state = source if source.get("schema") == REGIONAL_STATE_SCHEMA else None
    source_result = source if source.get("schema") == REGIONAL_RESULT_SCHEMA else None
    if source_state is not None and source_state.get("phase") != "terminal":
        raise ResonantNumericalError("regional execution requires completed construction")
    if source_result is not None and (
        source_result.get("status") not in {"active", "expanded"}
        and not (
            source_result.get("task") == "construction"
            and source_result.get("status") == "done"
        )
    ):
        raise ResonantNumericalError("regional execution result is not reusable")
    if horizon is None:
        horizon = (
            source_state.get("horizon") if source_state is not None
            else source_result.get("horizon") if source_result is not None
            else metadata["horizon_ticks"]
        )
    horizon = _int(horizon, "regional horizon", 1, _MAX_TICKS)
    ids = metadata["input_ids"]

    def vectors(values: Any, label: str) -> list[float]:
        if values is None:
            return [0.0] * input_count
        if isinstance(values, Mapping):
            if set(values) - set(ids):
                raise ResonantNumericalError(f"{label} has unknown input channels")
            values = [values.get(name, 0.0) for name in ids]
        array = _array(values, (input_count,), label)
        return [float(item) for item in array]

    inherited_inputs = None
    inherited_errors = None
    if source_state is not None:
        inherited_inputs = source_state["inputs"]
        inherited_errors = source_state["input_errors"]
    elif source_result is not None and isinstance(source_result.get("execution"), Mapping):
        inherited_inputs = source_result["execution"].get("inputs")
        inherited_errors = source_result["execution"].get("input_errors")
    current_inputs = vectors(inputs if inputs is not None else inherited_inputs, "regional inputs")
    current_errors = vectors(
        input_errors if input_errors is not None else inherited_errors, "regional input errors"
    )
    bound = _number(metadata["input_bound"], "regional input bound")
    if any(error < 0 for error in current_errors):
        raise ResonantNumericalError("regional input errors must be nonnegative")
    if any(abs(value) + error > bound for value, error in zip(current_inputs, current_errors, strict=True)):
        raise ResonantNumericalError("regional input uncertainty leaves its declared envelope")

    inherited = None
    if source_state is not None:
        inherited = source_state
    elif source_result is not None and isinstance(source_result.get("execution"), Mapping):
        inherited = source_result["execution"]
    if inherited is not None:
        mode = inherited.get("mode", "full")
        raw_coordinates = inherited.get("coordinates")
        if source_state is not None and source_state.get("task") == "construction" and mode == "reduced":
            raw_coordinates = metadata.get("initial_reduced", raw_coordinates)
        coordinates = _regional_copy(raw_coordinates)
        previous_inputs = vectors(inherited.get("previous_inputs"), "regional previous inputs")
        ticks = _int(inherited.get("ticks", 0), "regional ticks", 0, 2**53 - 1)
        error_radius = _number(inherited.get("error_radius", 0.0), "regional error radius")
        model_error = _number(inherited.get("model_error", error_radius), "regional model error")
        state_error = _number(inherited.get("state_error", 0.0), "regional state error")
        transport_error = _array(
            inherited.get("transport_error", ()),
            (rank if mode == "reduced" else 0,),
            "regional transport error",
        ).tolist()
    else:
        mode = "reduced" if rank else "full"
        coordinates = _regional_copy(material["full_words"]["initial_state"])
        if mode == "reduced":
            # The reduced initial coordinates are part of the optional source
            # metadata when supplied by a legacy kernel; otherwise zero is the
            # canonical regional origin.
            initial_reduced = metadata.get("initial_reduced", [0.0] * rank)
            coordinates = _array(initial_reduced, (rank,), "regional initial reduced").tolist()
        previous_inputs = [0.0] * input_count
        ticks = 0
        initial_error = _number(metadata.get("initial_error", 0.0), "regional initial error")
        error_radius = model_error = initial_error
        full_initial = _array(material["full_words"]["initial_state"])
        if mode == "reduced":
            base = _array(material["full_words"]["base_state"])
            lift = _array(material["reduced_words"]["lift"])
            state_error = float(np.linalg.norm(full_initial - base - lift @ np.asarray(coordinates)))
        else:
            state_error = 0.0
        transport_error = [0.0] * (rank if mode == "reduced" else 0)
    if mode not in {"full", "reduced"} or mode == "reduced" and rank == 0:
        raise ResonantNumericalError("regional execution mode is invalid")
    if force_full and mode == "full":
        force_full = False
    if mode == "full":
        coordinates = _array(coordinates, (dimension,), "regional full coordinates").tolist()
        transport_error = []
    else:
        coordinates = _array(coordinates, (rank,), "regional reduced coordinates").tolist()
    if source_state is not None:
        operation = "advance"
        task = "advance"
        recipe = _regional_copy(source_state["recipe"])
        full_words = _regional_copy(source_state["full_words"])
        reduced_words = _regional_copy(source_state["reduced_words"])
        construction_cursor = _regional_copy(source_state["construction_cursor"])
    else:
        operation = "advance"
        task = "advance"
        recipe = {
            "metadata": _regional_copy(metadata),
            "full_words": _regional_copy(material["full_words"]),
            "reduced_words": _regional_copy(material["reduced_words"]),
        }
        full_words = _regional_copy(material["full_words"])
        reduced_words = _regional_copy(material["reduced_words"])
        construction_cursor = {"panel": 0, "panel_count": 0, "panel_size": _REGIONAL_PANEL_MAX}
    return {
        "schema": REGIONAL_STATE_SCHEMA,
        "family": REGIONAL_KERNEL_NAME,
        "task": task,
        "operation": operation,
        "phase": "running",
        "parent_versions": parents,
        "metadata": _regional_copy(metadata),
        "recipe": recipe,
        "full_words": full_words,
        "reduced_words": reduced_words,
        "inputs": current_inputs,
        "input_errors": current_errors,
        "previous_inputs": previous_inputs,
        "mode": mode,
        "coordinates": coordinates,
        "ticks": ticks,
        "error_radius": max(0.0, error_radius),
        "model_error": max(0.0, model_error),
        "state_error": max(0.0, state_error),
        "transport_error": transport_error,
        "horizon": horizon,
        "force_full": force_full,
        "construction_cursor": construction_cursor,
        "advance_cursor": {"tick": ticks},
        "journal": [],
        "ledger": {"panels": 0, "matrix_elements": 0, "ticks": 0, "reduced_steps": 0, "full_steps": 0},
        "result": None,
    }


def regional_expansion_state(
    source: Mapping[str, Any],
    *,
    parent_versions: Sequence[Any] | None = None,
    horizon: int | None = None,
) -> dict[str, Any]:
    """Create a one-quantum task that expands a reduced state to full words."""
    requested = 1 if horizon is None else _int(horizon, "regional horizon", 1, _MAX_TICKS)
    inherited_ticks = 0
    if isinstance(source, Mapping):
        if source.get("schema") == REGIONAL_STATE_SCHEMA:
            inherited_ticks = int(source.get("ticks", 0))
        elif source.get("schema") == REGIONAL_RESULT_SCHEMA and isinstance(source.get("execution"), Mapping):
            inherited_ticks = int(source["execution"].get("ticks", 0))
    requested = max(requested, inherited_ticks)
    state = regional_advance_state(
        source, parent_versions=parent_versions, horizon=requested, force_full=True
    )
    if state["mode"] != "reduced":
        raise ResonantNumericalError("regional expansion requires a reduced realization")
    state["task"] = "expand"
    state["operation"] = "expansion"
    return state


def regional_state(
    source: Mapping[str, Any],
    *,
    operation: str = "construction",
    task: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Dispatch to one typed transceiver construction or execution task."""
    selected = operation if task is None else task
    if selected in {"construction", "realization", "reduction", "condensation"}:
        if selected != "construction":
            kwargs.setdefault("operation", selected)
        return regional_construction_state(source, **kwargs)
    if selected == "advance":
        return regional_advance_state(source, **kwargs)
    if selected in {"expand", "expansion"}:
        return regional_expansion_state(source, **kwargs)
    raise ResonantNumericalError("unknown regional transceiver task")
def _regional_validate_state(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _REGIONAL_STATE_KEYS:
        raise ResonantNumericalError("regional transceiver state keys are invalid")
    if value.get("schema") != REGIONAL_STATE_SCHEMA or value.get("family") != REGIONAL_KERNEL_NAME:
        raise ResonantNumericalError("regional transceiver state schema is invalid")
    if value.get("task") not in {"construction", "advance", "expand"}:
        raise ResonantNumericalError("regional transceiver task is invalid")
    if value.get("phase") not in {"running", "terminal", "fault"}:
        raise ResonantNumericalError("regional transceiver phase is invalid")
    if value.get("operation") not in {
        "construction", "realization", "reduction", "condensation", "advance", "expansion"
    }:
        raise ResonantNumericalError("regional transceiver operation is invalid")
    metadata = _regional_metadata(value.get("metadata"))
    recipe = value.get("recipe")
    if not isinstance(recipe, Mapping) or set(recipe) != {"metadata", "full_words", "reduced_words"}:
        raise ResonantNumericalError("regional transceiver recipe is invalid")
    recipe_material = {
        "metadata": _regional_metadata(recipe["metadata"]),
        "full_words": _regional_full_word_map(recipe["full_words"], "regional recipe full words"),
        "reduced_words": (
            None if recipe["reduced_words"] is None else
            _regional_word_map(recipe["reduced_words"], _REGIONAL_REDUCED_WORDS, "regional recipe reduced words")
        ),
    }
    dimensions = _regional_validate_material(recipe_material)
    material = {
        "metadata": metadata,
        "full_words": _regional_full_word_map(value["full_words"], "regional full words"),
        "reduced_words": (
            None if value["reduced_words"] is None else
            _regional_word_map(value["reduced_words"], _REGIONAL_REDUCED_WORDS, "regional reduced words")
        ),
    }
    if _regional_validate_material(material) != dimensions:
        raise ResonantNumericalError("regional transceiver words changed shape")
    parents = _regional_parents(value["parent_versions"], metadata)
    _, input_count, _, rank = dimensions
    mode = value["mode"]
    if mode not in {"full", "reduced"} or mode == "reduced" and rank == 0:
        raise ResonantNumericalError("regional transceiver mode is invalid")
    _array(value["inputs"], (input_count,), "regional inputs")
    _array(value["input_errors"], (input_count,), "regional input errors")
    _array(value["previous_inputs"], (input_count,), "regional previous inputs")
    if np.any(np.asarray(value["input_errors"], dtype=np.float64) < 0):
        raise ResonantNumericalError("regional input errors must be nonnegative")
    coordinate_size = rank if mode == "reduced" else dimensions[0]
    _array(value["coordinates"], (coordinate_size,), "regional coordinates")
    transport = _array(value["transport_error"], (rank if mode == "reduced" else 0,), "regional transport error")
    if np.any(transport < 0):
        raise ResonantNumericalError("regional transport errors must be nonnegative")
    for key in ("error_radius", "model_error", "state_error"):
        if _number(value[key], f"regional {key}") < 0:
            raise ResonantNumericalError(f"regional {key} must be nonnegative")
    if value["model_error"] > value["error_radius"] + 1e-12:
        raise ResonantNumericalError("regional model error exceeds error radius")
    horizon = _int(value["horizon"], "regional horizon", 1, _MAX_TICKS)
    ticks = _int(value["ticks"], "regional ticks", 0, 2**53 - 1)
    if ticks > horizon:
        raise ResonantNumericalError("regional ticks exceed horizon")
    cursor = value["construction_cursor"]
    if not isinstance(cursor, Mapping) or set(cursor) != {"panel", "panel_count", "panel_size"}:
        raise ResonantNumericalError("regional construction cursor is invalid")
    panel_size = _int(cursor["panel_size"], "regional panel size", 1, _REGIONAL_PANEL_MAX)
    panel_count = _int(cursor["panel_count"], "regional panel count", 1, _REGIONAL_MAX_PANELS)
    panel = _int(cursor["panel"], "regional construction cursor", 0, panel_count)
    expected_count = len(_regional_panels(
        recipe_material["full_words"], tuple(recipe_material["full_words"]), panel_size
    ))
    if recipe_material["reduced_words"] is not None:
        expected_count += len(_regional_panels(
            recipe_material["reduced_words"], _REGIONAL_REDUCED_WORDS, panel_size
        ))
    if panel_count != expected_count:
        raise ResonantNumericalError("regional construction panel count changed")
    if value["task"] == "construction" and panel_size != value["construction_cursor"]["panel_size"]:
        raise ResonantNumericalError("regional construction panel size is invalid")
    advance_cursor = value["advance_cursor"]
    if not isinstance(advance_cursor, Mapping) or set(advance_cursor) != {"tick"}:
        raise ResonantNumericalError("regional advance cursor is invalid")
    if _int(advance_cursor["tick"], "regional advance cursor", 0, 2**53 - 1) != ticks:
        raise ResonantNumericalError("regional advance cursor is out of sync")
    if not isinstance(value["force_full"], bool):
        raise ResonantNumericalError("regional force_full is invalid")
    if not isinstance(value["journal"], list) or not isinstance(value["ledger"], Mapping):
        raise ResonantNumericalError("regional transceiver journal or ledger is invalid")
    if set(value["ledger"]) != {"panels", "matrix_elements", "ticks", "reduced_steps", "full_steps"}:
        raise ResonantNumericalError("regional transceiver ledger is invalid")
    if any(_int(item, "regional ledger", 0, 2**53 - 1) != item for item in value["ledger"].values()):
        raise ResonantNumericalError("regional transceiver ledger values are invalid")
    if value["phase"] == "terminal" and not isinstance(value["result"], Mapping):
        raise ResonantNumericalError("regional terminal result is missing")
    if value["phase"] != "terminal" and value["result"] is not None:
        raise ResonantNumericalError("unfinished regional state has a result")
    return dict(value)


def _regional_bound(metadata: Mapping[str, Any], name: str, default: float) -> float:
    bounds = metadata.get("bounds", {})
    value = bounds.get(name, default) if isinstance(bounds, Mapping) else default
    return max(0.0, _number(value, f"regional bound {name}"))


def _regional_readout(
    metadata: Mapping[str, Any],
    full_words: Mapping[str, Any],
    reduced_words: Mapping[str, Any] | None,
    mode: str,
    coordinates: np.ndarray,
    inputs: np.ndarray,
) -> np.ndarray:
    if mode == "full":
        return _array(full_words["output_rows"]) @ coordinates
    if reduced_words is None:
        raise ResonantNumericalError("regional reduced readout is missing")
    return (
        _array(reduced_words["offset"])
        + _array(reduced_words["direct"]) @ inputs
        + _array(reduced_words["output"]) @ coordinates
    )


def _regional_transport_output(
    reduced_words: Mapping[str, Any] | None,
    transport: np.ndarray,
    input_errors: np.ndarray,
) -> float:
    if reduced_words is None:
        return 0.0
    rows = np.abs(_array(reduced_words["output"])) @ np.abs(transport)
    rows += np.abs(_array(reduced_words["direct"])) @ np.abs(input_errors)
    return float(np.max(rows, initial=0.0))


def _regional_expand_execution(state: dict[str, Any]) -> None:
    if state["mode"] != "reduced" or state["reduced_words"] is None:
        raise ResonantNumericalError("regional expansion requires reduced coordinates")
    reduced = state["reduced_words"]
    transport = _array(state["transport_error"])
    input_errors = _array(state["input_errors"])
    mapped = np.abs(_array(reduced["lift"])) @ np.abs(transport)
    mapped += np.abs(_array(state["recipe"]["full_words"]["input_lift"])) @ np.abs(input_errors)
    physical = float(np.linalg.norm(mapped))
    state["state_error"] = float(state["state_error"]) + physical
    base = _array(state["recipe"]["full_words"]["base_state"])
    input_lift = _array(state["recipe"]["full_words"]["input_lift"])
    lift = _array(reduced["lift"])
    previous = _array(state["previous_inputs"])
    state["coordinates"] = (
        base + input_lift @ previous + lift @ _array(state["coordinates"])
    ).tolist()
    state["mode"] = "full"
    state["transport_error"] = []
    full_gain = _regional_bound(
        state["metadata"], "full_output_gain",
        float(np.linalg.norm(_array(state["recipe"]["full_words"]["output_rows"]), 2)),
    )
    state["model_error"] = max(float(state["model_error"]), full_gain * float(state["state_error"]))
    state["error_radius"] = max(
        float(state["error_radius"]), float(state["model_error"]),
        full_gain * float(state["state_error"]),
    )


def _regional_step_execution(state: dict[str, Any]) -> dict[str, int]:
    metadata = state["metadata"]
    full_words = state["recipe"]["full_words"]
    reduced_words = state["reduced_words"]
    inputs = _array(state["inputs"])
    input_errors = _array(state["input_errors"])
    counts = {"reduced_steps": 0, "full_steps": 0}
    if state["mode"] == "reduced":
        if reduced_words is None:
            raise ResonantNumericalError("regional reduced execution words are missing")
        if state["force_full"]:
            _regional_expand_execution(state)
        else:
            coordinates = _array(state["coordinates"])
            joined = np.concatenate((coordinates, inputs, [1.0]))
            residual = float(np.linalg.norm(_array(reduced_words["residual"]) @ joined))
            state_norm = float(np.linalg.norm(coordinates))
            input_norm = float(np.linalg.norm(joined))
            roundoff = _regional_bound(metadata, "roundoff", 0.0) * (1 + state_norm + input_norm)
            output_gain = _regional_bound(metadata, "output_gain", 1.0)
            local = output_gain * residual + roundoff
            transition = _array(reduced_words["transition"])
            drive = _array(reduced_words["drive"])
            next_transport = (
                np.abs(transition) @ _array(state["transport_error"])
                + np.abs(drive[:, :len(inputs)]) @ np.abs(input_errors)
            )
            residual_uncertainty = np.abs(_array(reduced_words["residual"])[:, :len(coordinates)]) @ np.abs(_array(state["transport_error"]))
            residual_uncertainty += (
                np.abs(_array(reduced_words["residual"])[:, len(coordinates):len(coordinates) + len(inputs)])
                @ np.abs(input_errors)
            )
            residual_uncertainty_norm = float(np.linalg.norm(residual_uncertainty))
            growth = _regional_bound(metadata, "growth", 1.0)
            state_gain = _regional_bound(metadata, "state_gain", 1.0)
            state_next = growth * float(state["state_error"]) + state_gain * (
                residual + residual_uncertainty_norm
                + _regional_bound(metadata, "state_roundoff", 0.0) * (1 + state_norm + input_norm)
            )
            model_next = growth * float(state["model_error"]) + local + output_gain * residual_uncertainty_norm
            model_next = max(model_next, _regional_bound(metadata, "full_output_gain", 0.0) * state_next)
            output_uncertainty = _regional_transport_output(reduced_words, next_transport, input_errors)
            proposed = max(float(state["error_radius"]), model_next + output_uncertainty)
            allowance = _number(metadata["error_allowance"], "regional error allowance")
            if proposed <= allowance:
                state["coordinates"] = (transition @ coordinates + drive @ joined).tolist()
                state["transport_error"] = next_transport.tolist()
                state["state_error"] = state_next
                state["model_error"] = model_next
                state["error_radius"] = proposed
                counts["reduced_steps"] = 1
                state["previous_inputs"] = inputs.tolist()
                return counts
            _regional_expand_execution(state)
    coordinates = _array(state["coordinates"])
    transition = (
        _array(full_words["transition"])
        if "transition" in full_words else np.eye(len(coordinates), dtype=np.float64)
    )
    drive = (
        _array(full_words["drive"])
        if "drive" in full_words else np.zeros((len(coordinates), len(inputs) + 1), dtype=np.float64)
    )
    joined = np.concatenate((inputs, [1.0]))
    state["coordinates"] = (transition @ coordinates + drive @ joined).tolist()
    radius = float(np.linalg.norm(input_errors))
    growth = _regional_bound(metadata, "growth", 1.0)
    input_gain = _regional_bound(metadata, "input_gain", 0.0)
    full_gain = _regional_bound(
        metadata, "full_output_gain",
        float(np.linalg.norm(_array(full_words["output_rows"]), 2)),
    )
    previous_error = float(state["error_radius"])
    state["model_error"] = max(
        float(state["model_error"]),
        growth * (float(state["model_error"]) + full_gain * float(state["state_error"]))
        + input_gain * radius,
    )
    state["state_error"] = 0.0
    state["transport_error"] = []
    state["error_radius"] = max(previous_error, float(state["model_error"]))
    state["previous_inputs"] = inputs.tolist()
    counts["full_steps"] = 1
    return counts


def _regional_execution_result(state: Mapping[str, Any]) -> dict[str, Any]:
    material = {
        "metadata": state["metadata"],
        "full_words": state["recipe"]["full_words"],
        "reduced_words": state["reduced_words"],
    }
    dimension, input_count, output_count, rank = _regional_validate_material(material)
    values = _regional_readout(
        state["metadata"], state["recipe"]["full_words"], state["reduced_words"],
        state["mode"], _array(state["coordinates"]), _array(state["inputs"]),
    )
    allowance = _number(state["metadata"]["error_allowance"], "regional error allowance")
    execution = {
        "mode": state["mode"],
        "coordinates": _regional_copy(state["coordinates"]),
        "inputs": _regional_copy(state["inputs"]),
        "input_errors": _regional_copy(state["input_errors"]),
        "previous_inputs": _regional_copy(state["previous_inputs"]),
        "ticks": int(state["ticks"]),
        "error_radius": float(state["error_radius"]),
        "model_error": float(state["model_error"]),
        "state_error": float(state["state_error"]),
        "transport_error": _regional_copy(state["transport_error"]),
    }
    return {
        "schema": REGIONAL_RESULT_SCHEMA,
        "family": REGIONAL_KERNEL_NAME,
        "operation": state["operation"],
        "status": "active" if state["mode"] == "reduced" else "expanded",
        "parent_versions": _regional_copy(state["parent_versions"]),
        "metadata": _regional_copy(state["metadata"]),
        "full_words": _regional_copy(state["recipe"]["full_words"]),
        "reduced_words": _regional_copy(state["reduced_words"]),
        "dimensions": {
            "full": dimension, "reduced": rank, "inputs": input_count, "outputs": output_count
        },
        "values": dict(zip(state["metadata"]["output_ids"], values.tolist(), strict=True)),
        "error_bound": float(state["error_radius"]),
        "resolved": float(state["error_radius"]) <= allowance,
        "horizon": int(state["horizon"]),
        "execution": execution,
    }


def _regional_construction_result(state: Mapping[str, Any]) -> dict[str, Any]:
    material = {
        "metadata": state["metadata"],
        "full_words": state["full_words"],
        "reduced_words": state["reduced_words"],
    }
    dimension, input_count, output_count, rank = _regional_validate_material(material)
    return {
        "schema": REGIONAL_RESULT_SCHEMA,
        "family": REGIONAL_KERNEL_NAME,
        "operation": state["operation"],
        "status": "active" if rank else "expanded",
        "parent_versions": _regional_copy(state["parent_versions"]),
        "metadata": _regional_copy(state["metadata"]),
        "full_words": _regional_copy(state["full_words"]),
        "reduced_words": _regional_copy(state["reduced_words"]),
        "dimensions": {
            "full": dimension, "reduced": rank, "inputs": input_count, "outputs": output_count
        },
        "values": None,
        "error_bound": 0.0,
        "resolved": True,
        "horizon": int(state["horizon"]),
        "execution": None,
    }


def regional_kernel(
    state: Any,
    arguments: Mapping[str, Any],
    quantum: int,
) -> KernelResult:
    """Advance one typed construction, execution, or expansion task quantum."""
    current = _regional_validate_state(state)
    if not isinstance(arguments, Mapping) or arguments:
        raise ResonantNumericalError("regional transceiver kernel takes no arguments")
    quantum = _int(quantum, "regional transceiver quantum", 1, REGIONAL_KERNEL_MAX_WORK)
    if current["phase"] == "terminal":
        return KernelResult(state=current, status="done", work=0, output=current["result"])
    if current["phase"] == "fault":
        return KernelResult(state=current, status="fault", work=0, output=current["result"])
    updated = _regional_copy(current)
    used = 0
    if updated["task"] == "construction":
        panels: list[tuple[str, str, int, int]] = []
        panels.extend(
            ("full_words", name, start, end)
            for _, name, start, end in _regional_panels(
                updated["recipe"]["full_words"],
                tuple(updated["recipe"]["full_words"]),
                int(updated["construction_cursor"]["panel_size"]),
            )
        )
        if updated["recipe"]["reduced_words"] is not None:
            panels.extend(
                ("reduced_words", name, start, end)
                for _, name, start, end in _regional_panels(
                    updated["recipe"]["reduced_words"],
                    _REGIONAL_REDUCED_WORDS,
                    int(updated["construction_cursor"]["panel_size"]),
                )
            )
        while used < quantum and updated["construction_cursor"]["panel"] < len(panels):
            index = int(updated["construction_cursor"]["panel"])
            target_name, word_name, start, end = panels[index]
            source_words = updated["recipe"][target_name]
            target_words = updated[target_name]
            shape = _regional_shape(source_words[word_name], word_name)
            for offset in range(start, end):
                _regional_set_flat(
                    target_words[word_name], shape, offset,
                    _regional_get_flat(source_words[word_name], shape, offset),
                )
            updated["construction_cursor"]["panel"] = index + 1
            updated["ledger"]["panels"] += 1
            updated["ledger"]["matrix_elements"] += end - start
            updated["journal"].append({
                "kind": "construction-panel", "panel": index,
                "word": f"{target_name}.{word_name}", "start": start, "end": end,
            })
            used += 1
        if updated["construction_cursor"]["panel"] >= len(panels):
            updated["phase"] = "terminal"
            updated["result"] = _regional_construction_result(updated)
        status = "done" if updated["phase"] == "terminal" else "yield"
        return KernelResult(
            state=_regional_validate_state(updated), status=status, work=used,
            output=updated["result"] if status == "done" else None,
        )
    if updated["task"] == "expand":
        _regional_expand_execution(updated)
        updated["phase"] = "terminal"
        updated["result"] = _regional_execution_result(updated)
        updated["journal"].append({"kind": "expansion", "tick": updated["ticks"]})
        return KernelResult(
            state=_regional_validate_state(updated), status="done", work=1,
            output=updated["result"],
        )
    while used < quantum and updated["ticks"] < updated["horizon"]:
        counts = _regional_step_execution(updated)
        updated["ticks"] += 1
        updated["advance_cursor"]["tick"] = updated["ticks"]
        updated["ledger"]["ticks"] += 1
        updated["ledger"]["reduced_steps"] += counts["reduced_steps"]
        updated["ledger"]["full_steps"] += counts["full_steps"]
        updated["journal"].append({
            "kind": "advance", "tick": updated["ticks"],
            "mode": updated["mode"], "error_bound": updated["error_radius"],
        })
        used += 1
    if updated["ticks"] >= updated["horizon"]:
        updated["phase"] = "terminal"
        updated["result"] = _regional_execution_result(updated)
    return KernelResult(
        state=_regional_validate_state(updated),
        status="done" if updated["phase"] == "terminal" else "yield",
        work=used,
        output=updated["result"] if updated["phase"] == "terminal" else None,
    )
__all__ = [
    "SCHEMA", "condense_workspace", "advance_transceiver", "reset_transceiver",
    "inspect_transceiver", "validate_transceiver",
    "REGIONAL_KERNEL_NAME", "REGIONAL_KERNEL_MAX_WORK",
    "REGIONAL_STATE_SCHEMA", "REGIONAL_RESULT_SCHEMA", "REGIONAL_TASK_SCHEMA",
    "regional_state", "regional_construction_state", "regional_condensation_state",
    "regional_advance_state", "regional_expansion_state", "regional_kernel",
]
