from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from run_cassi_qi_flow import run
from verify_cassi_qi_transport import W3VerificationError, verify_artifact


class W3ArtifactVerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        result = run()
        cls.artifact = Path(__file__).resolve().parent / result["artifact"]

    def test_source_exact_artifact_passes_independent_replay(self) -> None:
        receipt = verify_artifact(self.artifact)
        self.assertEqual(receipt["status"], "PASS_W3_G3")
        self.assertEqual(receipt["run_id"], self.artifact.name)

    def test_raw_candidate_tamper_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            copy = Path(directory) / "artifact"
            shutil.copytree(self.artifact, copy)
            target = copy / "fixtures" / "seeded-candidate.f64le"
            raw = bytearray(target.read_bytes())
            raw[len(raw) // 2] ^= 1
            target.write_bytes(raw)
            with self.assertRaises(W3VerificationError):
                verify_artifact(copy)

    def test_source_snapshot_tamper_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            copy = Path(directory) / "artifact"
            shutil.copytree(self.artifact, copy)
            target = copy / "run-spec" / "sources" / "cassi_qi_transport.py"
            target.write_bytes(target.read_bytes() + b"\n")
            with self.assertRaises(W3VerificationError):
                verify_artifact(copy)


if __name__ == "__main__":
    unittest.main()
