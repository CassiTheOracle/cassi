from __future__ import annotations

import base64
import hashlib
from pathlib import Path
import pytest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_cassipi_runtime import build_runtime
from cassi_field_owner import FieldIntelligenceError
from cassi_cassipi_v2 import CanonicalOwnerAdapter


def test_forget_generation_removes_managed_source_and_survives_restart(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    build_runtime(runtime)
    data_home = tmp_path / "data-home"
    adapter = CanonicalOwnerAdapter(runtime, data_home=data_home)
    initial = adapter.owner_status()
    observed = adapter.observe(
        {
            "schema": "cassipi.observe.v1",
            "operation_id": "observe-private-source",
            "native_identity": "private-source",
            "producer_id": "host",
            "producer_sequence": 0,
            "predecessor_event_id": None,
            "profile_id": "profile-a",
            "project_id": "project-a",
            "session_id": "session-a",
            "branch_id": "branch-a",
            "task_scope": "task-a",
            "parent_head_id": initial["field_head_sha256"],
            "event_kind": "observation",
            "source": {
                "source_id": "message:private-source",
                "content_base64": base64.b64encode(b"unique managed source to remove").decode(),
                "mime_type": "text/plain",
                "codec": "utf-8",
                "content_sha256": hashlib.sha256(b"unique managed source to remove").hexdigest(),
                "profile_id": "profile-a",
                "project_id": "project-a",
                "session_id": "session-a",
                "branch_id": "branch-a",
                "task_scope": "task-a",
                "native_source_entry_id": "private-source",
                "author_origin": "user",
                "message_role": "user",
                "observed_timestamp": "2026-09-04T23:00:00Z",
                "claim_category": "user-instruction",
                "fidelity": "exact-observed-bytes",
            },
            "payload": {"memory_scope": "task"},
            "native_entry_id": "private-source",
        }
    )
    revision_id = observed["source"]["revision_id"]
    preview = adapter.forget_preview(
        {
            "schema": "cassipi.forget-preview.v1",
            "profile_id": "profile-a",
            "project_id": "project-a",
            "session_id": "session-a",
            "branch_id": "branch-a",
            "task_scope": "task-a",
            "memory_scope": "task",
            "revision_ids": [revision_id],
        }
    )
    forgotten = adapter.forget_generation(
        {
            "schema": "cassipi.rebuild.v1",
            "operation_id": "forget-private-source",
            "native_identity": "forget-private-source",
            "producer_id": "host",
            "producer_sequence": 1,
            "predecessor_event_id": observed["event_id"],
            "profile_id": "profile-a",
            "project_id": "project-a",
            "session_id": "session-a",
            "branch_id": "branch-a",
            "task_scope": "task-a",
            "parent_head_id": observed["receipt"]["checkpoint_metadata_sha256"],
            "allowed_memory_scopes": ["task"],
            "confirmation_id": preview["preview_id"],
            "reason": "direct-user-approved-forget",
            "revoked_revision_ids": [revision_id],
        }
    )

    assert forgotten["revoked_revision_ids"] == [revision_id]
    assert forgotten["receipt"]["checkpoint_metadata_sha256"]
    with pytest.raises(FieldIntelligenceError) as revoked:
        adapter.owner.exact_recall(
            revision_id=revision_id,
            allowed_labels=frozenset(
                {
                    "profile_id=profile-a",
                    "project_id=project-a",
                    "session_id=session-a",
                    "branch_id=branch-a",
                    "task_scope=task-a",
                }
            ),
        )
    assert revoked.value.code == "SOURCE_REVOKED"
    adapter.close()
    restarted = CanonicalOwnerAdapter(runtime, data_home=data_home)
    owner = restarted.owner_status()
    scope = {
        "profile_id": "profile-a",
        "project_id": "project-a",
        "session_id": "session-a",
        "branch_id": "branch-a",
        "task_scope": "task-a",
        "task": "find the removed source",
        "expected_head_id": owner["field_head_sha256"],
        "expected_journal_head_sha256": owner["journal_head_sha256"],
        "expected_revocation_epoch": owner["revocation_epoch"],
        "input_revision_sha256": "1" * 64,
        "provider_call_id": "forget-restart-check",
        "model_id": "test-model",
        "tokenizer_id": "test-tokenizer",
        "allowed_memory_scopes": ["task"],
        "mandatory_revision_ids": [],
        "excluded_revision_ids": [],
    }
    inventory = restarted.projection_inventory(scope)
    assert revision_id not in {row["revision_id"] for row in inventory["candidates"]}
    restarted.close()
