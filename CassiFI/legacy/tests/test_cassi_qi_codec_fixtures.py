from __future__ import annotations

import unittest
from pathlib import Path

import cassi_qi_profile as runtime
import verify_cassi_qi_flow as independent

CORPUS_PATH = Path(__file__).with_name("cassi-qi-flow-canonical-fixtures.json")


class CanonicalFixtureTests(unittest.TestCase):
    def test_source_pinned_cross_language_fixture_corpus(self) -> None:
        raw = CORPUS_PATH.read_bytes()
        corpus = runtime.canonical_fixture_corpus()
        # The pinned file is the byte-identical canonical encoding of the
        # runtime-generated adversarial corpus.
        self.assertEqual(raw, runtime.canonical_json_bytes(corpus))
        # The runtime codec classifies every pinned fixture with its exact
        # outcome (ACCEPT or the named REJECT_* family).
        runtime.bootstrap_self_test()
        # The independent codec authenticates the same corpus, every outcome,
        # the sealed keyset, and the self hash without importing the runtime.
        verified = independent.validate_canonical_fixture_corpus(raw)
        self.assertEqual(verified["fixtures"], corpus["fixtures"])
        self.assertEqual(verified["self_sha256"], corpus["self_sha256"])


if __name__ == "__main__":
    unittest.main()
