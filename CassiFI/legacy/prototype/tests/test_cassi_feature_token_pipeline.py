"""Pure synthetic coverage for cassi_feature_token_pipeline."""

from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch

try:
    import cassi_feature_token_pipeline as pipeline
except ImportError:  # package-style test execution
    from . import cassi_feature_token_pipeline as pipeline


class PipelineTest(unittest.TestCase):
    def _record(self, targets, pieces, teacher_ids):
        teacher_rows = []
        for target, row in zip(targets, teacher_ids):
            candidates = []
            for rank, token in enumerate(row):
                piece = pieces[targets.index(target)] if target is not None and int(token) == int(target) else f"p{token}"
                candidates.append({"token_id": int(token), "piece": piece, "logit": float(rank)})
            teacher_rows.append(candidates)
        return {
            "horizon": len(targets),
            "target_next_token_ids": list(targets),
            "target_next_token_pieces": list(pieces),
            "teacher_top_candidates": teacher_rows,
        }

    def test_target_alignment_padding_and_terminal_rejection(self) -> None:
        records = [self._record([3, 4, None], ["b", "c", None], [[3], [4], [5]])]
        valid = np.asarray([[True, True, True, False, False]], dtype=np.bool_)
        actual = pipeline.target_ids(records, valid, vocabulary_size=8)
        np.testing.assert_array_equal(actual, np.asarray([[3, 4, -1, -1, -1]], dtype=np.int64))
        bad_terminal = [self._record([3, None, 4], ["b", None, "d"], [[3], [4], [5]])]
        with self.assertRaises(pipeline.FeatureTokenPipelineError):
            pipeline.target_ids(bad_terminal, valid, vocabulary_size=8)
        missing_target = [self._record([3, 4], ["b", "c"], [[3], [4]])]
        with self.assertRaises(pipeline.FeatureTokenPipelineError):
            pipeline.target_ids(missing_target, np.asarray([[True, True, True]], dtype=np.bool_), vocabulary_size=8)

    def test_train_only_candidate_lexicon(self) -> None:
        train = [self._record([9, None], ["nine", None], [[9, 11], [2]])]
        validation = [self._record([12, None], ["twelve", None], [[12, 13], [2]])]
        train_ids, train_pieces = pipeline.candidate_lexicon(train, vocabulary_size=32)
        validation_ids, _ = pipeline.candidate_lexicon(validation, vocabulary_size=32)
        np.testing.assert_array_equal(train_ids, np.asarray([2, 9, 11], dtype=np.int64))
        self.assertEqual(train_pieces, ("p2", "nine", "p11"))
        self.assertNotIn(12, train_ids.tolist())
        self.assertIn(12, validation_ids.tolist())

    def test_normalized_round_trip(self) -> None:
        normalizer = pipeline.Normalization(
            observation_mean=np.asarray([2.0, -1.0], dtype=np.float32),
            observation_std=np.asarray([2.0, 4.0], dtype=np.float32),
            action_mean=np.asarray([1.0], dtype=np.float32),
            action_std=np.asarray([0.5], dtype=np.float32),
        )
        raw = np.asarray([[6.0, 7.0]], dtype=np.float32)
        standardized = normalizer.observation_standardized(raw)
        np.testing.assert_allclose(standardized, [[2.0, 2.0]])
        np.testing.assert_allclose(normalizer.observation_raw(standardized), raw)
        np.testing.assert_allclose(normalizer.action_standardized([[2.0]]), [[2.0]])

    def test_candidate_asset_hash_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            npz_path = root / "candidate.npz"
            json_path = root / "candidate.json"
            ids = np.asarray([2, 9], dtype=np.int64)
            rows = np.arange(8, dtype=np.float32).reshape(2, 4)
            pipeline.save_candidate_assets(npz_path, json_path, ids, rows, ("two", "nine"), {"source": "train"})
            loaded = pipeline.load_candidate_assets(npz_path, json_path, expected_feature_dim=4)
            np.testing.assert_array_equal(loaded.token_ids, ids)
            np.testing.assert_array_equal(loaded.rows, rows)
            manifest = json.loads(json_path.read_text(encoding="utf-8"))
            manifest["pieces"][0] = "tampered"
            json_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaises(pipeline.FeatureTokenPipelineError):
                pipeline.load_candidate_assets(npz_path, json_path, expected_feature_dim=4)
            pipeline.save_candidate_assets(npz_path, json_path, ids, rows, ("two", "nine"), {"source": "train"})
            tampered = rows.copy()
            tampered[0, 0] += 1.0
            with npz_path.open("wb") as handle:
                np.savez(handle, token_ids=ids, rows=tampered)
            with self.assertRaises(pipeline.FeatureTokenPipelineError):
                pipeline.load_candidate_assets(npz_path, json_path, expected_feature_dim=4)

    def test_causal_rule_does_not_leak_future_observation(self) -> None:
        model = _SyntheticWorldModel()
        observations = torch.tensor([[[1.0], [2.0], [3.0]]])
        actions = torch.tensor([[[0.5], [0.5], [0.5]]])
        trajectory = SimpleNamespace(
            observations=observations,
            actions=actions,
            valid=torch.ones((1, 3), dtype=torch.bool),
            resets=torch.tensor([[True, False, False]]),
        )
        first = pipeline.causal_prior_features(model, trajectory, device="cpu")
        future_changed = SimpleNamespace(
            observations=observations.clone(),
            actions=actions,
            valid=trajectory.valid,
            resets=trajectory.resets,
        )
        future_changed.observations[0, 1, 0] = 900.0
        second = pipeline.causal_prior_features(_SyntheticWorldModel(), future_changed, device="cpu")
        np.testing.assert_array_equal(first[:, :2], second[:, :2])
        self.assertNotEqual(float(first[0, 2, 0]), float(second[0, 2, 0]))

    def test_nonfinite_and_mismatch_errors(self) -> None:
        normalizer = pipeline.Normalization(
            np.ones(2, dtype=np.float32), np.ones(2, dtype=np.float32), np.ones(1, dtype=np.float32), np.ones(1, dtype=np.float32)
        )
        with self.assertRaises(pipeline.FeatureTokenPipelineError):
            normalizer.observation_raw([[np.nan, 1.0]])
        with self.assertRaises(pipeline.FeatureTokenPipelineError):
            pipeline.supervision_rows(
                np.zeros((1, 2, 2), dtype=np.float32),
                np.asarray([[2, -1]], dtype=np.int64),
                np.asarray([[True, False]], dtype=np.bool_),
                normalizer,
                np.asarray([1], dtype=np.int64),
            )
        with self.assertRaises(pipeline.FeatureTokenPipelineError):
            pipeline.target_ids([self._record([1], ["x"], [[1]])], np.asarray([[True, True]], dtype=np.bool_))
@dataclass(frozen=True)
class _SyntheticStep:
    observation_mean: torch.Tensor
    state: torch.Tensor


class _SyntheticWorldModel:
    def __init__(self) -> None:
        self.training = True
        self.imagine_states: list[torch.Tensor] = []
        self.observe_states: list[torch.Tensor] = []

    def eval(self):
        self.training = False
        return self

    def train(self, mode: bool = True):
        self.training = mode
        return self

    def initial_state(self, batch_size: int, *, device, dtype):
        return torch.zeros((batch_size, 1), device=device, dtype=dtype)

    def imagine_step(self, action, state, *, valid, reset, sample):
        self.imagine_states.append(state.clone())
        prior = state + action
        return _SyntheticStep(prior, state + action)

    def observe_step(self, observation, action, state, *, valid, reset, sample):
        self.observe_states.append(state.clone())
        return _SyntheticStep(observation, state + observation)


if __name__ == "__main__":
    unittest.main()
