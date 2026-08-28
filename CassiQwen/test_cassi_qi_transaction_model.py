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
        self.assertEqual(receipt.schedules_explored, 2 * 4 * 6)
        self.assertFalse(receipt.invariant_failures)
        payload = receipt.payload()
        self.assertTrue(payload["at_most_one_applied_world_effect"])
        self.assertTrue(payload["committed_response_never_dropped"])
        self.assertEqual(len(payload["self_sha256"]), 64)

    def test_commit_a_is_cas_and_retry_exact(self) -> None:
        state, result = QiTransactionState().commit_a(prepared("A"))
        self.assertEqual(result, "committed")
        replay, result = state.commit_a(prepared("A"))
        self.assertIs(replay, state)
        self.assertEqual(result, "replay")
        with self.assertRaises(QiTransactionError):
            state.commit_a(prepared("B"))

    def test_unknown_truth_seals_until_authenticated_resolution(self) -> None:
        state, _ = QiTransactionState().commit_a(prepared())
        sealed = state.observe_world_result(
            ExternalTruth.UNKNOWN,
            acknowledgement_sha256=None,
            authentication_proof_sha256=None,
        )
        self.assertTrue(sealed.sealed_indeterminate)
        with self.assertRaises(QiTransactionError):
            sealed.commit_b()
        with self.assertRaises(QiTransactionError):
            sealed.resolve_indeterminate(
                ExternalTruth.APPLIED,
                acknowledgement_sha256="ack",
                authentication_proof_sha256="auth",
                outbox_sha256="wrong-outbox",
            )
        resolved = sealed.resolve_indeterminate(
            ExternalTruth.APPLIED,
            acknowledgement_sha256="ack",
            authentication_proof_sha256="auth",
            outbox_sha256="outbox-A",
        )
        self.assertFalse(resolved.sealed_indeterminate)
        self.assertIs(resolved.external_truth, ExternalTruth.APPLIED)

    def test_only_applied_truth_creates_one_efference(self) -> None:
        for truth in (ExternalTruth.APPLIED, ExternalTruth.REJECTED, ExternalTruth.EXPIRED):
            with self.subTest(truth=truth):
                state, _ = QiTransactionState().commit_a(prepared())
                state = state.observe_world_result(
                    truth,
                    acknowledgement_sha256=f"ack-{truth.value}",
                    authentication_proof_sha256=f"auth-{truth.value}",
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

    def test_unauthenticated_terminal_truth_rejects(self) -> None:
        state, _ = QiTransactionState().commit_a(prepared())
        with self.assertRaises(QiTransactionError):
            state.observe_world_result(
                ExternalTruth.APPLIED,
                acknowledgement_sha256="ack",
                authentication_proof_sha256=None,
            )


if __name__ == "__main__":
    unittest.main()
