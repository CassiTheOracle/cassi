#!/usr/bin/env python3
"""Independently verify the universal interpreter full-program receipt.

The verifier intentionally does not import the runner or interpreter.  It
checks the immutable source manifest, twelve lifecycle obligations, durable
field generations, branch separation, interruption journals, native-task
identity (when supplied), and the receipt's own digest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

PROGRAM_SCHEMA = "cassi.universal-interpreter-full-program.v1"
PROGRAM_ID = "universal-interpreter-full-workshop-20260917"
TASK_ID = "universal-interpreter-workshop"
TASK_QUESTION = "Determine the corrected workshop load and emit its correction."


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _same(value: Any, expected: Any, label: str, errors: list[str]) -> None:
    if value != expected:
        errors.append(f"{label}: expected {expected!r}, got {value!r}")


def _truth(value: Any, label: str, errors: list[str]) -> None:
    if value is not True:
        errors.append(f"{label}: expected true, got {value!r}")




def _verify_generation(store_root: Path, label: str, errors: list[str]) -> dict[str, Any] | None:
    current = store_root / "CURRENT"
    generations = store_root / "generations"
    if not current.is_file() or not generations.is_dir():
        errors.append(f"{label}: missing CURRENT or generations")
        return None
    pointer = current.read_text(encoding="ascii").strip()
    if not pointer.startswith("gen-") or not (generations / pointer).is_dir():
        errors.append(f"{label}: invalid CURRENT pointer {pointer!r}")
        return None
    directory = generations / pointer
    manifest_path = directory / "manifest.json"
    checkpoint_path = directory / "field.chk"
    journal_path = directory / "journal.jsonl"
    if not all(path.is_file() for path in (manifest_path, checkpoint_path, journal_path)):
        errors.append(f"{label}: current generation is incomplete")
        return None
    try:
        manifest = _load_json(manifest_path)
    except Exception as error:
        errors.append(f"{label}: invalid manifest: {error}")
        return None
    if not isinstance(manifest, Mapping):
        errors.append(f"{label}: manifest is not an object")
        return None
    _same(manifest.get("schema"), "cassi.raw-event-store-generation.v1", f"{label}.manifest.schema", errors)
    _same(manifest.get("checkpoint_sha256"), _sha_bytes(checkpoint_path.read_bytes()), f"{label}.checkpoint_digest", errors)
    journal = journal_path.read_bytes()
    _same(manifest.get("journal_sha256"), _sha_bytes(journal), f"{label}.journal_digest", errors)
    _same(manifest.get("journal_bytes"), len(journal), f"{label}.journal_bytes", errors)
    rows = []
    for line_number, line in enumerate(journal.splitlines(), start=1):
        try:
            row = json.loads(line.decode("utf-8"))
        except Exception as error:
            errors.append(f"{label}.journal[{line_number}]: invalid JSON: {error}")
            continue
        if not isinstance(row, Mapping):
            errors.append(f"{label}.journal[{line_number}]: not an object")
            continue
        rows.append(row)
        if set(row) != {"event", "learn", "promote", "revoked"}:
            errors.append(f"{label}.journal[{line_number}]: schema keys differ")
    _same(manifest.get("event_count"), len(rows), f"{label}.event_count", errors)
    _same(manifest.get("active_event_count"), sum(not bool(row.get("revoked")) for row in rows), f"{label}.active_event_count", errors)
    return dict(manifest)


def _find_state(store_root: Path, state_sha256: str, errors: list[str]) -> bool:
    generations = store_root / "generations"
    if not generations.is_dir():
        return False
    found = False
    for directory in sorted(generations.glob("gen-*")):
        manifest_path = directory / "manifest.json"
        if not manifest_path.is_file():
            continue
        try:
            manifest = _load_json(manifest_path)
        except Exception:
            continue
        if isinstance(manifest, Mapping) and manifest.get("state_sha256") == state_sha256:
            found = True
            break
    if not found:
        errors.append(f"{store_root}: no immutable generation carries state {state_sha256}")
    return found


def verify(root: Path, receipt_path: Path | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    receipt_path = (receipt_path or (root / "full-program-receipt.json")).resolve()
    errors: list[str] = []
    if not root.is_dir():
        return {"schema": "cassi.full-program-verification.v1", "status": "FAIL", "errors": [f"missing root: {root}"]}
    if not receipt_path.is_file():
        return {"schema": "cassi.full-program-verification.v1", "status": "FAIL", "errors": [f"missing receipt: {receipt_path}"]}
    try:
        receipt = _load_json(receipt_path)
    except Exception as error:
        return {"schema": "cassi.full-program-verification.v1", "status": "FAIL", "errors": [f"invalid receipt: {error}"]}
    if not isinstance(receipt, Mapping):
        return {"schema": "cassi.full-program-verification.v1", "status": "FAIL", "errors": ["receipt is not an object"]}

    _same(receipt.get("schema"), PROGRAM_SCHEMA, "receipt.schema", errors)
    _same(receipt.get("program_id"), PROGRAM_ID, "receipt.program_id", errors)
    _same(receipt.get("status"), "PASS", "receipt.status", errors)
    declared_digest = receipt.get("content_sha256")
    _same(declared_digest, _sha({key: value for key, value in receipt.items() if key != "content_sha256"}), "receipt.content_sha256", errors)

    task = receipt.get("task")
    lifecycle = receipt.get("structured_lifecycle")
    checks = receipt.get("checks")
    if not isinstance(task, Mapping):
        errors.append("task: missing object")
        task = {}
    if not isinstance(lifecycle, Mapping):
        errors.append("structured_lifecycle: missing object")
        lifecycle = {}
    if not isinstance(checks, Mapping):
        errors.append("checks: missing object")
        checks = {}
    _same(task.get("task_id"), TASK_ID, "task.task_id", errors)
    _same(task.get("question"), TASK_QUESTION, "task.question", errors)
    _same(task.get("source_revision_id"), lifecycle.get("source_revisions", {}).get("initial") if isinstance(lifecycle.get("source_revisions"), Mapping) else None, "task.source_revision_id", errors)

    source_path = root / "source-manifest.json"
    if not source_path.is_file():
        errors.append("source-manifest.json: missing")
        source = {}
    else:
        try:
            source = _load_json(source_path)
        except Exception as error:
            source = {}
            errors.append(f"source-manifest.json: invalid JSON: {error}")
    if not isinstance(source, Mapping):
        errors.append("source-manifest.json: not an object")
        source = {}
    _same(source.get("schema"), "cassi.full-program-source-manifest.v1", "source.schema", errors)
    _same(source.get("program_id"), PROGRAM_ID, "source.program_id", errors)
    source_revisions = source.get("source_revisions")
    if not isinstance(source_revisions, Mapping):
        errors.append("source.source_revisions: missing object")
        source_revisions = {}
    source_observations = source.get("observations")
    expected_initial = _sha({"schema": "cassi.full-program-source.v1", "source_id": "workshop-observations-v1", "observations": source_observations})
    expected_correction = _sha({"schema": "cassi.full-program-source.v1", "source_id": "workshop-correction-v2", "observations": {"participant": "beta", "base": 7.0, "delay": 2.0, "outcome": 11.0}})
    expected_development = _sha({"schema": "cassi.full-program-source.v1", "source_id": "workshop-regime-study-v1", "observations": {"participant": "delta", "base": 5.0, "delay": 4.0, "outcome": 12.0}})
    thermal_gap = source_observations.get("thermal_gap") if isinstance(source_observations, Mapping) else None
    thermal_observation = (
        {
            "participant": thermal_gap.get("participant"),
            "base": thermal_gap.get("base"),
            "delay": thermal_gap.get("delay"),
            "outcome": thermal_gap.get("outcome"),
        }
        if isinstance(thermal_gap, Mapping)
        else None
    )
    expected_thermal = _sha({"schema": "cassi.full-program-source.v1", "source_id": "thermal-observations-v1", "observations": thermal_observation})
    for key, expected in (("initial", expected_initial), ("correction", expected_correction), ("development", expected_development), ("thermal", expected_thermal)):
        _same(source_revisions.get(key), expected, f"source.source_revisions.{key}", errors)
    lifecycle_revisions = lifecycle.get("source_revisions")
    if isinstance(lifecycle_revisions, Mapping):
        for key in ("initial", "correction", "development", "thermal"):
            _same(lifecycle_revisions.get(key), source_revisions.get(key), f"lifecycle.source_revisions.{key}", errors)

    steps = {key: lifecycle.get(key) for key in lifecycle if str(key).startswith("step_")}
    expected_steps = {
        "step_01_acquisition", "step_02_new_participant", "step_03_language_composition",
        "step_04_05_field_compute_and_emit", "step_06_correction_and_repair", "step_07_pause_reopen",
        "step_08_model_replacement", "step_09_selective_relation_loss", "step_10_field_owned_emission",
        "step_11_gap_and_development", "step_12_method_transfer",
    }
    if set(steps) != expected_steps:
        errors.append(f"lifecycle steps: expected {sorted(expected_steps)}, got {sorted(steps)}")
    for key in expected_steps:
        if not isinstance(steps.get(key), Mapping):
            errors.append(f"{key}: missing object")

    s1 = steps.get("step_01_acquisition", {})
    s2 = steps.get("step_02_new_participant", {})
    s3 = steps.get("step_03_language_composition", {})
    s45 = steps.get("step_04_05_field_compute_and_emit", {})
    s6 = steps.get("step_06_correction_and_repair", {})
    s7 = steps.get("step_07_pause_reopen", {})
    s8 = steps.get("step_08_model_replacement", {})
    s9 = steps.get("step_09_selective_relation_loss", {})
    s10 = steps.get("step_10_field_owned_emission", {})
    s11 = steps.get("step_11_gap_and_development", {})
    s12 = steps.get("step_12_method_transfer", {})

    predictions = s1.get("predictions_before_outcomes", []) if isinstance(s1, Mapping) else []
    acquisition_ok = isinstance(predictions, list) and len(predictions) == 2 and all(isinstance(row, Mapping) and row.get("made_before_outcome") is True for row in predictions)
    new_participant_ok = s2.get("participant") == "beta" and s2.get("calculated_value") == s2.get("held_out_truth") == 13.0
    composition_ok = s3.get("parser_owner") == "fixed-language-boundary" and s3.get("field_owner") == "acquired-relation-readout" and s3.get("model_calls") == 0
    calculation_ok = isinstance(s45.get("calculation"), Mapping) and s45["calculation"].get("executor") == "cassi-field-arithmetic-v1" and s45["calculation"].get("model_calls") == 0
    emission_before = s45.get("emission_before_correction", {})
    emission_ok = isinstance(emission_before, Mapping) and emission_before.get("owner") == "field" and emission_before.get("native_fallback") is False
    explanation = s6.get("repaired_explanation", {})
    correction_ok = s6.get("repaired_prediction") == 11.0 and isinstance(s6.get("repaired_plan"), Mapping) and s6["repaired_plan"].get("target_load") == 11.0 and isinstance(explanation, Mapping) and explanation.get("dependent_plan_repaired") is True and explanation.get("unrelated_safety_preserved") is True
    pending = s7.get("pending_before_close", {})
    resumed_query = s7.get("resumed_query", {})
    pause_ok = isinstance(pending, Mapping) and pending.get("status") == "pending" and s7.get("accepted_learning_replayed") is False and s7.get("external_effect_count") == 1 and isinstance(resumed_query, Mapping) and resumed_query.get("status") == "field-owned"
    replacement_ok = s8.get("old_model_fingerprint") != s8.get("new_model_fingerprint") and s8.get("same_adapter_coordinate") is True and s8.get("value") == s8.get("held_out_truth") == 12.0
    loss_ok = s9.get("selective_loss") is True and s9.get("relation_status") != "field-owned" and s9.get("safety_status") == "field-owned"
    emission10 = s10.get("emission", {})
    emission10_ok = isinstance(emission10, Mapping) and emission10.get("owner") == "field" and s10.get("held_out_correct") == 1 and emission10.get("native_fallback") is False
    gap = s11.get("gap", {})
    development_ok = isinstance(gap, Mapping) and float(gap.get("error", 0.0)) > 0.0 and s11.get("guarded_calculation") == 12.0 and s11.get("prior_beta_value_preserved") == 11.0 and s11.get("development_cost", {}).get("model_calls") == 0
    fixed = s12.get("fixed_arm", {})
    acquired = s12.get("acquired_arm", {})
    comparison = s12.get("comparison", {})
    transfer_ok = isinstance(fixed, Mapping) and isinstance(acquired, Mapping) and isinstance(comparison, Mapping) and fixed.get("value") == 17.0 and fixed.get("truth") == 9.0 and fixed.get("error") == 8.0 and acquired.get("before_method_value") == 17.0 and acquired.get("after_method_value") == 9.0 and acquired.get("status") == "correct" and acquired.get("prior_beta_value") == 11.0 and acquired.get("unfinished_work_preserved") is True and comparison.get("same_initial_field_sha256") is True and comparison.get("same_source_revision_id") is True and comparison.get("same_allocation") is True and comparison.get("same_permissions") is True and comparison.get("acquired_method_improves_unfamiliar_family") is True
    ownership = receipt.get("ownership", {})
    one_field_ok = isinstance(ownership, Mapping) and ownership.get("field_adaptive_object") == "QiFieldState.field" and ownership.get("model_calls_in_structured_episode") == 0 and ownership.get("native_fallback") is False
    native = receipt.get("native_shared_task", {})
    native_ok = (
        native.get("shared_task_verified") is True
        and native.get("answer_bearing_activation_supplied") is False
        if native.get("status") == "verified-shared-task"
        else native.get("status") == "unavailable"
    )

    recomputed_checks = {
        "step_01_acquires_relation_with_prior_predictions": acquisition_ok,
        "step_02_new_participant_uses_relation": new_participant_ok,
        "step_03_language_composes_with_retained_meaning": composition_ok,
        "step_04_field_owns_formal_calculation": calculation_ok,
        "step_05_declared_field_emission": emission_ok,
        "step_06_correction_repairs_dependents_locally": correction_ok,
        "step_07_reopen_is_exact_and_once": pause_ok,
        "step_08_replacement_model_transfers": replacement_ok,
        "step_09_relation_removal_is_selective": loss_ok,
        "step_10_field_emission_has_heldout_adequacy": emission10_ok,
        "step_11_development_repairs_gap_preserves_prior": development_ok,
        "step_12_method_reuses_across_family_after_restart": transfer_ok,
        "one_adaptive_field": one_field_ok,
        "native_shared_task_if_supplied": native_ok,
    }
    for key, value in recomputed_checks.items():
        _truth(value, f"recomputed.{key}", errors)
        _truth(checks.get(key), f"receipt.checks.{key}", errors)

    # Verify every persistent field branch, not just the values copied into the
    # receipt.  This catches a receipt fabricated after deleting the branch.
    manifests: dict[str, dict[str, Any]] = {}
    for label in ("field-main", "common-after-transfer", "relation-removed-branch", "method-compare-base", "fixed-method-arm", "acquired-method-arm"):
        manifest = _verify_generation(root / label / "field", label, errors)
        if manifest is not None:
            manifests[label] = manifest
    for path in (root / "unfinished-work.json", root / "unfinished-thermal-work.json"):
        if not path.is_file():
            errors.append(f"missing interruption journal: {path.name}")
    if (root / "unfinished-work.json").is_file():
        work = _load_json(root / "unfinished-work.json")
        if not isinstance(work, Mapping) or work.get("status") != "completed" or len(work.get("effects", [])) != 1:
            errors.append("unfinished-work.json: completion/effect contract failed")
    if (root / "unfinished-thermal-work.json").is_file():
        thermal_work = _load_json(root / "unfinished-thermal-work.json")
        if not isinstance(thermal_work, Mapping) or thermal_work.get("status") != "completed" or thermal_work.get("effect_ids") != ["thermal:delta:guarded-load"]:
            errors.append("unfinished-thermal-work.json: completion/effect contract failed")
    lineage = lifecycle.get("state_lineage", {})
    if isinstance(lineage, Mapping):
        for key in ("initial", "paused_before_reopen", "reopened", "thermal_common_predecessor"):
            value = lineage.get(key)
            if not isinstance(value, str) or len(value) != 64:
                errors.append(f"state_lineage.{key}: invalid digest")
        if isinstance(lineage.get("paused_before_reopen"), str):
            _find_state(root / "field-main" / "field", lineage["paused_before_reopen"], errors)
        if isinstance(lineage.get("thermal_common_predecessor"), str):
            _find_state(root / "method-compare-base" / "field", lineage["thermal_common_predecessor"], errors)
    for label, state in (("fixed-method-arm", fixed.get("initial_field_sha256")), ("acquired-method-arm", acquired.get("initial_field_sha256"))):
        if isinstance(state, str):
            _find_state(root / label / "field", state, errors)
        else:
            errors.append(f"{label}: missing initial field digest")

    native_path = native.get("path") if isinstance(native, Mapping) else None
    if isinstance(native_path, str) and native.get("status") == "verified-shared-task":
        path = Path(native_path)
        if not path.is_file():
            errors.append("native shared-task receipt disappeared")
        else:
            native_bytes = path.read_bytes()
            _same(native.get("file_sha256"), _sha_bytes(native_bytes), "native.file_sha256", errors)
            try:
                native_value = json.loads(native_bytes.decode("utf-8"))
            except Exception as error:
                errors.append(f"native receipt invalid: {error}")
            else:
                if isinstance(native_value, Mapping):
                    _same(native_value.get("task_id"), TASK_ID, "native.task_id", errors)
                    _same(native_value.get("question"), TASK_QUESTION, "native.question", errors)
                    _same(native_value.get("source_revision_id"), task.get("source_revision_id"), "native.source_revision_id", errors)
                    _same(native_value.get("answer_bearing_activation_supplied"), False, "native.answer_bearing_activation_supplied", errors)

    result = {
        "schema": "cassi.full-program-verification.v1",
        "status": "PASS" if not errors else "FAIL",
        "root": str(root),
        "receipt": str(receipt_path),
        "checks": recomputed_checks,
        "verified_generations": sorted(manifests),
        "errors": errors,
    }
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = verify(args.root, args.receipt)
    payload = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
