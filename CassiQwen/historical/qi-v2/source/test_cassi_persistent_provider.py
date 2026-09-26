"""Focused contracts for the native-Qi persistent provider.

The integration case uses the checked-in fixed Qi v2 configuration and the
pinned Qwen baseline receipt.  It is intentionally not coupled to a Qwen
runtime, an organism checkpoint, a learned language head, a sampler, or a
session seed.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cassi_persistent_provider import (
    MODEL_NAME,
    DEFAULT_PORT,
    PersistentFieldProvider,
    ProviderConfig,
    ProviderError,
    _validate_determinism,
    _validate_messages,
    build_parser,
)


ROOT = Path(__file__).resolve().parent
ARTIFACTS = ROOT / "_diag"


class NativeQiProviderContractTests(unittest.TestCase):
    def test_defaults_are_field_only(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        self.assertEqual(args.port, DEFAULT_PORT)
        self.assertEqual(args.host, "127.0.0.1")
        self.assertEqual(MODEL_NAME, "cassi-qi-language-v1")
        self.assertTrue(hasattr(PersistentFieldProvider, "complete"))
        self.assertTrue(hasattr(PersistentFieldProvider, "start"))

    def test_message_bounds(self) -> None:
        _validate_messages([{"role": "user", "content": "field"}])
        with self.assertRaises(ProviderError):
            _validate_messages([{"role": "tool", "content": "unsupported"}])

    def test_determinism_rejects_sampling_parameters(self) -> None:
        _validate_determinism({"temperature": 0.0})
        _validate_determinism({})
        with self.assertRaises(ProviderError):
            _validate_determinism({"temperature": 0.7})
        with self.assertRaises(ProviderError):
            _validate_determinism({"top_k": 5})
        with self.assertRaises(ProviderError):
            _validate_determinism({"top_p": 0.9})
        with self.assertRaises(ProviderError):
            _validate_determinism({"seed": 12345})
        with self.assertRaises(ProviderError):
            _validate_determinism({"cassi_session_seed": "seed"})

    def test_final_artifact_completion_is_qi_owned(self) -> None:
        paths = {
            "qi_config_path": ROOT / "cassi-qi-language.json",
            "baseline_receipt_path": ARTIFACTS / "qwen-displacement" / "baseline-receipt.json",
        }
        if not all(path.is_file() for path in paths.values()):
            self.skipTest("native-Qi artifacts are not present")
        with tempfile.TemporaryDirectory() as directory:
            provider = PersistentFieldProvider(
                ProviderConfig(
                    state_dir=Path(directory),
                    max_output_symbols=4,
                    **paths,
                )
            )
            provider.start()
            try:
                response = provider.complete(
                    {
                        "model": MODEL_NAME,
                        "messages": [{"role": "user", "content": "field"}],
                        "max_tokens": 2,
                        "user": "contract-session",
                    }
                )
                cassi = response["cassi"]
                displacement = cassi["displacement_receipt"]
                self.assertEqual(len(cassi["state_in_sha256"]), 64)
                self.assertTrue(cassi["field_text_receipt_sha256"])
                self.assertEqual(
                    cassi["field_text_receipt"]["schema"],
                    "cassi.qi-text-result.v1",
                )
                self.assertEqual(
                    displacement["schema"],
                    "cassi.qi-native-displacement.v1",
                )
                self.assertEqual(
                    displacement["architecture"]["adaptive_persistent_tensor_count"],
                    1,
                )
                self.assertEqual(
                    displacement["architecture"]["learned_parameter_count"],
                    0,
                )
                self.assertEqual(
                    displacement["architecture"]["neural_layer_count"],
                    0,
                )
                self.assertEqual(
                    displacement["architecture"]["optimizer_state_bytes"],
                    0,
                )
                self.assertEqual(
                    displacement["architecture"]["engineered_feature_width"],
                    0,
                )
                self.assertIs(
                    displacement["architecture"]["probabilistic_sampler"],
                    False,
                )
                counts = displacement["qwen_serving"]["counts"]
                self.assertTrue(all(value == 0 for value in counts.values()))
                self.assertTrue(displacement["field_text"]["all_outputs_field_owned"])
                self.assertIs(displacement["teacher"]["called"], False)
                self.assertEqual(displacement["teacher"]["calls"], 0)
                self.assertTrue(cassi["checkpoint_sha256"])
            finally:
                provider.close()


if __name__ == "__main__":
    unittest.main()
