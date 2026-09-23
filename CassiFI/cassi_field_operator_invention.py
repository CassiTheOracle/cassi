"""Field-owned recursive invention of typed world-equation operators.

A fixed interpreter measures typed scalar trees in four vector frames.  The
persistent root field chooses the parents that may reproduce; only descendants
of those choices reach final synthesis.  Structural holdouts are not loaded
until the final field selection exists.
"""
from __future__ import annotations

import copy
import hashlib
import itertools
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from cassi_research_residency import open_research_residency

SCHEMA = "cassifi.field-operator-invention.v1"
VERIFICATION_SCHEMA = "cassifi.field-operator-invention-verification.v1"
CAMPAIGN_KIND = "field-operator-invention-20260919"
FIT_FRACTION = 0.60
TRACER_MODULUS = 16
MINIMUM_RADIUS = 1e-9
VALUE_BOUND = 1e6
TERM_PENALTY = 0.005
NODE_PENALTY = 0.001
ATOMS = ("one", "q", "radial_speed", "speed", "transverse_speed")
FRAMES = ("radial", "flow", "transverse", "normal")
UNARY_OPS = (
    "abs",
    "signed_square",
    "signed_sqrt",
    "signed_log1p",
    "inv1p_abs",
    "exp_neg_abs",
    "tanh",
)

_DEVELOPMENT_FIT = tuple(
    [
        f"CassiCosmos/_diag/matter_formation/energy_gaussian_s20260910_v{speed}"
        for speed in ("0p0", "0p5", "1p0", "2p0")
    ]
    + [
        f"CassiCosmos/_diag/matter_formation/attractor_ic{index}"
        for index in (2, 5, 6, 7, 10)
    ]
)
_DEVELOPMENT_REPLICATION = tuple(
    f"CassiCosmos/_diag/matter_formation/energy_gaussian_s20260911_v{speed}"
    for speed in ("0p0", "0p5", "1p0", "2p0")
)
_HIDDEN_HOLDOUT = tuple(
    f"CassiCosmos/_diag/matter_formation/attractor_scene_calibrated/{name}"
    for name in ("G3", "G6", "GC2", "GL3")
)
_PREREGISTRATION = (
    "CassiCosmos/research/equation_discovery/field_operator_invention_prereg.md"
)
_PREVIOUS_RECEIPT = "CassiFI/_diag/equation-discovery/receipt.json"
_TRAJECTORY_FILES = (
    "receipt.json",
    "analysis.json",
    "history_pos.bin",
    "history_vel.bin",
    "sample_steps.bin",
)


class OperatorInventionError(RuntimeError):
    """Raised when the typed invention campaign violates its frozen contract."""


@dataclass(slots=True)
class ArmData:
    arm_id: str
    segment: str
    atoms: dict[str, np.ndarray]
    frames: dict[str, np.ndarray]
    target: np.ndarray
    scales: dict[str, float]
    source_summary: dict[str, Any]


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def _protocol_contract() -> dict[str, Any]:
    return {
        "campaign_kind": CAMPAIGN_KIND,
        "fit_fraction": FIT_FRACTION,
        "tracer_rule": f"index modulo {TRACER_MODULUS} equals zero",
        "minimum_radius": MINIMUM_RADIUS,
        "value_bound": VALUE_BOUND,
        "atoms": list(ATOMS),
        "frames": list(FRAMES),
        "unary_ops": list(UNARY_OPS),
        "binary_ops": ["multiply", "divide_one_plus_abs"],
        "selection_score": {
            "metric": "arm-balanced validation NRMSE",
            "term_penalty": TERM_PENALTY,
            "node_penalty": NODE_PENALTY,
        },
        "development_fit": list(_DEVELOPMENT_FIT),
        "development_replication": list(_DEVELOPMENT_REPLICATION),
        "hidden_holdout": list(_HIDDEN_HOLDOUT),
        "classification": {
            "semantic_cosine": 0.999,
            "minimum_relative_improvement": 0.05,
            "maximum_per_arm_relative_regression": 0.10,
            "unsupported_nrmse": 0.85,
        },
    }


def _expected_source_paths() -> list[str]:
    paths = [_PREREGISTRATION, _PREVIOUS_RECEIPT]
    for root in (*_DEVELOPMENT_FIT, *_DEVELOPMENT_REPLICATION, *_HIDDEN_HOLDOUT):
        paths.extend(f"{root}/{name}" for name in _TRAJECTORY_FILES)
    return sorted(paths)


def _source_manifest(workspace: Path) -> list[dict[str, Any]]:
    rows = []
    for relative in _expected_source_paths():
        path = workspace / relative
        if not path.is_file():
            raise OperatorInventionError(f"required operator evidence is absent: {relative}")
        rows.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": _file_sha256(path),
            }
        )
    return rows


def _qualifying_metadata(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        receipt = json.loads((root / "receipt.json").read_text(encoding="utf-8"))
        analysis = json.loads((root / "analysis.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OperatorInventionError(f"trajectory metadata is unreadable: {root}") from exc
    if receipt.get("schema") != "cassi.trajectory-probe.v1":
        raise OperatorInventionError(f"trajectory schema is unsupported: {root}")
    if analysis.get("status") != "OK" or analysis.get("domain_status") != "BOUNDED":
        raise OperatorInventionError(f"trajectory is not a bounded qualifying arm: {root}")
    if int(receipt.get("event_overflow", -1)) != 0 or int(receipt.get("sample_overflow", -1)) != 0:
        raise OperatorInventionError(f"trajectory recorder overflowed: {root}")
    if abs(float(analysis.get("relative_mass_error", math.inf))) > 1e-9:
        raise OperatorInventionError(f"trajectory mass drift exceeded the bound: {root}")
    return receipt, analysis


def _load_arm(root: Path, segment: str) -> ArmData:
    receipt, analysis = _qualifying_metadata(root)
    slots = int(receipt["sample_slots"])
    tracers = int(receipt["tracer_count"])
    expected_history = slots * tracers * 4 * np.dtype("<f4").itemsize
    for name in ("history_pos.bin", "history_vel.bin"):
        if (root / name).stat().st_size != expected_history:
            raise OperatorInventionError(f"trajectory history size mismatch: {root / name}")
    if (root / "sample_steps.bin").stat().st_size != slots * np.dtype("<u4").itemsize:
        raise OperatorInventionError(f"trajectory clock size mismatch: {root}")

    position = np.fromfile(root / "history_pos.bin", dtype="<f4").reshape(slots, tracers, 4)
    velocity = np.fromfile(root / "history_vel.bin", dtype="<f4").reshape(slots, tracers, 4)
    steps = np.fromfile(root / "sample_steps.bin", dtype="<u4").astype(np.float64)
    if not np.isfinite(position).all() or not np.isfinite(velocity).all():
        raise OperatorInventionError(f"trajectory contains nonfinite samples: {root}")
    clock = steps * float(receipt["dt"])
    if not np.all(np.diff(clock) > 0.0):
        raise OperatorInventionError(f"trajectory clock is not strictly increasing: {root}")

    center = np.asarray(receipt["engine"]["window_center"], dtype=np.float64)
    initial = position[0, :, :3].astype(np.float64) - center
    initial_radius = np.linalg.norm(initial, axis=1)
    initial_mask = (position[0, :, 3] > 0.0) & (np.arange(tracers) % TRACER_MODULUS == 0)
    radius_scale = float(np.median(initial_radius[initial_mask]))
    mass_scale = float(receipt["initial_total_mass"])
    if not math.isfinite(radius_scale) or radius_scale <= 0.0:
        raise OperatorInventionError(f"trajectory radius scale is invalid: {root}")
    if not math.isfinite(mass_scale) or mass_scale <= 0.0:
        raise OperatorInventionError(f"trajectory mass scale is invalid: {root}")
    velocity_scale = math.sqrt(mass_scale / radius_scale)
    acceleration_scale = mass_scale / (radius_scale * radius_scale)

    r = position[1:-1, :, :3].astype(np.float64) - center
    v = velocity[1:-1, :, :3].astype(np.float64)
    acceleration = (
        velocity[2:, :, :3].astype(np.float64)
        - velocity[:-2, :, :3].astype(np.float64)
    ) / (clock[2:, None, None] - clock[:-2, None, None])
    radius = np.linalg.norm(r, axis=2)
    count = radius.shape[0]
    cutoff = int(FIT_FRACTION * count)
    time_index = np.arange(count)[:, None]
    tracer_index = np.arange(tracers)[None, :]
    eligible = (
        (position[1:-1, :, 3] > 0.0)
        & (radius > MINIMUM_RADIUS)
        & (tracer_index % TRACER_MODULUS == 0)
    )
    if segment == "early":
        eligible &= time_index < cutoff
    elif segment == "late":
        eligible &= time_index >= cutoff
    elif segment != "all":
        raise OperatorInventionError(f"unknown trajectory segment: {segment}")

    r = r[eligible]
    v = v[eligible]
    acceleration = acceleration[eligible]
    radius = radius[eligible]
    if len(r) == 0:
        raise OperatorInventionError(f"trajectory segment is empty: {root}")
    radial_hat = r / radius[:, None]
    velocity_dimensionless = v / velocity_scale
    radial_speed = np.einsum("ni,ni->n", velocity_dimensionless, radial_hat)
    transverse = velocity_dimensionless - radial_speed[:, None] * radial_hat
    transverse_speed = np.linalg.norm(transverse, axis=1)
    normal = np.cross(radial_hat, transverse)
    atoms = {
        "one": np.ones(len(r), dtype=np.float64),
        "q": radius / radius_scale,
        "radial_speed": radial_speed,
        "speed": np.linalg.norm(velocity_dimensionless, axis=1),
        "transverse_speed": transverse_speed,
    }
    frames = {
        "radial": radial_hat,
        "flow": velocity_dimensionless,
        "transverse": transverse,
        "normal": normal,
    }
    target = acceleration / acceleration_scale
    if not all(np.isfinite(value).all() for value in (*atoms.values(), *frames.values(), target)):
        raise OperatorInventionError(f"dimensionless trajectory contains nonfinite values: {root}")
    return ArmData(
        arm_id=root.name,
        segment=segment,
        atoms=atoms,
        frames=frames,
        target=target,
        scales={
            "radius": radius_scale,
            "mass": mass_scale,
            "velocity": velocity_scale,
            "acceleration": acceleration_scale,
        },
        source_summary={
            "seed": int(receipt["seed"]),
            "initial_condition": analysis.get("ic_name", receipt.get("geometry", {}).get("initial_condition")),
            "field_frozen": bool(receipt["field_control"]["freeze_field"]),
            "sample_slots": slots,
            "tracer_count": tracers,
            "sample_count": int(len(target)),
            "domain_status": analysis["domain_status"],
            "relative_mass_error": float(analysis["relative_mass_error"]),
        },
    )


def _atom(name: str) -> dict[str, Any]:
    if name not in ATOMS:
        raise OperatorInventionError(f"unknown scalar atom: {name}")
    return {"op": "atom", "name": name}


def _canonical_program(program: Mapping[str, Any]) -> dict[str, Any]:
    op = str(program.get("op"))
    if op == "atom":
        return _atom(str(program.get("name")))
    if op == "control_power":
        power = float(program.get("power"))
        if power not in (-2.0, 0.75, 1.0):
            raise OperatorInventionError("unregistered control power")
        return {"op": op, "power": power}
    if op in UNARY_OPS:
        return {"op": op, "arg": _canonical_program(program["arg"])}
    if op == "multiply":
        raw_args = program.get("args")
        if not isinstance(raw_args, Sequence) or isinstance(raw_args, (str, bytes)):
            raise OperatorInventionError("multiply requires typed arguments")
        flattened: list[dict[str, Any]] = []
        for raw in raw_args:
            child = _canonical_program(raw)
            if child["op"] == "multiply":
                flattened.extend(child["args"])
            elif child != _atom("one"):
                flattened.append(child)
        if not flattened:
            return _atom("one")
        flattened.sort(key=lambda value: _canonical(value))
        if len(flattened) == 1:
            return flattened[0]
        return {"op": op, "args": flattened}
    if op == "divide_one_plus_abs":
        return {
            "op": op,
            "numerator": _canonical_program(program["numerator"]),
            "denominator": _canonical_program(program["denominator"]),
        }
    raise OperatorInventionError(f"unknown scalar operation: {op}")


def _node_count(program: Mapping[str, Any]) -> int:
    op = program["op"]
    if op in ("atom", "control_power"):
        return 1
    if op in UNARY_OPS:
        return 1 + _node_count(program["arg"])
    if op == "multiply":
        return 1 + sum(_node_count(arg) for arg in program["args"])
    if op == "divide_one_plus_abs":
        return 1 + _node_count(program["numerator"]) + _node_count(program["denominator"])
    raise OperatorInventionError(f"cannot count operation: {op}")


def _evaluate_scalar(program: Mapping[str, Any], atoms: Mapping[str, np.ndarray]) -> np.ndarray:
    program = _canonical_program(program)
    op = program["op"]
    if op == "atom":
        result = np.asarray(atoms[program["name"]], dtype=np.float64)
    elif op == "control_power":
        result = np.asarray(atoms["q"], dtype=np.float64) ** float(program["power"])
    elif op in UNARY_OPS:
        value = _evaluate_scalar(program["arg"], atoms)
        absolute = np.abs(value)
        if op == "abs":
            result = absolute
        elif op == "signed_square":
            result = np.sign(value) * absolute * absolute
        elif op == "signed_sqrt":
            result = np.sign(value) * np.sqrt(absolute)
        elif op == "signed_log1p":
            result = np.sign(value) * np.log1p(absolute)
        elif op == "inv1p_abs":
            result = 1.0 / (1.0 + absolute)
        elif op == "exp_neg_abs":
            result = np.exp(-absolute)
        else:
            result = np.tanh(value)
    elif op == "multiply":
        result = np.ones_like(next(iter(atoms.values())), dtype=np.float64)
        for arg in program["args"]:
            result = result * _evaluate_scalar(arg, atoms)
    elif op == "divide_one_plus_abs":
        result = _evaluate_scalar(program["numerator"], atoms) / (
            1.0 + np.abs(_evaluate_scalar(program["denominator"], atoms))
        )
    else:
        raise OperatorInventionError(f"cannot evaluate operation: {op}")
    if not np.isfinite(result).all():
        raise OperatorInventionError("typed scalar program produced nonfinite values")
    return np.clip(result, -VALUE_BOUND, VALUE_BOUND)


def _canonical_term(term: Mapping[str, Any]) -> dict[str, Any]:
    frame = str(term.get("frame"))
    if frame not in FRAMES:
        raise OperatorInventionError(f"unknown vector frame: {frame}")
    return {"frame": frame, "scalar": _canonical_program(term["scalar"])}


def _term_id(term: Mapping[str, Any]) -> str:
    return "term-" + _digest(_canonical_term(term))[:20]


def _canonical_equation(terms: Sequence[Mapping[str, Any]], *, kind: str) -> dict[str, Any]:
    canonical = [_canonical_term(term) for term in terms]
    if not 1 <= len(canonical) <= 2:
        raise OperatorInventionError("equations require one or two terms")
    canonical.sort(key=lambda value: _canonical(value))
    if len({_digest(term) for term in canonical}) != len(canonical):
        raise OperatorInventionError("equation terms must be distinct")
    return {"kind": kind, "terms": canonical}


def _equation_id(equation: Mapping[str, Any]) -> str:
    return "program-" + _digest(equation)[:20]


def _term_value(term: Mapping[str, Any], arm: ArmData) -> np.ndarray:
    term = _canonical_term(term)
    scalar = _evaluate_scalar(term["scalar"], arm.atoms)
    result = scalar[:, None] * arm.frames[term["frame"]]
    if not np.isfinite(result).all():
        raise OperatorInventionError("typed vector term produced nonfinite values")
    return np.clip(result, -VALUE_BOUND, VALUE_BOUND)


def _fit_equation(
    equation: Mapping[str, Any], fit_arms: Sequence[ArmData]
) -> list[float]:
    terms = equation["terms"]
    gram = np.zeros((len(terms), len(terms)), dtype=np.float64)
    cross = np.zeros(len(terms), dtype=np.float64)
    for arm in fit_arms:
        values = [_term_value(term, arm) for term in terms]
        for left, value_left in enumerate(values):
            cross[left] += float(np.einsum("ni,ni->", value_left, arm.target))
            for right, value_right in enumerate(values):
                gram[left, right] += float(np.einsum("ni,ni->", value_left, value_right))
    try:
        coefficient = np.linalg.solve(gram, cross)
    except np.linalg.LinAlgError as exc:
        raise OperatorInventionError("typed equation support is singular") from exc
    if not np.isfinite(coefficient).all():
        raise OperatorInventionError("typed equation fit is nonfinite")
    return [float(value) for value in coefficient]


def _arm_nrmse(equation: Mapping[str, Any], coefficients: Sequence[float], arm: ArmData) -> float:
    prediction = sum(
        float(coefficient) * _term_value(term, arm)
        for coefficient, term in zip(coefficients, equation["terms"], strict=True)
    )
    target_sq = float(np.einsum("ni,ni->", arm.target, arm.target))
    if target_sq <= 0.0:
        raise OperatorInventionError("equation target has zero energy")
    residual = arm.target - prediction
    return math.sqrt(float(np.einsum("ni,ni->", residual, residual)) / target_sq)


def _evaluate_candidate(
    equation: Mapping[str, Any],
    fit_arms: Sequence[ArmData],
    validation_arms: Sequence[ArmData],
) -> dict[str, Any]:
    equation = _canonical_equation(equation["terms"], kind=str(equation["kind"]))
    coefficients = _fit_equation(equation, fit_arms)
    fit_rows = {
        arm.arm_id: _arm_nrmse(equation, coefficients, arm) for arm in fit_arms
    }
    validation_rows = {
        arm.arm_id: _arm_nrmse(equation, coefficients, arm) for arm in validation_arms
    }
    nodes = sum(_node_count(term["scalar"]) + 1 for term in equation["terms"])
    validation_mean = float(sum(validation_rows.values()) / len(validation_rows))
    score = validation_mean + TERM_PENALTY * len(equation["terms"]) + NODE_PENALTY * nodes
    candidate_id = _equation_id(equation)
    return {
        "candidate_id": candidate_id,
        "equation": equation,
        "coefficients": coefficients,
        "fit_nrmse_by_arm": fit_rows,
        "fit_mean_nrmse": float(sum(fit_rows.values()) / len(fit_rows)),
        "validation_nrmse_by_arm": validation_rows,
        "validation_mean_nrmse": validation_mean,
        "term_count": len(equation["terms"]),
        "node_count": nodes,
        "selection_score": score,
        "development_score": 1.0 - score,
    }


def _evaluate_candidates(
    equations: Sequence[Mapping[str, Any]],
    fit_arms: Sequence[ArmData],
    validation_arms: Sequence[ArmData],
) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for equation in equations:
        try:
            result = _evaluate_candidate(equation, fit_arms, validation_arms)
        except OperatorInventionError as exc:
            if "singular" in str(exc):
                continue
            raise
        results[result["candidate_id"]] = result
    if len(results) < 2:
        raise OperatorInventionError("typed candidate family has fewer than two valid equations")
    return results


def _metric_winner(candidates: Mapping[str, Mapping[str, Any]]) -> str:
    return min(candidates, key=lambda key: (float(candidates[key]["selection_score"]), key))


def _field_contract(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": candidate["candidate_id"],
        "development_score": candidate["development_score"],
        "development_cost": candidate["node_count"],
        "development_evidence": {
            "validation_mean_nrmse": candidate["validation_mean_nrmse"],
            "selection_score": candidate["selection_score"],
            "validation_arm_count": len(candidate["validation_nrmse_by_arm"]),
        },
    }


def _field_select(
    organism: Any,
    *,
    campaign_id: str,
    laboratory_id: str,
    candidates: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    selection = organism.select_laboratory_candidate(
        campaign_id=campaign_id,
        laboratory_id=laboratory_id,
        objective="construct the most predictive compact typed world operator",
        candidates=[_field_contract(candidates[key]) for key in sorted(candidates)],
    )
    selected = str(selection["candidate_id"])
    if selected != _metric_winner(candidates):
        raise OperatorInventionError("root field did not choose the registered operator priority")
    return selection


def _seed_scalars() -> list[dict[str, Any]]:
    seeds = [_atom(name) for name in ATOMS]
    q = _atom("q")
    radial = _atom("radial_speed")
    speed = _atom("speed")
    transverse = _atom("transverse_speed")
    for op in ("signed_square", "signed_sqrt", "signed_log1p", "inv1p_abs", "exp_neg_abs", "tanh"):
        seeds.append({"op": op, "arg": q})
    for op in ("abs", "signed_square", "tanh", "inv1p_abs"):
        seeds.append({"op": op, "arg": radial})
    for atom in (speed, transverse):
        for op in ("signed_square", "signed_sqrt", "signed_log1p", "inv1p_abs", "exp_neg_abs"):
            seeds.append({"op": op, "arg": atom})
    canonical = {_digest(_canonical_program(seed)): _canonical_program(seed) for seed in seeds}
    result = [canonical[key] for key in sorted(canonical)]
    if len(result) != 25:
        raise OperatorInventionError("seed language does not contain exactly 25 trees")
    return result


def _mutations(parent: Mapping[str, Any]) -> list[dict[str, Any]]:
    parent = _canonical_program(parent)
    programs = [parent]
    programs.extend({"op": op, "arg": parent} for op in UNARY_OPS)
    for name in ATOMS:
        atom = _atom(name)
        programs.append({"op": "multiply", "args": [parent, atom]})
        programs.append(
            {"op": "divide_one_plus_abs", "numerator": parent, "denominator": atom}
        )
    q = _atom("q")
    for op in ("signed_square", "signed_sqrt", "signed_log1p", "inv1p_abs", "exp_neg_abs", "tanh"):
        programs.append(
            {"op": "multiply", "args": [parent, {"op": op, "arg": q}]}
        )
    canonical = {_digest(_canonical_program(program)): _canonical_program(program) for program in programs}
    return [canonical[key] for key in sorted(canonical)]


def _single_term_equations(frame: str, scalars: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        _canonical_equation(
            [{"frame": frame, "scalar": scalar}],
            kind="field-constructed",
        )
        for scalar in scalars
    ]


def _human_equations() -> dict[str, dict[str, Any]]:
    inverse = _canonical_equation(
        [{"frame": "radial", "scalar": {"op": "control_power", "power": -2.0}}],
        kind="human-inverse-square",
    )
    harmonic = _canonical_equation(
        [{"frame": "radial", "scalar": {"op": "control_power", "power": 1.0}}],
        kind="human-harmonic",
    )
    prior = _canonical_equation(
        [
            {"frame": "radial", "scalar": {"op": "control_power", "power": 0.75}},
            {"frame": "radial", "scalar": {"op": "control_power", "power": 1.0}},
        ],
        kind="human-prior-radial-support",
    )
    return {"inverse-square": inverse, "harmonic": harmonic, "prior-radial": prior}


def _load_development(workspace: Path) -> tuple[list[ArmData], list[ArmData]]:
    fit = [_load_arm(workspace / relative, "early") for relative in _DEVELOPMENT_FIT]
    validation = [_load_arm(workspace / relative, "late") for relative in _DEVELOPMENT_FIT]
    validation.extend(
        _load_arm(workspace / relative, "all") for relative in _DEVELOPMENT_REPLICATION
    )
    return fit, validation


def _load_holdout(workspace: Path) -> list[ArmData]:
    return [_load_arm(workspace / relative, "all") for relative in _HIDDEN_HOLDOUT]


def _arm_summary(arms: Sequence[ArmData]) -> list[dict[str, Any]]:
    return [
        {
            "arm_id": arm.arm_id,
            "segment": arm.segment,
            "scales": arm.scales,
            "source_summary": arm.source_summary,
        }
        for arm in arms
    ]


def _run_construction(
    organism: Any,
    *,
    campaign_id: str,
    fit_arms: Sequence[ArmData],
    validation_arms: Sequence[ArmData],
) -> dict[str, Any]:
    seed_results: dict[str, Any] = {}
    mutation_results: dict[str, Any] = {}
    selection_records: list[dict[str, Any]] = []
    evolved_terms: dict[str, dict[str, Any]] = {}

    for frame in FRAMES:
        seeds = _evaluate_candidates(
            _single_term_equations(frame, _seed_scalars()), fit_arms, validation_arms
        )
        seed_selection = _field_select(
            organism,
            campaign_id=campaign_id,
            laboratory_id=f"operator-seed-{frame}",
            candidates=seeds,
        )
        selection_records.append(seed_selection)
        selected_seed = seeds[str(seed_selection["candidate_id"])]
        parent_term = selected_seed["equation"]["terms"][0]
        mutations = _evaluate_candidates(
            _single_term_equations(frame, _mutations(parent_term["scalar"])),
            fit_arms,
            validation_arms,
        )
        mutation_selection = _field_select(
            organism,
            campaign_id=campaign_id,
            laboratory_id=f"operator-mutation-{frame}",
            candidates=mutations,
        )
        selection_records.append(mutation_selection)
        selected_mutation = mutations[str(mutation_selection["candidate_id"])]
        evolved_terms[frame] = selected_mutation["equation"]["terms"][0]
        seed_results[frame] = {
            "candidate_results": seeds,
            "selection": seed_selection,
            "selected_term": parent_term,
        }
        mutation_results[frame] = {
            "parent_candidate": seed_selection["candidate_id"],
            "parent_term": parent_term,
            "candidate_results": mutations,
            "selection": mutation_selection,
            "selected_term": evolved_terms[frame],
        }

    synthesis_equations = [
        _canonical_equation([term], kind="field-constructed")
        for term in evolved_terms.values()
    ]
    synthesis_equations.extend(
        _canonical_equation([evolved_terms[left], evolved_terms[right]], kind="field-constructed")
        for left, right in itertools.combinations(FRAMES, 2)
    )
    synthesis_equations.extend(_human_equations().values())
    synthesis = _evaluate_candidates(synthesis_equations, fit_arms, validation_arms)
    final_selection = _field_select(
        organism,
        campaign_id=campaign_id,
        laboratory_id="operator-synthesis",
        candidates=synthesis,
    )
    selection_records.append(final_selection)
    return {
        "seed_phase": seed_results,
        "mutation_phase": mutation_results,
        "evolved_terms": evolved_terms,
        "synthesis_candidates": synthesis,
        "final_selection": final_selection,
        "selection_records": selection_records,
    }


def _prediction(
    candidate: Mapping[str, Any], arm: ArmData
) -> np.ndarray:
    return sum(
        float(coefficient) * _term_value(term, arm)
        for coefficient, term in zip(
            candidate["coefficients"], candidate["equation"]["terms"], strict=True
        )
    )


def _prediction_cosine(
    left: Mapping[str, Any], right: Mapping[str, Any], arms: Sequence[ArmData]
) -> float:
    dot = left_sq = right_sq = 0.0
    for arm in arms:
        left_value = _prediction(left, arm)
        right_value = _prediction(right, arm)
        dot += float(np.einsum("ni,ni->", left_value, right_value))
        left_sq += float(np.einsum("ni,ni->", left_value, left_value))
        right_sq += float(np.einsum("ni,ni->", right_value, right_value))
    denominator = math.sqrt(left_sq * right_sq)
    return 0.0 if denominator == 0.0 else dot / denominator


def _holdout_metrics(candidate: Mapping[str, Any], arms: Sequence[ArmData]) -> dict[str, Any]:
    rows = {
        arm.arm_id: _arm_nrmse(candidate["equation"], candidate["coefficients"], arm)
        for arm in arms
    }
    return {"nrmse_by_arm": rows, "mean_nrmse": float(sum(rows.values()) / len(rows))}


def _classify(
    selected: Mapping[str, Any],
    synthesis: Mapping[str, Mapping[str, Any]],
    holdout_arms: Sequence[ArmData],
) -> dict[str, Any]:
    selected_metrics = _holdout_metrics(selected, holdout_arms)
    controls = {
        name: next(
            candidate
            for candidate in synthesis.values()
            if candidate["equation"]["kind"] == equation["kind"]
        )
        for name, equation in _human_equations().items()
    }
    control_metrics = {
        name: {**_holdout_metrics(candidate, holdout_arms), "candidate_id": candidate["candidate_id"]}
        for name, candidate in controls.items()
    }
    cosines = {
        name: _prediction_cosine(selected, candidate, holdout_arms)
        for name, candidate in controls.items()
    }
    threshold = _protocol_contract()["classification"]
    best_mean = min(metric["mean_nrmse"] for metric in control_metrics.values())
    relative_improvement = 1.0 - selected_metrics["mean_nrmse"] / best_mean
    per_arm_ok = all(
        selected_metrics["nrmse_by_arm"][arm_id]
        <= (1.0 + threshold["maximum_per_arm_relative_regression"])
        * min(metric["nrmse_by_arm"][arm_id] for metric in control_metrics.values())
        for arm_id in selected_metrics["nrmse_by_arm"]
    )
    human_equivalent = (
        selected["equation"]["kind"].startswith("human-")
        or max(cosines.values()) >= threshold["semantic_cosine"]
    )
    if human_equivalent:
        classification = "HUMAN_EQUIVALENT"
    elif selected_metrics["mean_nrmse"] >= threshold["unsupported_nrmse"]:
        classification = "UNSUPPORTED_INVENTION"
    elif relative_improvement >= threshold["minimum_relative_improvement"] and per_arm_ok:
        classification = "ALIEN_OPERATOR_LAW"
    else:
        classification = "ALIEN_REGIME_DESCRIPTION"
    return {
        "classification": classification,
        "selected": selected_metrics,
        "human_comparators": control_metrics,
        "prediction_cosine_to_human_comparators": cosines,
        "relative_improvement_over_best_human": relative_improvement,
        "per_arm_regression_gate": per_arm_ok,
        "scope": "dimensionless reduced collective law; not a microscopic-force replacement",
    }


def _scalar_text(program: Mapping[str, Any]) -> str:
    program = _canonical_program(program)
    op = program["op"]
    atom_text = {
        "one": "1",
        "q": "q",
        "radial_speed": "u_r",
        "speed": "s",
        "transverse_speed": "s_perp",
    }
    if op == "atom":
        return atom_text[program["name"]]
    if op == "control_power":
        return f"q^({program['power']:g})"
    inner = _scalar_text(program["arg"]) if op in UNARY_OPS else ""
    if op == "abs":
        return f"abs({inner})"
    if op == "signed_square":
        return f"sign({inner})*abs({inner})^2"
    if op == "signed_sqrt":
        return f"sign({inner})*sqrt(abs({inner}))"
    if op == "signed_log1p":
        return f"sign({inner})*log1p(abs({inner}))"
    if op == "inv1p_abs":
        return f"1/(1+abs({inner}))"
    if op == "exp_neg_abs":
        return f"exp(-abs({inner}))"
    if op == "tanh":
        return f"tanh({inner})"
    if op == "multiply":
        return "*".join(f"({_scalar_text(arg)})" for arg in program["args"])
    if op == "divide_one_plus_abs":
        return (
            f"({_scalar_text(program['numerator'])})/"
            f"(1+abs({_scalar_text(program['denominator'])}))"
        )
    raise OperatorInventionError(f"cannot render scalar operation: {op}")


def _render(candidate: Mapping[str, Any]) -> str:
    frame_text = {
        "radial": "r_hat",
        "flow": "v/V0",
        "transverse": "v_perp/V0",
        "normal": "r_hat×(v_perp/V0)",
    }
    terms = []
    for coefficient, term in zip(
        candidate["coefficients"], candidate["equation"]["terms"], strict=True
    ):
        terms.append(
            f"{coefficient:+.12g}*{frame_text[term['frame']]}*({_scalar_text(term['scalar'])})"
        )
    return "a/A0 = " + " ".join(terms).lstrip("+")


def _synthetic_arm(kind: str, *, arm_id: str) -> ArmData:
    index = np.arange(1, 514, dtype=np.float64)
    q = 0.5 + index / 71.0
    angle = index * 0.37
    radial = np.stack(
        [np.cos(angle), np.sin(angle), 0.3 * np.sin(index * 0.11)], axis=1
    )
    radial /= np.linalg.norm(radial, axis=1, keepdims=True)
    tangent_seed = np.stack(
        [-np.sin(angle), np.cos(angle), 0.2 * np.cos(index * 0.17)], axis=1
    )
    tangent = tangent_seed - np.einsum("ni,ni->n", tangent_seed, radial)[:, None] * radial
    radial_speed = np.sin(index * 0.23) * 0.4
    transverse_speed = 0.2 + 0.03 * np.cos(index * 0.31)
    tangent /= np.linalg.norm(tangent, axis=1, keepdims=True)
    transverse = transverse_speed[:, None] * tangent
    flow = radial_speed[:, None] * radial + transverse
    normal = np.cross(radial, transverse)
    atoms = {
        "one": np.ones(len(index)),
        "q": q,
        "radial_speed": radial_speed,
        "speed": np.linalg.norm(flow, axis=1),
        "transverse_speed": transverse_speed,
    }
    frames = {"radial": radial, "flow": flow, "transverse": transverse, "normal": normal}
    if kind == "harmonic":
        target = -q[:, None] * radial
    elif kind == "drag":
        target = -0.7 * flow
    elif kind == "normal":
        target = 1.3 * normal
    elif kind == "mixed":
        target = -0.8 * q[:, None] * radial - 0.35 * flow
    else:
        raise OperatorInventionError(f"unknown synthetic world: {kind}")
    return ArmData(
        arm_id=arm_id,
        segment="synthetic",
        atoms=atoms,
        frames=frames,
        target=target,
        scales={"radius": 1.0, "mass": 1.0, "velocity": 1.0, "acceleration": 1.0},
        source_summary={"known_world": kind},
    )


def calibration_controls() -> dict[str, Any]:
    human = _human_equations()
    drag = _canonical_equation(
        [{"frame": "flow", "scalar": _atom("one")}], kind="calibration-drag"
    )
    normal = _canonical_equation(
        [{"frame": "normal", "scalar": _atom("one")}], kind="calibration-normal"
    )
    mixed = _canonical_equation(
        [
            {"frame": "radial", "scalar": _atom("q")},
            {"frame": "flow", "scalar": _atom("one")},
        ],
        kind="calibration-mixed",
    )
    pool = [human["harmonic"], human["inverse-square"], drag, normal, mixed]
    expected = {
        "harmonic": "human-harmonic",
        "drag": "calibration-drag",
        "normal": "calibration-normal",
        "mixed": "calibration-mixed",
    }
    controls = {}
    for world, expected_kind in expected.items():
        fit = [_synthetic_arm(world, arm_id=f"{world}-fit")]
        validation = [_synthetic_arm(world, arm_id=f"{world}-holdout")]
        results = _evaluate_candidates(pool, fit, validation)
        winner = _metric_winner(results)
        result = results[winner]
        passed = (
            result["equation"]["kind"] == expected_kind
            and result["validation_mean_nrmse"] <= 1e-10
        )
        controls[world] = {
            "status": "PASS" if passed else "FAIL",
            "selected_candidate": winner,
            "selected_kind": result["equation"]["kind"],
            "expected_kind": expected_kind,
            "validation_nrmse": result["validation_mean_nrmse"],
        }
    canonical_left = _canonical_program(
        {"op": "multiply", "args": [_atom("one"), _atom("q")]}
    )
    canonical_right = _canonical_program(_atom("q"))
    q_term = {"frame": "radial", "scalar": canonical_right}
    equivalent = _canonical_equation([q_term], kind="equivalence")
    arm = _synthetic_arm("harmonic", arm_id="equivalence")
    candidate = _evaluate_candidate(equivalent, [arm], [arm])
    cosine = _prediction_cosine(candidate, candidate, [arm])
    controls["canonicalization"] = {
        "status": "PASS" if canonical_left == canonical_right and cosine >= 0.999999999999 else "FAIL",
        "canonical_equal": canonical_left == canonical_right,
        "semantic_cosine": cosine,
    }
    if any(control["status"] != "PASS" for control in controls.values()):
        raise OperatorInventionError("typed operator calibration failed")
    return controls


def _core_receipt(
    *,
    organism: Any,
    workspace: Path,
    source_manifest: list[dict[str, Any]],
    campaign_id: str,
    fit_arms: Sequence[ArmData],
    validation_arms: Sequence[ArmData],
    construction: Mapping[str, Any],
    selected: Mapping[str, Any],
    holdout_arms: Sequence[ArmData],
    holdout: Mapping[str, Any],
    outcome: Mapping[str, Any],
    controls: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "campaign_id": campaign_id,
        "workspace": str(workspace),
        "organism_home": str(organism.home.resolve()),
        "protocol": _protocol_contract(),
        "preregistration": {
            "path": _PREREGISTRATION,
            "sha256": next(row["sha256"] for row in source_manifest if row["path"] == _PREREGISTRATION),
        },
        "previous_equation_receipt": {
            "path": _PREVIOUS_RECEIPT,
            "sha256": next(row["sha256"] for row in source_manifest if row["path"] == _PREVIOUS_RECEIPT),
        },
        "implementation_sha256": _file_sha256(Path(__file__)),
        "source_manifest": source_manifest,
        "measurement_identity_sha256": _digest(
            {
                "schema": SCHEMA,
                "protocol": _protocol_contract(),
                "sources": source_manifest,
                "implementation_sha256": _file_sha256(Path(__file__)),
            }
        ),
        "calibration_controls": dict(controls),
        "development": {
            "fit_arms": _arm_summary(fit_arms),
            "validation_arms": _arm_summary(validation_arms),
        },
        "construction": dict(construction),
        "selected_equation": {
            "candidate_id": selected["candidate_id"],
            "equation": selected["equation"],
            "coefficients": selected["coefficients"],
            "rendered": _render(selected),
            "validation_mean_nrmse": selected["validation_mean_nrmse"],
        },
        "hidden_holdout": {"arms": _arm_summary(holdout_arms), **dict(holdout)},
        "field_outcome": dict(outcome),
        "model_calls": 0,
    }


def _with_digest(body: Mapping[str, Any]) -> dict[str, Any]:
    plain = copy.deepcopy(dict(body))
    return {**plain, "result_sha256": _digest(plain)}


def _verify_field_records(receipt: Mapping[str, Any]) -> int:
    home = Path(str(receipt["organism_home"]))
    count = 0
    with open_research_residency(home / "root") as residency:
        for selection in receipt["construction"]["selection_records"]:
            record = residency._record(selection["selection_record_id"])
            if record is None:
                raise OperatorInventionError("operator selection lineage record is missing")
            payload = record.get("payload", {})
            if (
                payload.get("campaign_id") != receipt["campaign_id"]
                or payload.get("candidate_id") != selection["candidate_id"]
                or payload.get("holdout_visible_during_selection") is not False
            ):
                raise OperatorInventionError("operator selection lineage record changed")
            count += 1
        outcome = receipt["field_outcome"]
        record = residency._record(outcome["record_id"])
        if record is None:
            raise OperatorInventionError("operator holdout outcome record is missing")
        payload = record.get("payload", {})
        if (
            payload.get("campaign_id") != receipt["campaign_id"]
            or payload.get("candidate_id") != receipt["selected_equation"]["candidate_id"]
            or payload.get("selected_result_sha256") != outcome["selected_result_sha256"]
            or payload.get("holdout_revealed_after_selection") is not True
        ):
            raise OperatorInventionError("operator holdout outcome record changed")
        count += 1
    return count


def _exercise_mutations(receipt: Mapping[str, Any]) -> dict[str, str]:
    mutations: dict[str, dict[str, Any]] = {}
    source = copy.deepcopy(dict(receipt))
    source["source_manifest"][0]["sha256"] = "0" * 64
    mutations["source-hash"] = source
    split = copy.deepcopy(dict(receipt))
    split["protocol"]["fit_fraction"] = 0.61
    mutations["split"] = split
    tree = copy.deepcopy(dict(receipt))
    original_frame = tree["selected_equation"]["equation"]["terms"][0]["frame"]
    tree["selected_equation"]["equation"]["terms"][0]["frame"] = next(
        frame for frame in FRAMES if frame != original_frame
    )
    mutations["typed-tree"] = tree
    coefficient = copy.deepcopy(dict(receipt))
    coefficient["selected_equation"]["coefficients"][0] += 0.125
    mutations["coefficient"] = coefficient
    lineage = copy.deepcopy(dict(receipt))
    lineage["construction"]["selection_records"][0]["selection_record_id"] = "missing:lineage"
    mutations["lineage-record"] = lineage
    classification = copy.deepcopy(dict(receipt))
    original_class = classification["hidden_holdout"]["classification"]
    classification["hidden_holdout"]["classification"] = (
        "HUMAN_EQUIVALENT"
        if original_class != "HUMAN_EQUIVALENT"
        else "UNSUPPORTED_INVENTION"
    )
    mutations["classification"] = classification
    results = {}
    for name, mutated in mutations.items():
        mutated.pop("result_sha256", None)
        mutated = _with_digest(mutated)
        try:
            verify_operator_receipt(mutated, check_mutation_controls=False)
        except (AssertionError, OperatorInventionError, ValueError):
            results[name] = "PASS"
        else:
            results[name] = "FAIL"
    return results


def run_operator_invention(organism: Any, *, workspace: Path) -> dict[str, Any]:
    """Execute the frozen field-owned construction before loading holdouts."""

    workspace = Path(workspace).resolve(strict=True)
    source_manifest = _source_manifest(workspace)
    controls = calibration_controls()
    fit_arms, validation_arms = _load_development(workspace)
    campaign_id = _digest(
        {
            "schema": SCHEMA,
            "protocol": _protocol_contract(),
            "sources": source_manifest,
            "implementation_sha256": _file_sha256(Path(__file__)),
        }
    )[:24]
    construction = _run_construction(
        organism,
        campaign_id=campaign_id,
        fit_arms=fit_arms,
        validation_arms=validation_arms,
    )
    selected_id = str(construction["final_selection"]["candidate_id"])
    selected = construction["synthesis_candidates"][selected_id]

    holdout_arms = _load_holdout(workspace)
    holdout = _classify(selected, construction["synthesis_candidates"], holdout_arms)
    selected_result = {
        "selected_equation": {
            "candidate_id": selected_id,
            "equation": selected["equation"],
            "coefficients": selected["coefficients"],
            "rendered": _render(selected),
        },
        "hidden_holdout": holdout,
    }
    outcome = organism.admit_laboratory_outcome(
        campaign_id=campaign_id,
        laboratory_id="alien-equation-discovery",
        candidate_id=selected_id,
        selected_result=selected_result,
    )
    body = _core_receipt(
        organism=organism,
        workspace=workspace,
        source_manifest=source_manifest,
        campaign_id=campaign_id,
        fit_arms=fit_arms,
        validation_arms=validation_arms,
        construction=construction,
        selected=selected,
        holdout_arms=holdout_arms,
        holdout=holdout,
        outcome=outcome,
        controls=controls,
    )
    core = _with_digest(body)
    mutations = _exercise_mutations(core)
    if any(value != "PASS" for value in mutations.values()):
        raise OperatorInventionError("operator verifier mutation control failed")
    body["mutation_controls"] = mutations
    return _with_digest(body)


def _verify_sources(receipt: Mapping[str, Any]) -> Path:
    workspace = Path(str(receipt["workspace"])).resolve(strict=True)
    manifest = receipt.get("source_manifest")
    expected = _expected_source_paths()
    if not isinstance(manifest, list) or [row.get("path") for row in manifest] != expected:
        raise OperatorInventionError("operator source manifest path set changed")
    for row in manifest:
        path = workspace / str(row["path"])
        if not path.is_file():
            raise OperatorInventionError(f"operator source disappeared: {path}")
        if path.stat().st_size != int(row["bytes"]) or _file_sha256(path) != row["sha256"]:
            raise OperatorInventionError(f"operator source changed: {path}")
    if receipt.get("protocol") != _protocol_contract():
        raise OperatorInventionError("operator protocol changed")
    implementation = _file_sha256(Path(__file__))
    if receipt.get("implementation_sha256") != implementation:
        raise OperatorInventionError("operator implementation changed")
    identity = _digest(
        {
            "schema": SCHEMA,
            "protocol": _protocol_contract(),
            "sources": manifest,
            "implementation_sha256": implementation,
        }
    )
    if receipt.get("measurement_identity_sha256") != identity or receipt.get("campaign_id") != identity[:24]:
        raise OperatorInventionError("operator measurement identity changed")
    return workspace


def _rebuild_construction(
    receipt: Mapping[str, Any], fit_arms: Sequence[ArmData], validation_arms: Sequence[ArmData]
) -> dict[str, Any]:
    recorded = receipt["construction"]
    seed_results: dict[str, Any] = {}
    mutation_results: dict[str, Any] = {}
    evolved_terms: dict[str, dict[str, Any]] = {}
    selection_records: list[dict[str, Any]] = []
    for frame in FRAMES:
        seeds = _evaluate_candidates(
            _single_term_equations(frame, _seed_scalars()), fit_arms, validation_arms
        )
        seed_selection = recorded["seed_phase"][frame]["selection"]
        selected_seed_id = str(seed_selection["candidate_id"])
        if selected_seed_id != _metric_winner(seeds):
            raise OperatorInventionError("recorded seed is not the metric winner")
        parent_term = seeds[selected_seed_id]["equation"]["terms"][0]
        mutations = _evaluate_candidates(
            _single_term_equations(frame, _mutations(parent_term["scalar"])),
            fit_arms,
            validation_arms,
        )
        mutation_selection = recorded["mutation_phase"][frame]["selection"]
        selected_mutation_id = str(mutation_selection["candidate_id"])
        if selected_mutation_id != _metric_winner(mutations):
            raise OperatorInventionError("recorded mutation is not the metric winner")
        evolved_terms[frame] = mutations[selected_mutation_id]["equation"]["terms"][0]
        seed_results[frame] = {
            "candidate_results": seeds,
            "selection": seed_selection,
            "selected_term": parent_term,
        }
        mutation_results[frame] = {
            "parent_candidate": seed_selection["candidate_id"],
            "parent_term": parent_term,
            "candidate_results": mutations,
            "selection": mutation_selection,
            "selected_term": evolved_terms[frame],
        }
        selection_records.extend((seed_selection, mutation_selection))
    equations = [
        _canonical_equation([term], kind="field-constructed")
        for term in evolved_terms.values()
    ]
    equations.extend(
        _canonical_equation([evolved_terms[left], evolved_terms[right]], kind="field-constructed")
        for left, right in itertools.combinations(FRAMES, 2)
    )
    equations.extend(_human_equations().values())
    synthesis = _evaluate_candidates(equations, fit_arms, validation_arms)
    final_selection = recorded["final_selection"]
    if str(final_selection["candidate_id"]) != _metric_winner(synthesis):
        raise OperatorInventionError("recorded synthesis is not the metric winner")
    selection_records.append(final_selection)
    return {
        "seed_phase": seed_results,
        "mutation_phase": mutation_results,
        "evolved_terms": evolved_terms,
        "synthesis_candidates": synthesis,
        "final_selection": final_selection,
        "selection_records": selection_records,
    }


def verify_operator_receipt(
    receipt: Mapping[str, Any], *, check_mutation_controls: bool = True
) -> dict[str, Any]:
    """Reconstruct the typed lineage, holdouts, and canonical field records."""

    body = copy.deepcopy(dict(receipt))
    claimed = body.pop("result_sha256", None)
    if not isinstance(claimed, str) or claimed != _digest(body):
        raise OperatorInventionError("operator receipt digest mismatch")
    if receipt.get("schema") != SCHEMA or receipt.get("model_calls") != 0:
        raise OperatorInventionError("operator receipt schema or model-call boundary changed")
    workspace = _verify_sources(receipt)
    field_records = _verify_field_records(receipt)
    controls = calibration_controls()
    if receipt.get("calibration_controls") != controls:
        raise OperatorInventionError("operator calibration reconstruction mismatch")
    fit_arms, validation_arms = _load_development(workspace)
    if receipt["development"]["fit_arms"] != _arm_summary(fit_arms) or receipt["development"]["validation_arms"] != _arm_summary(validation_arms):
        raise OperatorInventionError("operator development split changed")
    construction = _rebuild_construction(receipt, fit_arms, validation_arms)
    if receipt.get("construction") != construction:
        raise OperatorInventionError("operator construction lineage reconstruction mismatch")
    selected_id = str(construction["final_selection"]["candidate_id"])
    selected = construction["synthesis_candidates"][selected_id]
    expected_selected = {
        "candidate_id": selected_id,
        "equation": selected["equation"],
        "coefficients": selected["coefficients"],
        "rendered": _render(selected),
        "validation_mean_nrmse": selected["validation_mean_nrmse"],
    }
    if receipt.get("selected_equation") != expected_selected:
        raise OperatorInventionError("selected invented equation reconstruction mismatch")
    holdout_arms = _load_holdout(workspace)
    expected_holdout = {
        "arms": _arm_summary(holdout_arms),
        **_classify(selected, construction["synthesis_candidates"], holdout_arms),
    }
    if receipt.get("hidden_holdout") != expected_holdout:
        raise OperatorInventionError("operator hidden holdout reconstruction mismatch")
    if check_mutation_controls:
        core = copy.deepcopy(dict(receipt))
        recorded_mutations = core.pop("mutation_controls", None)
        core.pop("result_sha256", None)
        rebuilt = _exercise_mutations(_with_digest(core))
        if recorded_mutations != rebuilt or any(value != "PASS" for value in rebuilt.values()):
            raise OperatorInventionError("operator mutation controls failed reconstruction")
    return {
        "schema": VERIFICATION_SCHEMA,
        "status": "PASS",
        "result_sha256": claimed,
        "classification": expected_holdout["classification"],
        "selected_candidate": selected_id,
        "selection_records_verified": field_records,
        "source_hashes_verified": len(receipt["source_manifest"]),
        "mutation_controls_verified": 6 if check_mutation_controls else 0,
        "model_calls": 0,
    }


__all__ = [
    "OperatorInventionError",
    "SCHEMA",
    "VERIFICATION_SCHEMA",
    "calibration_controls",
    "run_operator_invention",
    "verify_operator_receipt",
]
