from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import cassi_qi_profile as profile
import verify_cassi_qi_flow as independent


_ARTIFACT = Path(__file__).with_name("_diag") / "cassi-qi-flow-w1-final" / "24d42153fe05cdc5fe467c096c705fbb14211021449e60fcb6f03ae8809f578c"


class IndependentW1VerifierTests(unittest.TestCase):
    def _copy_artifact(self, destination: Path) -> Path:
        self.assertTrue(_ARTIFACT.is_dir(), "sealed W1/G1 artifact must be available")
        target = destination / _ARTIFACT.name
        shutil.copytree(_ARTIFACT, target)
        return target

    def test_sealed_w1_g1_artifact_passes_independently(self) -> None:
        result = independent.verify_g1_identity(_ARTIFACT)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["receipt_count"], 39)

    def test_missing_post_index_attestation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            clone = self._copy_artifact(Path(directory))
            (clone / "gates" / "g01-identity" / "verification.json").unlink()
            with self.assertRaises(independent.VerificationError):
                independent.verify_g1_identity(clone)

    def test_raw_checkpoint_mutation_fails_independently(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            clone = self._copy_artifact(Path(directory))
            checkpoint = clone / "gates" / "g01-identity" / "checkpoint.qiflow"
            mutated = bytearray(checkpoint.read_bytes())
            mutated[-1] ^= 1
            checkpoint.write_bytes(mutated)
            with self.assertRaises(independent.VerificationError):
                independent.verify_g1_identity(clone)

    def test_resealed_mutation_control_failure_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            clone = self._copy_artifact(Path(directory))
            candidate_path = clone / "gates" / "g01-identity" / "identity.json"
            candidate = profile.canonical_json_loads(candidate_path.read_bytes())
            candidate["mutation_controls"]["predecessor_unchanged"] = False
            without_self = dict(candidate)
            without_self.pop("self_sha256")
            candidate["self_sha256"] = profile.canonical_hash(
                without_self,
                "cassi.qi-flow-g1-identity-candidate.v1",
            )
            candidate_path.write_bytes(profile.canonical_json_bytes(candidate))
            with self.assertRaises(independent.VerificationError):
                independent.verify_g1_identity(clone)


if __name__ == "__main__":
    unittest.main()
