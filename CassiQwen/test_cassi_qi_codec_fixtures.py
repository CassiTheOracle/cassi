from __future__ import annotations

import base64
import unittest
from pathlib import Path

import cassi_qi_profile as runtime
import verify_cassi_qi_flow as independent


class CanonicalFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.corpus = runtime.canonical_json_loads(
            Path(__file__).with_name("cassi-qi-flow-canonical-fixtures.json").read_bytes()
        )

    def _classify(self, codec_loads, codec_bytes, rejected, payload: bytes) -> str:
        try:
            decoded = codec_loads(payload)
            return "ACCEPT" if codec_bytes(decoded) == payload else "REJECT_NONCANONICAL"
        except rejected:
            return "REJECT"

    def test_source_pinned_cross_language_fixture_corpus(self) -> None:
        self.assertEqual(self.corpus["schema"], "cassi.qi-flow-canonical-fixtures.v1")
        self.assertEqual(self.corpus["codec_schema"], runtime.CANONICAL_CODEC_SCHEMA)
        for fixture in self.corpus["fixtures"]:
            payload = base64.b64decode(fixture["payload_base64"], validate=True)
            runtime_outcome = self._classify(
                runtime.canonical_json_loads,
                runtime.canonical_json_bytes,
                runtime.CanonicalCodecError,
                payload,
            )
            independent_outcome = self._classify(
                independent.canonical_json_loads,
                independent.canonical_json_bytes,
                independent.VerificationError,
                payload,
            )
            self.assertEqual(runtime_outcome, fixture["expected"], fixture["fixture_id"])
            self.assertEqual(independent_outcome, fixture["expected"], fixture["fixture_id"])
            self.assertEqual(runtime_outcome, independent_outcome, fixture["fixture_id"])


if __name__ == "__main__":
    unittest.main()
