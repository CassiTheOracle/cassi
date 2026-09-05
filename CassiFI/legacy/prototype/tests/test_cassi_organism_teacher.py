import tempfile
import unittest
from pathlib import Path

import numpy as np
import torch

from cassi_organism_law import CassiOrganismLawError, _capture_digest
from cassi_organism_teacher import (
    CassiTeacherWeaveError,
    runtime_artifact_sha256,
    teacher_weave_from_decode,
)
from l18_generated_token_trajectory import (
    DecodeRecord,
    VectorCapture,
)

MODEL_SHA = "a" * 64
RUNTIME_SHA = "b" * 64
WRONG_SHA = "not-a-digest"
HIDDEN_DIMENSION = 5120


def _trunk_values(layer_index: int) -> np.ndarray:
    """Small finite nonzero trunk vector, distinct per layer."""
    return np.full(HIDDEN_DIMENSION, 0.001, dtype=np.float32) + layer_index * 1e-5


def _head_values() -> np.ndarray:
    """Distinct layer-64 reference, clearly outside the trunk band."""
    return np.full(HIDDEN_DIMENSION, 0.5, dtype=np.float32)


def _make_record(*, token_index: int = 3) -> DecodeRecord:
    trunk = tuple(
        VectorCapture(
            token_index=token_index,
            token_position=0,
            layer_index=layer_index,
            role="field_trunk",
            values=_trunk_values(layer_index),
        )
        for layer_index in range(64)
    )
    head = VectorCapture(
        token_index=token_index,
        token_position=0,
        layer_index=64,
        role="head_output_reference",
        values=_head_values(),
    )
    logits = np.arange(64, dtype=np.float32) * 0.01
    return DecodeRecord(
        protocol="CassiQwen L18 generated-token field-output trajectory",
        version=1,
        decode_index=0,
        token_index=token_index,
        mode="token",
        token_ids=(42,),
        token_positions=(0,),
        token_pieces=("a",),
        trunk=trunk,
        head_output_reference=head,
        ordinary_logits=logits,
    )


class TeacherWeaveAdapterTests(unittest.TestCase):
    def test_valid_weave_matches_record_and_excludes_head(self) -> None:
        record = _make_record(token_index=3)
        weave = teacher_weave_from_decode(
            record, source_model_sha256=MODEL_SHA, source_runtime_sha256=RUNTIME_SHA
        )

        self.assertEqual(weave.token_index, 3)
        self.assertEqual(weave.source_model_sha256, MODEL_SHA)
        self.assertEqual(weave.source_runtime_sha256, RUNTIME_SHA)
        self.assertEqual(len(weave.layer_vectors), 64)

        expected_digest = _capture_digest(
            weave.layer_vectors,
            source_model_sha256=MODEL_SHA,
            source_runtime_sha256=RUNTIME_SHA,
            token_index=3,
        )
        self.assertEqual(weave.capture_sha256, expected_digest)
        self.assertEqual(len(weave.capture_sha256), 64)
        self.assertTrue(all(ch in "0123456789abcdef" for ch in weave.capture_sha256))

        for index, layer in enumerate(weave.layer_vectors):
            self.assertEqual(layer.dtype, torch.float32)
            self.assertEqual(layer.device.type, "cpu")
            self.assertFalse(layer.requires_grad)
            self.assertEqual(layer.shape, (HIDDEN_DIMENSION,))
            self.assertTrue(torch.isfinite(layer).all())
            np.testing.assert_array_equal(layer.numpy(), np.asarray(record.trunk[index].values, dtype=np.float32))

        head_bytes = np.asarray(record.head_output_reference.values, dtype=np.float32).tobytes()
        for layer in weave.layer_vectors:
            self.assertNotEqual(layer.numpy().tobytes(), head_bytes)

    def test_determinism(self) -> None:
        record = _make_record(token_index=5)
        first = teacher_weave_from_decode(record, source_model_sha256=MODEL_SHA, source_runtime_sha256=RUNTIME_SHA)
        second = teacher_weave_from_decode(record, source_model_sha256=MODEL_SHA, source_runtime_sha256=RUNTIME_SHA)
        self.assertEqual(first.capture_sha256, second.capture_sha256)

    def test_source_mutation_does_not_change_weave(self) -> None:
        record = _make_record(token_index=2)
        weave = teacher_weave_from_decode(record, source_model_sha256=MODEL_SHA, source_runtime_sha256=RUNTIME_SHA)
        before_digest = weave.capture_sha256
        before_bytes = [layer.numpy().tobytes() for layer in weave.layer_vectors]

        for capture in record.trunk:
            capture.values[...] += 1.0

        self.assertEqual(weave.capture_sha256, before_digest)
        for index, layer in enumerate(weave.layer_vectors):
            self.assertEqual(layer.numpy().tobytes(), before_bytes[index])

        rebuilt = teacher_weave_from_decode(record, source_model_sha256=MODEL_SHA, source_runtime_sha256=RUNTIME_SHA)
        self.assertNotEqual(rebuilt.capture_sha256, before_digest)

    def test_rejects_wrong_type(self) -> None:
        for bad in (None, object(), (1, 2, 3), {"trunk": ()}, _make_record().trunk):
            with self.assertRaises(CassiTeacherWeaveError):
                teacher_weave_from_decode(bad, source_model_sha256=MODEL_SHA, source_runtime_sha256=RUNTIME_SHA)

    def test_rejects_wrong_order(self) -> None:
        record = _make_record()
        trunk = list(record.trunk)
        trunk[0], trunk[1] = trunk[1], trunk[0]
        object.__setattr__(record, "trunk", tuple(trunk))
        with self.assertRaises(CassiTeacherWeaveError):
            teacher_weave_from_decode(record, source_model_sha256=MODEL_SHA, source_runtime_sha256=RUNTIME_SHA)

    def test_rejects_missing_layers(self) -> None:
        record = _make_record()
        object.__setattr__(record, "trunk", record.trunk[:63])
        with self.assertRaises(CassiTeacherWeaveError):
            teacher_weave_from_decode(record, source_model_sha256=MODEL_SHA, source_runtime_sha256=RUNTIME_SHA)

    def test_rejects_wrong_role(self) -> None:
        record = _make_record()
        bad_capture = record.trunk[0]
        object.__setattr__(bad_capture, "role", "head_output_reference")
        object.__setattr__(record, "trunk", (bad_capture,) + record.trunk[1:])
        with self.assertRaises(CassiTeacherWeaveError):
            teacher_weave_from_decode(record, source_model_sha256=MODEL_SHA, source_runtime_sha256=RUNTIME_SHA)

    def test_rejects_bad_digest_provenance_and_chains(self) -> None:
        record = _make_record()
        with self.assertRaises(CassiTeacherWeaveError) as ctx:
            teacher_weave_from_decode(record, source_model_sha256=WRONG_SHA, source_runtime_sha256=RUNTIME_SHA)
        self.assertIsInstance(ctx.exception.__cause__, CassiOrganismLawError)


class RuntimeArtifactSha256Tests(unittest.TestCase):
    def test_digest_binds_content_order_and_filename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            alpha = Path(tmp) / "alpha.bin"
            beta = Path(tmp) / "beta.bin"
            alpha.write_bytes(b"alpha-bytes")
            beta.write_bytes(b"beta-bytes")

            stable = runtime_artifact_sha256([alpha, beta])
            self.assertEqual(stable, runtime_artifact_sha256([alpha, beta]))

            alpha.write_bytes(b"ALPHA-BYTES")
            changed_content = runtime_artifact_sha256([alpha, beta])
            self.assertNotEqual(changed_content, stable)

            alpha.write_bytes(b"alpha-bytes")
            swapped_order = runtime_artifact_sha256([beta, alpha])
            self.assertNotEqual(swapped_order, stable)

            gamma = Path(tmp) / "gamma.bin"
            gamma.write_bytes(b"alpha-bytes")
            renamed = runtime_artifact_sha256([gamma, beta])
            self.assertNotEqual(renamed, stable)
            self.assertNotEqual(renamed, changed_content)

    def test_rejects_empty_missing_duplicate_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "real.bin"
            file_path.write_bytes(b"payload")

            with self.assertRaises(CassiTeacherWeaveError):
                runtime_artifact_sha256([])

            with self.assertRaises(CassiTeacherWeaveError):
                runtime_artifact_sha256([file_path, file_path])

            with self.assertRaises(CassiTeacherWeaveError):
                runtime_artifact_sha256([Path(tmp) / "missing.bin"])

            with self.assertRaises(CassiTeacherWeaveError):
                runtime_artifact_sha256([tmp])


if __name__ == "__main__":
    unittest.main()
