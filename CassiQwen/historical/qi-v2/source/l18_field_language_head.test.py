"""Pure tests for the L18 GGUF field-language output head.

The fixture is a tiny synthetic GGUF v3 file.  It uses a Python callback as a
stand-in for the pinned native dequantizer and never opens the checked-in model
or ggml-base.dll.
"""

from __future__ import annotations

import ctypes as ct
import math
import struct
import tempfile
import unittest
from pathlib import Path
from typing import Any

import numpy as np

from l18_field_language_head import (
    GGML_TYPE_F32,
    GGML_TYPE_Q6_K,
    Q6_K_BLOCK_BYTES,
    FieldLanguageHead,
    _decode_q6_k_reference,
    parse_gguf,
)


NORM_EPSILON = 1.0e-5
HIDDEN = 256
VOCABULARY = 2
ALIGNMENT = 32


def align_up(value: int, alignment: int) -> int:
    return ((value + alignment - 1) // alignment) * alignment


def gguf_string(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return struct.pack("<Q", len(encoded)) + encoded


def metadata_entry(key: str, value_type: int, value: bytes) -> bytes:
    return gguf_string(key) + struct.pack("<I", value_type) + value


def q6_constant(value: int) -> bytes:
    """Encode a 256-value Q6_K block whose every value is ``value``."""
    if value not in (1, 2):
        raise ValueError(value)
    nibble = value
    # q = 32 + value: low nibble is value and the two high bits are 2.
    block = bytearray(Q6_K_BLOCK_BYTES)
    block[0:128] = bytes([(nibble << 4) | nibble]) * 128
    block[128:192] = bytes([0xAA]) * 64
    block[192:208] = bytes([1]) * 16
    struct.pack_into("<e", block, 208, 1.0)
    return bytes(block)


def synthetic_gguf(path: Path) -> tuple[int, int]:
    metadata = b"".join(
        (
            metadata_entry("general.architecture", 8, gguf_string("qwen3.5")),
            metadata_entry("general.alignment", 4, struct.pack("<I", ALIGNMENT)),
            metadata_entry(
                "qwen3.5.attention.layer_norm_rms_epsilon", 6, struct.pack("<f", NORM_EPSILON)
            ),
        )
    )
    output_bytes = q6_constant(1) + q6_constant(2)
    output_offset = 0
    norm_offset = align_up(len(output_bytes), ALIGNMENT)
    norm = np.linspace(1.0, 1.5, HIDDEN, dtype="<f4").tobytes()
    descriptors = b"".join(
        (
            gguf_string("output.weight")
            + struct.pack("<I", 2)
            + struct.pack("<QQ", HIDDEN, VOCABULARY)
            + struct.pack("<IQ", GGML_TYPE_Q6_K, output_offset),
            gguf_string("output_norm.weight")
            + struct.pack("<I", 1)
            + struct.pack("<Q", HIDDEN)
            + struct.pack("<IQ", GGML_TYPE_F32, norm_offset),
        )
    )
    header = struct.pack("<4sIQQ", b"GGUF", 3, 2, 3) + metadata + descriptors
    data_start = align_up(len(header), ALIGNMENT)
    payload = bytearray(data_start - len(header))
    payload.extend(output_bytes)
    payload.extend(b"\0" * (norm_offset - len(output_bytes)))
    payload.extend(norm)
    path.write_bytes(header + payload)
    return data_start, norm_offset


def fake_dequantize_row(source: Any, destination: Any, count: int) -> None:
    raw = ct.string_at(source, count // 256 * Q6_K_BLOCK_BYTES)
    decoded = _decode_q6_k_reference(raw)
    target = np.ctypeslib.as_array(destination, shape=(count,))
    target[:] = decoded
class FieldLanguageHeadTest(unittest.TestCase):
    def test_q6_block_and_rms_logits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            model_path = Path(directory) / "synthetic.gguf"
            data_start, norm_offset = synthetic_gguf(model_path)
            layout = parse_gguf(model_path)
            self.assertEqual(layout.version, 3)
            self.assertEqual(layout.data_start, data_start)
            self.assertEqual(layout.tensor("output.weight").dimensions, (HIDDEN, VOCABULARY))
            self.assertEqual(layout.tensor("output.weight").ggml_type, GGML_TYPE_Q6_K)
            self.assertEqual(layout.tensor("output_norm.weight").offset, norm_offset)
            self.assertEqual(_decode_q6_k_reference(q6_constant(1))[:32].tolist(), [1.0] * 32)
            self.assertEqual(_decode_q6_k_reference(q6_constant(2))[:32].tolist(), [2.0] * 32)

            head = FieldLanguageHead(
                model_path,
                enabled=True,
                chunk_tokens=1,
                expected_hidden_dimension=HIDDEN,
                expected_vocabulary_size=VOCABULARY,
                dequantize_row=fake_dequantize_row,
            )
            try:
                field = np.linspace(-0.75, 1.25, HIDDEN, dtype=np.float32)
                norm = np.linspace(1.0, 1.5, HIDDEN, dtype=np.float32)
                mean_square = np.sum(field * field, dtype=np.float32) / HIDDEN
                inverse_rms = np.float32(1.0 / math.sqrt(float(mean_square) + NORM_EPSILON))
                normalized = field * inverse_rms * norm
                expected = np.array(
                    [
                        np.sum(normalized, dtype=np.float32),
                        np.sum(normalized * np.float32(2.0), dtype=np.float32),
                    ],
                    dtype=np.float32,
                )
                actual = head.logits(field)
                self.assertEqual(actual.shape, (VOCABULARY,))
                np.testing.assert_allclose(actual, expected, rtol=2.0e-6, atol=2.0e-6)
            finally:
                head.close(unload_dll=False)

            with self.assertRaisesRegex(RuntimeError, "closed"):
                head.logits(np.ones(HIDDEN, dtype=np.float32))

    def test_bounded_candidate_rows_and_logits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            model_path = Path(directory) / "synthetic.gguf"
            synthetic_gguf(model_path)
            head = FieldLanguageHead(
                model_path,
                enabled=True,
                expected_hidden_dimension=HIDDEN,
                expected_vocabulary_size=VOCABULARY,
                dequantize_row=fake_dequantize_row,
            )
            try:
                features = np.ones(HIDDEN, dtype=np.float32)
                rows = head.candidate_rows([1, 0, 1])
                self.assertEqual(rows.shape, (3, HIDDEN))
                self.assertEqual(rows.dtype, np.dtype(np.float32))
                self.assertTrue(rows.flags.c_contiguous)
                np.testing.assert_allclose(rows, np.array([[2.0] * HIDDEN, [1.0] * HIDDEN, [2.0] * HIDDEN], dtype=np.float32))
                logits = head.candidate_logits_from_output_features(features, [1, 0, 1])
                np.testing.assert_allclose(logits, np.array([2.0 * HIDDEN, HIDDEN, 2.0 * HIDDEN], dtype=np.float32))

                field = np.ones(HIDDEN, dtype=np.float32)
                expected_features = head.output_features(field)
                expected = np.array(
                    [
                        np.sum(expected_features * np.float32(2.0), dtype=np.float32),
                        np.sum(expected_features, dtype=np.float32),
                    ],
                    dtype=np.float32,
                )
                actual = head.candidate_logits(field, [1, 0])
                np.testing.assert_allclose(actual, expected, rtol=2.0e-6, atol=2.0e-6)
                for invalid in ([], [True], [0.0], [[0]], [-1], [VOCABULARY]):
                    with self.assertRaises(RuntimeError):
                        head.candidate_rows(invalid)
            finally:
                head.close(unload_dll=False)

            disabled = FieldLanguageHead(
                model_path,
                expected_hidden_dimension=HIDDEN,
                expected_vocabulary_size=VOCABULARY,
                dequantize_row=fake_dequantize_row,
            )
            try:
                with self.assertRaisesRegex(RuntimeError, "disabled"):
                    disabled.candidate_rows([0])
                with self.assertRaisesRegex(RuntimeError, "disabled"):
                    disabled.candidate_logits_from_output_features(features, [0])
                with self.assertRaisesRegex(RuntimeError, "disabled"):
                    disabled.candidate_logits(field, [0])
            finally:
                disabled.close(unload_dll=False)



    def test_default_field_off_does_not_substitute_embeddings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            model_path = Path(directory) / "synthetic.gguf"
            synthetic_gguf(model_path)
            head = FieldLanguageHead(
                model_path,
                expected_hidden_dimension=HIDDEN,
                expected_vocabulary_size=VOCABULARY,
                dequantize_row=fake_dequantize_row,
            )
            try:
                with self.assertRaisesRegex(RuntimeError, "disabled"):
                    head.logits(np.ones(HIDDEN, dtype=np.float32))
            finally:
                head.close(unload_dll=False)


if __name__ == "__main__":
    unittest.main()
