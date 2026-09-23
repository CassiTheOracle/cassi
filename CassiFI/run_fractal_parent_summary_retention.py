"""Causal receipt for the field-owned L level-zero summary register."""
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

SCHEMA = "cassifi.fractal-parent-summary-retention.v1"
DEFAULT_OUTPUT = Path("_diag/fractal-parent-summary-causality/retention.json")
PARENT_PATH = "L"
FINE_PATH = "LL"
FIRST_SIGNAL = (1.0, 0.0)
CHANGE_SIGNAL = (0.0, 1.0)
FIRST_BUDGET = 1e-3
CHANGE_BUDGET = 5e-4
SOURCE_OFF_TICKS = 1
MARGIN = 1e-12
TIMING_KEYS = frozenset({"elapsed_seconds", "runtime_seconds", "content_digest", "receipt_sha256"})


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
        return {str(k): _strip_timing(v) for k, v in value.items() if k not in TIMING_KEYS}
    if isinstance(value, (list, tuple)):
        return [_strip_timing(v) for v in value]
    return value


def content_digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(_strip_timing(value)).encode("utf-8")).hexdigest()


def _norm(left: Any, right: Any) -> float:
    return float(np.linalg.norm(np.asarray(left, dtype=np.float64) - np.asarray(right, dtype=np.float64)))


def _impulse(workspace: field.ResonantWorkspace, signal: tuple[float, float], budget: float):
    return field.apply_helical_packet_impulse(
        workspace,
        path=FINE_PATH,
        component="scale",
        flow_signal=list(signal),
        work_budget=budget,
        evidence_tick=workspace.evidence_tick,
        event_kind="reasoning-work",
    )


def _read_row(workspace: field.ResonantWorkspace, phase: str) -> dict[str, Any]:
    stored = field.read_parent_summary(workspace)
    live = field.analyze_helical_packet(workspace, path=PARENT_PATH)
    live_level_zero = np.asarray(live["coefficients"], dtype=np.float64)[0]
    stored_values = np.asarray(stored["values"], dtype=np.float64) if stored["present"] else np.zeros(4)
    return {
        "phase": phase,
        "state_sha256": workspace.state_sha256,
        "page_sha256": hashlib.sha256(workspace.page_bytes).hexdigest(),
        "stored": stored,
        "live_level_zero": live_level_zero.tolist(),
        "stored_live_drift_norm": _norm(stored_values, live_level_zero) if stored["present"] else None,
    }

def _mutation_control(workspace: field.ResonantWorkspace) -> dict[str, Any]:
    payload = copy.deepcopy(workspace.as_dict())
    raw = bytearray(base64.b64decode(payload["field_b64"]))
    page = np.frombuffer(raw, dtype="<f8").copy()
    start = 9 * workspace.profile.port_count + 3
    page[start] += 0.125
    payload["field_b64"] = base64.b64encode(page.astype("<f8").tobytes()).decode("ascii")
    payload["field"] = page.reshape(workspace.profile.page_shape).tolist()
    try:
        field.ResonantWorkspace.from_dict(payload)
    except Exception as exc:
        return {
            "attempted": True,
            "accepted": False,
            "can_fail": True,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
    return {"attempted": True, "accepted": True, "can_fail": False, "error_type": None, "error": None}


def build_receipt() -> dict[str, Any]:
    started = perf_counter()
    origin = field.initial_workspace(field.ResonantProfile())
    first, first_impulse = _impulse(origin, FIRST_SIGNAL, FIRST_BUDGET)
    stored, write_receipt = field.write_parent_summary(first)
    post_write = _read_row(stored, "post-first-LL-write-and-L-store")
    off, advance = field.advance_workspace(stored, ticks=SOURCE_OFF_TICKS, demand=0.0, source_enabled=False)
    pre_second = _read_row(off, "source-off-before-second-LL")
    changed, change_impulse = _impulse(off, CHANGE_SIGNAL, CHANGE_BUDGET)
    noop, noop_impulse = _impulse(off, (0.0, 0.0), 0.0)
    changed_row = _read_row(changed, "post-second-LL-change")
    noop_row = _read_row(noop, "post-second-LL-noop")

    checkpoint = field.ResonantWorkspace.from_dict(changed.as_dict())
    checkpoint_read = field.read_parent_summary(checkpoint)
    analyzer_was_called = False
    original_analyzer = field.analyze_helical_packet
    def forbidden_analyzer(*args: Any, **kwargs: Any) -> Any:
        nonlocal analyzer_was_called
        analyzer_was_called = True
        raise AssertionError("direct stored read recomputed a live packet")
    field.analyze_helical_packet = forbidden_analyzer
    try:
        direct_read = field.read_parent_summary(changed)
    finally:
        field.analyze_helical_packet = original_analyzer
    changed_live_drift = float(changed_row["stored_live_drift_norm"])
    noop_live_drift = float(noop_row["stored_live_drift_norm"])
    stored_equal = _norm(changed_row["stored"]["values"], noop_row["stored"]["values"]) <= MARGIN
    direct_equal = _norm(direct_read["values"], checkpoint_read["values"]) <= MARGIN
    changed_fine = change_impulse["state_sha256"] != noop_impulse["state_sha256"]
    controls = {
        "serialized_register_mutation": _mutation_control(changed),
        "direct_read_analyzer_bypass": {
            "attempted": True,
            "accepted": bool(analyzer_was_called),
            "can_fail": not analyzer_was_called,
            "analyzer_called": analyzer_was_called,
        },
    }
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "declared": {
            "question": "Does the canonical Workspace retain a field-owned L level-zero summary across source-off and changed LL successors?",
            "semantic_memory_claim": False,
            "field_only": True,
            "path": PARENT_PATH,
            "fine_path": FINE_PATH,
            "register_layout": field.PARENT_SUMMARY_LAYOUT,
            "schedule": [
                "LL impulse",
                "write L level-zero summary into canonical Workspace page",
                "source-off advance",
                "second LL change and matched zero-work noop",
                "direct stored read and checkpoint roundtrip",
            ],
        },
        "source_off_advance": {
            "ticks": int(advance["ticks"]),
            "source_enabled": bool(advance["source_enabled"]),
            "positive_heartbeat_work": float(advance["positive_heartbeat_work"]),
            "state_sha256": str(advance["state_sha256"]),
        },
        "write": write_receipt,
        "reads": {
            "post_write": post_write,
            "pre_second": pre_second,
            "changed": changed_row,
            "noop": noop_row,
            "checkpoint": checkpoint_read,
            "direct_without_live_recompute": direct_read,
        },
        "effects": {
            "second_LL_successor_changes_state": changed_fine,
            "stored_summary_change_norm": _norm(changed_row["stored"]["values"], noop_row["stored"]["values"]),
            "stored_summary_equal_after_change_vs_noop": stored_equal,
            "live_L_recompute_drift_after_change": changed_live_drift,
            "live_L_recompute_drift_after_noop": noop_live_drift,
            "checkpoint_direct_read_equal": direct_equal,
            "direct_read_called_analyzer": analyzer_was_called,
            "first_impulse_source_state_sha256": first_impulse["source_state_sha256"],
        },
        "controls": controls,
        "limitations": [
            "This proves numerical field-owned retention of four L level-zero coefficients only.",
            "It makes no semantic recall, hierarchy, learned state, temporal field, or utility claim.",
            "Resolution transitions explicitly reject an active register; regional serialization explicitly rejects active summaries.",
        ],
    }
    body["comparisons"] = [
        {"id": "stored_parent_survives_LL_change", "holds": stored_equal, "margin": MARGIN},
        {"id": "live_parent_recompute_drifts", "holds": changed_live_drift > MARGIN, "margin": MARGIN},
        {"id": "checkpoint_roundtrip_preserves_register", "holds": direct_equal, "margin": MARGIN},
        {"id": "direct_read_does_not_recompute", "holds": not analyzer_was_called, "margin": 0.0},
        {"id": "mutation_control_fires", "holds": controls["serialized_register_mutation"]["can_fail"], "margin": 0.0},
    ]
    body["verdict"] = (
        "PASS_FIELD_OWNED_PARENT_SUMMARY_RETENTION"
        if all(row["holds"] for row in body["comparisons"])
        else "FAIL_PARENT_SUMMARY_IMPLEMENTATION"
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
