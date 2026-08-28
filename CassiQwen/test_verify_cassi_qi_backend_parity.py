"""Focused W14A/G14A independent artifact-verifier checks."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from cassi_qi_profile import canonical_json_bytes
from run_cassi_qi_backend_parity import REQUIRED_REGISTRY_SCHEMAS, run
from verify_cassi_qi_backend_parity import W14AArtifactVerificationError, verify_artifact


ROOT = Path(__file__).resolve().parent
REGISTRY = ROOT / "cassi-fi-schema-registry" / "manifest.json"


def _registry_has_backend_contract() -> bool:
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    names = {row.get("schema") for row in payload.get("entry_hashes", []) if isinstance(row, dict)}
    return set(REQUIRED_REGISTRY_SCHEMAS).issubset(names)


@unittest.skipUnless(
    _registry_has_backend_contract(),
    "canonical backend schemas are not installed in the static registry yet",
)
class W14AArtifactVerificationTests(unittest.TestCase):
    """Run the real CPU/ROCm attempt once, then exercise independent checks."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._output = tempfile.TemporaryDirectory(prefix="w14a-test-")
        result = run(output_root=Path(cls._output.name))
        cls.artifact = Path(result["artifact"])

    @classmethod
    def tearDownClass(cls) -> None:
        cls._output.cleanup()

    def _copy_artifact(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        holder = tempfile.TemporaryDirectory(prefix="w14a-mutation-")
        copy = Path(holder.name) / self.artifact.name
        shutil.copytree(self.artifact, copy)
        return holder, copy

    def test_content_addressed_artifact_passes(self) -> None:
        receipt = verify_artifact(self.artifact)
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["run_id"], self.artifact.name)
        self.assertIn("cpu-f32", receipt["executed_comparisons"])

    def test_raw_tensor_mutation_is_rejected(self) -> None:
        holder, copy = self._copy_artifact()
        self.addCleanup(holder.cleanup)
        target = next((copy / "gates" / "g14a-operator-parity" / "raw").glob("*.f64le"))
        raw = bytearray(target.read_bytes())
        raw[len(raw) // 2] ^= 1
        target.write_bytes(raw)
        with self.assertRaises(W14AArtifactVerificationError):
            verify_artifact(copy)

    def test_term_order_mutation_is_rejected(self) -> None:
        holder, copy = self._copy_artifact()
        self.addCleanup(holder.cleanup)
        target = copy / "gates" / "g14a-operator-parity" / "termwise.json"
        payload = json.loads(target.read_text(encoding="utf-8"))
        payload["term_order"] = list(reversed(payload["term_order"]))
        target.write_bytes(canonical_json_bytes(payload) + b"\n")
        with self.assertRaises(W14AArtifactVerificationError):
            verify_artifact(copy)

    def test_source_snapshot_mutation_is_rejected(self) -> None:
        holder, copy = self._copy_artifact()
        self.addCleanup(holder.cleanup)
        target = copy / "run-spec" / "sources" / "run_cassi_qi_backend_parity.py"
        target.write_bytes(target.read_bytes() + b"\n")
        with self.assertRaises(W14AArtifactVerificationError):
            verify_artifact(copy)


if __name__ == "__main__":
    unittest.main()
