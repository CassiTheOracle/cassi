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
from dataclasses import replace
from typing import Any, Mapping, Sequence

import numpy as np

from cassi_resonant_field import (
    ResonantNumericalError, ResonantProblem, ResonantProfile, ResonantWorkspace,
    _WaveOperator, bind_workspace,
)

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


__all__ = ["SCHEMA", "condense_workspace", "advance_transceiver", "reset_transceiver", "inspect_transceiver", "validate_transceiver"]
