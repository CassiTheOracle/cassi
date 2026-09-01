from __future__ import annotations

import unittest

from cassi_qi_transaction_model import (
    ExternalTruth,
    QiPreparedTransaction,
    QiTransactionError,
    QiTransactionState,
    explore_transaction_model,
)


def prepared(caller: str = "A") -> QiPreparedTransaction:
    return QiPreparedTransaction(
        caller_id=caller,
        retry_key=f"retry-{caller}",
        request_sha256=f"request-{caller}",
        predecessor_head=0,
        ingress_cursor=3,
        response_sha256=f"response-{caller}",
        proposal_sha256=f"proposal-{caller}",
        outbox_sha256=f"outbox-{caller}",
    )


class TransactionModelTest(unittest.TestCase):
    def test_explorer_covers_every_declared_cross_product(self) -> None:
        receipt = explore_transaction_model()
        self.assertEqual(receipt.schedules_explored, 2 * 12 * 3 * 6)
        self.assertFalse(receipt.invariant_failures)
        self.assertEqual(len(receipt.covered_crash_cases), 12)
        self.assertEqual(len(receipt.covered_replay_cases), 3)
        self.assertEqual(len(receipt.covered_ack_cases), 6)
        self.assertEqual(len(receipt.covered_interleavings), receipt.schedules_explored)
        self.assertIn("indeterminate-seal", receipt.covered_seal_cases)
        self.assertIn("applied-efference", receipt.covered_efference_cases)
        self.assertEqual({row["result"] for row in receipt.invariants}, {"pass"})
        payload = receipt.payload()
        self.assertEqual(payload["caller_count"], 2)
        self.assertEqual(len(payload["self_sha256"]), 64)

    def test_commit_a_is_cas_and_retry_exact(self) -> None:
        state, result = QiTransactionState().commit_a(prepared("A"))
        self.assertEqual(result, "committed")
        replay, result = state.commit_a(prepared("A"))
        self.assertIs(replay, state)
        self.assertEqual(result, "replay")
        with self.assertRaises(QiTransactionError):
            state.commit_a(prepared("B"))

    def test_unknown_truth_blocks_commit_b_until_seal(self) -> None:
        state, _ = QiTransactionState().commit_a(prepared())
        unresolved = state.observe_world_result(
            ExternalTruth.UNKNOWN,
            acknowledgement_sha256=None,
            authentication_proof_sha256=None,
        )
        self.assertIs(unresolved.external_truth, ExternalTruth.UNKNOWN)
        self.assertFalse(unresolved.sealed_indeterminate)
        with self.assertRaises(QiTransactionError):
            unresolved.commit_b()
        sealed = unresolved.seal_indeterminate("world-resolution-unavailable")
        self.assertTrue(sealed.sealed_indeterminate)
        self.assertEqual(sealed.lineage_status, "indeterminate_sealed")
        receipt = sealed.sealed_indeterminate_receipt
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt.payload()["terminal_status"], "indeterminate")
        self.assertEqual(receipt.payload()["lineage_status"], "indeterminate_sealed")
        self.assertEqual(receipt.payload()["disposition"], "new-session-only")
        # The seal is terminal for that session: no caller, retry, resolution,
        # recovery, or Commit-B turns unknown external truth into continuation.
        with self.assertRaises(QiTransactionError):
            sealed.commit_b()
        with self.assertRaises(QiTransactionError):
            sealed.resolve_indeterminate(
                ExternalTruth.APPLIED,
                acknowledgement_sha256="a" * 64,
                authentication_proof_sha256="b" * 64,
                outbox_sha256="outbox-A",
            )
        with self.assertRaises(QiTransactionError):
            sealed.commit_a(prepared("B"))
        with self.assertRaises(QiTransactionError):
            sealed.recover_outbox()
        self.assertIs(sealed.seal_indeterminate("again"), sealed)

    def test_authenticated_resolution_before_seal_completes_commit_b(self) -> None:
        state, _ = QiTransactionState().commit_a(prepared())
        unresolved = state.observe_world_result(
            ExternalTruth.UNKNOWN,
            acknowledgement_sha256=None,
            authentication_proof_sha256=None,
        )
        acknowledgement = "a" * 64
        proof = unresolved.authenticated_resolution_proof(ExternalTruth.APPLIED, acknowledgement)
        resolved = unresolved.resolve_indeterminate(
            ExternalTruth.APPLIED,
            acknowledgement_sha256=acknowledgement,
            authentication_proof_sha256=proof,
            outbox_sha256="outbox-A",
        )
        self.assertIs(resolved.external_truth, ExternalTruth.APPLIED)
        self.assertFalse(resolved.sealed_indeterminate)
        terminal, result = resolved.commit_b()
        self.assertEqual(result, "committed")
        self.assertIsNotNone(terminal.applied_efference_sha256)

    def test_only_applied_truth_creates_one_efference(self) -> None:
        for truth, acknowledgement in (
            (ExternalTruth.APPLIED, "a" * 64),
            (ExternalTruth.REJECTED, "b" * 64),
            (ExternalTruth.EXPIRED, "c" * 64),
        ):
            with self.subTest(truth=truth):
                state, _ = QiTransactionState().commit_a(prepared())
                proof = state.authenticated_resolution_proof(truth, acknowledgement)
                state = state.observe_world_result(
                    truth,
                    acknowledgement_sha256=acknowledgement,
                    authentication_proof_sha256=proof,
                )
                terminal, result = state.commit_b()
                self.assertEqual(result, "committed")
                self.assertEqual(
                    terminal.applied_efference_sha256 is not None,
                    truth is ExternalTruth.APPLIED,
                )
                replay, result = terminal.commit_b()
                self.assertIs(replay, terminal)
                self.assertEqual(result, "replay")
                consumed = terminal.consume_efference()
                self.assertIs(consumed.consume_efference(), consumed)

    def test_unauthenticated_terminal_truth_rejects(self) -> None:
        state, _ = QiTransactionState().commit_a(prepared())
        with self.assertRaises(QiTransactionError):
            state.observe_world_result(
                ExternalTruth.APPLIED,
                acknowledgement_sha256="a" * 64,
                authentication_proof_sha256=None,
            )


if __name__ == "__main__":
    unittest.main()
