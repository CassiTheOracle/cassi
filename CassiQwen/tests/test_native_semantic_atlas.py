#!/usr/bin/env python3
"""Regression tests for semantic atlas geometry and holdout scoring."""

from __future__ import annotations

import unittest
from pathlib import Path

import numpy as np

from verify_native_semantic_atlas import _axis_measurement, _load_manifest, _spectrum


class SemanticAtlasTests(unittest.TestCase):
    def test_broad_manifest_expands_axes_and_declares_source_control(self) -> None:
        manifest = _load_manifest(Path(__file__).with_name("semantic-atlas-broad-manifest.json"))
        self.assertEqual(len(manifest["axes"]), 8)
        self.assertEqual(len(manifest["negative_controls"]), 1)
        expected_captures = (
            len(manifest["axes"])
            * (
                manifest["capture_contract"]["training_pairs_per_axis"]
                + manifest["capture_contract"]["holdout_pairs_per_axis"]
            )
            * 2
            + len(manifest["negative_controls"]) * 2
        )
        self.assertEqual(expected_captures, 66)
    def test_iq1s_27b_manifest_pins_downloaded_model(self) -> None:
        manifest = _load_manifest(
            Path(__file__).with_name("semantic-atlas-27b-iq1s-manifest.json")
        )
        contract = manifest["model_contract"]
        self.assertEqual(contract["model_filename"], "Qwen3.8-27B-UD-IQ1_S.gguf")
        self.assertEqual(
            contract["model_sha256"],
            "3895b6eaa91e705c06ad1938d16c22e86f073c6a67df86260a1da79be3d1f887",
        )
        self.assertEqual(contract["quantization"], "IQ1_S")
        self.assertEqual(contract["backend"], "vulkan")
        self.assertEqual(contract["gpu_layers"], 99)


    def test_distinct_shared_scalar_and_duplicate_controls_have_expected_rank(self) -> None:
        distinct = np.eye(8, dtype=np.float32)
        shared = np.repeat(distinct[:1], 8, axis=0)
        scalar = distinct[:1] * np.linspace(0.5, 2.0, 8, dtype=np.float32)[:, None]
        duplicate = np.vstack([distinct[:-1], distinct[:1]])
        self.assertEqual(_spectrum(distinct, 1.0e-6)["rank"], 8)
        self.assertEqual(_spectrum(shared, 1.0e-6)["rank"], 1)
        self.assertEqual(_spectrum(scalar, 1.0e-6)["rank"], 1)
        self.assertEqual(_spectrum(duplicate, 1.0e-6)["rank"], 7)
        self.assertEqual(float(np.linalg.norm(duplicate[0] - duplicate[-1])), 0.0)

    def test_heldout_sign_and_swapped_control_are_opposite(self) -> None:
        e1 = np.asarray([1.0, 0.0, 0.0], dtype=np.float32)
        e2 = np.asarray([0.0, 1.0, 0.0], dtype=np.float32)
        values = {
            "timing__timing-1__a": e1,
            "timing__timing-1__b": -e1,
            "timing__timing-2__a": e1 + 0.1 * e2,
            "timing__timing-2__b": -e1 + 0.1 * e2,
            "timing__timing-3__a": e1 - 0.1 * e2,
            "timing__timing-3__b": -e1 - 0.1 * e2,
            "timing__timing-4-holdout__a": 2.0 * e1,
            "timing__timing-4-holdout__b": -2.0 * e1,
        }
        axis = {
            "axis_id": "timing",
            "pole_a": "act_now",
            "pole_b": "defer",
            "pairs": [
                {"pair_id": "timing-1"},
                {"pair_id": "timing-2"},
                {"pair_id": "timing-3"},
                {"pair_id": "timing-4-holdout"},
            ],
        }
        result, _, _, _ = _axis_measurement(axis, values)
        self.assertGreater(result["holdout_score"], 0.0)
        self.assertLess(result["swapped_holdout_score"], 0.0)
        self.assertEqual(result["predicted_pole"], "pole_a")
        self.assertTrue(result["passed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
