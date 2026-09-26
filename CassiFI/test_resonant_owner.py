"""Helpers for exercising the explicit v1-to-v2 owner migration boundary."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping
from cassi_field_owner import canonical_json_bytes


V1_ROOT_SCHEMA = "cassifi.field-atlas-root.v1"

V1_ATLAS_SCHEMA = "cassifi.field-atlas.v1"

def make_v1_checkpoint_fixture(root: Path, state_payload: Mapping[str, Any]) -> str:
    """Write a real v1 object/page closure and return its CURRENT manifest digest.

    The fixture deliberately uses the historical root descriptor shape and stores
    each chart's ``numeric_field`` as an independently addressed object, matching
    the on-disk representation consumed by ``AtlasCheckpointStore.migrate_v1``.
    """
    root = Path(root)
    objects = root / "objects"
    manifests = root / "manifests"
    objects.mkdir(parents=True, exist_ok=True)
    manifests.mkdir(parents=True, exist_ok=True)
    payload = json.loads(canonical_json_bytes(dict(state_payload)).decode("utf-8"))
    payload["schema"] = V1_ATLAS_SCHEMA
    state_sha256 = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    page_hashes: list[str] = []
    for chart in payload.get("charts", []):
        numeric = chart.get("numeric_field")
        if not isinstance(numeric, Mapping):
            continue
        page = canonical_json_bytes(dict(numeric))
        page_sha = hashlib.sha256(page).hexdigest()
        (objects / page_sha).write_bytes(page)
        page_hashes.append(page_sha)
        chart["numeric_field"] = {"object_sha256": page_sha}
    descriptor = {
        "pages": page_hashes,
        "schema": V1_ROOT_SCHEMA,
        "state": payload,
        "state_sha256": state_sha256,
    }
    descriptor_bytes = canonical_json_bytes(descriptor)
    descriptor_sha = hashlib.sha256(descriptor_bytes).hexdigest()
    (objects / descriptor_sha).write_bytes(descriptor_bytes)
    manifest = {
        "event_id": None,
        "generation": int(payload.get("generation", 0)),
        "operation_id": "genesis",
        "parent_manifest_sha256": None,
        "revocation_generation": int(payload.get("revocation_generation", 0)),
        "schema": "cassifi.field-atlas-checkpoint.v1",
        "state_descriptor_sha256": descriptor_sha,
        "state_sha256": descriptor["state_sha256"],
        "transition": {"kind": "genesis"},
    }
    manifest_bytes = canonical_json_bytes(manifest)
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    (manifests / manifest_sha).write_bytes(manifest_bytes)
    (root / "CURRENT").write_text(manifest_sha + "\n", encoding="ascii")
    return manifest_sha


def _legacy_owner(home: Path) -> tuple[str, bytes, Mapping[str, Any]]:
    from cassi_field_atlas import RelationChart, VariableSpec
    from cassi_field_owner import FieldIntelligenceOwner, SourceInput

    owner = FieldIntelligenceOwner(home)
    try:
        for name in ("x", "y"):
            owner.configure_variable(f"variable:{name}", VariableSpec(name))
        owner.configure_chart(
            "chart:identity",
            RelationChart.empty(chart_id="identity", scope=("x", "y")),
        )
        admitted = owner.admit_observation(
            operation_id="observe:identity",
            source=SourceInput(
                source_id="migration-observation",
                content=b'{"x":2,"y":2}',
                media_type="application/json",
                codec="utf-8",
                observed_timestamp="2026-09-06T00:00:00Z",
                scope="migration-test",
                claim_category="controlled-measurement",
                fidelity="exact-record",
                labels=("migration-test",),
            ),
            values={"x": 2.0, "y": 2.0},
            context={},
        )
        chart_bytes = canonical_json_bytes([chart.as_dict() for chart in owner.state.charts])
        revision = admitted["source"]["revision_id"]
        recalled = owner.exact_recall(
            revision_id=revision, allowed_labels=frozenset({"migration-test"})
        )
        payload = dict(owner.state.as_dict())
        for key in ("resonant_workspace", "transition_epoch_floor", "prepared_queries", "frozen_query_ids"):
            payload.pop(key, None)
    finally:
        owner.close()
    make_v1_checkpoint_fixture(home / "field", payload)
    return revision, chart_bytes, recalled


def test_explicit_migration_preserves_learned_memory_and_source_bytes(tmp_path: Path) -> None:
    import numpy as np
    import pytest
    from cassi_field_atlas import FieldIntelligenceError
    from cassi_field_owner import FieldIntelligenceOwner

    revision, chart_bytes, recalled = _legacy_owner(tmp_path)
    with pytest.raises(FieldIntelligenceError) as legacy:
        FieldIntelligenceOwner(tmp_path)
    assert legacy.value.code == "MIGRATION_REQUIRED"
    migration = FieldIntelligenceOwner.migrate_v1(tmp_path)
    owner = FieldIntelligenceOwner(tmp_path)
    try:
        committed = owner.checkpoints._committed_operation("migrate-v1")
        assert committed is not None
        record, manifest = committed
        assert (
            record["parent_manifest_sha256"]
            == migration["source_manifest_sha256"]
        )
        assert manifest["parent_manifest_sha256"] is None
        assert canonical_json_bytes([chart.as_dict() for chart in owner.state.charts]) == chart_bytes
        assert owner.exact_recall(
            revision_id=revision, allowed_labels=frozenset({"migration-test"})
        ) == recalled
        assert owner.state.resonant_workspace is not None
        assert not np.any(owner.state.resonant_workspace.field)
        advanced = owner.advance(operation_id="post-migration", ticks=2)
        assert advanced["resonance_receipt"]["positive_heartbeat_work"] > 0
        saved = owner.state.state_sha256
    finally:
        owner.close()
    restored = FieldIntelligenceOwner(tmp_path)
    try:
        assert restored.state.state_sha256 == saved
        assert canonical_json_bytes([chart.as_dict() for chart in restored.state.charts]) == chart_bytes
    finally:
        restored.close()


def test_migration_rejects_corrupt_page_without_replacing_legacy_head(tmp_path: Path) -> None:
    import pytest
    from cassi_field_atlas import FieldIntelligenceError
    from cassi_field_owner import FieldIntelligenceOwner

    _legacy_owner(tmp_path)
    root = tmp_path / "field"
    original = (root / "CURRENT").read_bytes()
    manifest = json.loads((root / "manifests" / original.decode("ascii").strip()).read_bytes())
    descriptor = json.loads((root / "objects" / manifest["state_descriptor_sha256"]).read_bytes())
    page = root / "objects" / descriptor["pages"][0]
    page.write_bytes(page.read_bytes() + b" ")
    with pytest.raises(FieldIntelligenceError) as corrupt:
        FieldIntelligenceOwner.migrate_v1(tmp_path)
    assert corrupt.value.code == "MIGRATION_CORRUPT"
    assert (root / "CURRENT").read_bytes() == original


def test_migration_capacity_counts_referenced_numeric_pages(tmp_path: Path) -> None:
    import pytest
    from cassi_field_atlas import FieldIntelligenceError
    from cassi_field_owner import CapacityLimits, FieldIntelligenceOwner

    _legacy_owner(tmp_path)
    root = tmp_path / "field"
    original = (root / "CURRENT").read_bytes()
    manifest = json.loads((root / "manifests" / original.decode("ascii").strip()).read_bytes())
    descriptor_bytes = (root / "objects" / manifest["state_descriptor_sha256"]).read_bytes()
    descriptor = json.loads(descriptor_bytes)
    page_bytes = sum((root / "objects" / digest).stat().st_size for digest in set(descriptor["pages"]))
    closure_bytes = len(descriptor_bytes) + page_bytes
    limits = CapacityLimits(
        max_state_bytes=closure_bytes - 1,
        max_workspace_bytes=closure_bytes - 1,
    )
    with pytest.raises(FieldIntelligenceError) as capacity:
        FieldIntelligenceOwner.migrate_v1(tmp_path, limits=limits)
    assert capacity.value.code == "STATE_CAPACITY"
    assert (root / "CURRENT").read_bytes() == original


def test_interrupted_advance_recovers_once_on_both_publication_boundaries(tmp_path: Path) -> None:
    from unittest.mock import patch
    import pytest
    import cassi_field_owner as persistence

    for boundary in ("CURRENT", "operations"):
        home = tmp_path / boundary
        owner = persistence.FieldIntelligenceOwner(home)
        generation = owner.state.generation
        original_replace = persistence.os.replace

        def interrupted(source: Path, destination: Path) -> None:
            path = Path(destination)
            if path.name == boundary or path.parent.name == boundary:
                raise OSError("simulated publication interruption")
            original_replace(source, destination)

        try:
            with patch.object(persistence.os, "replace", interrupted):
                with pytest.raises(OSError):
                    owner.advance(operation_id="interrupted-beat", ticks=2)
        finally:
            owner.close()
        recovered = persistence.FieldIntelligenceOwner(home)
        try:
            assert recovered.state.generation == generation + 1
            assert recovered.state.resonant_workspace is not None
            assert recovered.state.resonant_workspace.field_ticks == 2
            committed = recovered.state.state_sha256
            replay = recovered.advance(operation_id="interrupted-beat", ticks=2)
            assert replay["checkpoint_receipt"]["replayed"]
            assert recovered.state.state_sha256 == committed
        finally:
            recovered.close()


def test_staged_operation_identity_tampering_quarantines_without_publication(
    tmp_path: Path,
) -> None:
    from unittest.mock import patch

    import pytest

    import cassi_field_owner as persistence
    from cassi_field_atlas import FieldIntelligenceError

    for corruption in ("filename", "semantic"):
        home = tmp_path / corruption
        operation_id = f"staged-{corruption}"
        owner = persistence.FieldIntelligenceOwner(home)
        current_path = owner.checkpoints.current_path
        original_current = current_path.read_bytes()
        original_write = persistence._atomic_write

        def interrupt_current(path: Path, payload: bytes) -> None:
            if path == current_path:
                raise OSError("simulated interruption before CURRENT publication")
            original_write(path, payload)

        try:
            with patch.object(persistence, "_atomic_write", interrupt_current):
                with pytest.raises(OSError):
                    owner.advance(operation_id=operation_id, ticks=1)
        finally:
            owner.close()

        staged_paths = tuple((home / "field" / "staging").iterdir())
        assert len(staged_paths) == 1
        staged_path = staged_paths[0]
        if corruption == "filename":
            replacement_name = "0" * 64
            if staged_path.name == replacement_name:
                replacement_name = "1" * 64
            replacement = staged_path.with_name(replacement_name)
            staged_path.rename(replacement)
            staged_path = replacement
        else:
            staged = json.loads(staged_path.read_bytes())
            staged["semantic_sha256"] = "0" * 64
            staged_path.write_bytes(canonical_json_bytes(staged))
        corrupted_stage = staged_path.read_bytes()

        with pytest.raises(FieldIntelligenceError) as rejected:
            persistence.FieldIntelligenceOwner(home)
        assert rejected.value.code == "STATE_QUARANTINED"
        assert rejected.value.details["reason"] == "STAGE_INVALID"
        assert current_path.read_bytes() == original_current
        assert staged_path.read_bytes() == corrupted_stage
        operation_path = (
            home
            / "field"
            / "operations"
            / hashlib.sha256(operation_id.encode("utf-8")).hexdigest()
        )
        assert not operation_path.exists()


def test_compacted_unsequenced_retry_cannot_advance_restarted_owner(tmp_path: Path) -> None:
    import pytest
    from cassi_field_atlas import FieldIntelligenceError
    from cassi_field_owner import CapacityLimits, FieldIntelligenceOwner

    limits = CapacityLimits(max_history_entries=3)
    owner = FieldIntelligenceOwner(tmp_path, limits=limits)
    try:
        owner.advance(operation_id="old-unsequenced", source_enabled=False)
        for index in range(12):
            owner.advance(operation_id=f"heartbeat:{index}", source_enabled=False)
        committed = owner.state.state_sha256
    finally:
        owner.close()
    recovered = FieldIntelligenceOwner(tmp_path, limits=limits)
    try:
        with pytest.raises(FieldIntelligenceError) as replay:
            recovered.advance(operation_id="old-unsequenced", source_enabled=False)
        assert replay.value.code == "REPLAY_FLOOR"
        assert recovered.state.state_sha256 == committed
    finally:
        recovered.close()


def test_migration_respects_revocation_fence_and_exact_source_integrity(tmp_path: Path) -> None:
    import pytest
    from cassi_field_atlas import FieldIntelligenceError
    from cassi_field_owner import FieldIntelligenceOwner

    for failure in ("revocation", "source"):
        home = tmp_path / failure
        _legacy_owner(home)
        head = (home / "field" / "CURRENT").read_bytes()
        if failure == "revocation":
            fence_path = home / "field" / "REVOCATION"
            fence = json.loads(fence_path.read_bytes())
            fence["generation"] += 1
            fence_path.write_bytes(canonical_json_bytes(fence))
            expected_error = "MIGRATION_PENDING"
        else:
            blob = next((home / "evidence" / "blobs").iterdir())
            blob.write_bytes(b"corrupt source")
            expected_error = "SOURCE_CORRUPT"
        with pytest.raises(FieldIntelligenceError) as rejected:
            FieldIntelligenceOwner.migrate_v1(home)
        assert rejected.value.code == expected_error
        assert (home / "field" / "CURRENT").read_bytes() == head


def test_interrupted_explicit_migration_recovers_verified_successor(tmp_path: Path) -> None:
    from unittest.mock import patch
    import pytest
    import cassi_field_owner as persistence

    _, learned, _ = _legacy_owner(tmp_path)
    original_write = persistence._atomic_write

    def interrupted(path: Path, encoded: bytes) -> None:
        if path.name == "CURRENT":
            raise OSError("simulated migration interruption")
        original_write(path, encoded)

    with patch.object(persistence, "_atomic_write", interrupted):
        with pytest.raises(OSError):
            persistence.FieldIntelligenceOwner.migrate_v1(tmp_path)
    recovered = persistence.FieldIntelligenceOwner(tmp_path)
    try:
        assert canonical_json_bytes([chart.as_dict() for chart in recovered.state.charts]) == learned
        assert recovered.state.resonant_workspace is not None
        assert recovered.state.resonant_workspace.field_ticks == 0
        recovered.advance(operation_id="first-migrated-beat")
        assert recovered.state.resonant_workspace.field_ticks == 1
    finally:
        recovered.close()


def test_interrupted_publication_then_compaction_retains_recovered_head(tmp_path: Path) -> None:
    """A staged head recovered after a crash remains a GC root for later compaction."""
    from unittest.mock import patch

    import pytest
    import cassi_field_owner as persistence

    limits = persistence.CapacityLimits(max_history_entries=3)
    owner = persistence.FieldIntelligenceOwner(tmp_path, limits=limits)
    original_write = persistence._atomic_write

    def interrupted(path: Path, encoded: bytes) -> None:
        if path.name == "CURRENT":
            raise OSError("simulated publication interruption")
        original_write(path, encoded)

    try:
        with patch.object(persistence, "_atomic_write", interrupted):
            with pytest.raises(OSError):
                owner.advance(operation_id="crash:0", source_enabled=False)
    finally:
        owner.close()

    recovered = persistence.FieldIntelligenceOwner(tmp_path, limits=limits)
    try:
        for index in range(12):
            recovered.advance(
                operation_id=f"after-crash:{index}",
                source_enabled=False,
            )
        committed = recovered.state.state_sha256
    finally:
        recovered.close()

    reopened = persistence.FieldIntelligenceOwner(tmp_path, limits=limits)
    try:
        assert reopened.state.state_sha256 == committed
    finally:
        reopened.close()


def test_failed_immutable_flush_cannot_publish_partial_checkpoint(tmp_path: Path) -> None:
    from unittest.mock import patch

    import pytest
    import cassi_field_owner as persistence

    owner = persistence.FieldIntelligenceOwner(tmp_path)
    original_write = persistence._atomic_write
    before = owner.state.state_sha256

    def interrupted(path: Path, encoded: bytes) -> None:
        if path.parent == owner.checkpoints.objects:
            raise OSError("simulated immutable object flush failure")
        original_write(path, encoded)

    try:
        with patch.object(persistence, "_atomic_write", interrupted):
            with pytest.raises(OSError):
                owner.advance(operation_id="flush:0", source_enabled=False)
    finally:
        owner.close()
    recovered = persistence.FieldIntelligenceOwner(tmp_path)
    try:
        assert recovered.state.state_sha256 == before
        recovered.advance(operation_id="flush:0", source_enabled=False)
        assert recovered.state.resonant_workspace is not None
        assert recovered.state.resonant_workspace.field_ticks == 1
    finally:
        recovered.close()


def test_temporal_pool_impulse_is_work_bounded_and_propagates() -> None:
    import pytest

    from cassi_resonant_field import (
        ResonantWorkspace,
        advance_workspace,
        apply_pool_impulse,
        initial_workspace,
        score_pool_probes,
        inspect_workspace,
    )

    signal = [3.0 ** -0.5, 0.0, 0.0, 3.0 ** -0.5, 0.0, 0.0, 3.0 ** -0.5]
    initial = initial_workspace()
    coupled, receipt = apply_pool_impulse(
        initial,
        pool_signal=signal,
        work_budget=1e-3,
        evidence_tick=1,
        event_kind="formation",
    )
    assert receipt["accepted"] is True
    assert receipt["applied_work"] == pytest.approx(1e-3, abs=1e-12)
    assert receipt["balance_defect"] == pytest.approx(0.0, abs=1e-12)
    assert coupled.field_ticks == 0
    assert coupled.evidence_tick == 1
    assert coupled.ledger["temporal_coupling_work"] == pytest.approx(1e-3)
    assert ResonantWorkspace.from_dict(coupled.as_dict()).state_sha256 == coupled.state_sha256
    before_score = coupled.state_sha256
    scores = score_pool_probes(
        coupled,
        {
            "matching": signal,
            "orthogonal": [0.0, 1.0, 1.0, 0.0, 1.0, 0.0, 0.0],
        },
    )
    by_id = {row["probe_id"]: row for row in scores["scores"]}
    assert by_id["matching"]["compatibility"] > 0.0
    assert by_id["orthogonal"]["compatibility"] == pytest.approx(0.0)
    assert scores["workspace_state_sha256"] == before_score
    assert scores["workspace_unchanged"] is True
    assert coupled.state_sha256 == before_score

    immediate = inspect_workspace(coupled)
    assert [
        row["power"] > 0.0 for row in immediate["pool_sample"]
    ] == [True, False, False, True, False, False, True]

    propagated, advance = advance_workspace(
        coupled,
        ticks=8,
        source_enabled=False,
    )
    control, _ = advance_workspace(
        initial,
        ticks=8,
        source_enabled=False,
    )
    assert all(
        row["power"] > 0.0
        for row in inspect_workspace(propagated)["pool_sample"]
    )
    assert all(
        row["power"] == 0.0
        for row in inspect_workspace(control)["pool_sample"]
    )
    assert advance["end_energy"] < receipt["end_energy"]
    assert advance["balance_defect"] == pytest.approx(0.0, abs=1e-12)


def test_owner_atomically_couples_temporal_formation_and_withdrawal(
    tmp_path: Path,
) -> None:
    import pytest

    from cassi_field_atlas import AtlasState
    from cassi_field_owner import FieldIntelligenceOwner, SourceInput

    owner = FieldIntelligenceOwner(
        tmp_path,
        initial_state=AtlasState(resonant_workspace=None),
    )
    try:
        owner.configure_temporal(
            "configure",
            memory_id="release-memory",
            action_ids=("prime", "align", "open"),
            observation_ids=("primed", "aligned", "opened"),
            max_states=8,
        )
        pending = owner.condense_temporal_skill(
            "register",
            memory_id="release-memory",
            skill_id="release",
            goal_observations=("opened",),
        )
        assert pending["receipt"]["status"] == "pending"
        assert pending["receipt"]["resonance_coupling"]["applied"] is False
        assert owner.state.resonant_workspace is None

        content = canonical_json_bytes({
            "schema": "cassifi.temporal-episode.v1",
            "steps": [
                {"action": "prime", "observation": "primed"},
                {"action": "align", "observation": "aligned"},
                {"action": "open", "observation": "opened"},
            ],
        })
        learned = owner.learn_temporal(
            "learn",
            memory_id="release-memory",
            source=SourceInput(
                source_id="release-source",
                content=content,
                media_type="application/json",
                codec="utf-8",
                observed_timestamp="2026-09-09T00:00:00Z",
                scope="temporal-resonance-test",
                claim_category="controlled-observation",
                fidelity="exact-record",
                labels=("test",),
            ),
        )
        coupling = learned["receipt"]["resonance_coupling"]
        assert learned["receipt"]["formed_skills"] == ["release"]
        assert coupling["formed_skills"] == ["release"]
        assert coupling["withdrawn_skills"] == []
        assert coupling["total_applied_work"] == pytest.approx(1e-3)
        formation_event = next(
            event
            for event in coupling["events"]
            if event["event_kind"] == "formation"
        )
        assert any(
            event["event_kind"] == "goal-observation"
            for event in coupling["events"]
        )
        assert any(
            event["event_kind"] == "mismatch-observation"
            for event in coupling["events"]
        )
        assert coupling["admitted_step_count"] == 3
        assert coupling["evidence_event_id"]
        assert owner.state.resonant_workspace is not None
        formed_workspace_sha256 = owner.state.resonant_workspace.state_sha256
        formed_state_sha256 = owner.state.state_sha256
        assert owner.inspect_temporal(
            "release-memory",
            skill_id="release",
        )["skill_pool_signal"]["pool_signal"] == list(
            formation_event["impulse"]["pool_signal"]
        )
    finally:
        owner.close()

    restored = FieldIntelligenceOwner(tmp_path)
    try:
        assert restored.state.state_sha256 == formed_state_sha256
        assert restored.state.resonant_workspace is not None
        assert restored.state.resonant_workspace.state_sha256 == formed_workspace_sha256
        withdrawn = restored.condense_temporal_skill(
            "withdraw",
            memory_id="release-memory",
            skill_id="release",
            goal_observations=("opened",),
            forbidden_observations=("aligned",),
        )
        coupling = withdrawn["receipt"]["resonance_coupling"]
        assert withdrawn["receipt"]["status"] == "pending"

        assert coupling["formed_skills"] == []
        assert coupling["withdrawn_skills"] == ["release"]
        assert coupling["total_applied_work"] == pytest.approx(1e-3)
        assert coupling["events"][0]["event_kind"] == "withdrawal"
        assert restored.state.resonant_workspace.ledger[
            "temporal_coupling_work"
        ] == pytest.approx(2e-3)
        assert restored.state.resonant_workspace.ledger[
            "temporal_withdrawal_work"
        ] == pytest.approx(1e-3)
    finally:
        restored.close()
def test_admitted_outcomes_continue_to_change_the_wave_after_skill_formation(
    tmp_path: Path,
) -> None:
    import pytest

    from cassi_field_atlas import AtlasState
    from cassi_field_owner import FieldIntelligenceOwner, SourceInput

    steps = [
        {"action": "prime", "observation": "primed"},
        {"action": "align", "observation": "aligned"},
        {"action": "open", "observation": "opened"},
    ]

    def episode_source(source_id: str) -> SourceInput:
        return SourceInput(
            source_id=source_id,
            content=canonical_json_bytes({
                "schema": "cassifi.temporal-episode.v1",
                "steps": steps,
            }),
            media_type="application/json",
            codec="utf-8",
            observed_timestamp="2026-09-09T00:00:00Z",
            scope="temporal-outcome-test",
            claim_category="controlled-observation",
            fidelity="exact-record",
            labels=("test",),
        )

    owner = FieldIntelligenceOwner(
        tmp_path,
        initial_state=AtlasState(resonant_workspace=None),
    )
    try:
        owner.configure_temporal(
            "configure",
            memory_id="outcome-memory",
            action_ids=("prime", "align", "open"),
            observation_ids=("primed", "aligned", "opened"),
            max_states=8,
        )
        owner.condense_temporal_skill(
            "register",
            memory_id="outcome-memory",
            skill_id="release",
            goal_observations=("opened",),
        )
        formed = owner.learn_temporal(
            "learn-first",
            memory_id="outcome-memory",
            source=episode_source("first-source"),
        )
        assert formed["receipt"]["formed_skills"] == ["release"]
        assert owner.state.resonant_workspace is not None
        before_sha256 = owner.state.resonant_workspace.state_sha256
        before_ledger = dict(owner.state.resonant_workspace.ledger)

        repeated = owner.learn_temporal(
            "learn-repeated-outcome",
            memory_id="outcome-memory",
            source=episode_source("second-source"),
        )
        coupling = repeated["receipt"]["resonance_coupling"]
        assert repeated["receipt"]["formed_skills"] == []
        assert repeated["receipt"]["withdrawn_skills"] == []
        assert coupling["formed_skills"] == []
        assert coupling["withdrawn_skills"] == []
        assert coupling["admitted_step_count"] == len(steps)
        assert coupling["total_applied_work"] == pytest.approx(1e-3)
        assert {
            event["event_kind"] for event in coupling["events"]
        } == {"context-observation", "goal-observation"}
        assert all(
            event["impulse"]["accepted"] is True
            for event in coupling["events"]
        )
        assert owner.state.resonant_workspace.state_sha256 != before_sha256
        after_sha256 = owner.state.state_sha256
        after_workspace_sha256 = owner.state.resonant_workspace.state_sha256
        assert owner.state.resonant_workspace.ledger[
            "temporal_outcome_work"
        ] == pytest.approx(
            before_ledger.get("temporal_outcome_work", 0.0) + 1e-3
        )
        assert owner.state.resonant_workspace.ledger[
            "temporal_formation_work"
        ] == pytest.approx(before_ledger["temporal_formation_work"])
        evidence_count = owner.evidence.event_count

        replayed = owner.learn_temporal(
            "learn-repeated-outcome",
            memory_id="outcome-memory",
            source=episode_source("second-source"),
        )
        assert replayed["receipt"] == repeated["receipt"]
        assert replayed["checkpoint_receipt"] == {
            **repeated["checkpoint_receipt"],
            "replayed": True,
        }
        assert owner.state.state_sha256 == after_sha256
        assert owner.state.resonant_workspace.state_sha256 == after_workspace_sha256
        assert owner.evidence.event_count == evidence_count
    finally:
        owner.close()



def test_resonant_selector_is_read_only_order_invariant_and_safety_bounded(
    tmp_path: Path,
) -> None:
    import pytest

    from cassi_field_atlas import canonical_json_bytes
    from cassi_field_owner import (
        FieldIntelligenceOwner,
        FieldIntelligenceSurface,
        RPC_SCHEMA,
        SourceInput,
    )
    from cassi_resonant_field import apply_pool_impulse, initial_workspace

    def episode(name: str, steps: list[dict[str, str]]) -> SourceInput:
        return SourceInput(
            source_id=name,
            content=canonical_json_bytes(
                {"schema": "cassifi.temporal-episode.v1", "steps": steps}
            ),
            media_type="application/json",
            codec="utf-8",
            observed_timestamp=name,
            scope="resonant-selector-test",
            claim_category="controlled-observation",
            fidelity="exact-record",
            labels=("test",),
        )

    operations = [
        {
            "action": "short",
            "authorized": True,
            "feasible": True,
            "represented_forbidden": False,
        },
        {
            "action": "long",
            "authorized": True,
            "feasible": True,
            "represented_forbidden": False,
        },
    ]
    owner = FieldIntelligenceOwner(tmp_path)
    try:
        owner.configure_temporal(
            "selector-configure",
            memory_id="selector",
            action_ids=("short", "long", "continue"),
            observation_ids=("done-a", "stage", "done-b"),
            max_states=16,
        )
        owner.learn_temporal(
            "selector-learn-a",
            memory_id="selector",
            source=episode(
                "selector-a",
                [{"action": "short", "observation": "done-a"}],
            ),
        )
        owner.learn_temporal(
            "selector-learn-b",
            memory_id="selector",
            source=episode(
                "selector-b",
                [
                    {"action": "long", "observation": "stage"},
                    {"action": "continue", "observation": "done-b"},
                ],
            ),
        )
        owner.condense_temporal_skill(
            "selector-skill-a",
            memory_id="selector",
            skill_id="skill-a",
            goal_observations=("done-a",),
        )
        owner.condense_temporal_skill(
            "selector-skill-b",
            memory_id="selector",
            skill_id="skill-b",
            goal_observations=("done-b",),
        )

        assert owner.state.resonant_workspace is not None
        profile = owner.state.resonant_workspace.profile
        zero = initial_workspace(profile)
        zero_successor = owner.state.with_transition(
            "selector-zero-control",
            {},
            resonant_workspace=zero,
        )
        owner._publish(
            operation_id="selector-zero-control",
            successor=zero_successor,
            event_id=None,
            transition={"kind": "selector-zero-control"},
        )
        before = owner.state.encode_bundle()

        one = owner.select_temporal_action(
            "selector",
            skill_ids=("skill-a",),
            operations=operations,
        )
        assert one["status"] == "selected"
        assert one["reason"] == "categorical-singleton"
        assert one["selected"]["action"] == "short"
        assert one["resonant_scoring"] is None
        assert owner.state.encode_bundle() == before

        zero_choice = owner.select_temporal_action(
            "selector",
            skill_ids=("skill-a", "skill-b"),
            operations=operations,
        )
        assert zero_choice["status"] == "unresolved"
        assert zero_choice["reason"] == "insufficient-resonant-margin"
        assert zero_choice["selection_margin"] == pytest.approx(0.0)
        assert owner.state.encode_bundle() == before

        signal_b = owner.inspect_temporal(
            "selector", skill_id="skill-b"
        )["skill_pool_signal"]["pool_signal"]
        wave_b, _ = apply_pool_impulse(
            zero,
            pool_signal=signal_b,
            work_budget=1e-3,
            evidence_tick=owner.state.logical_tick,
            event_kind="formation",
        )
        wave_b_successor = owner.state.with_transition(
            "selector-wave-b",
            {},
            resonant_workspace=wave_b,
        )
        owner._publish(
            operation_id="selector-wave-b",
            successor=wave_b_successor,
            event_id=None,
            transition={"kind": "selector-wave-b"},
        )
        before_choice = owner.state.encode_bundle()
        selected_b = owner.select_temporal_action(
            "selector",
            skill_ids=("skill-a", "skill-b"),
            operations=operations,
        )
        reversed_b = owner.select_temporal_action(
            "selector",
            skill_ids=("skill-b", "skill-a"),
            operations=list(reversed(operations)),
        )
        assert selected_b["status"] == "selected"
        assert selected_b["reason"] == "resonant-compatibility"
        assert selected_b["selected"]["skill_id"] == "skill-b"
        assert reversed_b["selected"] == selected_b["selected"]
        assert reversed_b["candidate_set_sha256"] == selected_b["candidate_set_sha256"]
        assert reversed_b["candidates"] == selected_b["candidates"]
        assert (
            reversed_b["presentation_order_sha256"]
            != selected_b["presentation_order_sha256"]
        )
        assert owner.state.encode_bundle() == before_choice

        forbidden = [
            operations[0],
            {**operations[1], "represented_forbidden": True},
        ]
        safety = owner.select_temporal_action(
            "selector",
            skill_ids=("skill-a", "skill-b"),
            operations=forbidden,
        )
        assert safety["status"] == "selected"
        assert safety["reason"] == "categorical-singleton"
        assert safety["selected"]["skill_id"] == "skill-a"
        assert any(
            row["skill_id"] == "skill-b"
            and row["exclusion_reason"] == "represented-forbidden"
            for row in safety["excluded"]
        )

        signal_a = owner.inspect_temporal(
            "selector", skill_id="skill-a"
        )["skill_pool_signal"]["pool_signal"]
        wave_a, _ = apply_pool_impulse(
            zero,
            pool_signal=signal_a,
            work_budget=1e-3,
            evidence_tick=owner.state.logical_tick,
            event_kind="formation",
        )
        wave_a_successor = owner.state.with_transition(
            "selector-wave-a",
            {},
            resonant_workspace=wave_a,
        )
        owner._publish(
            operation_id="selector-wave-a",
            successor=wave_a_successor,
            event_id=None,
            transition={"kind": "selector-wave-a"},
        )
        selected_a = owner.select_temporal_action(
            "selector",
            skill_ids=("skill-a", "skill-b"),
            operations=operations,
        )
        assert selected_a["status"] == "selected"
        assert selected_a["selected"]["skill_id"] == "skill-a"
        assert selected_a["selected"]["action"] == "short"
        before_surface = owner.state.encode_bundle()
        surface_result = FieldIntelligenceSurface(owner).handle({
            "schema": RPC_SCHEMA,
            "request_id": "selector-surface",
            "operation": "select_temporal_action",
            "params": {
                "memory_id": "selector",
                "skill_ids": ["skill-a", "skill-b"],
                "operations": operations,
                "expected_state_sha256": owner.state.state_sha256,
            },
        })["result"]
        assert surface_result["selected"] == selected_a["selected"]
        assert owner.state.encode_bundle() == before_surface
    finally:
        owner.close()


def test_resonant_regional_advance_pauses_and_restarts_exactly() -> None:
    import json

    from cassi_resonant_field import (
        REGIONAL_KERNEL_MAX_WORK,
        REGIONAL_KERNEL_NAME,
        REGIONAL_RESULT_SCHEMA,
        REGIONAL_STATE_SCHEMA,
        initial_workspace,
        regional_kernel,
        regional_state,
    )

    workspace = initial_workspace()
    paused_task = regional_state(
        workspace,
        ticks=2,
        demand=0.35,
        source_enabled=True,
    )
    assert REGIONAL_KERNEL_NAME == "numerical.resonant"
    assert REGIONAL_STATE_SCHEMA.endswith("-state.v1")
    assert REGIONAL_RESULT_SCHEMA.endswith("-result.v1")
    paused = regional_kernel(paused_task, {}, 1)
    assert paused.status == "yield"
    assert paused.work == 1
    assert paused.state["continuation"]["operation"] == "step"
    encoded = json.dumps(paused.state, sort_keys=True, allow_nan=False)
    decoded = json.loads(encoded)

    resumed = decoded
    resumed_receipt = paused
    while resumed_receipt.status == "yield":
        resumed_receipt = regional_kernel(resumed, {}, REGIONAL_KERNEL_MAX_WORK)
        resumed = json.loads(json.dumps(resumed_receipt.state, sort_keys=True, allow_nan=False))

    uninterrupted_receipt = regional_kernel(
        regional_state(workspace, ticks=2, demand=0.35, source_enabled=True),
        {},
        REGIONAL_KERNEL_MAX_WORK,
    )
    assert resumed_receipt.status == uninterrupted_receipt.status == "done"
    assert resumed_receipt.state["wave_words"] == uninterrupted_receipt.state["wave_words"]
    assert resumed_receipt.state["phases"] == uninterrupted_receipt.state["phases"]
    assert resumed_receipt.state["activity"] == uninterrupted_receipt.state["activity"]
    assert resumed_receipt.output["energy_roundoff_allowance"] == uninterrupted_receipt.output["energy_roundoff_allowance"]
    assert resumed_receipt.output["logical_work"] == uninterrupted_receipt.output["logical_work"]


def test_dual_helical_packet_hierarchy_roundtrips_and_rejects_mixed_sources() -> None:
    import json

    import numpy as np
    import pytest

    from cassi_resonant_field import (
        ResonantNumericalError,
        ResonantWorkspace,
        analyze_helical_packet,
        compose_helical_packets,
        helical_packet_channels,
        split_helical_packet,
    )

    workspace = ResonantWorkspace()
    profile = workspace.profile
    count = profile.port_count
    page = workspace.field.reshape(-1)
    index = np.arange(count, dtype=np.float64)
    for lane, values in enumerate((
        np.sin(0.17 * index),
        np.cos(0.11 * index),
        0.3 * np.sin(0.07 * index * index),
        -0.2 * np.cos(0.13 * index),
    )):
        page[lane:9 * count:9] = values
    workspace = ResonantWorkspace(
        profile=profile,
        field_page=page.reshape(profile.page_shape),
    )

    original_sha256 = workspace.state_sha256
    parent = analyze_helical_packet(workspace)
    left, right = split_helical_packet(parent)
    left = json.loads(json.dumps(left, allow_nan=False))
    right = json.loads(json.dumps(right, allow_nan=False))
    recomposed = compose_helical_packets(left, right)

    assert workspace.state_sha256 == original_sha256
    assert len(parent["modes"]) == count
    assert len(parent["coefficients"]) == count
    assert parent["support"] == {"start": 0, "stop": count}
    assert left["support"]["stop"] == right["support"]["start"]
    np.testing.assert_allclose(
        helical_packet_channels(recomposed),
        helical_packet_channels(parent),
        rtol=0.0,
        atol=2e-15,
    )
    assert recomposed["coefficient_squared_norm"] == pytest.approx(
        parent["coefficient_squared_norm"],
        rel=2e-15,
        abs=2e-15,
    )

    malformed = dict(parent)
    malformed["channels"] = np.asarray(parent["channels"])
    with pytest.raises(
        ResonantNumericalError,
        match="channels are incompatible",
    ):
        split_helical_packet(malformed)

    changed_page = workspace.field
    changed_page[0, 0, 0] += 1.0
    changed = ResonantWorkspace(profile=profile, field_page=changed_page)
    _other_left, other_right = split_helical_packet(
        analyze_helical_packet(changed)
    )
    with pytest.raises(
        ResonantNumericalError,
        match="one profile and source state",
    ):
        compose_helical_packets(left, other_right)


def test_helical_packet_impulse_matches_the_regional_field_transition() -> None:
    import numpy as np
    import pytest

    from cassi_resonant_field import (
        REGIONAL_KERNEL_MAX_WORK,
        analyze_helical_packet,
        apply_helical_packet_impulse,
        initial_workspace,
        regional_kernel,
        regional_state,
    )

    workspace = initial_workspace()
    payload = {
        "path": "LR",
        "component": "detail",
        "flow_signal": [0.6, -0.8],
        "work_budget": 1e-3,
        "evidence_tick": 7,
        "event_kind": "context-observation",
    }
    successor, receipt = apply_helical_packet_impulse(workspace, **payload)
    regional = regional_kernel(
        regional_state(workspace, packet_impulse=payload),
        {},
        REGIONAL_KERNEL_MAX_WORK,
    )

    count = workspace.profile.port_count
    page = successor.field.reshape(-1)
    expected_words = np.concatenate((
        page[0:9 * count:9],
        page[1:9 * count:9],
        page[2:9 * count:9],
        page[3:9 * count:9],
    ))
    assert regional.status == "done"
    assert regional.work == 1
    assert regional.output["operation"] == "packet-impulse"
    assert regional.output["basis_sha256"] == receipt["basis_sha256"]
    assert regional.output["support"] == receipt["support"]
    assert regional.output["flow_signal"] == pytest.approx([0.6, -0.8])
    assert regional.output["applied_work"] == pytest.approx(
        payload["work_budget"],
        abs=receipt["energy_roundoff_allowance"],
    )
    assert receipt["applied_work"] == pytest.approx(
        payload["work_budget"],
        abs=receipt["energy_roundoff_allowance"],
    )
    assert successor.evidence_tick == regional.output["evidence_tick"] == 7
    np.testing.assert_allclose(
        regional.state["wave_words"]["values"],
        expected_words,
        rtol=0.0,
        atol=1e-15,
    )
    packet = analyze_helical_packet(successor, path=payload["path"])
    coefficients = np.asarray(packet["coefficients"])
    assert np.linalg.norm(coefficients[:, 2:]) > 0.0
    assert successor.ledger["helical_packet_work"] == pytest.approx(1e-3)
