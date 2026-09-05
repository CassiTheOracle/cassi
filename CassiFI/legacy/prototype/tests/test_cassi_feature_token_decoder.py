"""Synthetic CPU-only tests for the compact feature-token decoder."""

from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

import torch

from cassi_feature_token_decoder import (
    FEATURE_TOKEN_DECODER_CHECKPOINT_SCHEMA,
    FEATURE_TOKEN_DECODER_CONFIG_SCHEMA,
    CassiFeatureTokenDecoder,
    CassiFeatureTokenDecoderConfig,
    CassiFeatureTokenDecoderError,
    load_feature_token_decoder_checkpoint,
    save_feature_token_decoder_checkpoint,
)


class FeatureTokenDecoderTests(unittest.TestCase):
    def setUp(self) -> None:
        torch.manual_seed(1234)
        self.config = CassiFeatureTokenDecoderConfig(
            feature_dim=8,
            adapter_rank=3,
            adapter_scale=0.1,
            min_temperature=0.2,
            max_temperature=2.0,
        )
        self.model = CassiFeatureTokenDecoder(self.config)
        self.features = torch.randn(2, self.config.feature_dim)
        self.rows = torch.randn(5, self.config.feature_dim)
        self.ids = torch.tensor([31, 7, 19, 2, 11], dtype=torch.int64)

    def test_forward_backward_finiteness_and_identity_initialization(self) -> None:
        features = self.features.clone().requires_grad_(True)
        adapted = self.model.adapt(features)
        torch.testing.assert_close(adapted, features, rtol=0.0, atol=0.0)
        self.assertTrue(bool(torch.isfinite(adapted).all()))

        logits = self.model.logits(features, self.rows)
        self.assertEqual(tuple(logits.shape), (2, 5))
        self.assertTrue(bool(torch.isfinite(logits).all()))
        logits.square().mean().backward()
        self.assertIsNotNone(features.grad)
        self.assertIsNotNone(self.model.down.weight.grad)
        self.assertIsNotNone(self.model.up.weight.grad)
        self.assertTrue(bool(torch.isfinite(features.grad).all()))
        self.assertTrue(bool(torch.isfinite(self.model.down.weight.grad).all()))
        self.assertTrue(bool(torch.isfinite(self.model.up.weight.grad).all()))
        self.assertGreater(float(self.model.down.weight.grad.abs().sum()), 0.0)
        self.assertGreater(float(self.model.up.weight.grad.abs().sum()), 0.0)

    def test_batched_candidate_rows_and_no_candidate_parameter(self) -> None:
        batched_rows = self.rows.unsqueeze(0).expand(2, -1, -1).clone()
        logits = self.model.logits(self.features, batched_rows)
        self.assertEqual(tuple(logits.shape), (2, 5))
        parameter_names = {name for name, _ in self.model.named_parameters()}
        self.assertNotIn("candidate_rows", parameter_names)
        self.assertLess(sum(parameter.numel() for parameter in self.model.parameters()), 8 * 8 * 2)

    def test_candidate_shape_dtype_finiteness_and_id_validation(self) -> None:
        with self.assertRaises(CassiFeatureTokenDecoderError):
            self.model.logits(self.features, torch.randn(8, 5))
        with self.assertRaises(CassiFeatureTokenDecoderError):
            self.model.logits(self.features, torch.ones(5, 8, dtype=torch.int64))
        invalid_rows = self.rows.clone()
        invalid_rows[0, 0] = float("nan")
        with self.assertRaises(CassiFeatureTokenDecoderError):
            self.model.logits(self.features, invalid_rows)
        with self.assertRaises(CassiFeatureTokenDecoderError):
            self.model.top_k(self.features, self.rows, torch.tensor([1, 2, 3, 4, 5], dtype=torch.bool), 2)
        with self.assertRaises(CassiFeatureTokenDecoderError):
            self.model.top_k(self.features, self.rows, torch.tensor([-1, 2, 3, 4, 5]), 2)
        with self.assertRaises(CassiFeatureTokenDecoderError):
            self.model.top_k(self.features, self.rows, torch.tensor([1.0, 2, 3, 4, 5]), 2)
        with self.assertRaises(CassiFeatureTokenDecoderError):
            self.model.top_k(self.features, self.rows, self.ids, 6)

    def test_deterministic_tie_ordering(self) -> None:
        zero_rows = torch.zeros_like(self.rows)
        result = self.model.top_k(self.features, zero_rows, self.ids, 5)
        self.assertEqual([row["token_id"] for row in result[0]], [2, 7, 11, 19, 31])
        self.assertEqual([row["token_id"] for row in result[1]], [2, 7, 11, 19, 31])
        self.assertEqual([row["logit"] for row in result[0]], [0.0] * 5)

    def test_config_roundtrip_and_validation(self) -> None:
        self.assertEqual(self.config, CassiFeatureTokenDecoderConfig.from_dict(self.config.to_dict()))
        self.assertEqual(len(self.config.fingerprint), 64)
        self.assertEqual(self.config.to_dict()["feature_dim"], 8)
        with self.assertRaises(CassiFeatureTokenDecoderError):
            CassiFeatureTokenDecoderConfig(adapter_rank=0)
        with self.assertRaises(CassiFeatureTokenDecoderError):
            CassiFeatureTokenDecoderConfig(min_temperature=float("nan"))
        with self.assertRaises(CassiFeatureTokenDecoderError):
            CassiFeatureTokenDecoderConfig.from_dict({"unexpected": 1})

    def test_checkpoint_roundtrip_and_sha256(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "decoder.pt"
            digest = save_feature_token_decoder_checkpoint(
                path, self.model, step=17, metadata={"purpose": "synthetic", "count": 2}
            )
            self.assertEqual(digest, hashlib.sha256(path.read_bytes()).hexdigest())
            loaded = load_feature_token_decoder_checkpoint(path)
            self.assertEqual(loaded.step, 17)
            self.assertEqual(loaded.metadata, {"purpose": "synthetic", "count": 2})
            self.assertEqual(loaded.config, self.config)
            self.assertEqual(loaded.sha256, digest)
            torch.testing.assert_close(
                loaded.model.logits(self.features, self.rows), self.model.logits(self.features, self.rows)
            )

    def test_incompatible_and_nonfinite_checkpoint_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "decoder.pt"
            save_feature_token_decoder_checkpoint(path, self.model)
            payload = torch.load(path, map_location="cpu", weights_only=True)
            self.assertEqual(payload["schema"], FEATURE_TOKEN_DECODER_CHECKPOINT_SCHEMA)
            self.assertEqual(payload["config_schema"], FEATURE_TOKEN_DECODER_CONFIG_SCHEMA)

            incompatible = dict(payload)
            incompatible["config"] = dict(payload["config"], feature_dim=9)
            incompatible_path = Path(directory) / "incompatible.pt"
            torch.save(incompatible, incompatible_path)
            with self.assertRaises(CassiFeatureTokenDecoderError):
                load_feature_token_decoder_checkpoint(incompatible_path)

            nonfinite = dict(payload)
            nonfinite_state = dict(payload["model_state"])
            nonfinite_state["down.weight"] = nonfinite_state["down.weight"].clone()
            nonfinite_state["down.weight"][0, 0] = float("inf")
            nonfinite["model_state"] = nonfinite_state
            nonfinite_path = Path(directory) / "nonfinite.pt"
            torch.save(nonfinite, nonfinite_path)
            with self.assertRaises(CassiFeatureTokenDecoderError):
                load_feature_token_decoder_checkpoint(nonfinite_path)


if __name__ == "__main__":
    unittest.main()
