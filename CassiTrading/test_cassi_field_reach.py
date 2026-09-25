from __future__ import annotations

import unittest

from cassi_field_reach import FIELD_REACH_SCHEMA, FieldReachConfig, run_field_reach_arms
from cassi_trading_foundry import RefinementField


class FieldReachTests(unittest.TestCase):
    def test_lesion_and_supported_control_are_observable(self) -> None:
        field = RefinementField()
        field.learn_program("edge", "synthesized-transfer-program", "promote", repeats=1)
        receipt = run_field_reach_arms(field)
        self.assertEqual(receipt["schema"], FIELD_REACH_SCHEMA)
        arms = {arm["arm"]: arm for arm in receipt["arms"]}
        self.assertEqual(set(arms), {"native", "lesion", "supported-control"})
        self.assertNotEqual(
            arms["native"]["readout"]["status"],
            arms["lesion"]["readout"]["status"],
        )
        self.assertFalse(arms["lesion"]["strict_promote_authority"])
        self.assertTrue(arms["supported-control"]["strict_promote_authority"])
        self.assertNotEqual(
            arms["lesion"]["field_after_sha256"],
            receipt["input_field_sha256"],
        )

    def test_support_repeat_bound_is_explicit(self) -> None:
        with self.assertRaises(ValueError):
            FieldReachConfig(support_repeats=0)
        with self.assertRaises(ValueError):
            FieldReachConfig(support_repeats=5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
