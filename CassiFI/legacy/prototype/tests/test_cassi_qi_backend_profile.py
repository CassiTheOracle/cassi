"""Focused W14B/G14B measured-profiler artifact checks."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from cassi_qi_profile import canonical_json_bytes
from cassi_qi_backend_profile import REQUIRED_REGISTRY_SCHEMAS, run
from verify_cassi_qi_backend_profile import W14BArtifactVerificationError, verify_artifact


ROOT = Path(__file__).resolve().parent
REGISTRY = ROOT / "cassi-fi-schema-registry" / "manifest.json"


def _registry_has_required_schemas() -> bool:
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    names = {row.get("schema") for row in payload.get("entry_hashes", []) if isinstance(row, dict)}
    return set(REQUIRED_REGISTRY_SCHEMAS).issubset(names)


@unittest.skipUnless(
    _registry_has_required_schemas(),
    "canonical backend/capacity schemas are not installed in the static registry yet",
)
class W14BArtifactVerificationTests(unittest.TestCase):
    """Run the real CPU float64 profiler once, then exercise sealed checks."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._output = tempfile.TemporaryDirectory(prefix="w14b-test-")
        result = run(output_root=Path(cls._output.name))
        cls.artifact = Path(result["artifact"])

    @classmethod
    def tearDownClass(cls) -> None:
        cls._output.cleanup()

    def _copy_artifact(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        holder = tempfile.TemporaryDirectory(prefix="w14b-mutation-")
        copy = Path(holder.name) / self.artifact.name
        shutil.copytree(self.artifact, copy)
        return holder, copy

    @staticmethod
    def _rewrite(path: Path, payload: object) -> None:
        path.write_bytes(canonical_json_bytes(payload))

    def test_content_addressed_artifact_passes(self) -> None:
        receipt = verify_artifact(self.artifact)
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["artifact_sha256"], self.artifact.name)
        self.assertEqual(receipt["gate_status"], "BLOCKED")
        self.assertEqual(receipt["profiler_status"], "PASS")

    def test_raw_tensor_mutation_is_rejected(self) -> None:
        holder, copy = self._copy_artifact()
        self.addCleanup(holder.cleanup)
        target = next((copy / "gates" / "g14b-full-system-capacity" / "raw").glob("*.f64le"))
        raw = bytearray(target.read_bytes())
        raw[len(raw) // 2] ^= 1
        target.write_bytes(raw)
        with self.assertRaises(W14BArtifactVerificationError):
            verify_artifact(copy)

    def test_memory_counter_mutation_is_rejected(self) -> None:
        holder, copy = self._copy_artifact()
        self.addCleanup(holder.cleanup)
        target = copy / "gates" / "g14b-full-system-capacity" / "profiler.json"
        payload = json.loads(target.read_bytes())
        payload["memory"]["receipt"]["op_count"] += 1
        self._rewrite(target, payload)
        with self.assertRaises(W14BArtifactVerificationError):
            verify_artifact(copy)

    def test_threshold_mutation_is_rejected(self) -> None:
        holder, copy = self._copy_artifact()
        self.addCleanup(holder.cleanup)
        target = copy / "run-spec" / "thresholds.json"
        payload = json.loads(target.read_bytes())
        payload["max_state_bytes"] += 1
        self._rewrite(target, payload)
        with self.assertRaises(W14BArtifactVerificationError):
            verify_artifact(copy)

    def test_backend_identity_mutation_is_rejected(self) -> None:
        holder, copy = self._copy_artifact()
        self.addCleanup(holder.cleanup)
        target = copy / "gates" / "g14b-full-system-capacity" / "profiler.json"
        payload = json.loads(target.read_bytes())
        payload["identities"]["backend"]["device_type"] = "cuda"
        self._rewrite(target, payload)
        with self.assertRaises(W14BArtifactVerificationError):
            verify_artifact(copy)

    def test_sealed_source_mutation_is_rejected(self) -> None:
        holder, copy = self._copy_artifact()
        self.addCleanup(holder.cleanup)
        target = copy / "run-spec" / "sources" / "cassi_qi_backend_profile.py"
        target.write_bytes(target.read_bytes() + b"\n")
        with self.assertRaises(W14BArtifactVerificationError):
            verify_artifact(copy)


if __name__ == "__main__":
    unittest.main()
