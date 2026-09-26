"""Field-owned sparse equation discovery over measured Cassi worlds.

The numerical projection is a fixed measurement kernel.  Candidate equations are
content-addressed and opaque at the cognition boundary; the persistent root
field selects among them from development evidence before structural holdouts
are loaded.  Only the root ``cognition.field`` retains the selection and its
revealed outcome.
"""
from __future__ import annotations

import copy
import hashlib
import itertools
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from cassi_research_residency import open_research_residency

SCHEMA = "cassifi.field-equation-discovery.v1"
VERIFICATION_SCHEMA = "cassifi.field-equation-discovery-verification.v1"
CAMPAIGN_KIND = "field-equation-discovery-20260919"
POWERS = tuple(round(-3.0 + 0.25 * index, 2) for index in range(17))
FIT_FRACTION = 0.60
TRACER_MODULUS = 16
MINIMUM_RADIUS = 0.25
TERM_PENALTY = 0.005

_GAUSSIAN_FIT = tuple(
    f"CassiCosmos/_diag/matter_formation/energy_gaussian_s20260910_v{speed}"
    for speed in ("0p0", "0p5", "1p0", "2p0")
)
_GAUSSIAN_VALIDATION = tuple(
    f"CassiCosmos/_diag/matter_formation/energy_gaussian_s20260911_v{speed}"
    for speed in ("0p0", "0p5", "1p0", "2p0")
)
_HIDDEN_HOLDOUT = tuple(
    f"CassiCosmos/_diag/matter_formation/attractor_ic{index}"
    for index in (2, 5, 6, 7, 10)
)
_COUNTERFLOW_DYNAMIC = (
    "CassiCosmos/_diag/native_counterflow_20260915_endpoint_audited/"
    "r9_dynamic_s20260915_sites_coarse/frames.json"
)
_COUNTERFLOW_FROZEN = (
    "CassiCosmos/_diag/native_counterflow_20260915_endpoint_audited/"
    "r9_frozen_s20260915_sites_coarse/frames.json"
)
_PREREGISTRATION = (
    "CassiCosmos/research/equation_discovery/field_equation_discovery_prereg.md"
)
_FAILED_INVOCATION = "CassiFI/_diag/equation-discovery/failed-first-invocation.json"
_STOPPED_CAMPAIGN_ID = "5d57fe87d014c0d2c176456d"
_STOPPED_SELECTED_ID = "eq-5a0fa950e339625e2008"
_TRAJECTORY_FILES = (
    "receipt.json",
    "analysis.json",
    "history_pos.bin",
    "history_vel.bin",
    "sample_steps.bin",
)


class EquationDiscoveryError(RuntimeError):
    """Raised when evidence cannot support the frozen discovery protocol."""


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
        "basis": "B_p(r)=r*|r|^(p-1)",
        "powers": list(POWERS),
        "candidate_terms": [1, 2],
        "fit_fraction": FIT_FRACTION,
        "tracer_rule": f"index modulo {TRACER_MODULUS} equals zero",
        "minimum_radius": MINIMUM_RADIUS,
        "derivative": "centered velocity difference",
        "selection_statistic": "arm-balanced validation NRMSE plus term penalty",
        "term_penalty": TERM_PENALTY,
        "human_baselines": {"inverse-square": [-2.0], "harmonic-core": [1.0]},
        "hidden_holdouts": list(_HIDDEN_HOLDOUT),
        "novelty_thresholds": {
            "minimum_relative_improvement": 0.10,
            "maximum_per_arm_relative_regression": 0.05,
            "semantic_cosine": 0.999,
            "unsupported_nrmse": 0.75,
        },
    }


def _expected_source_paths() -> list[str]:
    paths = [
        _PREREGISTRATION,
        _FAILED_INVOCATION,
        _COUNTERFLOW_DYNAMIC,
        _COUNTERFLOW_FROZEN,
    ]
    for root in (*_GAUSSIAN_FIT, *_GAUSSIAN_VALIDATION, *_HIDDEN_HOLDOUT):
        paths.extend(f"{root}/{name}" for name in _TRAJECTORY_FILES)
    return sorted(paths)


def _source_manifest(workspace: Path) -> list[dict[str, Any]]:
    rows = []
    for relative in _expected_source_paths():
        path = workspace / relative
        if not path.is_file():
            raise EquationDiscoveryError(f"required equation evidence is absent: {relative}")
        rows.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": _file_sha256(path),
            }
        )
    return rows


def _qualifying_trajectory(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        receipt = json.loads((root / "receipt.json").read_text(encoding="utf-8"))
        analysis = json.loads((root / "analysis.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EquationDiscoveryError(f"trajectory metadata is unreadable: {root}") from exc
    if receipt.get("schema") != "cassi.trajectory-probe.v1":
        raise EquationDiscoveryError(f"trajectory schema is unsupported: {root}")
    if analysis.get("status") != "OK" or analysis.get("domain_status") != "BOUNDED":
        raise EquationDiscoveryError(f"trajectory arm does not qualify: {root}")
    if int(receipt.get("event_overflow", -1)) != 0 or int(receipt.get("sample_overflow", -1)) != 0:
        raise EquationDiscoveryError(f"trajectory recorder overflowed: {root}")
    if abs(float(analysis.get("relative_mass_error", math.inf))) > 1e-9:
        raise EquationDiscoveryError(f"trajectory mass is not conserved: {root}")
    return receipt, analysis
def _initial_speed(receipt: Mapping[str, Any]) -> float:
    geometry = receipt.get("geometry")
    engine = receipt.get("engine")
    value = geometry.get("initial_speed") if isinstance(geometry, Mapping) else None
    if value is None and isinstance(engine, Mapping):
        value = engine.get("initial_speed")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EquationDiscoveryError("trajectory initial-speed provenance is unavailable")
    result = float(value)
    if not math.isfinite(result):
        raise EquationDiscoveryError("trajectory initial-speed provenance is nonfinite")
    return result




def _trajectory_statistics(root: Path, segment: str) -> dict[str, Any]:
    receipt, analysis = _qualifying_trajectory(root)
    slots = int(receipt["sample_slots"])
    tracers = int(receipt["tracer_count"])
    if slots < 3 or tracers < TRACER_MODULUS:
        raise EquationDiscoveryError(f"trajectory dimensions are insufficient: {root}")
    expected_history_bytes = slots * tracers * 4 * np.dtype("<f4").itemsize
    for name in ("history_pos.bin", "history_vel.bin"):
        if (root / name).stat().st_size != expected_history_bytes:
            raise EquationDiscoveryError(f"trajectory history size mismatch: {root / name}")
    if (root / "sample_steps.bin").stat().st_size != slots * np.dtype("<u4").itemsize:
        raise EquationDiscoveryError(f"trajectory clock size mismatch: {root}")

    position = np.fromfile(root / "history_pos.bin", dtype="<f4").reshape(slots, tracers, 4)
    velocity = np.fromfile(root / "history_vel.bin", dtype="<f4").reshape(slots, tracers, 4)
    steps = np.fromfile(root / "sample_steps.bin", dtype="<u4").astype(np.float64)
    clock = steps * float(receipt["dt"])
    if not np.isfinite(position).all() or not np.isfinite(velocity).all():
        raise EquationDiscoveryError(f"trajectory contains nonfinite samples: {root}")
    if not np.all(np.diff(clock) > 0.0):
        raise EquationDiscoveryError(f"trajectory clock is not strictly increasing: {root}")

    center = np.asarray(receipt["engine"]["window_center"], dtype=np.float64)
    radius_vector = position[1:-1, :, :3].astype(np.float64) - center
    acceleration = (
        velocity[2:, :, :3].astype(np.float64)
        - velocity[:-2, :, :3].astype(np.float64)
    ) / (clock[2:, None, None] - clock[:-2, None, None])
    radius = np.linalg.norm(radius_vector, axis=2)
    time_count = radius.shape[0]
    cutoff = int(FIT_FRACTION * time_count)
    time_indices = np.arange(time_count)[:, None]
    tracer_indices = np.arange(tracers)[None, :]
    eligible = (
        (position[1:-1, :, 3] > 0.0)
        & (radius > MINIMUM_RADIUS)
        & (tracer_indices % TRACER_MODULUS == 0)
    )
    if segment == "early":
        eligible &= time_indices < cutoff
    elif segment == "late":
        eligible &= time_indices >= cutoff
    elif segment != "all":
        raise EquationDiscoveryError(f"unknown trajectory segment: {segment}")
    r = radius_vector[eligible]
    a = acceleration[eligible]
    rho = radius[eligible]
    if len(r) == 0:
        raise EquationDiscoveryError(f"trajectory segment has no eligible samples: {root}")
    basis = np.stack([r * rho[:, None] ** (power - 1.0) for power in POWERS], axis=0)
    gram = np.einsum("pni,qni->pq", basis, basis, optimize=True)
    target_cross = np.einsum("pni,ni->p", basis, a, optimize=True)
    target_sq = float(np.einsum("ni,ni->", a, a, optimize=True))
    if not math.isfinite(target_sq) or target_sq <= 0.0:
        raise EquationDiscoveryError(f"trajectory target has no finite energy: {root}")
    return {
        "arm_id": root.name,
        "segment": segment,
        "sample_count": int(len(r)),
        "vector_component_count": int(a.size),
        "target_sq": target_sq,
        "target_cross": target_cross.tolist(),
        "gram": gram.tolist(),
        "source_summary": {
            "seed": int(receipt["seed"]),
            "initial_condition": analysis.get("ic_name"),
            "initial_motion": receipt["geometry"]["initial_motion"],
            "initial_speed": _initial_speed(receipt),
            "sample_slots": slots,
            "tracer_count": tracers,
            "relative_mass_error": float(analysis["relative_mass_error"]),
            "domain_status": analysis["domain_status"],
        },
    }


def _fit_coefficients(support: Sequence[float], arms: Sequence[Mapping[str, Any]]) -> list[float]:
    indices = [POWERS.index(float(power)) for power in support]
    gram = np.zeros((len(indices), len(indices)), dtype=np.float64)
    cross = np.zeros(len(indices), dtype=np.float64)
    for arm in arms:
        arm_gram = np.asarray(arm["gram"], dtype=np.float64)
        arm_cross = np.asarray(arm["target_cross"], dtype=np.float64)
        gram += arm_gram[np.ix_(indices, indices)]
        cross += arm_cross[indices]
    try:
        coefficients = np.linalg.solve(gram, cross)
    except np.linalg.LinAlgError as exc:
        raise EquationDiscoveryError(f"singular equation support: {support}") from exc
    if not np.isfinite(coefficients).all():
        raise EquationDiscoveryError(f"nonfinite equation coefficients: {support}")
    return [float(value) for value in coefficients]


def _arm_nrmse(
    support: Sequence[float], coefficients: Sequence[float], arm: Mapping[str, Any]
) -> float:
    indices = [POWERS.index(float(power)) for power in support]
    coefficient = np.asarray(coefficients, dtype=np.float64)
    gram = np.asarray(arm["gram"], dtype=np.float64)[np.ix_(indices, indices)]
    cross = np.asarray(arm["target_cross"], dtype=np.float64)[indices]
    target_sq = float(arm["target_sq"])
    squared_error = target_sq - 2.0 * float(coefficient @ cross) + float(coefficient @ gram @ coefficient)
    return math.sqrt(max(0.0, squared_error) / target_sq)


def _candidate_id(support: Sequence[float]) -> str:
    return "eq-" + _digest({"basis": "radial-power-v1", "support": list(support)})[:20]


def _supports() -> list[tuple[float, ...]]:
    return [(power,) for power in POWERS] + list(itertools.combinations(POWERS, 2))


def _candidate_results(
    fit_arms: Sequence[Mapping[str, Any]], validation_arms: Sequence[Mapping[str, Any]]
) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for support in _supports():
        coefficients = _fit_coefficients(support, fit_arms)
        fit_rows = {
            str(arm["arm_id"]): _arm_nrmse(support, coefficients, arm)
            for arm in fit_arms
        }
        validation_rows = {
            str(arm["arm_id"]): _arm_nrmse(support, coefficients, arm)
            for arm in validation_arms
        }
        validation_mean = float(sum(validation_rows.values()) / len(validation_rows))
        selection_score = validation_mean + TERM_PENALTY * len(support)
        candidate_id = _candidate_id(support)
        results[candidate_id] = {
            "candidate_id": candidate_id,
            "support": list(support),
            "coefficients": coefficients,
            "fit_nrmse_by_arm": fit_rows,
            "fit_mean_nrmse": float(sum(fit_rows.values()) / len(fit_rows)),
            "validation_nrmse_by_arm": validation_rows,
            "validation_mean_nrmse": validation_mean,
            "term_count": len(support),
            "selection_score": selection_score,
            "development_score": 1.0 - selection_score,
        }
    return results


def _metric_winner(candidates: Mapping[str, Mapping[str, Any]]) -> str:
    return min(candidates, key=lambda key: (float(candidates[key]["selection_score"]), key))


def _field_contract(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": candidate["candidate_id"],
        "development_score": candidate["development_score"],
        "development_cost": candidate["term_count"],
        "development_evidence": {
            "validation_mean_nrmse": candidate["validation_mean_nrmse"],
            "selection_score": candidate["selection_score"],
            "arm_count": len(candidate["validation_nrmse_by_arm"]),
        },
    }


def _field_tournament(
    organism: Any,
    *,
    campaign_id: str,
    candidates: Mapping[str, Mapping[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    active = sorted(candidates)
    selections: list[dict[str, Any]] = []
    round_index = 0
    while len(active) > 1:
        winners: list[str] = []
        for group_index, start in enumerate(range(0, len(active), 32)):
            group = active[start : start + 32]
            if len(group) == 1:
                winners.extend(group)
                continue
            laboratory_id = f"equation-r{round_index}-g{group_index}"
            selection = organism.select_laboratory_candidate(
                campaign_id=campaign_id,
                laboratory_id=laboratory_id,
                objective="select the most predictive compact world equation from development evidence",
                candidates=[_field_contract(candidates[candidate_id]) for candidate_id in group],
            )
            selections.append(selection)
            winners.append(str(selection["candidate_id"]))
        active = sorted(winners)
        round_index += 1
    return active[0], selections


def _synthetic_statistics(exponent: float, *, segment: str) -> dict[str, Any]:
    index = np.arange(1, 258, dtype=np.float64)
    radius = 0.75 + index / 19.0
    directions = np.stack(
        [
            np.cos(index * 0.37),
            np.sin(index * 0.37),
            np.sin(index * 0.19) * 0.5,
        ],
        axis=1,
    )
    directions /= np.linalg.norm(directions, axis=1, keepdims=True)
    r = directions * radius[:, None]
    basis = np.stack([r * radius[:, None] ** (power - 1.0) for power in POWERS], axis=0)
    target = r * radius[:, None] ** (exponent - 1.0)
    return {
        "arm_id": f"synthetic-p{exponent:g}-{segment}",
        "segment": segment,
        "sample_count": len(r),
        "vector_component_count": int(target.size),
        "target_sq": float(np.einsum("ni,ni->", target, target)),
        "target_cross": np.einsum("pni,ni->p", basis, target, optimize=True).tolist(),
        "gram": np.einsum("pni,qni->pq", basis, basis, optimize=True).tolist(),
        "source_summary": {"known_exponent": exponent},
    }


def calibration_controls() -> dict[str, Any]:
    controls: dict[str, Any] = {}
    for label, exponent in (("harmonic", 1.0), ("inverse-square", -2.0)):
        fit = [_synthetic_statistics(exponent, segment="fit")]
        validation = [_synthetic_statistics(exponent, segment="holdout")]
        candidates = _candidate_results(fit, validation)
        winner = _metric_winner(candidates)
        result = candidates[winner]
        passed = result["support"] == [exponent] and result["validation_mean_nrmse"] <= 1e-10
        controls[label] = {
            "status": "PASS" if passed else "FAIL",
            "expected_support": [exponent],
            "selected_candidate": winner,
            "selected_support": result["support"],
            "holdout_nrmse": result["validation_mean_nrmse"],
        }
    if any(control["status"] != "PASS" for control in controls.values()):
        raise EquationDiscoveryError("synthetic equation calibration failed")
    return controls


def _scalar_fit(feature: np.ndarray, target: np.ndarray) -> tuple[float, float]:
    denominator = float(feature @ feature)
    coefficient = 0.0 if denominator == 0.0 else float(feature @ target) / denominator
    target_sq = float(target @ target)
    error = float(np.sum((target - coefficient * feature) ** 2))
    nrmse = 0.0 if target_sq == 0.0 and error == 0.0 else math.sqrt(error / target_sq)
    return coefficient, nrmse


def _counterflow_control(workspace: Path) -> dict[str, Any]:
    dynamic_path = workspace / _COUNTERFLOW_DYNAMIC
    frozen_path = workspace / _COUNTERFLOW_FROZEN
    dynamic = json.loads(dynamic_path.read_text(encoding="utf-8"))["frames"]
    frozen = json.loads(frozen_path.read_text(encoding="utf-8"))["frames"]
    if len(dynamic) < 10 or not frozen:
        raise EquationDiscoveryError("counterflow control has insufficient frames")
    split = int(FIT_FRACTION * len(dynamic))
    feature_names = ("source_work_rate", "graph_energy", "time", "constant")
    target_fit = np.asarray(
        [float(frame["energy"]["semidiscrete_energy_derivative"]) for frame in dynamic[:split]],
        dtype=np.float64,
    )
    target_valid = np.asarray(
        [float(frame["energy"]["semidiscrete_energy_derivative"]) for frame in dynamic[split:]],
        dtype=np.float64,
    )
    results = {}
    for name in feature_names:
        def values(frames: Sequence[Mapping[str, Any]]) -> np.ndarray:
            if name == "time":
                return np.asarray([float(frame["t"]) for frame in frames], dtype=np.float64)
            if name == "constant":
                return np.ones(len(frames), dtype=np.float64)
            return np.asarray([float(frame["energy"][name]) for frame in frames], dtype=np.float64)
        coefficient, _ = _scalar_fit(values(dynamic[:split]), target_fit)
        _, valid_nrmse = _scalar_fit(values(dynamic[split:]) * coefficient, target_valid)
        prediction = coefficient * values(dynamic[split:])
        target_sq = float(target_valid @ target_valid)
        valid_nrmse = math.sqrt(float(np.sum((target_valid - prediction) ** 2)) / target_sq)
        candidate_id = "scalar-" + _digest({"feature": name})[:20]
        results[candidate_id] = {
            "candidate_id": candidate_id,
            "feature": name,
            "coefficient": coefficient,
            "validation_nrmse": valid_nrmse,
        }
    selected = min(results, key=lambda key: (results[key]["validation_nrmse"], key))
    selected_result = results[selected]
    nonzero_rows = [
        frame for frame in dynamic if float(frame["energy"]["source_work_rate"]) != 0.0
    ]
    max_relative_error = max(
        abs(
            float(frame["energy"]["semidiscrete_energy_derivative"])
            - float(frame["energy"]["source_work_rate"])
        )
        / abs(float(frame["energy"]["source_work_rate"]))
        for frame in nonzero_rows
    )
    frozen_zero = all(
        float(frame["energy"]["semidiscrete_energy_derivative"]) == 0.0
        and float(frame["energy"]["source_work_rate"]) == 0.0
        for frame in frozen
    )
    passed = (
        selected_result["feature"] == "source_work_rate"
        and max_relative_error <= 1e-10
        and frozen_zero
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "candidate_results": results,
        "selected_candidate": selected,
        "selected_feature": selected_result["feature"],
        "max_nonzero_relative_error": max_relative_error,
        "dynamic_nonzero_rows": len(nonzero_rows),
        "frozen_all_zero": frozen_zero,
        "frozen_rows": len(frozen),
    }


def _load_development(workspace: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    fit = [_trajectory_statistics(workspace / relative, "early") for relative in _GAUSSIAN_FIT]
    validation = [
        _trajectory_statistics(workspace / relative, "late") for relative in _GAUSSIAN_FIT
    ] + [
        _trajectory_statistics(workspace / relative, "all")
        for relative in _GAUSSIAN_VALIDATION
    ]
    return fit, validation


def _load_holdout(workspace: Path) -> list[dict[str, Any]]:
    return [_trajectory_statistics(workspace / relative, "all") for relative in _HIDDEN_HOLDOUT]


def _summary(arms: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "arm_id": arm["arm_id"],
            "segment": arm["segment"],
            "sample_count": arm["sample_count"],
            "vector_component_count": arm["vector_component_count"],
            "source_summary": arm["source_summary"],
        }
        for arm in arms
    ]


def _prediction_cosine(
    left: Mapping[str, Any], right: Mapping[str, Any], arms: Sequence[Mapping[str, Any]]
) -> float:
    left_indices = [POWERS.index(float(power)) for power in left["support"]]
    right_indices = [POWERS.index(float(power)) for power in right["support"]]
    left_coefficient = np.asarray(left["coefficients"], dtype=np.float64)
    right_coefficient = np.asarray(right["coefficients"], dtype=np.float64)
    dot = left_norm = right_norm = 0.0
    for arm in arms:
        gram = np.asarray(arm["gram"], dtype=np.float64)
        cross_gram = gram[np.ix_(left_indices, right_indices)]
        dot += float(left_coefficient @ cross_gram @ right_coefficient)
        left_norm += float(
            left_coefficient @ gram[np.ix_(left_indices, left_indices)] @ left_coefficient
        )
        right_norm += float(
            right_coefficient @ gram[np.ix_(right_indices, right_indices)] @ right_coefficient
        )
    denominator = math.sqrt(left_norm * right_norm)
    return 0.0 if denominator == 0.0 else dot / denominator


def _holdout_result(
    selected: Mapping[str, Any],
    candidates: Mapping[str, Mapping[str, Any]],
    holdout_arms: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    def measured(candidate: Mapping[str, Any]) -> dict[str, Any]:
        rows = {
            str(arm["arm_id"]): _arm_nrmse(
                candidate["support"], candidate["coefficients"], arm
            )
            for arm in holdout_arms
        }
        return {"nrmse_by_arm": rows, "mean_nrmse": float(sum(rows.values()) / len(rows))}

    selected_metric = measured(selected)
    baseline_ids = {
        "inverse-square": _candidate_id((-2.0,)),
        "harmonic-core": _candidate_id((1.0,)),
    }
    baselines = {
        name: {**measured(candidates[candidate_id]), "candidate_id": candidate_id}
        for name, candidate_id in baseline_ids.items()
    }
    cosine = {
        name: _prediction_cosine(selected, candidates[value["candidate_id"]], holdout_arms)
        for name, value in baselines.items()
    }
    thresholds = _protocol_contract()["novelty_thresholds"]
    support = list(selected["support"])
    if support in ([-2.0], [1.0]):
        classification = "HUMAN_EQUIVALENT"
    elif selected_metric["mean_nrmse"] >= thresholds["unsupported_nrmse"]:
        classification = "UNSUPPORTED_DIFFERENCE"
    else:
        better_mean = min(value["mean_nrmse"] for value in baselines.values())
        improvement = 1.0 - selected_metric["mean_nrmse"] / better_mean
        per_arm_ok = all(
            selected_metric["nrmse_by_arm"][arm_id]
            <= (1.0 + thresholds["maximum_per_arm_relative_regression"])
            * min(value["nrmse_by_arm"][arm_id] for value in baselines.values())
            for arm_id in selected_metric["nrmse_by_arm"]
        )
        semantically_same = max(cosine.values()) >= thresholds["semantic_cosine"]
        if (
            improvement >= thresholds["minimum_relative_improvement"]
            and per_arm_ok
            and not semantically_same
        ):
            classification = "ALTERNATIVE_EFFECTIVE_LAW"
        else:
            classification = "DIFFERENT_DESCRIPTION_ONLY"
    return {
        "selected": selected_metric,
        "human_baselines": baselines,
        "prediction_cosine_to_human_baselines": cosine,
        "classification": classification,
        "scope": "reduced collective trajectory law; not a microscopic-force replacement",
    }


def _render_equation(candidate: Mapping[str, Any]) -> dict[str, str]:
    terms = []
    latex_terms = []
    for coefficient, power in zip(candidate["coefficients"], candidate["support"], strict=True):
        terms.append(f"{coefficient:+.12g} * r * |r|^({power:g}-1)")
        latex_terms.append(f"{coefficient:+.12g}\\,\\mathbf r|\\mathbf r|^{{{power:g}-1}}")
    return {
        "plain": "a = " + " ".join(terms).lstrip("+"),
        "latex": "\\ddot{\\mathbf r}=" + "".join(latex_terms).lstrip("+"),
    }
def _resume_stopped_selection(
    organism: Any, candidates: Mapping[str, Mapping[str, Any]]
) -> tuple[str, list[dict[str, Any]]]:
    prefix = f"organism:lab:{_STOPPED_CAMPAIGN_ID}:equation-r"
    selections: list[dict[str, Any]] = []
    with open_research_residency(Path(organism.root_home)) as residency:
        record_ids = sorted(
            record_id
            for record_id in residency._task()["records"]
            if record_id.startswith(prefix) and record_id.endswith(":selection")
        )
        for record_id in record_ids:
            record = residency._record(record_id)
            if record is None or not isinstance(record.get("payload"), Mapping):
                raise EquationDiscoveryError("stopped field selection record is unreadable")
            selection = copy.deepcopy(dict(record["payload"]))
            if (
                selection.get("campaign_id") != _STOPPED_CAMPAIGN_ID
                or selection.get("holdout_visible_during_selection") is not False
                or selection.get("selection_record_id") != record_id
            ):
                raise EquationDiscoveryError("stopped field selection record changed")
            selections.append(selection)
    if len(selections) != 6:
        raise EquationDiscoveryError("stopped invocation field tournament is incomplete")
    selected_id = str(selections[-1].get("candidate_id"))
    if selected_id != _STOPPED_SELECTED_ID or selected_id not in candidates:
        raise EquationDiscoveryError("stopped invocation selected candidate changed")
    return selected_id, selections


def _repair_contract(source_manifest: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    failed = next(row for row in source_manifest if row["path"] == _FAILED_INVOCATION)
    return {
        "status": "ONE_TIME_INSTRUMENT_REPAIR",
        "failed_invocation": {
            "path": _FAILED_INVOCATION,
            "sha256": failed["sha256"],
            "verdict_issued": False,
        },
        "selection_campaign_id": _STOPPED_CAMPAIGN_ID,
        "selection_reused_not_repeated": True,
        "selected_candidate": _STOPPED_SELECTED_ID,
        "statistical_contract_changed": False,
        "further_repair_invocations_permitted": False,
    }




def _core_receipt(
    *,
    workspace: Path,
    organism: Any,
    source_manifest: list[dict[str, Any]],
    campaign_id: str,
    calibration: Mapping[str, Any],
    conservation: Mapping[str, Any],
    fit_arms: Sequence[Mapping[str, Any]],
    validation_arms: Sequence[Mapping[str, Any]],
    candidates: Mapping[str, Mapping[str, Any]],
    selected_id: str,
    selections: Sequence[Mapping[str, Any]],
    holdout_arms: Sequence[Mapping[str, Any]],
    holdout: Mapping[str, Any],
    outcome: Mapping[str, Any],
) -> dict[str, Any]:
    selected = candidates[selected_id]
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
        "repair": _repair_contract(source_manifest),
        "calibration_controls": calibration,
        "conservation_control": conservation,
        "development": {
            "fit_arms": _summary(fit_arms),
            "validation_arms": _summary(validation_arms),
            "candidate_count": len(candidates),
            "candidate_language_sha256": _digest(
                [{"candidate_id": key, "support": value["support"]} for key, value in sorted(candidates.items())]
            ),
            "candidate_results": dict(candidates),
            "metric_winner": _metric_winner(candidates),
        },
        "field_selection": {
            "selected_candidate": selected_id,
            "selected_before_holdout": True,
            "candidate_id_is_content_addressed": True,
            "tournament_records": list(selections),
        },
        "selected_equation": {
            "candidate_id": selected_id,
            "support": selected["support"],
            "coefficients": selected["coefficients"],
            "rendered": _render_equation(selected),
        },
        "hidden_holdout": {
            "arms": _summary(holdout_arms),
            **dict(holdout),
        },
        "field_outcome": dict(outcome),
    }


def _with_digest(body: Mapping[str, Any]) -> dict[str, Any]:
    plain = copy.deepcopy(dict(body))
    return {**plain, "result_sha256": _digest(plain)}


def _exercise_mutations(receipt: Mapping[str, Any]) -> dict[str, str]:
    mutations: dict[str, Any] = {}
    source = copy.deepcopy(dict(receipt))
    source["source_manifest"][0]["sha256"] = "0" * 64
    mutations["source-hash"] = source
    equation = copy.deepcopy(dict(receipt))
    equation["selected_equation"]["coefficients"][0] += 0.125
    mutations["selected-equation"] = equation
    split = copy.deepcopy(dict(receipt))
    split["protocol"]["fit_fraction"] = 0.61
    mutations["split"] = split
    field_record = copy.deepcopy(dict(receipt))
    field_record["field_selection"]["tournament_records"][-1]["selection_record_id"] = "missing:selection"
    mutations["field-record-removal"] = field_record
    results = {}
    for name, mutated in mutations.items():
        mutated.pop("result_sha256", None)
        mutated = _with_digest(mutated)
        try:
            verify_equation_receipt(mutated, check_mutation_controls=False)
        except (AssertionError, EquationDiscoveryError, ValueError):
            results[name] = "PASS"
        else:
            results[name] = "FAIL"
    return results


def run_equation_discovery(organism: Any, *, workspace: Path) -> dict[str, Any]:
    """Run the frozen discovery once, with holdouts loaded only after field choice."""

    workspace = Path(workspace).resolve(strict=True)
    source_manifest = _source_manifest(workspace)
    calibration = calibration_controls()
    conservation = _counterflow_control(workspace)
    if conservation["status"] != "PASS":
        raise EquationDiscoveryError("counterflow conservation control failed")
    fit_arms, validation_arms = _load_development(workspace)
    candidates = _candidate_results(fit_arms, validation_arms)
    campaign_id = _STOPPED_CAMPAIGN_ID
    selected_id, selections = _resume_stopped_selection(organism, candidates)
    metric_winner = _metric_winner(candidates)
    if selected_id != metric_winner:
        raise EquationDiscoveryError("root field selection disagrees with registered development priority")

    holdout_arms = _load_holdout(workspace)
    holdout = _holdout_result(candidates[selected_id], candidates, holdout_arms)
    selected_result = {
        "selected_equation": {
            "candidate_id": selected_id,
            "support": candidates[selected_id]["support"],
            "coefficients": candidates[selected_id]["coefficients"],
            "rendered": _render_equation(candidates[selected_id]),
        },
        "hidden_holdout": holdout,
    }
    outcome = organism.admit_laboratory_outcome(
        campaign_id=campaign_id,
        laboratory_id="equation-discovery",
        candidate_id=selected_id,
        selected_result=selected_result,
    )
    body = _core_receipt(
        workspace=workspace,
        organism=organism,
        source_manifest=source_manifest,
        campaign_id=campaign_id,
        calibration=calibration,
        conservation=conservation,
        fit_arms=fit_arms,
        validation_arms=validation_arms,
        candidates=candidates,
        selected_id=selected_id,
        selections=selections,
        holdout_arms=holdout_arms,
        holdout=holdout,
        outcome=outcome,
    )
    core = _with_digest(body)
    mutations = _exercise_mutations(core)
    if any(value != "PASS" for value in mutations.values()):
        raise EquationDiscoveryError("equation verifier mutation control failed")
    body["mutation_controls"] = mutations
    return _with_digest(body)


def _verify_sources(receipt: Mapping[str, Any]) -> Path:
    workspace = Path(str(receipt["workspace"])).resolve(strict=True)
    expected = _expected_source_paths()
    manifest = receipt.get("source_manifest")
    if not isinstance(manifest, list) or [row.get("path") for row in manifest] != expected:
        raise EquationDiscoveryError("equation source manifest path set changed")
    for row in manifest:
        path = workspace / str(row["path"])
        if not path.is_file():
            raise EquationDiscoveryError(f"equation source disappeared: {path}")
        if path.stat().st_size != int(row["bytes"]) or _file_sha256(path) != row["sha256"]:
            raise EquationDiscoveryError(f"equation source changed: {path}")
    if receipt.get("protocol") != _protocol_contract():
        raise EquationDiscoveryError("equation protocol contract changed")
    if _file_sha256(Path(__file__)) != receipt.get("implementation_sha256"):
        raise EquationDiscoveryError("equation implementation digest changed")
    identity = _digest(
        {
            "schema": SCHEMA,
            "protocol": _protocol_contract(),
            "sources": manifest,
            "implementation_sha256": _file_sha256(Path(__file__)),
        }
    )
    if receipt.get("measurement_identity_sha256") != identity:
        raise EquationDiscoveryError("equation measurement identity changed")
    if receipt.get("repair") != _repair_contract(manifest):
        raise EquationDiscoveryError("equation repair record changed")
    if receipt.get("campaign_id") != _STOPPED_CAMPAIGN_ID:
        raise EquationDiscoveryError("equation selection campaign changed")
    return workspace


def _verify_field_records(receipt: Mapping[str, Any]) -> int:
    count = 0
    home = Path(str(receipt["organism_home"]))
    with open_research_residency(home / "root") as residency:
        for selection in receipt["field_selection"]["tournament_records"]:
            record = residency._record(selection["selection_record_id"])
            if record is None:
                raise EquationDiscoveryError("equation field selection record is missing")
            payload = record.get("payload", {})
            if (
                payload.get("campaign_id") != receipt["campaign_id"]
                or payload.get("candidate_id") != selection["candidate_id"]
                or payload.get("holdout_visible_during_selection") is not False
            ):
                raise EquationDiscoveryError("equation field selection record changed")
            count += 1
        outcome = receipt["field_outcome"]
        record = residency._record(outcome["record_id"])
        if record is None:
            raise EquationDiscoveryError("equation field outcome record is missing")
        payload = record.get("payload", {})
        if (
            payload.get("campaign_id") != receipt["campaign_id"]
            or payload.get("candidate_id") != receipt["field_selection"]["selected_candidate"]
            or payload.get("selected_result_sha256") != outcome["selected_result_sha256"]
            or payload.get("holdout_revealed_after_selection") is not True
        ):
            raise EquationDiscoveryError("equation field outcome record changed")
        count += 1
    return count


def verify_equation_receipt(
    receipt: Mapping[str, Any], *, check_mutation_controls: bool = True
) -> dict[str, Any]:
    """Rebuild all statistics and independently verify field-owned records."""

    body = copy.deepcopy(dict(receipt))
    claimed = body.pop("result_sha256", None)
    if not isinstance(claimed, str) or claimed != _digest(body):
        raise EquationDiscoveryError("equation receipt digest mismatch")
    if receipt.get("schema") != SCHEMA:
        raise EquationDiscoveryError("equation receipt schema is unsupported")
    workspace = _verify_sources(receipt)
    if calibration_controls() != receipt.get("calibration_controls"):
        raise EquationDiscoveryError("equation calibration reconstruction mismatch")
    if _counterflow_control(workspace) != receipt.get("conservation_control"):
        raise EquationDiscoveryError("conservation control reconstruction mismatch")
    fit_arms, validation_arms = _load_development(workspace)
    candidates = _candidate_results(fit_arms, validation_arms)
    development = receipt.get("development", {})
    if development.get("candidate_results") != candidates:
        raise EquationDiscoveryError("equation candidate reconstruction mismatch")
    if development.get("fit_arms") != _summary(fit_arms) or development.get("validation_arms") != _summary(validation_arms):
        raise EquationDiscoveryError("equation split reconstruction mismatch")
    selected_id = str(receipt["field_selection"]["selected_candidate"])
    if selected_id != _metric_winner(candidates):
        raise EquationDiscoveryError("equation field choice is not the registered priority winner")
    selected = candidates[selected_id]
    expected_selected = {
        "candidate_id": selected_id,
        "support": selected["support"],
        "coefficients": selected["coefficients"],
        "rendered": _render_equation(selected),
    }
    if receipt.get("selected_equation") != expected_selected:
        raise EquationDiscoveryError("selected equation reconstruction mismatch")
    holdout_arms = _load_holdout(workspace)
    expected_holdout = {
        "arms": _summary(holdout_arms),
        **_holdout_result(selected, candidates, holdout_arms),
    }
    if receipt.get("hidden_holdout") != expected_holdout:
        raise EquationDiscoveryError("hidden holdout reconstruction mismatch")
    field_records = _verify_field_records(receipt)
    if check_mutation_controls:
        core = copy.deepcopy(dict(receipt))
        recorded_mutations = core.pop("mutation_controls", None)
        core = _with_digest({key: value for key, value in core.items() if key != "result_sha256"})
        rebuilt_mutations = _exercise_mutations(core)
        if recorded_mutations != rebuilt_mutations or any(
            value != "PASS" for value in rebuilt_mutations.values()
        ):
            raise EquationDiscoveryError("equation mutation controls failed reconstruction")
    return {
        "schema": VERIFICATION_SCHEMA,
        "status": "PASS",
        "result_sha256": claimed,
        "candidate_count": len(candidates),
        "selected_candidate": selected_id,
        "classification": expected_holdout["classification"],
        "source_hashes_verified": len(receipt["source_manifest"]),
        "field_records_verified": field_records,
        "mutation_controls_verified": 4 if check_mutation_controls else 0,
    }


__all__ = [
    "EquationDiscoveryError",
    "SCHEMA",
    "VERIFICATION_SCHEMA",
    "calibration_controls",
    "run_equation_discovery",
    "verify_equation_receipt",
]
