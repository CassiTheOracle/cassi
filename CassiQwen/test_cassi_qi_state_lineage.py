from __future__ import annotations

import unittest

from cassi_qi_field import QiFlowStateV3
from cassi_qi_profile import QiFlowProfile
from cassi_qi_state_lineage import (
    QiParentSessionSnapshot,
    QiStateLineageError,
    fork_state_lineage,
)


def profile(name: str, *, receipt_bytes: int | None = None) -> QiFlowProfile:
    overrides = None if receipt_bytes is None else {"capacity": {"max_receipt_bytes": receipt_bytes}}
    return QiFlowProfile.from_defaults(profile_id=name, overrides=overrides)


def parent_snapshot(parent_profile: QiFlowProfile, payload: bytes) -> QiParentSessionSnapshot:
    return QiParentSessionSnapshot(
        session_id="parent-session",
        head_sha256="parent-head",
        profile=parent_profile,
        state_object_bytes=payload,
        protocol_epoch="parent-protocol",
        world_id="parent-world",
        episode_id="parent-episode",
        source_identity_sha256="parent-source",
        clock_sha256="parent-clock",
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
        new_source_identity_sha256="child-source",
        new_clock_sha256="child-clock",
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


if __name__ == "__main__":
    unittest.main()
