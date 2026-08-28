from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from run_cassi_f5_evidence import (
    PROMPTS,
    _forbidden,
    blind_packet,
    bootstrap_mean_ci,
    exact_sign_test,
    score_coherence,
    score_factuality,
    score_instruction,
    suite_digest,
    verdict_from_deltas,
)


class F5EvidenceTest(unittest.TestCase):
    def test_suite_is_fixed_and_deterministic(self) -> None:
        self.assertEqual(len(PROMPTS), 12)
        self.assertEqual(suite_digest(PROMPTS), suite_digest(PROMPTS))
        self.assertNotEqual(suite_digest(PROMPTS[:-1]), suite_digest(PROMPTS))

    def test_factuality_boundaries(self) -> None:
        exact = score_factuality("Earth orbits the Sun.", ("sun",))
        miss = score_factuality("The Moon is bright.", ("sun",))
        self.assertEqual(exact["score"], 1.0)
        self.assertEqual(miss["score"], 0.0)

    def test_instruction_boundaries(self) -> None:
        good = score_instruction("CASSI FIELD", ("CASSI", "FIELD"))
        bad = score_instruction("other", ("CASSI", "FIELD"))
        self.assertEqual(good["score"], 1.0)
        self.assertEqual(bad["score"], 0.0)

    def test_coherence_boundary(self) -> None:
        score = score_coherence("Ada checks the experiment; Bruno checks measurements.", ("ada", "bruno", "experiment"))
        self.assertAlmostEqual(score["score"], 1.0)
        self.assertTrue(0.0 <= score["unique_word_ratio"] <= 1.0)

    def test_bootstrap_and_sign_test_are_finite(self) -> None:
        ci = bootstrap_mean_ci([1.0, 1.0, -1.0, 1.0], seed=4, samples=200)
        sign = exact_sign_test([1.0, 1.0, -1.0, 0.0])
        self.assertTrue(ci["lower"] <= ci["mean"] <= ci["upper"])
        self.assertEqual(sign["positive"], 2)
        self.assertEqual(sign["negative"], 1)
        self.assertEqual(sign["tied"], 1)
        self.assertEqual(verdict_from_deltas([0.0, 0.0], {"lower": 0.0, "upper": 0.0}), "DOES NOT EMERGE")

    def test_blind_packet_is_a_permutation_with_answer_key(self) -> None:
        paired = [
            {"prompt_id": "a", "prompt": "p", "baseline": "b", "field": "f"},
            {"prompt_id": "c", "prompt": "q", "baseline": "d", "field": "e"},
        ]
        packet, key = blind_packet(paired, seed=5)
        self.assertEqual([item["prompt_id"] for item in packet], ["a", "c"])
        for item, answer in zip(packet, key):
            self.assertEqual({item["A"], item["B"]}, {paired[["a", "c"].index(item["prompt_id"])] ["baseline"], paired[["a", "c"].index(item["prompt_id"])] ["field"]})
            self.assertEqual({answer["A"], answer["B"]}, {"baseline", "field"})

    def test_forbidden_payload_detection(self) -> None:
        self.assertIsNone(_forbidden({"metrics": {"finite": True}}))
        self.assertEqual(_forbidden({"logits": [1.0]}), "logits")


if __name__ == "__main__":
    unittest.main()
