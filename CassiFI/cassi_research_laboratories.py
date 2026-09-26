"""Four evidence-grounded laboratories for the persistent Cassi research organism.

The laboratories never add learned sidecars.  They expose bounded candidate
representations to the organism's canonical cognition.field, let its semantic
agenda choose from development-only evidence, then reveal chronological or
structural holdouts after the choice is fixed.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from cassi_cubic_reduction import ReductionProfile, solve_cubic_reduction
from cassi_research_residency import open_research_residency

SCHEMA = "cassifi.research-laboratories.v1"


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _accuracy(truth: Sequence[int], predicted: Sequence[int]) -> dict[str, Any]:
    if len(truth) != len(predicted) or not truth:
        raise ValueError("accuracy requires nonempty matched observations")
    correct = sum(int(a == b) for a, b in zip(truth, predicted, strict=True))
    recalls = []
    for label in (0, 1):
        indices = [i for i, value in enumerate(truth) if value == label]
        if indices:
            recalls.append(sum(int(predicted[i] == label) for i in indices) / len(indices))
    return {
        "count": len(truth),
        "correct": correct,
        "accuracy": correct / len(truth),
        "balanced_accuracy": sum(recalls) / len(recalls),
        "truth_positive_fraction": sum(truth) / len(truth),
        "predicted_positive_fraction": sum(predicted) / len(predicted),
    }


def _nearest_neighbor(
    train_x: Sequence[Sequence[float]],
    train_y: Sequence[int],
    query: Sequence[float],
) -> int:
    if not train_x or len(train_x) != len(train_y):
        raise ValueError("nearest-neighbor training data are invalid")
    width = len(query)
    if any(len(row) != width for row in train_x):
        raise ValueError("nearest-neighbor feature widths disagree")
    means = [sum(row[j] for row in train_x) / len(train_x) for j in range(width)]
    scales = []
    for j, mean in enumerate(means):
        variance = sum((row[j] - mean) ** 2 for row in train_x) / len(train_x)
        scales.append(max(math.sqrt(variance), 1.0e-12))
    distance_and_index = []
    for index, row in enumerate(train_x):
        distance = sum(((row[j] - query[j]) / scales[j]) ** 2 for j in range(width))
        distance_and_index.append((distance, index))
    _, nearest = min(distance_and_index)
    return int(train_y[nearest])


def _evaluate_representation(
    features: Sequence[Sequence[float]],
    labels: Sequence[int],
    *,
    development_count: int,
    warmup: int = 3,
) -> dict[str, Any]:
    if not warmup < development_count < len(labels):
        raise ValueError("representation split is invalid")
    development_truth: list[int] = []
    development_predicted: list[int] = []
    for index in range(warmup, development_count):
        development_truth.append(int(labels[index]))
        development_predicted.append(
            _nearest_neighbor(features[:index], labels[:index], features[index])
        )
    holdout_truth = [int(value) for value in labels[development_count:]]
    holdout_predicted = [
        _nearest_neighbor(
            features[:development_count], labels[:development_count], features[index]
        )
        for index in range(development_count, len(labels))
    ]
    return {
        "development": _accuracy(development_truth, development_predicted),
        "holdout": _accuracy(holdout_truth, holdout_predicted),
        "development_predictions": development_predicted,
        "development_truth": development_truth,
        "holdout_predictions": holdout_predicted,
        "holdout_truth": holdout_truth,
    }


def _topology_series(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    phase = value.get("child_phase_rate_summaries")
    topology = value.get("topology_summaries")
    parent = value.get("parent_circulation_summaries")
    if not all(isinstance(item, list) for item in (phase, topology, parent)):
        raise ValueError("topology observatory receipt lacks required trajectories")
    if len(phase) != len(topology) or len(phase) != len(parent) or len(phase) < 16:
        raise ValueError("topology observatory trajectories are incomplete")
    series = []
    for index, (child, topo, circulation) in enumerate(zip(phase, topology, parent, strict=True)):
        series.append(
            {
                "epoch": index,
                "parent_omega": float(circulation["angular_velocity_z"]),
                "child_mean": float(child["weighted_mean"]),
                "child_std": float(child["weighted_std"]),
                "opposite": int(child["signed_relation_to_parent"] == "opposite_sign"),
                "amplitude_min": float(topo["amplitude_min"]),
                "amplitude_max": float(topo["amplitude_max"]),
                "winding_components": int(topo["component_count"]),
            }
        )
    provenance = {
        "path": str(path.resolve()),
        "sha256": _file_sha256(path),
        "status": value.get("status"),
        "phase_field_status": value.get("phase_field_status"),
        "epochs": len(series),
    }
    return series, provenance


def _physics_laboratories(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    series, provenance = _topology_series(path)
    baseline_floor = series[0]["amplitude_min"]
    survival_labels = [
        int(series[index + 2]["amplitude_min"] >= 0.75 * baseline_floor)
        for index in range(len(series) - 2)
    ]
    survival_features = {
        "amplitude-snapshot": [
            [row["amplitude_min"] / baseline_floor, row["amplitude_max"] / baseline_floor]
            for row in series[:-2]
        ],
        "phase-dynamics": [
            [row["parent_omega"], row["child_mean"], row["child_std"]]
            for row in series[:-2]
        ],
        "relational-multiscale": [
            [
                row["amplitude_min"] / baseline_floor,
                row["amplitude_max"] / max(row["amplitude_min"], 1.0e-12),
                row["child_std"] / max(abs(row["parent_omega"]), 1.0e-12),
                row["child_mean"] * row["parent_omega"],
            ]
            for row in series[:-2]
        ],
    }
    survival = {
        "objective": "predict whether the coherent amplitude floor remains at least 75% of its initial value two epochs later",
        "development_count": 11,
        "candidate_results": {
            name: _evaluate_representation(values, survival_labels, development_count=11)
            for name, values in survival_features.items()
        },
        "case_count": len(survival_labels),
        "label_positive_fraction": sum(survival_labels) / len(survival_labels),
        "support_boundary": "amplitude-floor persistence in one recorded trajectory; not string or winding survival",
    }

    relation_labels = [series[index + 1]["opposite"] for index in range(len(series) - 1)]
    relation_features = {
        "parent-only": [[row["parent_omega"]] for row in series[:-1]],
        "child-only": [[row["child_mean"], row["child_std"]] for row in series[:-1]],
        "coupled-flow": [
            [
                row["parent_omega"],
                row["child_mean"],
                row["child_std"],
                row["child_mean"] * row["parent_omega"],
                row["child_std"] / max(abs(row["parent_omega"]), 1.0e-12),
                row["amplitude_max"] / max(row["amplitude_min"], 1.0e-12),
            ]
            for row in series[:-1]
        ],
    }
    representation = {
        "objective": "predict whether child phase flow opposes parent circulation at the next epoch",
        "development_count": 11,
        "candidate_results": {
            name: _evaluate_representation(values, relation_labels, development_count=11)
            for name, values in relation_features.items()
        },
        "case_count": len(relation_labels),
        "label_positive_fraction": sum(relation_labels) / len(relation_labels),
        "discovered_variables": {
            "parent_flow": "parent angular velocity",
            "child_flow": "amplitude-weighted phase-rate mean and spread",
            "coupling": "signed child-parent product and scale-normalized phase dispersion",
            "breathing": "amplitude envelope ratio",
        },
        "winding_result": {
            "observed_components": sum(row["winding_components"] for row in series),
            "status": "support-gap",
            "meaning": "the live receipt contains no winding event from which reconnection or string survival can be learned",
        },
    }
    return survival, {"laboratory": representation, "provenance": provenance}


def _cyclic_formula(n: int, left: int, right: int) -> list[list[int]]:
    return [sorted((index + 1, (index + left) % n + 1, (index + right) % n + 1)) for index in range(n)]


def _tetra_union(count: int) -> list[list[int]]:
    clauses: list[list[int]] = []
    for block in range(count):
        offset = 4 * block
        clauses.extend(
            [
                [offset + 1, offset + 2, offset + 3],
                [offset + 1, offset + 2, offset + 4],
                [offset + 1, offset + 3, offset + 4],
                [offset + 2, offset + 3, offset + 4],
            ]
        )
    return clauses


def _exact_specs() -> tuple[list[tuple[str, list[list[int]]]], list[tuple[str, list[list[int]]]]]:
    development = [
        ("cyclic-7-1-3", _cyclic_formula(7, 1, 3)),
        ("cyclic-8-1-3", _cyclic_formula(8, 1, 3)),
        ("cyclic-9-2-4", _cyclic_formula(9, 2, 4)),
        ("cyclic-10-1-4", _cyclic_formula(10, 1, 4)),
        ("tetra-union-2", _tetra_union(2)),
        ("tetra-union-3", _tetra_union(3)),
    ]
    holdout = [
        ("cyclic-11-2-5", _cyclic_formula(11, 2, 5)),
        ("cyclic-12-1-5", _cyclic_formula(12, 1, 5)),
        ("cyclic-13-3-6", _cyclic_formula(13, 3, 6)),
        ("tetra-union-4", _tetra_union(4)),
    ]
    return development, holdout


def _solver_work(ledger: Mapping[str, Any]) -> int:
    keys = (
        "candidate_assignments",
        "equation_evaluations",
        "projection_states_checked",
        "separator_assignments_checked",
        "literal_probe_trials",
        "propagation_rows_checked",
        "fraction_updates",
    )
    return sum(int(ledger.get(key, 0)) for key in keys)


def _formula_components(formula: Sequence[Sequence[int]]) -> list[list[list[int]]]:
    variable_clauses: dict[int, list[int]] = {}
    for clause_index, clause in enumerate(formula):
        for variable in clause:
            variable_clauses.setdefault(int(variable), []).append(clause_index)
    unseen = set(range(len(formula)))
    components: list[list[list[int]]] = []
    while unseen:
        pending = [min(unseen)]
        clause_indices: set[int] = set()
        while pending:
            clause_index = pending.pop()
            if clause_index in clause_indices:
                continue
            clause_indices.add(clause_index)
            unseen.discard(clause_index)
            for variable in formula[clause_index]:
                pending.extend(
                    neighbor
                    for neighbor in variable_clauses[int(variable)]
                    if neighbor not in clause_indices
                )
        variables = sorted(
            {int(variable) for index in clause_indices for variable in formula[index]}
        )
        remap = {variable: index + 1 for index, variable in enumerate(variables)}
        components.append(
            sorted(
                [
                    sorted(remap[int(variable)] for variable in formula[index])
                    for index in clause_indices
                ]
            )
        )
    return components


def _exact_row(
    identity: str,
    formula: list[list[int]],
    *,
    method: str,
) -> dict[str, Any]:
    profile = ReductionProfile(
        terminal_nullity=5,
        schedule_mode="adaptive",
        literal_probing=False,
    )
    if method == "monolithic-adaptive":
        result = solve_cubic_reduction(formula, profile=profile)
        return {
            "instance_id": identity,
            "formula_sha256": result["formula_sha256"],
            "status": result["status"],
            "result_sha256": result["result_sha256"],
            "work": _solver_work(result["resource_ledger"]),
            "component_count": 1,
            "component_solves": 1,
            "component_reuses": 0,
        }
    components = _formula_components(formula)
    cache: dict[str, dict[str, Any]] = {}
    component_results = []
    work = 0
    reuses = 0
    for component in components:
        signature = _digest(component)
        if method == "repeated-component-reuse" and signature in cache:
            result = cache[signature]
            reuses += 1
        else:
            result = solve_cubic_reduction(component, profile=profile)
            cache[signature] = result
            work += _solver_work(result["resource_ledger"])
        component_results.append(result)
    statuses = [result["status"] for result in component_results]
    if "unsat" in statuses:
        status = "unsat"
    elif all(value == "sat" for value in statuses):
        status = "sat"
    else:
        status = "unresolved_residual"
    summary = {
        "method": method,
        "components": [
            {
                "formula_sha256": result["formula_sha256"],
                "result_sha256": result["result_sha256"],
                "status": result["status"],
            }
            for result in component_results
        ],
        "status": status,
    }
    return {
        "instance_id": identity,
        "formula_sha256": _digest(sorted(sorted(row) for row in formula)),
        "status": status,
        "result_sha256": _digest(summary),
        "work": work,
        "component_count": len(components),
        "component_solves": len(components) - reuses,
        "component_reuses": reuses,
    }


def _run_exact_method(
    specs: Sequence[tuple[str, list[list[int]]]], method: str
) -> dict[str, Any]:
    rows = [
        _exact_row(identity, formula, method=method)
        for identity, formula in specs
    ]
    resolved = sum(row["status"] in {"sat", "unsat"} for row in rows)
    total_work = sum(row["work"] for row in rows)
    return {
        "instances": rows,
        "resolved": resolved,
        "resolution_rate": resolved / len(rows),
        "total_work": total_work,
        "mean_work": total_work / len(rows),
        "component_solves": sum(row["component_solves"] for row in rows),
        "component_reuses": sum(row["component_reuses"] for row in rows),
    }


def _exact_laboratory() -> dict[str, Any]:
    development, holdout = _exact_specs()
    methods = (
        "monolithic-adaptive",
        "component-factor",
        "repeated-component-reuse",
    )
    return {
        "objective": "resolve unseen cubic exact-one instances with the least audited exact work",
        "candidate_results": {
            method: {
                "development": _run_exact_method(development, method),
                "holdout": _run_exact_method(holdout, method),
            }
            for method in methods
        },
        "development_instances": [name for name, _ in development],
        "holdout_instances": [name for name, _ in holdout],
        "method_boundary": (
            "exact connected-component factorization and byte-identical normalized "
            "component reuse; unresolved remains a valid outcome"
        ),
    }


def _market_cases(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) < 720 * 12:
        raise ValueError("historical market input requires at least twelve complete 720-hour cases")
    closes = [float(row["close"]) for row in rows]
    volumes = [float(row["volume"]) for row in rows]
    timestamps = [str(row["timestamp"]) for row in rows]
    cases = []
    width = 720
    observed = 552
    for start in range(0, len(rows) - width + 1, width):
        end_observed = start + observed
        end = start + width
        history = closes[start:end_observed]
        volume = volumes[start:end_observed]
        hourly = [math.log(history[i] / history[i - 1]) for i in range(1, len(history))]
        peak = history[0]
        drawdown = 0.0
        for price in history:
            peak = max(peak, price)
            drawdown = min(drawdown, price / peak - 1.0)
        mean = sum(hourly) / len(hourly)
        variance = sum((value - mean) ** 2 for value in hourly) / len(hourly)
        recent = hourly[-168:]
        recent_mean = sum(recent) / len(recent)
        recent_variance = sum((value - recent_mean) ** 2 for value in recent) / len(recent)
        returns = {
            "r24": math.log(history[-1] / history[-25]),
            "r168": math.log(history[-1] / history[-169]),
            "r552": math.log(history[-1] / history[0]),
        }
        future_return = math.log(closes[end - 1] / history[-1])
        cases.append(
            {
                "start": timestamps[start],
                "observed_end": timestamps[end_observed - 1],
                "outcome_end": timestamps[end - 1],
                "label": int(future_return > 0.0),
                "future_log_return": future_return,
                "returns": returns,
                "volatility": math.sqrt(variance),
                "recent_volatility": math.sqrt(recent_variance),
                "drawdown": drawdown,
                "volume_ratio": (sum(volume[-168:]) / 168) / max(sum(volume) / len(volume), 1.0e-12),
            }
        )
    provenance = {
        "path": str(path.resolve()),
        "sha256": _file_sha256(path),
        "rows": len(rows),
        "first_timestamp": timestamps[0],
        "last_timestamp": timestamps[-1],
    }
    return cases, provenance


def _market_features(cases: Sequence[Mapping[str, Any]]) -> dict[str, list[list[float]]]:
    return {
        "single-horizon-trend": [[float(case["returns"]["r552"])] for case in cases],
        "trend-volatility": [
            [
                float(case["returns"]["r24"]),
                float(case["returns"]["r168"]),
                float(case["returns"]["r552"]),
                float(case["volatility"]),
                float(case["drawdown"]),
            ]
            for case in cases
        ],
        "multiscale-regime": [
            [
                float(case["returns"]["r24"]),
                float(case["returns"]["r168"]),
                float(case["returns"]["r552"]),
                float(case["returns"]["r24"] * case["returns"]["r168"]),
                float(case["returns"]["r168"] * case["returns"]["r552"]),
                float(case["recent_volatility"]) / max(float(case["volatility"]), 1.0e-12),
                float(case["drawdown"]),
                float(case["volume_ratio"]),
            ]
            for case in cases
        ],
    }


def _market_laboratory(path: Path, external_path: Path | None) -> dict[str, Any]:
    cases, provenance = _market_cases(path)
    labels = [int(case["label"]) for case in cases]
    development_count = max(8, int(len(cases) * 0.72))
    candidates = {
        name: _evaluate_representation(values, labels, development_count=development_count, warmup=6)
        for name, values in _market_features(cases).items()
    }
    result: dict[str, Any] = {
        "objective": "transfer a regime representation from past 23-day observations to the following seven-day direction",
        "candidate_results": candidates,
        "case_count": len(cases),
        "development_count": development_count,
        "holdout_count": len(cases) - development_count,
        "provenance": provenance,
        "execution_boundary": "regime-direction representation only; not a profitability or deployment result",
    }
    if external_path is not None:
        external, external_provenance = _market_cases(external_path)
        train_features = _market_features(cases)
        external_features = _market_features(external)
        external_labels = [int(case["label"]) for case in external]
        result["external"] = {
            "provenance": external_provenance,
            "candidate_results": {
                name: _accuracy(
                    external_labels,
                    [
                        _nearest_neighbor(values, labels, query)
                        for query in external_features[name]
                    ],
                )
                for name, values in train_features.items()
            },
        }
    return result


def _candidate_contract(laboratory: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = sorted(laboratory["candidate_results"].items())
    exact_costs = [
        int(result.get("development", result).get("total_work", 0))
        for _, result in rows
    ]
    maximum_cost = max(exact_costs, default=0)
    candidates = []
    for candidate_id, result in rows:
        development = result.get("development", result)
        if "balanced_accuracy" in development:
            score = float(development["balanced_accuracy"])
            cost = len(result.get("development_predictions", []))
        else:
            cost = int(development["total_work"])
            efficiency = 0.0 if maximum_cost == 0 else 1.0 - cost / maximum_cost
            score = float(development["resolution_rate"]) + 0.1 * efficiency
        candidates.append(
            {
                "candidate_id": candidate_id,
                "development_score": score,
                "development_cost": cost,
                "development_evidence": development,
            }
        )
    return candidates


def run_laboratories(
    organism: Any,
    *,
    cosmos_receipt: Path,
    market_csv: Path,
    external_market_csv: Path | None = None,
) -> dict[str, Any]:
    """Run all four laboratories and admit choices through the root field."""

    survival, representation_bundle = _physics_laboratories(cosmos_receipt)
    representation = representation_bundle["laboratory"]
    exact = _exact_laboratory()
    market = _market_laboratory(market_csv, external_market_csv)
    laboratories = {
        "coherent-structure-survival": survival,
        "two-fluid-representation": representation,
        "exact-one-decomposition": exact,
        "chronological-market-regime": market,
    }
    input_identity = {
        "cosmos": representation_bundle["provenance"],
        "market": market["provenance"],
        "external_market": None if external_market_csv is None else market["external"]["provenance"],
        "exact_spec_sha256": _digest(_exact_specs()),
        "implementation_sha256": _file_sha256(Path(__file__)),
        "organism_home": str(organism.home.resolve()),
    }
    campaign_id = _digest({"schema": SCHEMA, "inputs": input_identity})[:24]
    selections = {}
    outcomes = {}
    for laboratory_id, laboratory in laboratories.items():
        selections[laboratory_id] = organism.select_laboratory_candidate(
            campaign_id=campaign_id,
            laboratory_id=laboratory_id,
            objective=str(laboratory["objective"]),
            candidates=_candidate_contract(laboratory),
        )
        chosen = selections[laboratory_id]["candidate_id"]
        laboratory["selected_candidate"] = chosen
        laboratory["selected_result"] = laboratory["candidate_results"][chosen]
        outcomes[laboratory_id] = organism.admit_laboratory_outcome(
            campaign_id=campaign_id,
            laboratory_id=laboratory_id,
            candidate_id=chosen,
            selected_result=laboratory["selected_result"],
        )
    body = {
        "schema": SCHEMA,
        "campaign_id": campaign_id,
        "inputs": input_identity,
        "laboratories": laboratories,
        "field_selections": selections,
        "field_outcomes": outcomes,
    }
    return {**body, "result_sha256": _digest(body)}


def verify_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Independently rebuild all measurements and compare the frozen receipt."""

    body = dict(receipt)
    claimed = body.pop("result_sha256", None)
    if claimed != _digest(body):
        raise ValueError("laboratory receipt digest mismatch")
    inputs = receipt["inputs"]
    cosmos = Path(inputs["cosmos"]["path"])
    market = Path(inputs["market"]["path"])
    external_info = inputs.get("external_market")
    external = None if external_info is None else Path(external_info["path"])
    for info, path in ((inputs["cosmos"], cosmos), (inputs["market"], market)):
        if _file_sha256(path) != info["sha256"]:
            raise ValueError(f"source evidence changed: {path}")
    if external is not None and _file_sha256(external) != external_info["sha256"]:
        raise ValueError(f"source evidence changed: {external}")
    if _file_sha256(Path(__file__)) != inputs.get("implementation_sha256"):
        raise ValueError("laboratory implementation digest mismatch")
    survival, representation_bundle = _physics_laboratories(cosmos)
    rebuilt = {
        "coherent-structure-survival": survival,
        "two-fluid-representation": representation_bundle["laboratory"],
        "exact-one-decomposition": _exact_laboratory(),
        "chronological-market-regime": _market_laboratory(market, external),
    }
    for laboratory_id, value in rebuilt.items():
        recorded = dict(receipt["laboratories"][laboratory_id])
        recorded.pop("selected_candidate", None)
        recorded.pop("selected_result", None)
        if _canonical(recorded) != _canonical(value):
            raise ValueError(f"laboratory reconstruction mismatch: {laboratory_id}")
        selected = receipt["laboratories"][laboratory_id]["selected_candidate"]
        if selected not in value["candidate_results"]:
            raise ValueError(f"unknown selected candidate: {laboratory_id}")
        if receipt["laboratories"][laboratory_id]["selected_result"] != value["candidate_results"][selected]:
            raise ValueError(f"selected result mismatch: {laboratory_id}")
    field_records_verified = 0
    with open_research_residency(Path(inputs["organism_home"]) / "root") as residency:
        for laboratory_id, selection in receipt["field_selections"].items():
            record = residency._record(selection["selection_record_id"])
            if record is None:
                raise ValueError(f"field selection record is missing: {laboratory_id}")
            payload = record.get("payload", {})
            if (
                payload.get("campaign_id") != receipt["campaign_id"]
                or payload.get("laboratory_id") != laboratory_id
                or payload.get("candidate_id") != selection["candidate_id"]
                or payload.get("holdout_visible_during_selection") is not False
            ):
                raise ValueError(f"field selection record mismatch: {laboratory_id}")
            field_records_verified += 1
        for laboratory_id, outcome in receipt["field_outcomes"].items():
            record = residency._record(outcome["record_id"])
            if record is None:
                raise ValueError(f"field outcome record is missing: {laboratory_id}")
            payload = record.get("payload", {})
            if (
                payload.get("campaign_id") != receipt["campaign_id"]
                or payload.get("laboratory_id") != laboratory_id
                or payload.get("candidate_id")
                != receipt["field_selections"][laboratory_id]["candidate_id"]
                or payload.get("selected_result_sha256")
                != outcome["selected_result_sha256"]
                or payload.get("holdout_revealed_after_selection") is not True
            ):
                raise ValueError(f"field outcome record mismatch: {laboratory_id}")
            field_records_verified += 1
    return {
        "schema": "cassifi.research-laboratories-verification.v1",
        "status": "PASS",
        "result_sha256": claimed,
        "laboratories_verified": sorted(rebuilt),
        "source_hashes_verified": 3 + int(external is not None),
        "field_records_verified": field_records_verified,
    }
