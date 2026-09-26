"""Probe whether a coarse L summary survives a changed LL detail.

This is a field-level causal probe.  The production packet API exposes only
recomputed, disposable views of one immutable live workspace; it does not
retain a parent summary as writable or readable state.  The runner therefore
measures the supported LL intervention and records the frozen-parent question
as OUT_OF_SCOPE/NOT_APPLICABLE rather than treating a Python snapshot as
persistent memory.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping, Sequence

import numpy as np

import cassi_resonant_field as field
import run_fractal_geometry_exploration as geometry
import run_fractal_localized_projection_exploration as localized
import run_fractal_memory_exploration as memory

SCHEMA = "cassifi.fractal-parent-summary-causality-exploration.v1"
DEFAULT_OUTPUT = Path("_diag/fractal-parent-summary-causality/exploration.json")
LOCALIZED_RECEIPT = Path("_diag/fractal-localized-projection/exploration.json")
SEED = 20260917
PARENT_PATH = "L"
FINE_PATH = "LL"
FIRST_SIGNAL = (1.0, 0.0)
CHANGE_SIGNAL = (0.0, 1.0)
FIRST_BUDGET = 1e-3
CHANGE_BUDGET = 5e-4
SOURCE_OFF_TICKS = 1
FINE_CHANGE_MARGIN = 1e-12
NOOP_IDENTITY_MARGIN = 1e-12
SOURCE_OFF_MARGIN = 1.0
CONTINUITY_TOLERANCE = 1e-12
TIMING_KEYS = frozenset({"elapsed_seconds", "runtime_seconds", "content_digest", "receipt_sha256"})

BOUNDARY = (
    "Canonical-field numerical measurements only. The L parent value is a "
    "level-zero projection recomputed from the live page; it is not retained "
    "parent state. No semantic memory, recall, consumer retrieval, or "
    "persistent-parent claim is made."
)
LIMITATIONS = [
    "analyze_helical_packet returns a disposable view tied to the current source_state_sha256.",
    "No public freeze_parent, read_parent_snapshot, summary writeback, or scale-indexed cross-scale API exists.",
    "expand_resolution and reduce_resolution are whole-page layout transitions, not localized parent/child operations.",
    "The saved pre-change parent packet is held transiently only to test the real mixed-source composition refusal; it is not persistent state.",
    "Live parent recompute drift is descriptive and cannot establish recoverability or persistence of a previously obtained summary.",
    "All observables are field-level numerical quantities, not semantic memory or task utility.",
]


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (np.integer, np.floating, np.bool_)):
        return value.item()
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


def _strip_timing(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _strip_timing(item)
            for key, item in value.items()
            if key not in TIMING_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_strip_timing(item) for item in value]
    return value


def content_digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(_strip_timing(value)).encode("utf-8")).hexdigest()


def page_sha256(workspace: Any) -> str:
    return hashlib.sha256(workspace.page_bytes).hexdigest()


def _profile() -> field.ResonantProfile:
    return geometry.build_profile(
        geometry.arrangement_named("helix7", seed=SEED),
        ports_per_pool=localized.PORTS_PER_POOL,
    )


def _impulse_record(impulse: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: impulse[key]
        for key in (
            "schema", "accepted", "event_kind", "basis_sha256", "path", "component",
            "support", "mode", "flow_signal", "requested_work", "applied_work",
            "impulse_amount", "balance_defect", "energy_roundoff_allowance",
            "source_state_sha256", "state_sha256",
        )
    }


def _apply_impulse(
    workspace: Any,
    *,
    signal: Sequence[float],
    budget: float,
) -> tuple[Any, dict[str, Any]]:
    return field.apply_helical_packet_impulse(
        workspace,
        path=FINE_PATH,
        component="scale",
        flow_signal=list(signal),
        work_budget=budget,
        evidence_tick=workspace.evidence_tick,
        event_kind=memory.EVENT_KIND,
    )


def _read(workspace: Any, phase: str) -> tuple[dict[str, Any], Mapping[str, Any], Mapping[str, Any]]:
    parent = field.analyze_helical_packet(workspace, path=PARENT_PATH)
    fine = field.analyze_helical_packet(workspace, path=FINE_PATH)
    parent_level_zero = np.asarray(parent["coefficients"], dtype=np.float64)[0].copy()
    fine_coefficients = np.asarray(fine["coefficients"], dtype=np.float64).reshape(-1).copy()
    row = {
        "phase": phase,
        "field_ticks": int(workspace.field_ticks),
        "evidence_tick": int(workspace.evidence_tick),
        "state_sha256": workspace.state_sha256,
        "page_sha256": page_sha256(workspace),
        "parent_path": PARENT_PATH,
        "fine_path": FINE_PATH,
        "parent_source_state_sha256": str(parent["source_state_sha256"]),
        "fine_source_state_sha256": str(fine["source_state_sha256"]),
        "parent_packet_sha256": str(parent["packet_sha256"]),
        "fine_packet_sha256": str(fine["packet_sha256"]),
        "parent_level_zero_projection": parent_level_zero.tolist(),
        "fine_coefficients": fine_coefficients.tolist(),
        "parent_summary_norm": float(np.linalg.norm(parent_level_zero)),
        "fine_norm": float(np.linalg.norm(fine_coefficients)),
        "finite": bool(np.isfinite(parent_level_zero).all() and np.isfinite(fine_coefficients).all()),
    }
    return row, parent, fine


def _run_arm(
    profile: field.ResonantProfile,
    origin: Any,
    name: str,
    second_action: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    workspace = origin
    first_impulse = None
    if name != "no-write-source-off":
        workspace, first_impulse = _apply_impulse(
            workspace, signal=FIRST_SIGNAL, budget=FIRST_BUDGET
        )
    pre_change, parent_before, fine_before = _read(workspace, "post-first-write")
    workspace, advance = field.advance_workspace(
        workspace, ticks=SOURCE_OFF_TICKS, demand=0.0, source_enabled=False
    )
    before_second, parent_before_second, fine_before_second = _read(workspace, "pre-second-action")
    second_impulse = None
    if second_action == "change":
        workspace, second_impulse = _apply_impulse(
            workspace, signal=CHANGE_SIGNAL, budget=CHANGE_BUDGET
        )
    elif second_action == "noop":
        workspace, second_impulse = _apply_impulse(
            workspace, signal=(0.0, 0.0), budget=0.0
        )
    post_change, parent_after, fine_after = _read(workspace, "post-second-action")
    public = {
        "arm": name,
        "write_path": None if first_impulse is None else FINE_PATH,
        "second_action": second_action,
        "component": "scale" if first_impulse is not None else None,
        "source_enabled": False,
        "demand": 0.0,
        "first_impulse": None if first_impulse is None else _impulse_record(first_impulse),
        "second_impulse": None if second_impulse is None else _impulse_record(second_impulse),
        "source_off_advance": {
            "ticks": int(advance["ticks"]),
            "field_ticks": int(advance["field_ticks"]),
            "source_enabled": bool(advance["source_enabled"]),
            "positive_heartbeat_work": float(advance["positive_heartbeat_work"]),
            "dissipated_work": float(advance["dissipated_work"]),
            "balance_defect": float(advance["balance_defect"]),
            "state_sha256": str(advance["state_sha256"]),
        },
        "reads": {
            "post_first_write": pre_change,
            "pre_second_action": before_second,
            "post_second_action": post_change,
        },
        "initial_state_sha256": origin.state_sha256,
        "initial_page_sha256": page_sha256(origin),
        "final_state_sha256": workspace.state_sha256,
        "final_page_sha256": page_sha256(workspace),
    }
    internal = {
        "parent_before": parent_before,
        "fine_before": fine_before,
        "parent_before_second": parent_before_second,
        "fine_before_second": fine_before_second,
        "parent_after": parent_after,
        "fine_after": fine_after,
    }
    return public, internal


def _norm_difference(left: Mapping[str, Any], right: Mapping[str, Any], key: str) -> float:
    return float(
        np.linalg.norm(
            np.asarray(left[key], dtype=np.float64)
            - np.asarray(right[key], dtype=np.float64)
        )
    )


def _comparison(
    identifier: str,
    quantity: float,
    quantity_name: str,
    predicate: str,
    margin: float,
    holds: bool,
    mutation: str,
    mutated_quantity: float,
    holds_after: bool,
) -> dict[str, Any]:
    return {
        "id": identifier,
        "quantity": float(quantity),
        "quantity_name": quantity_name,
        "predicate": predicate,
        "margin": float(margin),
        "holds": bool(holds),
        "firing_control": {
            "attempted": True,
            "mutation": mutation,
            "mutated_quantity": float(mutated_quantity),
            "holds_after": bool(holds_after),
            "can_fail": bool(not holds_after),
        },
    }


def _mixed_source_reuse(
    old_parent: Mapping[str, Any],
    new_fine: Mapping[str, Any],
) -> dict[str, Any]:
    old_left, old_right = field.split_helical_packet(old_parent)
    try:
        field.compose_helical_packets(new_fine, old_right)
    except Exception as exc:  # the public API raises ResonantNumericalError here
        return {
            "attempted": True,
            "accepted": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "old_parent_source_state_sha256": str(old_parent["source_state_sha256"]),
            "old_right_source_state_sha256": str(old_right["source_state_sha256"]),
            "new_fine_source_state_sha256": str(new_fine["source_state_sha256"]),
            "same_source_state": bool(
                old_right["source_state_sha256"] == new_fine["source_state_sha256"]
            ),
        }
    return {
        "attempted": True,
        "accepted": True,
        "error_type": None,
        "error": None,
        "old_parent_source_state_sha256": str(old_parent["source_state_sha256"]),
        "old_right_source_state_sha256": str(old_right["source_state_sha256"]),
        "new_fine_source_state_sha256": str(new_fine["source_state_sha256"]),
        "same_source_state": bool(
            old_right["source_state_sha256"] == new_fine["source_state_sha256"]
        ),
    }


def _api_probe() -> dict[str, Any]:
    supported = {
        "initial_workspace": callable(getattr(field, "initial_workspace", None)),
        "apply_helical_packet_impulse": callable(getattr(field, "apply_helical_packet_impulse", None)),
        "advance_workspace": callable(getattr(field, "advance_workspace", None)),
        "analyze_helical_packet": callable(getattr(field, "analyze_helical_packet", None)),
        "split_helical_packet": callable(getattr(field, "split_helical_packet", None)),
        "compose_helical_packets": callable(getattr(field, "compose_helical_packets", None)),
    }
    frozen_names = (
        "freeze_parent", "read_parent_snapshot", "apply_parent_summary",
        "write_parent_summary", "compose_with_frozen_parent",
    )
    frozen = {name: callable(getattr(field, name, None)) for name in frozen_names}
    return {
        "supported_live_apis": supported,
        "frozen_parent_api_symbols": frozen,
        "live_path_available": bool(all(supported.values())),
        "coarse_only_frozen_parent": {
            "available": bool(any(frozen.values())),
            "attempted": False,
            "verdict": "NOT_APPLICABLE" if any(frozen.values()) else "OUT_OF_SCOPE",
            "reason": (
                "a public frozen-parent API is present; implementation must inspect it before measuring"
                if any(frozen.values())
                else "no public operation can retain/read a parent summary independently of the live page"
            ),
        },
    }


def continuity_checks() -> list[dict[str, Any]]:
    root = Path(__file__).resolve().parent
    with (root / LOCALIZED_RECEIPT).open("r", encoding="utf-8") as stream:
        prior = json.load(stream)
    profile = _profile()
    no_write = localized._write_arm(profile, "no-write", None)
    fine = localized._write_arm(profile, "fine-LL", FINE_PATH)
    sibling = localized._write_arm(profile, "fine-LR", "LR")
    measured_child = float(
        np.linalg.norm(
            np.asarray(fine["views"]["fine_child"]["coefficients"], dtype=np.float64)
            - np.asarray(no_write["views"]["fine_child"]["coefficients"], dtype=np.float64)
        )
    )
    measured_parent = float(
        np.linalg.norm(
            np.asarray(fine["views"]["parent_level_zero_projection"], dtype=np.float64)
            - np.asarray(sibling["views"]["parent_level_zero_projection"], dtype=np.float64)
        )
    )
    checks = [
        (
            "comparisons[id=fine_child_reaches].quantity",
            measured_child,
            float(next(row["quantity"] for row in prior["comparisons"] if row["id"] == "fine_child_reaches")),
        ),
        (
            "comparisons[id=coarse_projection_separates_LL_from_LR].quantity",
            measured_parent,
            float(next(row["quantity"] for row in prior["comparisons"] if row["id"] == "coarse_projection_separates_LL_from_LR")),
        ),
    ]
    return [
        {
            "source": str(LOCALIZED_RECEIPT),
            "selector": selector,
            "expected": expected,
            "measured": measured,
            "difference": measured - expected,
            "tolerance": CONTINUITY_TOLERANCE,
            "within_tolerance": abs(measured - expected) <= CONTINUITY_TOLERANCE,
        }
        for selector, measured, expected in checks
    ]


def build_receipt() -> dict[str, Any]:
    started = perf_counter()
    profile = _profile()
    origin = field.initial_workspace(profile)
    arms: dict[str, dict[str, Any]] = {}
    internals: dict[str, dict[str, Any]] = {}
    for name, action in (
        ("no-write-source-off", None),
        ("LL-read-then-LL-change", "change"),
        ("LL-read-then-LL-noop", "noop"),
    ):
        arms[name], internals[name] = _run_arm(profile, origin, name, action)

    main = arms["LL-read-then-LL-change"]
    noop = arms["LL-read-then-LL-noop"]
    main_pre = main["reads"]["pre_second_action"]
    main_post = main["reads"]["post_second_action"]
    noop_pre = noop["reads"]["pre_second_action"]
    noop_post = noop["reads"]["post_second_action"]
    fine_intervention_effect = _norm_difference(main_post, noop_post, "fine_coefficients")
    parent_intervention_effect = _norm_difference(
        main_post, noop_post, "parent_level_zero_projection"
    )
    fine_live_change = _norm_difference(main_post, main_pre, "fine_coefficients")
    parent_live_recompute_drift = _norm_difference(
        main_post, main["reads"]["post_first_write"], "parent_level_zero_projection"
    )
    noop_parent_drift = _norm_difference(
        noop_post, noop["reads"]["post_first_write"], "parent_level_zero_projection"
    )
    source_off_rows = [arm["source_off_advance"] for arm in arms.values()]
    source_off_ok = all(
        not row["source_enabled"] and row["positive_heartbeat_work"] == 0.0
        for row in source_off_rows
    )
    noop_identity = max(
        _norm_difference(noop_post, noop_pre, "fine_coefficients"),
        _norm_difference(noop_post, noop_pre, "parent_level_zero_projection"),
    )
    reuse = _mixed_source_reuse(internals["LL-read-then-LL-change"]["parent_before"], internals["LL-read-then-LL-change"]["fine_after"])
    comparisons = [
        _comparison(
            "fine_LL_intervention_changes_live_child",
            fine_intervention_effect,
            "||C1(LL-change)-C1(LL-noop)||2",
            "quantity > margin",
            FINE_CHANGE_MARGIN,
            fine_intervention_effect > FINE_CHANGE_MARGIN,
            "silence the second LL impulse by replacing the changed arm's post-read with the no-op post-read",
            0.0,
            0.0 > FINE_CHANGE_MARGIN,
        ),
        _comparison(
            "LL_noop_preserves_read_at_fixed_state",
            noop_identity,
            "max(||C1-Cpre||2, ||P1-Ppre||2) after zero-work LL action",
            "quantity <= margin",
            NOOP_IDENTITY_MARGIN,
            noop_identity <= NOOP_IDENTITY_MARGIN,
            "replace the no-op identity error by 2*margin",
            2.0 * NOOP_IDENTITY_MARGIN,
            2.0 * NOOP_IDENTITY_MARGIN <= NOOP_IDENTITY_MARGIN,
        ),
        _comparison(
            "source_off_is_observed",
            1.0 if source_off_ok else 0.0,
            "all arm advances report source off and zero heartbeat work",
            "quantity >= margin",
            SOURCE_OFF_MARGIN,
            source_off_ok,
            "enable source or heartbeat in one sampled advance row",
            0.0,
            0.0 >= SOURCE_OFF_MARGIN,
        ),
        _comparison(
            "mixed_source_parent_reuse_refuses",
            1.0 if reuse["attempted"] and not reuse["accepted"] else 0.0,
            "old-parent/new-LL composition refusal",
            "quantity >= margin",
            1.0,
            bool(reuse["attempted"] and not reuse["accepted"]),
            "replace the refusal result with accepted composition",
            0.0,
            0.0 >= 1.0,
        ),
    ]
    continuity = continuity_checks()
    api_probe = _api_probe()
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "declared": {
            "question": "After an LL write and a coarse L read, does changing LL leave the previously obtained parent summary recoverable/stable while fine detail changes?",
            "probe_kind": "matched LL intervention with live coarse recompute and frozen-parent capability boundary",
            "seed": SEED,
            "semantic_recall_claim": False,
            "field_persistence_claim": False,
            "persistent_parent_claim": False,
            "profile": profile.as_dict(),
            "packet_paths": {"parent": PARENT_PATH, "fine": FINE_PATH},
            "arm_matrix": [
                "no-write-source-off",
                "LL-read-then-LL-change",
                "LL-read-then-LL-noop",
            ],
            "schedule": {
                "initial_workspace": "one shared immutable initial_workspace(profile) branch",
                "first_action": "LL scale impulse (1,0), work_budget=0.001, evidence tick 0",
                "coarse_read": "analyze_helical_packet(path='L') immediately after first LL write",
                "fine_read": "analyze_helical_packet(path='LL') at the same read points",
                "source_off_advance_ticks": SOURCE_OFF_TICKS,
                "source_enabled": False,
                "demand": 0.0,
                "second_action": "LL scale impulse (0,1), work_budget=0.0005, evidence tick 0",
                "noop_action": "LL scale impulse (0,0), work_budget=0, accepted false",
            },
            "drive": {
                "component": "scale",
                "first_signal": list(FIRST_SIGNAL),
                "first_work_budget": FIRST_BUDGET,
                "change_signal": list(CHANGE_SIGNAL),
                "change_work_budget": CHANGE_BUDGET,
                "event_kind": memory.EVENT_KIND,
                "all_write_paths": [FINE_PATH],
            },
            "margins": {
                "fine_intervention_change": FINE_CHANGE_MARGIN,
                "noop_identity": NOOP_IDENTITY_MARGIN,
                "source_off": SOURCE_OFF_MARGIN,
                "continuity": CONTINUITY_TOLERANCE,
            },
            "api_surface": [
                "initial_workspace", "apply_helical_packet_impulse", "advance_workspace",
                "analyze_helical_packet", "split_helical_packet", "compose_helical_packets",
            ],
        },
        "api_probe": api_probe,
        "arms": arms,
        "observables": {
            "fine_intervention_effect_norm": fine_intervention_effect,
            "parent_intervention_effect_norm": parent_intervention_effect,
            "fine_live_change_norm": fine_live_change,
            "live_parent_recompute_drift_norm": parent_live_recompute_drift,
            "noop_parent_drift_norm": noop_parent_drift,
            "interpretation": "live recompute quantities only; no frozen-parent recovery quantity is asserted",
        },
        "mixed_source_parent_reuse": reuse,
        "summary_persistence": {
            "attempted": False,
            "verdict": "NOT_APPLICABLE",
            "reason": "No public API retains or reads a parent summary independently of the live workspace; a transient Python snapshot is not a surrogate.",
        },
        "comparisons": comparisons,
        "continuity": continuity,
        "continuity_verdict": "PASS" if all(row["within_tolerance"] for row in continuity) else "FAIL",
        "controls": {
            "firing": [{"comparison": row["id"], **row["firing_control"]} for row in comparisons],
            "all_attempted": all(row["firing_control"]["attempted"] for row in comparisons),
            "all_can_fail": all(row["firing_control"]["can_fail"] for row in comparisons),
            "all_flip": all(not row["firing_control"]["holds_after"] for row in comparisons),
        },
        "limitations": LIMITATIONS,
        "boundary": BOUNDARY,
        "verdict": "OUT_OF_SCOPE_FROZEN_PARENT_RECOVERY_NO_API",
    }
    body["runtime_seconds"] = float(perf_counter() - started)
    body["content_digest"] = content_digest(body)
    body["receipt_sha256"] = body["content_digest"]
    return body


def verify_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    actual = content_digest(receipt)
    return {"content_digest_matches": actual == receipt.get("content_digest"), "digest": actual}


def can_fail_probes(receipt: Mapping[str, Any]) -> dict[str, Any]:
    controls = receipt.get("controls", {}).get("firing", [])
    return {
        "comparison_count": len(receipt.get("comparisons", [])),
        "control_count": len(controls),
        "all_attempted": bool(controls) and all(row.get("attempted") for row in controls),
        "all_can_fail": bool(controls) and all(row.get("can_fail") for row in controls),
        "all_flip": bool(controls) and all(not row.get("holds_after") for row in controls),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    receipt = build_receipt()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(_jsonable(receipt), sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "content_digest": receipt["content_digest"],
        "runtime_seconds": receipt["runtime_seconds"],
        "verdict": receipt["verdict"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
