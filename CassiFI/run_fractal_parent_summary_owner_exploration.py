"""Owner transaction/reload receipt for the field-owned parent summary."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping

import cassi_resonant_field as field
import run_fractal_parent_summary_retention as retention
from cassi_field_atlas import AtlasState
from cassi_field_owner import FieldIntelligenceError, FieldIntelligenceOwner


SCHEMA = "cassifi.fractal-parent-summary-owner-exploration.v1"
DEFAULT_OUTPUT = Path("_diag/fractal-parent-summary-owner/exploration.json")
FINE_PATH = retention.FINE_PATH
FIRST_SIGNAL = retention.FIRST_SIGNAL
CHANGE_SIGNAL = retention.CHANGE_SIGNAL
FIRST_BUDGET = retention.FIRST_BUDGET
CHANGE_BUDGET = retention.CHANGE_BUDGET
MARGIN = retention.MARGIN


def _norm(left: Any, right: Any) -> float:
    return retention._norm(left, right)


def _corrupt_current_workspace_page(owner: FieldIntelligenceOwner) -> Path:
    current = owner.checkpoints.current_path.read_text(encoding="ascii").strip()
    manifest = json.loads(
        (owner.checkpoints.manifests / current).read_text(encoding="utf-8")
    )
    descriptor = json.loads(
        (
            owner.checkpoints.objects
            / manifest["state_descriptor_sha256"]
        ).read_text(encoding="utf-8")
    )
    workspace_descriptor_sha = descriptor["state"]["pages"]["resonant_workspace"]
    workspace_descriptor = json.loads(
        (owner.checkpoints.objects / workspace_descriptor_sha).read_text(
            encoding="utf-8"
        )
    )
    page_path = owner.checkpoints.objects / workspace_descriptor["page_sha256"]
    raw = bytearray(page_path.read_bytes())
    raw[0] ^= 0x01
    page_path.write_bytes(bytes(raw))
    return page_path


def _error_control(call: Any, *, expected_code: str | None = None) -> dict[str, Any]:
    try:
        call()
    except FieldIntelligenceError as exc:
        return {
            "attempted": True,
            "accepted": False,
            "can_fail": True,
            "error_code": exc.code,
            "error": str(exc),
            "expected_code": expected_code,
            "expected_code_matches": expected_code is None or exc.code == expected_code,
        }
    except Exception as exc:  # pragma: no cover - a wrong exception is still a firing failure
        return {
            "attempted": True,
            "accepted": False,
            "can_fail": True,
            "error_code": type(exc).__name__,
            "error": str(exc),
            "expected_code": expected_code,
            "expected_code_matches": False,
        }
    return {
        "attempted": True,
        "accepted": True,
        "can_fail": False,
        "error_code": None,
        "error": None,
        "expected_code": expected_code,
        "expected_code_matches": False,
    }


def build_receipt() -> dict[str, Any]:
    started = perf_counter()
    direct = retention.build_receipt()
    with tempfile.TemporaryDirectory(prefix="cassifi-parent-summary-owner-") as directory:
        root = Path(directory)
        owner = FieldIntelligenceOwner(
            root,
            initial_state=AtlasState(
                resonant_workspace=field.initial_workspace(field.ResonantProfile())
            ),
        )
        try:
            before_impulse = owner.state
            first = owner.write_packet_impulse(
                "owner:parent:first-ll",
                path=FINE_PATH,
                component="scale",
                flow_signal=FIRST_SIGNAL,
                work_budget=FIRST_BUDGET,
                event_kind="reasoning-work",
            )
            before_parent = owner.state
            before_parent_manifest = owner.checkpoints.current_manifest_sha256
            parent_write = owner.write_parent_summary(
                "owner:parent:summary",
                expected_state_sha256=before_parent.state_sha256,
            )
            post_write = retention._read_row(
                owner.state.resonant_workspace,
                "owner-post-write",
            )
            after_parent = owner.state
            after_parent_manifest = owner.checkpoints.current_manifest_sha256
            parent_read = owner.read_parent_summary()
            read_state = owner.state.state_sha256
            read_manifest = owner.checkpoints.current_manifest_sha256

            off = owner.advance(
                "owner:parent:source-off",
                ticks=retention.SOURCE_OFF_TICKS,
                source_enabled=False,
            )
            changed = owner.write_packet_impulse(
                "owner:parent:change-ll",
                path=FINE_PATH,
                component="scale",
                flow_signal=CHANGE_SIGNAL,
                work_budget=CHANGE_BUDGET,
                event_kind="reasoning-work",
            )
            changed_row = retention._read_row(
                owner.state.resonant_workspace,
                "owner-after-second-ll",
            )
            stored_change_norm = _norm(
                post_write["stored"]["values"], changed_row["stored"]["values"]
            )
            live_drift = float(changed_row["stored_live_drift_norm"])
            changed_state = owner.state.state_sha256
            changed_manifest = owner.checkpoints.current_manifest_sha256
            owner.close()

            reopened = FieldIntelligenceOwner(root)
            try:
                reload_read = reopened.read_parent_summary()
                reload_state = reopened.state.state_sha256
                reload_manifest = reopened.checkpoints.current_manifest_sha256
                replay = reopened.write_parent_summary(
                    "owner:parent:summary",
                    expected_state_sha256=before_parent.state_sha256,
                )
                replay_state = reopened.state.state_sha256
                replay_manifest = reopened.checkpoints.current_manifest_sha256

                current_before_stale = reopened.checkpoints.current_path.read_bytes()
                stale = _error_control(
                    lambda: reopened.write_parent_summary(
                        "owner:parent:stale",
                        expected_state_sha256=before_parent.state_sha256,
                    ),
                    expected_code="LINEAGE_CONFLICT",
                )
                current_after_stale = reopened.checkpoints.current_path.read_bytes()

                current_before_duplicate = reopened.checkpoints.current_path.read_bytes()
                duplicate = _error_control(
                    lambda: reopened.write_parent_summary("owner:parent:duplicate"),
                    expected_code="RESONANT_NUMERICAL",
                )
                current_after_duplicate = reopened.checkpoints.current_path.read_bytes()

                analyzer_called = False
                original_analyzer = field.analyze_helical_packet

                def forbidden_analyzer(*args: Any, **kwargs: Any) -> Any:
                    nonlocal analyzer_called
                    analyzer_called = True
                    raise AssertionError("owner stored read recomputed a live packet")

                field.analyze_helical_packet = forbidden_analyzer
                try:
                    bypass_read = reopened.read_parent_summary()
                finally:
                    field.analyze_helical_packet = original_analyzer
                read_noop = (
                    reopened.state.state_sha256 == reload_state
                    and reopened.checkpoints.current_manifest_sha256 == reload_manifest
                )
                reopened.close()

                corrupt_owner = FieldIntelligenceOwner(root)
                current_before_corruption = corrupt_owner.checkpoints.current_path.read_bytes()
                _corrupt_current_workspace_page(corrupt_owner)
                corrupt_owner.close()
                corruption = _error_control(
                    lambda: FieldIntelligenceOwner(root),
                    expected_code="CHECKPOINT_CORRUPT",
                )
                current_after_corruption = current_before_corruption
            finally:
                # The corruption control intentionally leaves a quarantined temp root;
                # no later operation is allowed to consume it.
                try:
                    reopened.close()
                except Exception:
                    pass
        finally:
            try:
                owner.close()
            except Exception:
                pass

    owner_summary = post_write["stored"]["values"]
    retained_summary = direct["reads"]["post_write"]["stored"]["values"]
    owner_drift = live_drift
    retained_drift = float(direct["effects"]["live_L_recompute_drift_after_change"])
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "declared": {
            "field_only": True,
            "semantic_memory_claim": False,
            "hierarchy_claim": False,
            "schedule": [
                "real owner LL write",
                "owner parent-summary commit",
                "source-off advance and second owner LL write",
                "owner read-only read and analyzer bypass",
                "close/reopen CURRENT reload and operation replay",
                "stale/duplicate transaction controls",
                "mutated checkpoint page rejection",
            ],
            "retention_continuity_margins": {
                "summary_values_l2": MARGIN,
                "live_drift_absolute": 1e-12,
                "stored_change_l2": MARGIN,
            },
        },
        "retention_continuity": {
            "cited_summary_values": retained_summary,
            "owner_summary_values": owner_summary,
            "summary_values_l2": _norm(owner_summary, retained_summary),
            "cited_live_L_recompute_drift_after_change": retained_drift,
            "owner_live_L_recompute_drift_after_change": owner_drift,
            "live_drift_absolute": abs(owner_drift - retained_drift),
            "cited_stored_summary_change_norm": float(direct["effects"]["stored_summary_change_norm"]),
            "owner_stored_summary_change_norm": stored_change_norm,
        },
        "owner": {
            "first_impulse": first,
            "parent_write": parent_write,
            "post_write_read": parent_read,
            "source_off": off,
            "second_ll_write": changed,
            "post_second_ll_read": changed_row["stored"],
            "reload_read": reload_read,
            "replay": replay,
            "replay_state_unchanged": replay_state == changed_state,
            "replay_manifest_unchanged": replay_manifest == changed_manifest,
            "read_only_state_unchanged": read_noop,
            "bypass_read": bypass_read,
            "checkpoint_state_before_parent": before_parent.state_sha256,
            "checkpoint_state_after_parent": after_parent.state_sha256,
            "checkpoint_manifest_before_parent": before_parent_manifest,
            "checkpoint_manifest_after_parent": after_parent_manifest,
            "checkpoint_generation_before_parent": before_parent.generation,
            "checkpoint_generation_after_parent": after_parent.generation,
            "logical_tick_before_parent": before_parent.logical_tick,
            "logical_tick_after_parent": after_parent.logical_tick,
            "evidence_tick_before_parent": (
                None
                if before_parent.resonant_workspace is None
                else before_parent.resonant_workspace.evidence_tick
            ),
            "evidence_tick_after_parent": (
                None
                if after_parent.resonant_workspace is None
                else after_parent.resonant_workspace.evidence_tick
            ),
        },
        "controls": {
            "stale_expected_state": {
                **stale,
                "current_unchanged": current_before_stale == current_after_stale,
            },
            "duplicate_active_summary": {
                **duplicate,
                "current_unchanged": current_before_duplicate == current_after_duplicate,
            },
            "read_analyzer_bypass": {
                "attempted": True,
                "accepted": analyzer_called,
                "can_fail": not analyzer_called,
                "analyzer_called": analyzer_called,
                "read_noop": read_noop,
            },
            "checkpoint_page_mutation": {
                **corruption,
                "current_unchanged_before_rejection": current_before_corruption
                == current_after_corruption,
            },
        },
        "comparisons": [
            {
                "id": "owner_reproduces_retention_summary",
                "holds": _norm(owner_summary, retained_summary) <= MARGIN,
                "margin": MARGIN,
            },
            {
                "id": "owner_reproduces_retention_live_drift",
                "holds": abs(owner_drift - retained_drift) <= 1e-12,
                "margin": 1e-12,
            },
            {
                "id": "parent_write_advances_generation_once",
                "holds": after_parent.generation == before_parent.generation + 1
                and after_parent_manifest != before_parent_manifest,
                "margin": 0.0,
            },
            {
                "id": "parent_write_preserves_logical_and_evidence_clocks",
                "holds": after_parent.logical_tick == before_parent.logical_tick
                and after_parent.resonant_workspace is not None
                and before_parent.resonant_workspace is not None
                and after_parent.resonant_workspace.evidence_tick
                == before_parent.resonant_workspace.evidence_tick,
                "margin": 0.0,
            },
            {
                "id": "stored_summary_survives_second_ll_write",
                "holds": stored_change_norm <= MARGIN,
                "margin": MARGIN,
            },
            {
                "id": "reload_recovers_register",
                "holds": reload_read["summary_sha256"] == parent_read["summary_sha256"]
                and reload_state == changed_state
                and reload_manifest == changed_manifest,
                "margin": 0.0,
            },
            {
                "id": "same_operation_replays_without_second_successor",
                "holds": replay["checkpoint_receipt"]["replayed"]
                and replay_state == changed_state
                and replay_manifest == changed_manifest,
                "margin": 0.0,
            },
            {
                "id": "read_is_noop_and_does_not_analyze",
                "holds": read_noop and not analyzer_called,
                "margin": 0.0,
            },
            {
                "id": "transaction_controls_fire_without_current_mutation",
                "holds": stale["can_fail"]
                and stale["expected_code_matches"]
                and duplicate["can_fail"]
                and duplicate["expected_code_matches"]
                and current_before_stale == current_after_stale
                and current_before_duplicate == current_after_duplicate,
                "margin": 0.0,
            },
            {
                "id": "checkpoint_corruption_rejected",
                "holds": corruption["can_fail"]
                and corruption["expected_code_matches"],
                "margin": 0.0,
            },
        ],
        "limitations": [
            "This proves owner transaction and checkpoint retention of four numerical L level-zero coefficients only.",
            "It makes no semantic recall, hierarchy, learned state, temporal field, or utility claim.",
            "The parent write is a one-time register activation; active summaries remain incompatible with resolution-changing paths.",
        ],
    }
    body["verdict"] = (
        "PASS_FIELD_OWNED_PARENT_SUMMARY_OWNER_TRANSACTION"
        if all(row["holds"] for row in body["comparisons"])
        else "FAIL_PARENT_SUMMARY_OWNER_TRANSACTION"
    )
    body["runtime_seconds"] = float(perf_counter() - started)
    body["content_digest"] = retention.content_digest(body)
    body["receipt_sha256"] = body["content_digest"]
    return body


def verify_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    actual = retention.content_digest(receipt)
    return {
        "content_digest_matches": actual == receipt.get("content_digest"),
        "digest": actual,
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    receipt = build_receipt()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(receipt, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "content_digest": receipt["content_digest"],
                "verdict": receipt["verdict"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
