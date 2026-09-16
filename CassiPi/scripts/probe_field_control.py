from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
from typing import Any, Mapping

sys.dont_write_bytecode = True


RUNTIME_ID = "cassifi.cassipi-field-intelligence.v3"
ENCODING_SCHEMA = "cassipi.direct-host-metadata-codec.v2"
SCOPE = {
    "profile_id": "field-control-profile",
    "project_id": "field-control-project",
    "session_id": "field-control-session",
    "branch_id": "field-control-branch",
    "task_scope": "field-control-task",
}


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _source(native_id: str, content: bytes, role: str) -> Mapping[str, Any]:
    return {
        "source_id": f"field-control:{native_id}",
        "content_base64": base64.b64encode(content).decode("ascii"),
        "content_sha256": hashlib.sha256(content).hexdigest(),
        "mime_type": "text/plain",
        "codec": "utf-8",
        **SCOPE,
        "native_source_entry_id": native_id,
        "author_origin": role,
        "message_role": role,
        "observed_timestamp": "2026-09-05T00:00:00Z",
        "claim_category": (
            "user-instruction" if role == "user" else "assistant-claim"
        ),
        "fidelity": "exact-observed-bytes",
    }


def _observe(
    adapter: Any,
    *,
    native_id: str,
    content: bytes,
    role: str,
    sequence: int,
    predecessor: str | None,
) -> Mapping[str, Any]:
    owner = adapter.owner_status()
    return adapter.observe(
        {
            "schema": "cassipi.observe.v1",
            "operation_id": f"field-control-observe-{native_id}",
            "native_identity": native_id,
            "producer_id": "field-control-probe",
            "producer_sequence": sequence,
            "predecessor_event_id": predecessor,
            **SCOPE,
            "parent_head_id": owner["field_head_sha256"],
            "event_kind": "observation",
            "source": _source(native_id, content, role),
            "payload": {"memory_scope": "task"},
            "native_entry_id": native_id,
        }
    )


def _scope(adapter: Any) -> Mapping[str, Any]:
    owner = adapter.owner_status()
    return {
        **SCOPE,
        "task": "Which colour did the user ask us to retain?",
        "expected_head_id": owner["field_head_sha256"],
        "expected_journal_head_sha256": owner["journal_head_sha256"],
        "expected_revocation_epoch": owner["revocation_epoch"],
        "input_revision_sha256": hashlib.sha256(b"field-control-input").hexdigest(),
        "provider_call_id": "field-control-provider-call",
        "model_id": "field-control-local-model",
        "tokenizer_id": "field-control-byte-tokenizer",
        "allowed_memory_scopes": ["task"],
        "mandatory_revision_ids": [],
        "excluded_revision_ids": [],
    }


def _project(adapter: Any) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    scope = _scope(adapter)
    inventory = adapter.projection_inventory(scope)
    token_counts = {
        representation["action_id"]: max(
            1,
            math.ceil(len(_canonical(representation["message"])) / 4),
        )
        for candidate in inventory["candidates"]
        for representation in candidate["representations"]
    }
    result = adapter.project(
        {
            "schema": "cassipi.projection.v1",
            "scope": scope,
            "inventory_sha256": inventory["inventory_sha256"],
            "budget": {
                "schema": "cassipi.projection-budget.v1",
                "context_window_tokens": 4096,
                "system_tokens": 16,
                "tool_schema_tokens": 16,
                "protected_tokens": 0,
                "image_tokens": 0,
                "current_request_tokens": 16,
                "reserved_output_tokens": 256,
                "host_overhead_tokens": 16,
            },
            "token_counts": token_counts,
        }
    )
    return inventory, result


def _run(runtime: Path, receipt_path: Path) -> Mapping[str, Any]:
    manifest_path = runtime / "runtime-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("runtime_id") != RUNTIME_ID:
        raise RuntimeError("installed runtime identity is incompatible")
    sys.path.insert(0, str(runtime))
    from cassi_cassipi_v2 import CanonicalOwnerAdapter  # type: ignore

    user_bytes = b"Retain blue as the field-control colour."
    assistant_bytes = b"Blue is retained for this task."
    with tempfile.TemporaryDirectory(prefix="cassipi-field-control-") as temporary:
        data_home = Path(temporary) / "owner"
        adapter = CanonicalOwnerAdapter(runtime, data_home=data_home)
        compatibility = adapter.handshake({"runtime_id": RUNTIME_ID})
        if compatibility["encoding_schema"] != ENCODING_SCHEMA:
            raise AssertionError("unexpected field codec")
        initial = adapter.owner_status()
        first = _observe(
            adapter,
            native_id="user",
            content=user_bytes,
            role="user",
            sequence=0,
            predecessor=None,
        )
        _observe(
            adapter,
            native_id="assistant",
            content=assistant_bytes,
            role="assistant",
            sequence=1,
            predecessor=first["event_id"],
        )
        temporal_scope = dict(SCOPE)
        configured = adapter.configure_temporal(
            {
                "schema": "cassipi.configure-temporal.v1",
                "operation_id": "field-control-temporal-configure",
                "memory_id": "field-control-release",
                "action_ids": ["open", "close"],
                "observation_ids": ["ready", "closed"],
            },
            scope=temporal_scope,
        )
        registered = adapter.condense_temporal_skill(
            {
                "schema": "cassipi.condense-temporal-skill.v1",
                "operation_id": "field-control-temporal-register",
                "memory_id": "field-control-release",
                "skill_id": "open-skill",
                "goal_observations": ["ready"],
                "forbidden_observations": [],
            },
            scope=temporal_scope,
        )
        episode_content = _canonical(
            {
                "schema": "cassifi.temporal-episode.v1",
                "steps": [{"action": "open", "observation": "ready"}],
            }
        )
        learned = adapter.learn_temporal(
            {
                "schema": "cassipi.learn-temporal.v1",
                "operation_id": "field-control-temporal-learn",
                "memory_id": "field-control-release",
                "source": {
                    "source_id": "field-control-release-episode",
                    "content_base64": base64.b64encode(episode_content).decode("ascii"),
                    "media_type": "application/json",
                    "codec": "utf-8",
                    "observed_timestamp": "2026-09-10T00:00:00Z",
                    "scope": "task",
                    "claim_category": "observation",
                    "fidelity": "exact",
                    "parent_revision_id": None,
                    "span": None,
                    "labels": [],
                },
            },
            scope=temporal_scope,
        )
        bound = adapter.bind_temporal(
            {
                "schema": "cassipi.bind-temporal.v1",
                "operation_id": "field-control-temporal-bind",
                "memory_id": "field-control-release",
                "participant_id": "field-control-operator",
            },
            scope=temporal_scope,
        )
        before_selection = adapter.owner_status()
        temporal_selection = adapter.select_temporal_action(
            {
                "schema": "cassipi.select-temporal-action.v1",
                "memory_id": "field-control-release",
                "skill_ids": ["open-skill"],
                "participant_id": "field-control-operator",
                "operations": [
                    {
                        "action": "open",
                        "authorized": True,
                        "feasible": True,
                        "represented_forbidden": False,
                    }
                ],
            },
            scope=temporal_scope,
        )
        after_selection = adapter.owner_status()
        if after_selection["field_head_sha256"] != before_selection["field_head_sha256"]:
            raise AssertionError("temporal action selection mutated persistent owner state")
        advanced = adapter.advance_temporal(
            {
                "schema": "cassipi.advance-temporal.v1",
                "operation_id": "field-control-temporal-advance",
                "memory_id": "field-control-release",
                "participant_id": "field-control-operator",
                "action": "open",
                "observation": "ready",
            },
            scope=temporal_scope,
        )
        temporal_before_restart = adapter.inspect_temporal(
            {
                "schema": "cassipi.inspect-temporal.v1",
                "memory_id": "field-control-release",
                "skill_id": "open-skill",
                "participant_id": "field-control-operator",
            },
            scope=temporal_scope,
        )
        if registered["receipt"]["status"] != "pending":
            raise AssertionError("prospective temporal skill was not initially pending")
        if learned["receipt"]["formed_skills"] != ["open-skill"]:
            raise AssertionError("field evidence did not automatically form the temporal skill")
        if temporal_selection["status"] != "selected":
            raise AssertionError("field did not select the supported temporal skill action")
        if temporal_selection["selected"]["action"] != "open":
            raise AssertionError("field selected a different temporal action")
        if temporal_selection["read_only"] is not True or temporal_selection["memory_unchanged"] is not True:
            raise AssertionError("temporal action selection was not read-only")
        if advanced["receipt"]["supported"] is not True:
            raise AssertionError("selected temporal transition was not supported")
        if temporal_before_restart["skill"]["status"] != "complete":
            raise AssertionError("temporal skill did not complete after its observed outcome")
        inspection = adapter.owner.inspect()
        contribution_count = sum(
            len(chart.contributions) for chart in adapter.owner.state.charts
        )
        inventory, projection = _project(adapter)
        active_status = adapter.owner_status()
        selected_sources = [row["source"] for row in projection["selected"]]
        selected_scores = [
            row["field_score"]
            for row in projection["selected"]
            if row["field_score"] is not None
        ]
        if active_status["field_head_sha256"] == initial["field_head_sha256"]:
            raise AssertionError("field head did not advance")
        if inspection["capacity"]["usage"]["charts"] != 1:
            raise AssertionError("observations did not enter one scoped field chart")
        if contribution_count != 2:
            raise AssertionError("field chart did not retain both contributions")
        if projection["status"] != "ready" or not projection["selected"]:
            raise AssertionError("field projection did not select retained evidence")
        if not selected_scores or not all(math.isfinite(score) for score in selected_scores):
            raise AssertionError("field projection did not emit a finite field score")
        if hashlib.sha256(user_bytes).hexdigest() not in {
            source["content_sha256"] for source in selected_sources
        }:
            raise AssertionError("projected source identity changed across the field codec")
        if not any("Retain blue" in message["content"] for message in projection["messages"]):
            raise AssertionError("projected evidence did not preserve the exact source text")
        if projection["external_model_calls"] != 0:
            raise AssertionError("field selection invoked an external model")
        if projection["adaptive_sidecars"] != [] or projection["semantic_ranker"] is not None:
            raise AssertionError("projection used adaptive state outside the field owner")
        active_inventory_sha = inventory["inventory_sha256"]
        active_projection_sha = _sha256(projection)
        active_selection = [
            {
                "action_id": row["action_id"],
                "revision_id": row["revision_id"],
                "representation": row["representation"],
                "source_sha256": row["source"]["content_sha256"],
                "tokens": row["tokens"],
            }
            for row in projection["selected"]
        ]
        adapter.close()

        restarted = CanonicalOwnerAdapter(runtime, data_home=data_home)
        restarted_status = restarted.owner_status()
        if restarted_status["field_head_sha256"] != active_status["field_head_sha256"]:
            restarted.close()
            raise AssertionError(
                "restarted owner loaded a different field head: "
                f"before={active_status['field_head_sha256']} "
                f"after={restarted_status['field_head_sha256']} "
                f"before_state={active_status['active_state_sha256']} "
                f"after_state={restarted_status['active_state_sha256']}"
            )
        temporal_after_restart = restarted.inspect_temporal(
            {
                "schema": "cassipi.inspect-temporal.v1",
                "memory_id": "field-control-release",
                "skill_id": "open-skill",
                "participant_id": "field-control-operator",
            },
            scope=temporal_scope,
        )
        if temporal_after_restart["state_sha256"] != temporal_before_restart["state_sha256"]:
            restarted.close()
            raise AssertionError("temporal field state changed across owner restart")
        if temporal_after_restart["skill"] != temporal_before_restart["skill"]:
            restarted.close()
            raise AssertionError("formed temporal skill changed across owner restart")
        replay_inventory, replay_projection = _project(restarted)
        replay_status = restarted.owner_status()
        restarted.close()
        replay_selection = [
            {
                "action_id": row["action_id"],
                "revision_id": row["revision_id"],
                "representation": row["representation"],
                "source_sha256": row["source"]["content_sha256"],
                "tokens": row["tokens"],
            }
            for row in replay_projection["selected"]
        ]
        if replay_selection != active_selection:
            raise AssertionError("restarted owner selected different retained evidence")
        if replay_projection["messages"] != projection["messages"]:
            raise AssertionError("restarted owner projected different source-backed messages")

        receipt = {
            "schema": "cassipi.field-control-receipt.v3",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "PASS",
            "runtime": {
                "root": str(runtime.resolve()),
                "runtime_id": RUNTIME_ID,
                "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                "closure_sha256": compatibility["closure_sha256"],
                "corpus_schema": compatibility["corpus_schema"],
                "encoding_schema": compatibility["encoding_schema"],
            },
            "field": {
                "initial_head_sha256": initial["field_head_sha256"],
                "active_head_sha256": active_status["field_head_sha256"],
                "chart_count": inspection["capacity"]["usage"]["charts"],
                "contribution_count": contribution_count,
                "variable_count": inspection["capacity"]["usage"]["variables"],
                "selected_revision_ids": [
                    row["revision_id"] for row in projection["selected"]
                ],
                "finite_field_scores": selected_scores,
            },
            "temporal": {
                "configured_memory_sha256": configured["receipt"]["memory_sha256"],
                "registered_status": registered["receipt"]["status"],
                "formed_skills": learned["receipt"]["formed_skills"],
                "participant_id": bound["receipt"]["participant_id"],
                "selected_action": temporal_selection["selected"]["action"],
                "selection_read_only": temporal_selection["read_only"],
                "transition_supported": advanced["receipt"]["supported"],
                "skill_status": temporal_before_restart["skill"]["status"],
                "restart_state_identical": True,
                "restart_skill_identical": True,
            },
            "boundaries": {
                "exact_source_text_preserved": True,
                "external_model_calls": 0,
                "adaptive_sidecars": [],
                "learned_text_encoder": False,
            },
            "replay": {
                "owner_restart_identical": True,
                "selection_identical": True,
                "messages_identical": True,
                "initial_inventory_sha256": active_inventory_sha,
                "initial_projection_sha256": active_projection_sha,
                "replay_inventory_sha256": replay_inventory["inventory_sha256"],
                "replay_projection_sha256": _sha256(replay_projection),
                "post_replay_head_sha256": replay_status["field_head_sha256"],
            },
        }
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_bytes(_canonical(receipt) + b"\n")
        return receipt


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify that the installed CassiPi runtime is controlled by the current CassiFI field owner."
    )
    parser.add_argument("--profile", default="cassipi-rehearsal")
    parser.add_argument("--runtime", type=Path)
    parser.add_argument(
        "--receipt",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "probes"
        / "receipts"
        / "field-control.json",
    )
    args = parser.parse_args()
    runtime = args.runtime or (
        Path.home()
        / ".omp"
        / "profiles"
        / args.profile
        / "local-plugins"
        / "cassipi"
        / "fi-runtime"
    )
    receipt = _run(runtime.resolve(), args.receipt.resolve())
    print(
        json.dumps(
            {
                "status": receipt["status"],
                "receipt": str(args.receipt.resolve()),
                "runtime_id": receipt["runtime"]["runtime_id"],
                "field_head_changed": (
                    receipt["field"]["initial_head_sha256"]
                    != receipt["field"]["active_head_sha256"]
                ),
                "owner_restart_identical": receipt["replay"]["owner_restart_identical"],
                "selection_identical_after_restart": receipt["replay"]["selection_identical"],
                "messages_identical_after_restart": receipt["replay"]["messages_identical"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
