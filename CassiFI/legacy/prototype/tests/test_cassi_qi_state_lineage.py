from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cassi_qi_field import QiFlowStateV3
from cassi_qi_profile import QiFlowProfile
from cassi_qi_state_lineage import (
    QiParentSessionSnapshot,
    QiStateLineageError,
    fork_state_lineage,
)
from run_cassi_qi_state_lineage import run
from verify_cassi_qi_state_lineage import LineageVerificationError, verify_artifact


def profile(name: str, *, receipt_bytes: int | None = None) -> QiFlowProfile:
    overrides = None if receipt_bytes is None else {"capacity": {"max_receipt_bytes": receipt_bytes}}
    return QiFlowProfile.from_defaults(profile_id=name, overrides=overrides)


def parent_snapshot(parent_profile: QiFlowProfile, payload: bytes) -> QiParentSessionSnapshot:
    return QiParentSessionSnapshot(
        session_id="parent-session",
        head_sha256="e" * 64,
        profile=parent_profile,
        state_object_bytes=payload,
        protocol_epoch="parent-protocol",
        world_id="parent-world",
        episode_id="parent-episode",
        source_identity_sha256="a" * 64,
        clock_sha256="c" * 64,
    )


def fork(parent: QiParentSessionSnapshot, child_profile: QiFlowProfile):
    return fork_state_lineage(
        parent,
        new_profile=child_profile,
        new_session_id="child-session",
        reason="operator-approved new session",
        new_protocol_epoch="child-protocol",
        new_world_id="child-world",
        new_episode_id="child-episode",
        new_source_identity_sha256="b" * 64,
        new_clock_sha256="d" * 64,
        operator_id="operator-test",
    )


class StateLineageForkTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.parent_profile = profile("parent-profile")
        cls.state_bytes = QiFlowStateV3.create(
            cls.parent_profile,
            batch_lanes=1,
        ).dump_bytes(cls.parent_profile)

    def test_non_state_profile_difference_copies_exact_object(self) -> None:
        child_profile = profile("child-profile")
        result = fork(parent_snapshot(self.parent_profile, self.state_bytes), child_profile)
        self.assertEqual(result.state_object_bytes, self.state_bytes)
        receipt = result.receipt.payload()
        self.assertTrue(receipt["exact_state_object_copy"])
        self.assertEqual(receipt["parent_state_object_sha256"], receipt["child_state_object_sha256"])
        self.assertEqual(receipt["logical_tick"], 0)
        self.assertEqual(receipt["cycle_number"], 0)
        self.assertTrue(any(row["json_pointer"] == "/profile_id" for row in receipt["differing_profile_leaves"]))

    def test_state_consuming_profile_difference_rejects(self) -> None:
        changed = profile("child-profile", receipt_bytes=32769)
        with self.assertRaises(QiStateLineageError):
            fork(parent_snapshot(self.parent_profile, self.state_bytes), changed)

    def test_mutated_state_object_rejects_before_child(self) -> None:
        mutated = bytearray(self.state_bytes)
        mutated[-1] ^= 1
        with self.assertRaises(QiStateLineageError):
            fork(parent_snapshot(self.parent_profile, bytes(mutated)), profile("child-profile"))

    def test_pending_or_sealed_parent_rejects(self) -> None:
        base = parent_snapshot(self.parent_profile, self.state_bytes)
        pending = QiParentSessionSnapshot(
            **{field: getattr(base, field) for field in base.__dataclass_fields__ if field not in {"pending_outbox_sha256", "pending_applied_efference_sha256", "lineage_status"}},
            pending_outbox_sha256="outbox",
        )
        with self.assertRaises(QiStateLineageError):
            fork(pending, profile("child-profile"))
        sealed = QiParentSessionSnapshot(
            **{field: getattr(base, field) for field in base.__dataclass_fields__ if field not in {"pending_outbox_sha256", "pending_applied_efference_sha256", "lineage_status"}},
            lineage_status="indeterminate_sealed",
        )
        with self.assertRaises(QiStateLineageError):
            fork(sealed, profile("child-profile"))

    def test_parent_head_requires_hash(self) -> None:
        base = parent_snapshot(self.parent_profile, self.state_bytes)
        with self.assertRaises(QiStateLineageError):
            replace(base, head_sha256="invalid-parent-head")

    def test_child_must_reset_every_protocol_identity(self) -> None:
        parent = parent_snapshot(self.parent_profile, self.state_bytes)
        with self.assertRaises(QiStateLineageError):
            fork_state_lineage(
                parent,
                new_profile=profile("child-profile"),
                new_session_id="child-session",
                reason="fork",
                new_protocol_epoch="parent-protocol",
                new_world_id="child-world",
                new_episode_id="child-episode",
                new_source_identity_sha256="child-source",
                new_clock_sha256="child-clock",
            )

    def test_independent_verifier_rejects_mutated_checkpoint_artifact(self) -> None:
        with TemporaryDirectory() as temporary:
            result = run(output_root=temporary)
            artifact = Path(temporary) / result["run_id"]
            checkpoint = artifact / "gates" / "g12l-state-lineage" / "state" / "child-state.bin"
            mutated = bytearray(checkpoint.read_bytes())
            mutated[-1] ^= 1
            checkpoint.write_bytes(mutated)
            with self.assertRaises(LineageVerificationError):
                verify_artifact(artifact)

    def test_rejection_controls_cover_required_mutation_boundaries(self) -> None:
        required = {
            "mutated-state-object",
            "state-consuming-profile-drift",
            "receipt-mutation-parent_head_sha256",
            "receipt-mutation-parent_state_object_sha256",
            "receipt-mutation-child_state_object_sha256",
            "receipt-mutation-state_consuming_subhashes",
            "receipt-mutation-layout_identity_sha256",
            "receipt-mutation-operator_identity_sha256",
            "receipt-mutation-schema_identity_sha256",
            "receipt-mutation-backend_identity_sha256",
            "receipt-mutation-source_profile_identity_sha256",
            "receipt-mutation-old_source_identity_sha256",
            "receipt-mutation-new_source_identity_sha256",
            "receipt-mutation-compatibility_proof",
            "receipt-mutation-reset_reason",
            "receipt-mutation-differing_profile_leaves",
            "receipt-mutation-parent_session_id",
        }
        with TemporaryDirectory() as temporary:
            result = run(output_root=temporary)
            artifact = Path(temporary) / result["run_id"]
            lineage = json.loads(
                (artifact / "gates" / "g12l-state-lineage" / "lineage.json").read_text(
                    encoding="utf-8"
                )
            )
        controls = {row["control_id"]: row for row in lineage["mutation_controls"]}
        self.assertTrue(required <= controls.keys())
        self.assertTrue(all(controls[name]["observed"] == "REJECT" for name in required))


if __name__ == "__main__":
    unittest.main()
