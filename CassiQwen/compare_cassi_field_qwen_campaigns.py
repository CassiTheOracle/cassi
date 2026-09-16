#!/usr/bin/env python3
"""Compare a current CassiFI/Qwen workcase campaign with a prior report.

The two campaigns intentionally remain separate observations.  This utility
reports within-campaign measurements and only permits cross-campaign numeric
comparison when an exact task identity is available; otherwise cross-campaign
numeric deltas are explicitly null and the reason is retained in the output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

SCHEMA = "cassi.field-qwen.campaign-comparison.v1"
_ALLOWED_NUMERIC_KEYS = (
    "native_state_bytes_removed",
    "native_ops_skipped",
    "native_layers_skipped",
    "native_output_rows_skipped",
    "field_direct_token_overrides",
)


def _load_json(path: Path) -> dict[str, Any]:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant {value!r} in {path}")

    value = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _input_file(path: Path, filename: str) -> Path:
    candidate = path.expanduser()
    if candidate.is_dir():
        candidate = candidate / filename
    if not candidate.is_file():
        raise FileNotFoundError(f"required input not found: {candidate}")
    return candidate.resolve()


def _optional_file(root_or_file: Path, filename: str) -> Path | None:
    candidate = root_or_file.expanduser()
    if candidate.is_file():
        candidate = candidate.parent / filename
    else:
        candidate = candidate / filename
    return candidate.resolve() if candidate.is_file() else None


def _mapping(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _at(value: Any, *keys: str) -> Any:
    current = value
    for key in keys:
        if not isinstance(current, Mapping) or key not in current:
            return None
        current = current[key]
    return current


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def _boolean(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _delta(right: Any, left: Any) -> int | float | None:
    right_number = _number(right)
    left_number = _number(left)
    if right_number is None or left_number is None:
        return None
    return right_number - left_number


def _rate(passed: Any, cases: Any) -> float | None:
    passed_number = _number(passed)
    cases_number = _number(cases)
    if passed_number is None or cases_number is None or cases_number <= 0:
        return None
    return float(passed_number) / float(cases_number)


def _pass_summary(value: Any) -> dict[str, int | float | None]:
    row = _mapping(value)
    cases = _number(row.get("cases")) if row is not None else None
    passed = _number(row.get("passed")) if row is not None else None
    semantic_passed = _number(row.get("semantic_passed")) if row is not None else None
    return {
        "cases": cases,
        "passed": passed,
        "pass_rate": _rate(passed, cases),
        "semantic_passed": semantic_passed,
        "semantic_pass_rate": _rate(semantic_passed, cases),
    }


def _ids_from_list(value: Any) -> list[str] | None:
    if not isinstance(value, list) or not value:
        return None
    ids: list[str] = []
    for row in value:
        if not isinstance(row, Mapping) or not isinstance(row.get("id"), str):
            return None
        ids.append(row["id"])
    return ids if len(ids) == len(set(ids)) else None


def _analysis_ids(analysis: Mapping[str, Any], protocol: Mapping[str, Any] | None) -> list[str] | None:
    if protocol is not None:
        envelope = _mapping(protocol.get("protocol"))
        protocol_ids = _ids_from_list(envelope.get("cases")) if envelope is not None else None
        if protocol_ids is not None:
            return protocol_ids
    for key in ("comparisons", "cases", "rows"):
        ids = _ids_from_list(analysis.get(key))
        if ids is not None:
            return ids
    return None


def _prior_ids(summary: Mapping[str, Any]) -> list[str] | None:
    for key in ("comparisons", "cases", "rows"):
        ids = _ids_from_list(summary.get(key))
        if ids is not None:
            return ids
    # A complete per-suite comparison list is acceptable when supplied by a
    # newer report, but a regressions list is intentionally not treated as the
    # complete task set.
    for suite in ("primary", "reasoning", "memory"):
        section = _mapping(summary.get(suite))
        if section is None:
            continue
        for key in ("comparisons", "cases", "rows"):
            ids = _ids_from_list(section.get(key))
            if ids is not None:
                return ids
    return None


def _numeric_fields(value: Any) -> dict[str, int | float | None]:
    row = _mapping(value)
    if row is None:
        return {key: None for key in _ALLOWED_NUMERIC_KEYS}
    result: dict[str, int | float | None] = {}
    for key in _ALLOWED_NUMERIC_KEYS:
        source_key = "native_dynamic_state_bytes_removed" if key == "native_state_bytes_removed" and "native_dynamic_state_bytes_removed" in row else key
        result[key] = _number(row.get(source_key))
    return result


def _boundedness_current(analysis: Mapping[str, Any]) -> dict[str, Any]:
    memory = _mapping(analysis.get("memory"))
    state_after = _mapping(memory.get("state_after_evaluation")) if memory is not None else None
    if state_after is None and memory is not None:
        state_after = _mapping(memory.get("state_after"))
    if state_after is None:
        state_after = _mapping(analysis.get("state_after_evaluation"))
    if state_after is None:
        state_after = _mapping(analysis.get("state_after"))
    state_restart = _mapping(memory.get("state_after_evaluation_restart")) if memory is not None else None
    if state_restart is None and memory is not None:
        state_restart = _mapping(memory.get("state_after_restart"))
    if state_restart is None:
        state_restart = _mapping(analysis.get("state_after_evaluation_restart"))
    if state_restart is None:
        state_restart = _mapping(analysis.get("state_after_restart"))
    bounds = _mapping(state_after.get("semantic_bounds")) if state_after is not None else None
    active_bindings = _number(state_after.get("semantic_active_bindings")) if state_after is not None else None
    transitions = _number(state_after.get("semantic_transitions")) if state_after is not None else None
    all_finite = _boolean(state_after.get("all_finite")) if state_after is not None else None
    schema = state_after.get("semantic_state_schema") if state_after is not None else None
    kernel = state_after.get("kernel") if state_after is not None else None
    profile_sha256 = state_after.get("profile_sha256") if state_after is not None else None
    catalog_sha256 = state_after.get("catalog_sha256") if state_after is not None else None
    max_records = _number(bounds.get("max_records")) if bounds is not None else None
    max_operations = _number(bounds.get("max_operations")) if bounds is not None else None
    within_declared_bounds: bool | None = None
    if (
        all_finite is not None
        and active_bindings is not None
        and transitions is not None
        and max_records is not None
        and max_operations is not None
    ):
        within_declared_bounds = (
            all_finite is True
            and active_bindings <= max_records
            and transitions <= max_operations
        )
    return {
        "all_finite": all_finite,
        "semantic_state_schema": schema if isinstance(schema, str) else None,
        "kernel": kernel if isinstance(kernel, str) else None,
        "profile_sha256": profile_sha256 if isinstance(profile_sha256, str) else None,
        "catalog_sha256": catalog_sha256 if isinstance(catalog_sha256, str) else None,
        "semantic_active_bindings": active_bindings,
        "semantic_transitions": transitions,
        "semantic_bounds": dict(bounds) if bounds is not None else None,
        "within_declared_bounds": within_declared_bounds,
        "restart_state_all_finite": _boolean(state_restart.get("all_finite")) if state_restart is not None else None,
    }
def _boundedness_prior(summary: Mapping[str, Any], controls: Mapping[str, Any] | None) -> dict[str, Any]:
    long_session = _mapping(summary.get("long_session"))
    saturation = _mapping(controls.get("saturation_verified_from_prequery_bytes")) if controls else None
    return {
        "all_finite": None,
        "semantic_state_schema": None,
        "kernel": None,
        "profile_sha256": None,
        "catalog_sha256": None,
        "semantic_active_bindings": None,
        "semantic_transitions": None,
        "semantic_bounds": None,
        "within_declared_bounds": None,
        "saturation_verified": (
            _boolean(saturation.get("native_prequery_fingerprint_exact")) is True
            and _boolean(saturation.get("nonzero_count_at_least_saturated_count")) is True
        ) if saturation is not None else None,
        "saturated_coordinates": _number(saturation.get("at_abs_64")) if saturation is not None else None,
        "nonzero_coordinates": _number(saturation.get("nonzero_coordinates")) if saturation is not None else None,
        "restart_state_all_finite": None,
        "finite_state_caveat": long_session.get("finite_state_caveat")
        if long_session is not None and isinstance(long_session.get("finite_state_caveat"), str)
        else None,
    }


def _persistence_current(analysis: Mapping[str, Any]) -> dict[str, Any]:
    memory = _mapping(analysis.get("memory"))
    if memory is None:
        memory = {}
    return {
        "prepare_restart_exact": _boolean(memory.get("prepare_restart_exact")),
        "evaluation_restart_exact": _boolean(memory.get("evaluation_restart_exact")),
        "experience_restart_exact": _boolean(memory.get("experience_restart_exact")),
        "repeated_retention_pass": _boolean(memory.get("repeated_retention_pass")),
        "repeated_anchor_checks": _number(memory.get("repeated_anchor_checks")),
        "records_admitted_before_evaluation": _number(memory.get("records_admitted_before_evaluation")),
        "sustained_distractors": _number(memory.get("sustained_distractors")),
    }


def _persistence_prior(summary: Mapping[str, Any], controls: Mapping[str, Any] | None) -> dict[str, Any]:
    memory = _mapping(summary.get("memory")) or {}
    restart = controls.get("restart") if controls is not None else None
    restart_rows = restart if isinstance(restart, list) else []
    file_identity_values: list[bool] = []
    for item in restart_rows:
        row = _mapping(item)
        files = row.get("files") if row is not None else None
        if isinstance(files, Mapping):
            for file_row in files.values():
                if isinstance(file_row, Mapping) and isinstance(file_row.get("identical_after_process_restart"), bool):
                    file_identity_values.append(file_row["identical_after_process_restart"])
    reset = _mapping(controls.get("long_session_reset_counterfactual")) if controls is not None else None
    return {
        "exact_cross_process_restarts": _number(memory.get("exact_cross_process_restarts")),
        "restart_rows": len(restart_rows) if controls is not None and isinstance(restart, list) else None,
        "restart_file_identity_all_exact": all(file_identity_values) if file_identity_values else None,
        "restart_file_identity_observations": len(file_identity_values) if file_identity_values else None,
        "restored_history_without_replay": _boolean(reset.get("restored_history_without_replay")) if reset is not None else None,
        "retained_result_reproduced_exactly": _boolean(reset.get("retained_result_reproduced_exactly")) if reset is not None else None,
        "same_input_and_native_model": _boolean(reset.get("same_input_and_native_model")) if reset is not None else None,
    }


def _useful_memory_current(analysis: Mapping[str, Any]) -> dict[str, Any]:
    memory = _mapping(analysis.get("memory_dependent")) or {}
    cases = _number(memory.get("cases"))
    field_passed = _number(memory.get("field_passed"))
    baseline_passed = _number(memory.get("baseline_passed"))
    retrieval_exact = _number(memory.get("retrieval_exact"))
    demonstrated = None
    if cases is not None and field_passed is not None and retrieval_exact is not None:
        demonstrated = cases > 0 and field_passed > 0 and retrieval_exact == cases
    return {
        "demonstrated": demonstrated,
        "cases": cases,
        "baseline_passed": baseline_passed,
        "field_passed": field_passed,
        "retrieval_exact": retrieval_exact,
        "task_pass_delta": _delta(field_passed, baseline_passed),
    }


def _useful_memory_prior(summary: Mapping[str, Any]) -> dict[str, Any]:
    memory = _mapping(summary.get("memory")) or {}
    cases = _number(memory.get("fact_dependent_cases"))
    correct = _number(memory.get("fact_dependent_cases_correct_with_retained_qi"))
    demonstrated = (correct > 0) if correct is not None else None
    return {
        "demonstrated": demonstrated,
        "fact_dependent_cases": cases,
        "fact_dependent_cases_correct_with_retained_qi": correct,
        "only_pass_conclusion": memory.get("only_pass") if isinstance(memory.get("only_pass"), str) else None,
    }


def _current_observations(analysis: Mapping[str, Any], protocol: Mapping[str, Any] | None) -> dict[str, Any]:
    transitions = _mapping(analysis.get("transitions")) or {}
    ownership = analysis.get("ownership_receipt")
    return {
        "matched_task_passes": {
            "baseline": _pass_summary(analysis.get("baseline")),
            "field": _pass_summary(analysis.get("field")),
            "memory_dependent": _pass_summary(analysis.get("memory_dependent")),
            "memory_independent": _pass_summary(analysis.get("memory_independent")),
        },
        "gain_regression_counts": {
            "gains": _number(transitions.get("gains")),
            "regressions": _number(transitions.get("regressions")),
            "stable_pass": _number(transitions.get("stable_pass")),
            "stable_fail": _number(transitions.get("stable_fail")),
        },
        "persistence_restart": _persistence_current(analysis),
        "field_boundedness_saturation": _boundedness_current(analysis),
        "native_displacement": _numeric_fields(ownership),
        "useful_retained_memory": _useful_memory_current(analysis),
        "case_ids": _analysis_ids(analysis, protocol),
        "conclusion": analysis.get("conclusion") if isinstance(analysis.get("conclusion"), str) else None,
    }


def _prior_observations(summary: Mapping[str, Any], controls: Mapping[str, Any] | None) -> dict[str, Any]:
    suites: dict[str, Any] = {}
    for suite in ("primary", "reasoning", "memory"):
        section = _mapping(summary.get(suite)) or {}
        arms = _mapping(section.get("per_arm")) or {}
        suites[suite] = {
            "baseline": _pass_summary(arms.get("baseline")),
            "qi": _pass_summary(arms.get("qi")),
        }
    primary_comparison = _mapping(_at(summary, "primary", "comparison")) or {}
    reasoning_comparison = _mapping(_at(summary, "reasoning", "comparison")) or {}
    return {
        "matched_task_passes": suites,
        "gain_regression_counts": {
            "primary": {
                "gains": _number(primary_comparison.get("gains")),
                "regressions": _number(primary_comparison.get("regressions")),
            },
            "reasoning": {
                "gains": _number(reasoning_comparison.get("gains")),
                "regressions": _number(reasoning_comparison.get("regressions")),
            },
        },
        "persistence_restart": _persistence_prior(summary, controls),
        "field_boundedness_saturation": _boundedness_prior(summary, controls),
        "native_displacement": _numeric_fields(summary.get("ownership")),
        "useful_retained_memory": _useful_memory_prior(summary),
        "case_ids": _prior_ids(summary),
        "conclusion": summary.get("conclusion") if isinstance(summary.get("conclusion"), str) else None,
    }


def _within_current_deltas(observations: Mapping[str, Any]) -> dict[str, Any]:
    passes = _mapping(observations.get("matched_task_passes")) or {}
    baseline = _mapping(passes.get("baseline")) or {}
    field = _mapping(passes.get("field")) or {}
    return {
        "field_minus_baseline_passed": _delta(field.get("passed"), baseline.get("passed")),
        "field_minus_baseline_pass_rate": _delta(field.get("pass_rate"), baseline.get("pass_rate")),
        "gains": _at(observations, "gain_regression_counts", "gains"),
        "regressions": _at(observations, "gain_regression_counts", "regressions"),
    }


def _within_prior_deltas(observations: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    suites = _mapping(observations.get("matched_task_passes")) or {}
    for suite in ("primary", "reasoning", "memory"):
        arms = _mapping(suites.get(suite)) or {}
        baseline = _mapping(arms.get("baseline")) or {}
        qi = _mapping(arms.get("qi")) or {}
        result[suite] = {
            "qi_minus_baseline_passed": _delta(qi.get("passed"), baseline.get("passed")),
            "qi_minus_baseline_pass_rate": _delta(qi.get("pass_rate"), baseline.get("pass_rate")),
        }
    return result


def _cross_campaign_deltas(compatible: bool) -> dict[str, Any]:
    # This function intentionally does not perform a positional subtraction.
    # Equal counts are not proof of matched tasks, and the known campaigns use
    # different protocols/arm names.  Keep a fixed null-shaped record so a
    # consumer cannot mistake absent data for zero.
    deltas: dict[str, Any] = {
        "matched_task_passed": None,
        "matched_task_pass_rate": None,
        "gains": None,
        "regressions": None,
        "persistence_restart": None,
        "field_boundedness_saturation": None,
        "native_displacement": None,
        "useful_retained_memory": None,
    }
    return {
        "enabled": compatible,
        "deltas": deltas,
        "reason": None if compatible else "Cross-campaign numeric deltas are withheld because the methodologies and/or exact task sets are not proven identical.",
    }


def _source_record(role: str, path: Path) -> dict[str, str]:
    return {"role": role, "path": str(path), "sha256": _sha256(path)}


def compare(current_path: Path, prior_path: Path, out_path: Path) -> dict[str, Any]:
    current_analysis_path = _input_file(current_path, "analysis.json")
    prior_summary_path = _input_file(prior_path, "evaluation-summary.json")
    current_protocol_path = _optional_file(current_path, "protocol.json")
    prior_controls_path = _optional_file(prior_path, "controls.json")

    analysis = _load_json(current_analysis_path)
    prior_summary = _load_json(prior_summary_path)
    protocol = _load_json(current_protocol_path) if current_protocol_path is not None else None
    controls = _load_json(prior_controls_path) if prior_controls_path is not None else None

    current = _current_observations(analysis, protocol)
    prior = _prior_observations(prior_summary, controls)
    current_ids = current.get("case_ids")
    prior_ids = prior.get("case_ids")
    case_sets_proven_identical = isinstance(current_ids, list) and isinstance(prior_ids, list) and current_ids == prior_ids

    current_schema = analysis.get("schema") if isinstance(analysis.get("schema"), str) else None
    prior_schema = prior_summary.get("schema") if isinstance(prior_summary.get("schema"), str) else None
    rationale = [
        "The current report is a cassi.field-qwen.realistic-workcases.v1 analysis with baseline/field arms.",
        "The prior report is an enhancement-workcases evaluation-summary with primary/reasoning/memory suites and baseline/qi arms.",
        "The prior report does not provide a complete task-id set in its evaluation-summary.json, so exact matched-task identity is unproven.",
        "Different case sets, arm semantics, and report schemas must not be treated as one statistically comparable evaluation.",
    ]
    methodology_compatible = False
    if case_sets_proven_identical and current_schema == prior_schema:
        rationale = [
            "Exact ordered task IDs and report schemas are identical; high-level task deltas are permitted only for those matched IDs.",
        ]
        methodology_compatible = True
    elif case_sets_proven_identical:
        rationale.append("Task IDs appear identical, but report schemas differ; statistical comparability remains disabled.")

    sources = [_source_record("current.analysis", current_analysis_path), _source_record("prior.evaluation_summary", prior_summary_path)]
    if current_protocol_path is not None:
        sources.append(_source_record("current.protocol", current_protocol_path))
    if prior_controls_path is not None:
        sources.append(_source_record("prior.controls", prior_controls_path))
    source_files: dict[str, dict[str, str] | None] = {record["role"]: record for record in sources}
    for role in ("current.analysis", "current.protocol", "prior.evaluation_summary", "prior.controls"):
        source_files.setdefault(role, None)

    output = {
        "schema": SCHEMA,
        "status": "compared",
        "methodology_compatibility": methodology_compatible,
        "methodology": {
            "statistically_comparable": methodology_compatible,
            "case_sets_proven_identical": case_sets_proven_identical,
            "current_schema": current_schema,
            "prior_schema": prior_schema,
            "current_case_count": len(current_ids) if isinstance(current_ids, list) else None,
            "prior_case_count": len(prior_ids) if isinstance(prior_ids, list) else None,
            "current_case_ids": current_ids,
            "prior_case_ids": prior_ids,
            "rationale": rationale,
        },
        "sources": sources,
        "source_files": source_files,
        "observations": {"current": current, "prior": prior},
        "direct_numeric_deltas": {
            "within_current_campaign": _within_current_deltas(current),
            "within_prior_campaign": _within_prior_deltas(prior),
            "cross_campaign": _cross_campaign_deltas(methodology_compatible),
        },
        "qualitative_and_non_comparable_findings": {
            "cross_campaign_numeric_comparison": "withheld" if not methodology_compatible else "permitted only for proven identical task IDs",
            "prior_measured_conclusion": prior.get("conclusion"),
            "current_measured_conclusion": current.get("conclusion"),
            "persistence_restart": "Reported separately; persistence evidence is not a capability or task-pass delta.",
            "field_boundedness_saturation": "Reported separately; saturation/boundedness observations are not treated as task-set statistics.",
            "native_displacement": "Reported as measured ownership fields; zero is preserved and is not relabeled as replacement.",
            "useful_retained_memory": "Reported from explicit retained-memory evidence only; missing evidence remains null.",
        },
    }
    out_path = out_path.expanduser()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    return output


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current", type=Path, required=True, help="Current campaign directory or analysis.json")
    parser.add_argument("--prior", type=Path, required=True, help="Prior campaign directory or evaluation-summary.json")
    parser.add_argument("--out", type=Path, required=True, help="Output comparison JSON path")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        result = compare(args.current, args.prior, args.out)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(json.dumps({"schema": SCHEMA, "status": "error", "error": str(error)}, sort_keys=True), flush=True)
        return 1
    print(json.dumps({"schema": result["schema"], "status": result["status"], "out": str(args.out.resolve())}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
