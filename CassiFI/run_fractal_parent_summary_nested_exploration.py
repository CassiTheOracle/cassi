"""Bounded field-owned L/LL register exploration with a declared relation."""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping

import numpy as np

import cassi_resonant_field as field
import run_fractal_parent_summary_retention as retention

SCHEMA = "cassifi.fractal-parent-summary-nested-exploration.v1"
DEFAULT_OUTPUT = Path("_diag/fractal-parent-summary-nested/exploration.json")
MARGIN = retention.MARGIN
TIMING_KEYS = retention.TIMING_KEYS


def _jsonable(value: Any) -> Any:
    return retention._jsonable(value)


def canonical_json(value: Any) -> str:
    return retention.canonical_json(value)


def content_digest(value: Mapping[str, Any]) -> str:
    return retention.content_digest(value)


def _norm(left: Any, right: Any) -> float:
    return float(np.linalg.norm(np.asarray(left, dtype=np.float64) - np.asarray(right, dtype=np.float64)))


def _impulse(workspace: field.ResonantWorkspace, signal: tuple[float, float], budget: float):
    return retention._impulse(workspace, signal, budget)


def _register_snapshot(workspace: field.ResonantWorkspace, phase: str) -> dict[str, Any]:
    registers = field.read_parent_registers(workspace)
    return {
        "phase": phase,
        "state_sha256": workspace.state_sha256,
        "page_sha256": hashlib.sha256(workspace.page_bytes).hexdigest(),
        "registers": registers,
    }


def _relation_mutation_control(workspace: field.ResonantWorkspace) -> dict[str, Any]:
    payload = copy.deepcopy(workspace.as_dict())
    transition = payload["layout_transition"]
    relation = transition[field.PARENT_REGISTER_METADATA_KEY]["relations"][0]
    relation["relation_sha256"] = "0" * 64
    try:
        field.ResonantWorkspace.from_dict(payload)
    except Exception as exc:
        return {"attempted": True, "accepted": False, "can_fail": True,
                "error_type": type(exc).__name__, "error": str(exc)}
    return {"attempted": True, "accepted": True, "can_fail": False,
            "error_type": None, "error": None}


def _source_mutation_control(workspace: field.ResonantWorkspace) -> dict[str, Any]:
    payload = copy.deepcopy(workspace.as_dict())
    slots = payload["layout_transition"][field.PARENT_REGISTER_METADATA_KEY]["slots"]
    slots["LL"]["source_state_sha256"] = "f" * 64
    try:
        field.ResonantWorkspace.from_dict(payload)
    except Exception as exc:
        return {"attempted": True, "accepted": False, "can_fail": True,
                "error_type": type(exc).__name__, "error": str(exc)}
    return {"attempted": True, "accepted": True, "can_fail": False,
            "error_type": None, "error": None}


def build_receipt() -> dict[str, Any]:
    started = perf_counter()
    origin = field.initial_workspace(field.ResonantProfile())
    first, first_impulse = _impulse(origin, retention.FIRST_SIGNAL, retention.FIRST_BUDGET)
    nested, write = field.write_parent_registers(
        first, paths=("L", "LL"), ancestry_pairs=(("L", "LL"),)
    )
    post_write = _register_snapshot(nested, "post-atomic-same-source-L-LL-capture")
    off, advance = field.advance_workspace(nested, ticks=retention.SOURCE_OFF_TICKS, source_enabled=False)
    pre_correction = _register_snapshot(off, "source-off-before-LL-only-correction")
    changed, change_impulse = _impulse(off, retention.CHANGE_SIGNAL, retention.CHANGE_BUDGET)
    noop, noop_impulse = _impulse(off, (0.0, 0.0), 0.0)
    changed_row = _register_snapshot(changed, "post-LL-only-correction")
    noop_row = _register_snapshot(noop, "post-LL-only-noop")
    checkpoint = field.ResonantWorkspace.from_dict(changed.as_dict())
    checkpoint_row = _register_snapshot(checkpoint, "checkpoint-roundtrip")
    initial_l = np.asarray(post_write["registers"]["slots"]["L"]["values"], dtype=np.float64)
    changed_l = np.asarray(changed_row["registers"]["slots"]["L"]["values"], dtype=np.float64)
    initial_ll = np.asarray(post_write["registers"]["slots"]["LL"]["values"], dtype=np.float64)
    changed_ll = np.asarray(changed_row["registers"]["slots"]["LL"]["values"], dtype=np.float64)
    relation = write["relations"][0]
    controls = {
        "relation_digest_mutation": _relation_mutation_control(changed),
        "source_digest_mutation": _source_mutation_control(changed),
    }
    stored_l_equal = _norm(initial_l, changed_l) <= MARGIN
    stored_ll_equal = _norm(initial_ll, changed_ll) <= MARGIN
    checkpoint_equal = checkpoint_row["registers"] == changed_row["registers"]
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "declared": {
            "field_only": True,
            "semantic_memory_claim": False,
            "paths": ["L", "LL"],
            "relation": "L->LL",
            "schedule": [
                "one atomic same-source L+LL capture",
                "source-off advancement",
                "LL-only correction and matched zero-work noop",
                "direct register reads",
                "checkpoint and serialization roundtrip",
                "relation-certificate mutation controls",
            ],
            "register_layout": field.PARENT_REGISTER_LAYOUT,
        },
        "write": write,
        "relation_certificate": relation,
        "source_off_advance": {
            "ticks": int(advance["ticks"]),
            "source_enabled": bool(advance["source_enabled"]),
            "state_sha256": str(advance["state_sha256"]),
        },
        "reads": {
            "post_write": post_write,
            "pre_correction": pre_correction,
            "changed": changed_row,
            "noop": noop_row,
            "checkpoint": checkpoint_row,
        },
        "effects": {
            "same_source_capture_group": relation["source_state_sha256"] == write["source_state_sha256"],
            "path_prefix_proven": relation["path_prefix"],
            "support_containment_proven": relation["support_contained"],
            "stored_L_equal_after_LL_correction": stored_l_equal,
            "stored_LL_equal_after_LL_correction": stored_ll_equal,
            "LL_correction_changes_successor_state": change_impulse["state_sha256"] != noop_impulse["state_sha256"],
            "checkpoint_direct_read_equal": checkpoint_equal,
            "live_L_recompute_drift_after_change": retention._norm(
                changed_l, field.analyze_helical_packet(changed, path="L")["coefficients"][0]
            ),
            "live_L_recompute_drift_after_noop": retention._norm(
                initial_l, field.analyze_helical_packet(noop, path="L")["coefficients"][0]
            ),
            "reproduced_frozen_live_L_drift": retention._norm(
                retention.build_receipt()["effects"]["live_L_recompute_drift_after_change"],
                0.023689659536096586,
            ) <= 1e-12,
            "reproduced_frozen_noop_drift": retention._norm(
                retention.build_receipt()["effects"]["live_L_recompute_drift_after_noop"],
                0.002399058843388929,
            ) <= 1e-12,
            "first_impulse_source_state_sha256": first_impulse["source_state_sha256"],
        },
        "controls": controls,
        "limitations": [
            "This proves only two bounded field-owned numerical registers and an explicitly certified same-source relation.",
            "It does not prove semantic recall, self-organizing hierarchy, learned memory, or utility.",
            "Resolution and regional serialization remain explicitly rejected for active register maps.",
        ],
    }
    body["comparisons"] = [
        {"id": "same_source_nested_relation", "holds": body["effects"]["same_source_capture_group"], "margin": 0.0},
        {"id": "path_prefix_and_support_containment", "holds": body["effects"]["path_prefix_proven"] and body["effects"]["support_containment_proven"], "margin": 0.0},
        {"id": "stored_L_survives_LL_correction", "holds": stored_l_equal, "margin": MARGIN},
        {"id": "stored_LL_survives_LL_correction", "holds": stored_ll_equal, "margin": MARGIN},
        {"id": "LL_correction_changes_successor", "holds": body["effects"]["LL_correction_changes_successor_state"], "margin": 0.0},
        {"id": "checkpoint_roundtrip_preserves_registers", "holds": checkpoint_equal, "margin": 0.0},
        {"id": "relation_digest_mutation_fires", "holds": controls["relation_digest_mutation"]["can_fail"], "margin": 0.0},
        {"id": "source_digest_mutation_fires", "holds": controls["source_digest_mutation"]["can_fail"], "margin": 0.0},
        {"id": "frozen_live_L_drift_reproduced", "holds": body["effects"]["reproduced_frozen_live_L_drift"], "margin": 1e-12},
        {"id": "frozen_noop_drift_reproduced", "holds": body["effects"]["reproduced_frozen_noop_drift"], "margin": 1e-12},
    ]
    body["verdict"] = (
        "PASS_FIELD_OWNED_NESTED_PARENT_REGISTERS"
        if all(row["holds"] for row in body["comparisons"])
        else "FAIL_FIELD_OWNED_NESTED_PARENT_REGISTERS"
    )
    body["runtime_seconds"] = float(perf_counter() - started)
    body["content_digest"] = content_digest(body)
    body["receipt_sha256"] = body["content_digest"]
    return body


def verify_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    actual = content_digest(receipt)
    return {"content_digest_matches": actual == receipt.get("content_digest"), "digest": actual}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    receipt = build_receipt()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(_jsonable(receipt), sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "content_digest": receipt["content_digest"], "verdict": receipt["verdict"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
