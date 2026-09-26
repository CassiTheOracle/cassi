from __future__ import annotations

import unittest

from cassi_outcome_order_sweep import OUTCOME_ORDER_SCHEMA, run_outcome_order_sweep


class OutcomeOrderSweepTests(unittest.TestCase):
    def test_order_sweep_is_deterministic_and_order_bound(self) -> None:
        orders = (
            ("promote", "promote", "promote", "promote"),
            ("promote", "reject", "promote", "reject"),
            ("reject", "promote", "promote", "promote"),
        )
        first = run_outcome_order_sweep(orders=orders)
        second = run_outcome_order_sweep(orders=orders)
        self.assertEqual(first, second)
        self.assertEqual(first["schema"], OUTCOME_ORDER_SCHEMA)
        self.assertEqual([len(row["trace"]) for row in first["results"]], [4, 4, 4])
        self.assertGreaterEqual(len({row["final_field_sha256"] for row in first["results"]}), 2)

    def test_order_sweep_rejects_malformed_orders(self) -> None:
        with self.assertRaises(ValueError):
            run_outcome_order_sweep(orders=(("promote", "reject"),))
        with self.assertRaises(ValueError):
            run_outcome_order_sweep(orders=(("promote", "unknown", "promote", "reject"),))


if __name__ == "__main__":
    unittest.main(verbosity=2)
