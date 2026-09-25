from __future__ import annotations

import unittest

from cassi_campaign import CampaignError, RollingCampaign, RollingCampaignConfig
from cassi_trading_foundry import generate_demo_bars


class RollingCampaignTests(unittest.TestCase):
    def test_adaptive_and_frozen_arms_share_boundaries(self) -> None:
        campaign = RollingCampaign(
            RollingCampaignConfig(
                train_bars=32,
                horizon_bars=1,
                step_bars=4,
                max_windows=4,
                program_id="synth-native-program",
            )
        )
        receipt = campaign.run(generate_demo_bars(64))
        adaptive = receipt["adaptive"]
        frozen = receipt["frozen"]
        self.assertEqual(receipt["matched_window_starts"], [0, 4, 8, 12])
        self.assertEqual(adaptive["window_count"], frozen["window_count"])
        self.assertTrue(adaptive["field_changed"])
        self.assertFalse(frozen["field_changed"])
        for row in adaptive["windows"] + frozen["windows"]:
            self.assertLess(row["decision_available_at"], row["outcome_observed_at"])
            self.assertNotIn(row["outcome_event_id"], row["prediction_input_event_ids"])
            self.assertIn(row["field_prediction"]["status"], {None, "supported", "unsupported", "unresolved"})

    def test_campaign_fails_without_complete_future_window(self) -> None:
        campaign = RollingCampaign(RollingCampaignConfig(train_bars=32, horizon_bars=2))
        with self.assertRaises(CampaignError):
            campaign.run(generate_demo_bars(33))

    def test_campaign_receipt_is_content_addressed(self) -> None:
        campaign = RollingCampaign(RollingCampaignConfig(max_windows=2))
        first = campaign.run(generate_demo_bars(48))
        second = campaign.run(generate_demo_bars(48))
        self.assertEqual(first, second)
        self.assertEqual(len(first["content_sha256"]), 64)


if __name__ == "__main__":
    unittest.main(verbosity=2)
