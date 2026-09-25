from dataclasses import replace

import unittest

from cassi_market_coordinates import CoordinateConfig, CoordinateError, derive_market_coordinates
from cassi_trading_foundry import generate_demo_bars
from cassi_world_model import MarketWorldModel, WorldModelError


class WorldModelTests(unittest.TestCase):
    def _events(self, count: int = 64):
        bars = generate_demo_bars(count)
        return tuple(
            bar.as_event(source_id="world-model-test", source_revision="bars-v1")
            for bar in bars
        )

    def test_coordinates_are_provenance_bound_and_warm_up_without_future_data(self) -> None:
        events = self._events(32)[:12]
        config = CoordinateConfig(fast_window=2, slow_window=4, momentum_window=2, volatility_window=3)
        observations = derive_market_coordinates(events, config)
        self.assertEqual(len(observations), len(events))
        self.assertEqual(observations[0].value["ready"], 0)
        self.assertEqual(observations[3].value["ready"], 1)
        self.assertEqual(observations[3].input_event_ids[-1], events[3].event_id)
        self.assertIn(events[3].content_sha256, observations[3].input_digests)
        changed = list(events)
        changed[-1] = replace(events[-1], source_revision="bars-v2")
        changed_observations = derive_market_coordinates(tuple(changed), config)
        for before, after in zip(observations[:-1], changed_observations[:-1]):
            self.assertEqual(before.content_sha256, after.content_sha256)

    def test_coordinate_sequence_rejects_mixed_subjects(self) -> None:
        events = list(self._events(32))
        last = events[-1]
        events[-1] = replace(last, subject_ids=("OTHER",))
        with self.assertRaises(CoordinateError):
            derive_market_coordinates(tuple(events), CoordinateConfig(fast_window=2, slow_window=4))

    def test_world_model_advances_chronologically_and_records_regime_support(self) -> None:
        events = self._events()
        model = MarketWorldModel()
        first = model.update(events[:40])
        second = model.update(events[40:])
        self.assertEqual(first["before_revision"], 0)
        self.assertEqual(first["after_revision"], 40)
        self.assertEqual(second["before_revision"], 40)
        self.assertEqual(second["after_revision"], 64)
        self.assertIsNotNone(model.active_regime)
        self.assertTrue(model.active_regime.supporting_observations)
        self.assertTrue(model.hypotheses)
        self.assertEqual(model.snapshot()["content_sha256"], second["after_sha256"])
        with self.assertRaises(WorldModelError):
            model.update(events[39:40])

    def test_world_model_replay_is_deterministic(self) -> None:
        events = self._events(48)
        first = MarketWorldModel()
        second = MarketWorldModel()
        first.update(events[:32])
        first.update(events[32:])
        second.update(events[:32])
        second.update(events[32:])
        self.assertEqual(first.snapshot(), second.snapshot())
        self.assertEqual(first.checkpoint_bytes(), second.checkpoint_bytes())


if __name__ == "__main__":
    unittest.main(verbosity=2)
