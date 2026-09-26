from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cassi_account_reconciliation import AccountEvent, AccountReconciler, AccountReconciliationError
from cassi_market_ingestion import IngestionStore


class AccountReconciliationTests(unittest.TestCase):
    def _event(self, event_id: str, event_type: str, sequence: int, payload):
        return AccountEvent(
            event_id=event_id,
            venue="coinbase",
            account_id="account-1",
            event_type=event_type,
            occurred_at=f"2026-01-01T00:00:{sequence % 60:02d}.000000Z",
            available_at=f"2026-01-01T00:01:{sequence % 60:02d}.000000Z",
            sequence=sequence,
            payload=payload,
        )

    def _snapshot_payload(self, *, usd: str = "1000"):
        return {
            "orders": [
                {
                    "order_id": "order-1",
                    "product": "BTC-USD",
                    "side": "buy",
                    "status": "open",
                    "requested_size": "0.1",
                    "filled_size": "0",
                    "limit_price": "100",
                }
            ],
            "fills": [],
            "balances": [{"currency": "USD", "total": usd, "available": usd, "hold": "0"}],
            "positions": [{"product": "BTC-USD", "size": "0", "entry_price": None}],
        }

    def test_snapshot_incremental_events_gap_quarantine_and_snapshot_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as raw, IngestionStore(Path(raw) / "market.sqlite3") as store:
            with AccountReconciler(store) as reconciler:
                initial = self._event("snapshot-100", "snapshot", 100, self._snapshot_payload())
                first = reconciler.apply(initial)
                self.assertEqual(first["status"], "APPLIED")
                self.assertTrue(reconciler.snapshot("coinbase", "account-1")["reconciled"])

                balance = self._event(
                    "balance-101",
                    "balance",
                    101,
                    {"currency": "USD", "total": "900", "available": "850", "hold": "50"},
                )
                applied = reconciler.apply(balance)
                duplicate = reconciler.apply(balance)
                self.assertEqual(applied["status"], "APPLIED")
                self.assertEqual(duplicate["status"], "DUPLICATE")

                gap = self._event(
                    "position-103",
                    "position",
                    103,
                    {"product": "BTC-USD", "size": "0.01", "entry_price": "100"},
                )
                quarantined = reconciler.apply(gap)
                self.assertEqual(quarantined["status"], "QUARANTINED")
                self.assertEqual(quarantined["reason"], "account-sequence-gap")
                self.assertFalse(store.get_state("account_reconciled"))
                self.assertTrue(store.get_state("account_recovery_required"))

                recovery = self._event("snapshot-110", "snapshot", 110, self._snapshot_payload(usd="950"))
                recovered = reconciler.apply(recovery)
                self.assertEqual(recovered["status"], "APPLIED")
                snapshot = reconciler.snapshot("coinbase", "account-1")
                self.assertTrue(snapshot["reconciled"])
                self.assertEqual(snapshot["last_sequence"], 110)
                self.assertFalse(store.get_state("account_recovery_required"))
                comparison = reconciler.compare_snapshot(
                    "coinbase",
                    "account-1",
                    {
                        "orders": snapshot["orders"],
                        "fills": snapshot["fills"],
                        "balances": snapshot["balances"],
                        "positions": snapshot["positions"],
                    },
                )
                self.assertEqual(comparison["status"], "MATCH")

    def test_order_terminal_state_cannot_regress(self) -> None:
        with tempfile.TemporaryDirectory() as raw, IngestionStore(Path(raw) / "market.sqlite3") as store:
            with AccountReconciler(store) as reconciler:
                reconciler.apply(self._event("snapshot-10", "snapshot", 10, {**self._snapshot_payload(), "orders": []}))
                order = {
                    "order_id": "order-2",
                    "product": "BTC-USD",
                    "side": "buy",
                    "requested_size": "0.1",
                    "filled_size": "0.1",
                    "limit_price": "100",
                    "status": "filled",
                }
                reconciler.apply(self._event("order-11", "order", 11, order))
                with self.assertRaises(AccountReconciliationError):
                    reconciler.apply(
                        self._event(
                            "order-12",
                            "order",
                            12,
                            {**order, "status": "open", "filled_size": "0"},
                        )
                    )


if __name__ == "__main__":
    unittest.main(verbosity=2)
