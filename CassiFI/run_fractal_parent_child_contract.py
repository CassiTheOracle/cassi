"""Focused causal contract for field-owned L/LL parent-child memory."""
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping

import numpy as np

import cassi_resonant_field as field
from cassi_field_atlas import AtlasState
from cassi_field_owner import (
    FieldIntelligenceError,
    FieldIntelligenceOwner,
    FieldIntelligenceSurface,
    RPC_RESPONSE_SCHEMA,
    RPC_SCHEMA,
)

SCHEMA = "cassifi.fractal-parent-child-contract.v1"
DEFAULT_OUTPUT = Path("_diag/fractal-parent-child-contract/exploration.json")
PARENT_PATH = "L"
CHILD_PATH = "LL"
CHILD_SIGNAL = (1.0, 0.0)
CHILD_BUDGET = 1e-3
SOURCE_OFF_TICKS = 1
MARGIN = 1e-12
TIMING_KEYS = frozenset({"elapsed_seconds", "content_digest"})


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(v) for v in value]
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


def _strip_timing(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _strip_timing(item) for key, item in value.items() if key not in TIMING_KEYS}
    if isinstance(value, list):
        return [_strip_timing(item) for item in value]
    return value


def content_digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(_strip_timing(value)).encode("utf-8")).hexdigest()


def _norm(left: Any, right: Any) -> float:
    return float(np.linalg.norm(np.asarray(left, dtype=np.float64) - np.asarray(right, dtype=np.float64)))


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
    except Exception as exc:  # wrong exception is a failed firing control
        return {
            "attempted": True,
            "accepted": False,
            "can_fail": True,
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


def build_receipt() -> dict[str, Any]:
    started = perf_counter()
    with tempfile.TemporaryDirectory(prefix="cassifi-parent-child-contract-") as directory:
        root = Path(directory)
        workspace, initial_write = field.write_parent_registers(
            field.initial_workspace(), paths=(PARENT_PATH, CHILD_PATH), ancestry_pairs=((PARENT_PATH, CHILD_PATH),)
        )
        owner = FieldIntelligenceOwner(root, initial_state=AtlasState(resonant_workspace=workspace))
        try:
            before = owner.state
            before_workspace = before.resonant_workspace
            assert before_workspace is not None
            stored_before = field.read_parent_register(before_workspace, PARENT_PATH)
            relation_before = field.read_parent_registers(before_workspace)["relations"][0]
            child_packet_before = field.analyze_helical_packet(before_workspace, path=CHILD_PATH)

            child_write = owner.write_packet_impulse(
                "parent-child:child-write",
                path=CHILD_PATH,
                component="scale",
                flow_signal=CHILD_SIGNAL,
                work_budget=CHILD_BUDGET,
                event_kind="reasoning-work",
                expected_state_sha256=before.state_sha256,
            )
            after_child = owner.state
            after_child_workspace = after_child.resonant_workspace
            assert after_child_workspace is not None
            stored_after_child = field.read_parent_register(after_child_workspace, PARENT_PATH)
            live_parent_after_child = field.analyze_helical_packet(after_child_workspace, path=PARENT_PATH)
            live_child_after_child = field.analyze_helical_packet(after_child_workspace, path=CHILD_PATH)
            stale_state = _control(
                lambda: owner.recompute_parent_summary_from_child(
                    "parent-child:stale-state",
                    expected_state_sha256=before.state_sha256,
                ),
                "LINEAGE_CONFLICT",
            )
            mutated_relation = _control(
                lambda: owner.recompute_parent_summary_from_child(
                    "parent-child:mutated-relation",
                    expected_state_sha256=after_child.state_sha256,
                    expected_relation_sha256="0" * 64,
                ),
                "RESONANT_NUMERICAL",
            )
            surface = FieldIntelligenceSurface(owner)
            rpc_response = surface.handle(
                {
                    "operation": "recompute_parent_summary_from_child",
                    "params": {
                        "operation_id": "parent-child:recompute",
                        "expected_state_sha256": after_child.state_sha256,
                        "expected_relation_sha256": relation_before["relation_sha256"],
                        "expected_child_packet_sha256": live_child_after_child["packet_sha256"],
                    },
                    "request_id": "parent-child:rpc-recompute",
                    "schema": RPC_SCHEMA,
                }
            )
            assert rpc_response["ok"] is True
            assert rpc_response["schema"] == RPC_RESPONSE_SCHEMA
            recompute = rpc_response["result"]
            surface_rpc = {
                "operation": "recompute_parent_summary_from_child",
                "request_schema": RPC_SCHEMA,
                "response_schema": rpc_response["schema"],
                "request_id": rpc_response["request_id"],
                "ok": rpc_response["ok"],
                "result_lineage": {
                    "source_state_sha256": recompute["parent_child_receipt"]["source_state_sha256"],
                    "source_packet_sha256": recompute["parent_child_receipt"]["source_packet_sha256"],
                    "relation_sha256": recompute["parent_child_receipt"]["relation_sha256"],
                },
            }
            after_recompute = owner.state
            after_recompute_workspace = after_recompute.resonant_workspace
            assert after_recompute_workspace is not None
            stored_after_recompute = field.read_parent_register(after_recompute_workspace, PARENT_PATH)
            relation_after = field.read_parent_registers(after_recompute_workspace)["relations"][0]
            source_off = owner.advance(
                "parent-child:source-off",
                ticks=SOURCE_OFF_TICKS,
                source_enabled=False,
                expected_state_sha256=after_recompute.state_sha256,
            )
            after_source_off = owner.state
            source_off_workspace = after_source_off.resonant_workspace
            assert source_off_workspace is not None
            stored_after_source_off = field.read_parent_register(source_off_workspace, PARENT_PATH)
        finally:
            owner.close()
        reloaded = FieldIntelligenceOwner(root)
        try:
            reload_read = reloaded.read_parent_summary()
            reload_state = reloaded.state
        finally:
            reloaded.close()

    parent_unchanged_without_recompute = _norm(stored_before["values"], stored_after_child["values"])
    parent_changed_on_recompute = _norm(stored_after_child["values"], stored_after_recompute["values"])
    source_off_drift = _norm(stored_after_recompute["values"], stored_after_source_off["values"])
    reload_drift = _norm(stored_after_recompute["values"], reload_read["values"])
    parent_lineage_bound = (
        stored_after_recompute["source_state_sha256"] == recompute["parent_child_receipt"]["source_state_sha256"]
        and stored_after_recompute["source_packet_sha256"] == recompute["parent_child_receipt"]["source_packet_sha256"]
        and relation_after["relation_sha256"] == recompute["parent_child_receipt"]["relation_sha256"]
    )
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "verdict": "PASS_FIELD_OWNED_PARENT_CHILD_CONTRACT"
        if parent_unchanged_without_recompute <= MARGIN
        and parent_changed_on_recompute > MARGIN
        and source_off_drift <= MARGIN
        and reload_drift <= MARGIN
        and parent_lineage_bound
        and surface_rpc["ok"]
        and surface_rpc["response_schema"] == RPC_RESPONSE_SCHEMA
        and stale_state["expected_code_matches"]
        and mutated_relation["expected_code_matches"]
        else "FAIL_FIELD_OWNED_PARENT_CHILD_CONTRACT",
        "declared": {
            "arithmetic": "numpy-cpu-float64",
            "parent_path": PARENT_PATH,
            "child_path": CHILD_PATH,
            "source_off_ticks": SOURCE_OFF_TICKS,
            "margin": MARGIN,
            "scope": "canonical L/LL field registers only; no semantic-memory claim",
        },
        "observables": {
            "parent_unchanged_without_recompute_l2": parent_unchanged_without_recompute,
            "parent_changed_on_explicit_recompute_l2": parent_changed_on_recompute,
            "source_off_parent_drift_l2": source_off_drift,
            "reload_parent_drift_l2": reload_drift,
            "child_live_packet_changed": child_packet_before["packet_sha256"] != live_child_after_child["packet_sha256"],
            "live_parent_packet_sha256_after_child": live_parent_after_child["packet_sha256"],
            "reload_state_sha256": reload_state.state_sha256,
        },
        "lineage": {
            "initial_relation_sha256": relation_before["relation_sha256"],
            "recomputed_relation_sha256": relation_after["relation_sha256"],
            "parent_lineage_bound": parent_lineage_bound,
            "stored_parent_source_state_sha256": stored_after_recompute["source_state_sha256"],
            "stored_parent_source_packet_sha256": stored_after_recompute["source_packet_sha256"],
            "recompute_receipt": recompute["parent_child_receipt"],
        },
        "surface_rpc": surface_rpc,
        "controls": {"stale_source": stale_state, "mutated_relation": mutated_relation},
        "initial_write": initial_write,
        "child_write": child_write["impulse_receipt"],
        "source_off": source_off["resonance_receipt"],
        "reload_read": reload_read,
        "content_digest": None,
        "elapsed_seconds": perf_counter() - started,
    }
    body["content_digest"] = content_digest(body)
    return body


def verify_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    digest = content_digest(receipt)
    return {"content_digest_matches": digest == receipt.get("content_digest"), "digest": digest}


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    receipt = build_receipt()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(canonical_json(receipt) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": receipt["verdict"], "content_digest": receipt["content_digest"]}, sort_keys=True))
    return 0 if receipt["verdict"].startswith("PASS_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
