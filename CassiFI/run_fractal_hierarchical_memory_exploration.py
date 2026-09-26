"""Bounded hierarchical L<-LL memory probe across the three matched arrangements.

A fine LL packet impulse is written through the production owner, the real
parent-child summary operation consolidates the live child into L, and the
field is advanced with its source disabled.  The observable is deliberately
field-only: a stored L cue's projection onto the live LL level-zero cue after
source-off, compared with matched no-consolidation and silenced controls.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping

import numpy as np

import cassi_resonant_field as field
import run_fractal_arrangement_comparison as arrangements
from cassi_field_atlas import AtlasState
from cassi_field_owner import FieldIntelligenceError, FieldIntelligenceOwner

SCHEMA = "cassifi.fractal-hierarchical-memory-exploration.v1"
DEFAULT_OUTPUT = Path("_diag/fractal-hierarchical-memory/exploration.json")
SEED = arrangements.SEED
PARENT_PATH = "L"
CHILD_PATH = "LL"
CHILD_SIGNAL = (1.0, 0.0)
CHILD_BUDGET = 1e-3
SOURCE_OFF_TICKS = 1
MARGIN = 1e-12
CONTINUITY_TOLERANCE = 1e-12
TIMING_KEYS = frozenset({"elapsed_seconds", "runtime_seconds", "content_digest", "receipt_sha256"})
ARRANGEMENT_RECEIPT = arrangements.DEFAULT_OUTPUT


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer, np.bool_)):
        return value.item()
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


def strip_timing(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): strip_timing(item) for key, item in value.items() if key not in TIMING_KEYS}
    if isinstance(value, (tuple, list)):
        return [strip_timing(item) for item in value]
    return value


def content_digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(strip_timing(value)).encode("utf-8")).hexdigest()


def _norm(left: Any, right: Any) -> float:
    return float(np.linalg.norm(np.asarray(left, dtype=np.float64) - np.asarray(right, dtype=np.float64)))


def _compact_impulse(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value[key]
        for key in (
            "schema", "accepted", "path", "component", "flow_signal", "requested_work",
            "applied_work", "impulse_amount", "source_state_sha256", "state_sha256",
        )
        if key in value
    }


def _compact_recompute(value: Mapping[str, Any]) -> dict[str, Any]:
    receipt = value["parent_child_receipt"]
    return {
        "schema": receipt["schema"],
        "parent_path": receipt["parent_path"],
        "child_path": receipt["child_path"],
        "source_state_sha256": receipt["source_state_sha256"],
        "child_packet_sha256": receipt["child_packet_sha256"],
        "relation_sha256": receipt["relation_sha256"],
        "previous_relation_sha256": receipt["previous_relation_sha256"],
        "summary_sha256": receipt["summary_sha256"],
        "successor_state_sha256": receipt["successor_state_sha256"],
        "successor_is_distinct": receipt["successor_is_distinct"],
    }


def _control(call: Any, expected_code: str) -> dict[str, Any]:
    try:
        call()
    except FieldIntelligenceError as exc:
        return {
            "attempted": True,
            "accepted": False,
            "can_fail": True,
            "error_code": exc.code,
            "expected_code": expected_code,
            "expected_code_matches": exc.code == expected_code,
        }
    except Exception as exc:  # an unexpected exception is a failed firing control
        return {
            "attempted": True,
            "accepted": False,
            "can_fail": False,
            "error_code": type(exc).__name__,
            "expected_code": expected_code,
            "expected_code_matches": False,
        }
    return {
        "attempted": True,
        "accepted": True,
        "can_fail": False,
        "error_code": None,
        "expected_code": expected_code,
        "expected_code_matches": False,
    }


def _cue_metrics(parent_values: Any, child_values: Any) -> dict[str, float]:
    parent = np.asarray(parent_values, dtype=np.float64)
    child = np.asarray(child_values, dtype=np.float64)
    parent_norm = float(np.linalg.norm(parent))
    child_norm = float(np.linalg.norm(child))
    if parent_norm <= MARGIN or child_norm <= MARGIN:
        cosine_sq = 0.0
        recovered = 0.0
        residual = child_norm
    else:
        dot = float(np.dot(parent, child))
        cosine_sq = dot * dot / (parent_norm * parent_norm * child_norm * child_norm)
        recovered = abs(dot) / parent_norm
        projection = parent * (dot / (parent_norm * parent_norm))
        residual = float(np.linalg.norm(child - projection))
    return {
        "parent_norm": parent_norm,
        "child_level_zero_norm": child_norm,
        "parent_child_cue_cosine_sq": cosine_sq,
        "parent_guided_child_recovery_l2": recovered,
        "child_residual_after_parent_guidance_l2": residual,
    }


def _initial_workspace(profile: Any) -> tuple[Any, Mapping[str, Any]]:
    origin = field.initial_workspace(profile)
    # The relation and both register slots are public canonical field state;
    # they are the prerequisite for the production L<-LL recompute operation.
    workspace, initial_write = field.write_parent_registers(
        origin, paths=(PARENT_PATH, CHILD_PATH), ancestry_pairs=((PARENT_PATH, CHILD_PATH),)
    )
    return workspace, initial_write


def _read_state(owner: FieldIntelligenceOwner, phase: str) -> dict[str, Any]:
    workspace = owner.state.resonant_workspace
    assert workspace is not None
    stored = owner.read_parent_summary()
    child = field.analyze_helical_packet(workspace, path=CHILD_PATH)
    child_level_zero = np.asarray(child["coefficients"], dtype=np.float64)[0].copy()
    values = np.asarray(stored["values"], dtype=np.float64) if stored["present"] else np.zeros(4, dtype=np.float64)
    metrics = _cue_metrics(values, child_level_zero)
    return {
        "phase": phase,
        "state_sha256": owner.state.state_sha256,
        "workspace_state_sha256": workspace.state_sha256,
        "stored_parent": {
            "present": bool(stored["present"]),
            "summary_sha256": stored.get("summary_sha256"),
            "values": values.tolist(),
            "source_state_sha256": stored.get("source_state_sha256"),
            "source_packet_sha256": stored.get("source_packet_sha256"),
        },
        "child": {
            "packet_sha256": child["packet_sha256"],
            "source_state_sha256": child["source_state_sha256"],
            "level_zero": child_level_zero.tolist(),
        },
        "metrics": metrics,
    }


def _run_arm(label: str, profile: Any, mode: str) -> dict[str, Any]:
    workspace, initial_write = _initial_workspace(profile)
    root = Path(__file__).resolve().parent / "_diag" / ".hierarchical-owner-runtime"
    # The owner is initialized from the exact public workspace; all mutations
    # below are owner transitions and therefore enter its checkpoint closure.
    import tempfile
    with tempfile.TemporaryDirectory(prefix="cassifi-hierarchical-owner-", dir=str(root.parent)) as directory:
        owner = FieldIntelligenceOwner(Path(directory), initial_state=AtlasState(resonant_workspace=workspace))
        try:
            before = _read_state(owner, "before-child-write")
            relation = field.read_parent_registers(workspace)["relations"][0]
            child_write = None
            if mode != "silenced":
                child_write = owner.write_packet_impulse(
                    f"hierarchical:{label}:child-write",
                    path=CHILD_PATH,
                    component="scale",
                    flow_signal=list(CHILD_SIGNAL),
                    work_budget=CHILD_BUDGET,
                    event_kind="reasoning-work",
                    expected_state_sha256=owner.state.state_sha256,
                )
            after_child = _read_state(owner, "after-child-write" if child_write else "after-silenced-control")
            recompute = None
            if mode == "consolidated":
                child_packet = field.analyze_helical_packet(owner.state.resonant_workspace, path=CHILD_PATH)
                recompute = owner.recompute_parent_summary_from_child(
                    f"hierarchical:{label}:parent-consolidate",
                    expected_state_sha256=owner.state.state_sha256,
                    expected_relation_sha256=relation["relation_sha256"],
                    expected_child_packet_sha256=child_packet["packet_sha256"],
                )
            after_action = _read_state(owner, "after-parent-consolidation" if recompute else "after-no-consolidation")
            source_off = owner.advance(
                f"hierarchical:{label}:source-off",
                ticks=SOURCE_OFF_TICKS,
                source_enabled=False,
                expected_state_sha256=owner.state.state_sha256,
            )
            after_off = _read_state(owner, "after-source-off")
            mutation = None
            if mode == "consolidated":
                mutation = _control(
                    lambda: owner.recompute_parent_summary_from_child(
                        f"hierarchical:{label}:mutated-child-digest",
                        expected_state_sha256=owner.state.state_sha256,
                        expected_relation_sha256=relation["relation_sha256"],
                        expected_child_packet_sha256="0" * 64,
                    ),
                    "RESONANT_NUMERICAL",
                )
            return {
                "label": label,
                "mode": mode,
                "initial_register_write": {
                    "paths": initial_write["paths"],
                    "source_state_sha256": initial_write["source_state_sha256"],
                    "successor_state_sha256": initial_write["successor_state_sha256"],
                    "relations": initial_write["relations"],
                },
                "relation_before": dict(relation),
                "child_write": None if child_write is None else _compact_impulse(child_write["impulse_receipt"]),
                "parent_consolidation": None if recompute is None else _compact_recompute(recompute),
                "source_off": {
                    "ticks": source_off["resonance_receipt"]["ticks"],
                    "source_enabled": source_off["resonance_receipt"]["source_enabled"],
                    "state_sha256": source_off["resonance_receipt"]["state_sha256"],
                },
                "reads": {"before": before, "after_child": after_child, "after_action": after_action, "after_source_off": after_off},
                "mutation_control": mutation,
                "field_only_observable": {
                    "recovery_after_source_off": after_off["metrics"]["parent_guided_child_recovery_l2"],
                    "cue_cosine_sq_after_source_off": after_off["metrics"]["parent_child_cue_cosine_sq"],
                    "parent_survival_drift_l2": _norm(after_action["stored_parent"]["values"], after_off["stored_parent"]["values"]),
                    "child_source_off_change_l2": _norm(after_action["child"]["level_zero"], after_off["child"]["level_zero"]),
                },
            }
        finally:
            owner.close()


def continuity_checks(profiles: Mapping[str, Any]) -> list[dict[str, Any]]:
    source = Path(__file__).resolve().parent / ARRANGEMENT_RECEIPT
    cited_receipt = json.loads(source.read_text(encoding="utf-8"))
    checks: list[dict[str, Any]] = []
    for label in ("current-meaningful-helix", "nested-paired-loops"):
        cited_arm = next(row for row in cited_receipt["arms"] if row["label"] == label)
        profile = profiles[label]
        for selector, cited, observed in (
            ("operators.edge_l1", float(cited_arm["operators"]["edge_l1"]), float(np.abs(np.asarray(profile.projected_transport, dtype=np.float64)).sum())),
            ("operators.inverse_mass_sum", float(cited_arm["operators"]["inverse_mass_sum"]), float(np.asarray(profile.projected_inv_mass, dtype=np.float64).sum())),
        ):
            checks.append({"source_receipt": str(ARRANGEMENT_RECEIPT).replace("\\", "/"), "arm": label, "selector": selector, "cited": cited, "observed": observed, "tolerance": CONTINUITY_TOLERANCE, "within_tolerance": bool(abs(cited - observed) <= CONTINUITY_TOLERANCE)})
    return checks


def _comparison(consolidated: Mapping[str, Any], no_consolidation: Mapping[str, Any], silenced: Mapping[str, Any]) -> dict[str, Any]:
    c = consolidated["field_only_observable"]
    n = no_consolidation["field_only_observable"]
    s = silenced["field_only_observable"]
    recovery_difference = float(c["recovery_after_source_off"] - n["recovery_after_source_off"])
    parent_difference = _norm(consolidated["reads"]["after_source_off"]["stored_parent"]["values"], no_consolidation["reads"]["after_source_off"]["stored_parent"]["values"])
    silenced_recovery = float(s["recovery_after_source_off"])
    rows = [
        {"id": "consolidation_changes_parent_cue", "quantity": parent_difference, "margin": MARGIN, "holds": parent_difference > MARGIN},
        {"id": "parent_guided_recovery_separates_no_consolidation", "quantity": recovery_difference, "margin": MARGIN, "holds": abs(recovery_difference) > MARGIN},
        {"id": "silenced_recovery_is_zero", "quantity": silenced_recovery, "margin": MARGIN, "holds": silenced_recovery <= MARGIN},
        {"id": "consolidated_parent_survives_source_off", "quantity": float(c["parent_survival_drift_l2"]), "margin": MARGIN, "holds": c["parent_survival_drift_l2"] <= MARGIN},
    ]
    for row in rows:
        # Positive predicates fail when the measured quantity is mutated to
        # zero; upper-bound predicates fail when it is mutated above margin.
        mutated_quantity = 0.0 if float(row["quantity"]) > MARGIN else 1.0
        if row["id"] == "silenced_recovery_is_zero":
            holds_after = mutated_quantity <= float(row["margin"])
        elif row["id"] == "consolidated_parent_survives_source_off":
            holds_after = mutated_quantity <= float(row["margin"])
        else:
            holds_after = abs(mutated_quantity) > float(row["margin"])
        row["firing_control"] = {
            "attempted": True,
            "mutation": "replace measured quantity with a predicate-breaking value",
            "mutated_quantity": mutated_quantity,
            "holds_after_mutation": bool(holds_after),
            "can_fail": bool(not holds_after),
        }
    return {"rows": rows, "recovery_difference": recovery_difference, "parent_difference": parent_difference}


def build_receipt() -> dict[str, Any]:
    started = perf_counter()
    profiles, budgets = arrangements.matched_profiles()
    arms: dict[str, dict[str, Any]] = {}
    comparisons: list[dict[str, Any]] = []
    for label, _name in arrangements.ARRANGEMENTS:
        consolidated = _run_arm(label, profiles[label], "consolidated")
        no_consolidation = _run_arm(label, profiles[label], "no-consolidation")
        silenced = _run_arm(label, profiles[label], "silenced")
        comparison = _comparison(consolidated, no_consolidation, silenced)
        arms[label] = {"consolidated": consolidated, "no_consolidation": no_consolidation, "silenced": silenced, "comparison": comparison}
        comparisons.extend({"arrangement": label, **row} for row in comparison["rows"])
    continuity = continuity_checks(profiles)
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "declared": {
            "question": "After a real LL write and owner L<-LL consolidation, does a stored parent cue remain distinguishable from matched no-consolidation and silenced controls after source-off?",
            "seed": SEED,
            "arithmetic": "numpy-cpu-float64",
            "arrangements": [{"label": label, "builder_name": name} for label, name in arrangements.ARRANGEMENTS],
            "parent_path": PARENT_PATH,
            "child_path": CHILD_PATH,
            "child_signal": list(CHILD_SIGNAL),
            "child_budget": CHILD_BUDGET,
            "source_off_ticks": SOURCE_OFF_TICKS,
            "matched_budgets": budgets,
            "observable": "field-only parent-guided recovery proxy: projection of stored L values onto the live LL level-zero coefficient vector after source-off; no semantic reconstruction API is used",
            "margins": {"comparison": MARGIN, "continuity": CONTINUITY_TOLERANCE},
        },
        "arms": arms,
        "comparisons": comparisons,
        "continuity_checks": continuity,
        "controls": {
            "no_consolidation": "same relation/register bootstrap and owner LL write, with the explicit L<-LL operation omitted",
            "silenced": "same relation/register bootstrap, no LL write and source-off advance",
            "mutation": "consolidated arm retries the public recompute with a mutated child packet digest; expected rejection is recorded",
            "all_firing": bool(all(arm["consolidated"]["mutation_control"]["can_fail"] for arm in arms.values()) and all(row["firing_control"]["can_fail"] for row in comparisons)),
        },
        "limitations": [
            "The public APIs expose canonical numerical packet coefficients, not semantic reconstruction or a consumer retrieval task.",
            "Parent-guided recovery is therefore a direct field cue projection and child-vs-parent distinguishability observable, not semantic memory, hierarchy, or utility.",
            "The arrangement comparison is causal only for the three matched active profiles built by the existing public arrangement builder; it does not isolate geometry from every operator spectral difference.",
        ],
        "verdict": "PASS_FIELD_ONLY_HIERARCHICAL_MEMORY_PROBE" if all(row["holds"] for row in comparisons) and all(item["within_tolerance"] for item in continuity) else "FAIL_FIELD_ONLY_HIERARCHICAL_MEMORY_PROBE",
        "elapsed_seconds": float(perf_counter() - started),
    }
    body["content_digest"] = content_digest(body)
    body["receipt_sha256"] = body["content_digest"]
    body["runtime_seconds"] = body["elapsed_seconds"]
    return body


def verify_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    digest = content_digest(receipt)
    return {"content_digest_matches": digest == receipt.get("content_digest"), "digest": digest}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    receipt = build_receipt()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(_jsonable(receipt), sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "content_digest": receipt["content_digest"], "verdict": receipt["verdict"], "runtime_seconds": receipt["runtime_seconds"]}, sort_keys=True))
    return 0 if receipt["verdict"].startswith("PASS_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
