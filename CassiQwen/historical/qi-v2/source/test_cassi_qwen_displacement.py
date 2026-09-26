"""Focused contracts for :mod:`cassi_qwen_displacement`.

Pure-Python receipt-schema logic.  Baseline-validation tests use synthetic JSON
fixtures (no native/torch deps).  Builder tests use the real Qi-native engine
(:func:`cassi_field_language.generate_text`) so the
``CassiQiTextResult`` validator is exercised against a genuine committed-symbol
chain.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from typing import Any


from cassi_field_language import (
    CassiQiTextEngine,
    CassiQiTextResult,
    generate_text,
)
from cassi_qi_field import QiFieldConfig, QiFieldController
from cassi_qwen_displacement import (
    QI_NATIVE_DISPLACEMENT_SCHEMA,
    QWEN_DISPLACEMENT_BASELINE_SCHEMA,
    CassiQwenDisplacementError,
    build_qi_native_displacement_receipt,
    load_qwen_displacement_baseline,
    verify_displacement_receipt_hash,
)


def _baseline_body(**overrides: Any) -> dict[str, Any]:
    reference = {
        "qwen_kv_bytes": 1024,
        "qwen_recurrent_state_bytes": 2048,
        "qwen_serialized_state_bytes": 4096,
        "qwen_weight_bytes_loaded": 17095778304,
        "qwen_layers_full_attention": 16,
        "qwen_layers_recurrent": 48,
        "qwen_layers_mtp": 1,
        "qwen_output_vocab_rows": 248320,
        "gguf_open_count": 1,
    }
    reference.update(overrides)
    body = {
        "schema": QWEN_DISPLACEMENT_BASELINE_SCHEMA,
        "receipt_sha256": "",
        "identity": {
            "model_gguf_sha256": "a" * 64,
            "runtime_binary_sha256": "b" * 64,
            "runtime_source_sha256": "c" * 64,
            "model_id": "Qwen3.8-27B-Q4_K_M.gguf",
            "context_params": {"n_ctx": 16384},
        },
        "reference": reference,
    }
    digest = hashlib.sha256(
        json.dumps(
            {k: v for k, v in body.items() if k != "receipt_sha256"},
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    body["receipt_sha256"] = digest
    return body


def _baseline_to_file(baseline: dict[str, Any]) -> str:
    handle = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(baseline, handle, sort_keys=True)
    handle.close()
    return handle.name


class BaselineValidationTests(unittest.TestCase):
    """Baseline receipt loading rejects malformed / zero-reference receipts."""

    def test_load_valid_baseline(self) -> None:
        baseline = _baseline_body()
        loaded = load_qwen_displacement_baseline(_baseline_to_file(baseline))
        self.assertEqual(loaded["reference"]["qwen_kv_bytes"], 1024)
        verify_displacement_receipt_hash(loaded)

    def test_load_preserves_measured_provenance_for_builder_revalidation(self) -> None:
        baseline = _baseline_body()
        baseline["provenance"] = {
            "footprint_export": "llama_qwen35_footprint",
            "context_field_modes": {"cassi_qi_field": False},
        }
        baseline["receipt_sha256"] = hashlib.sha256(
            json.dumps(
                {key: value for key, value in baseline.items() if key != "receipt_sha256"},
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        loaded = load_qwen_displacement_baseline(_baseline_to_file(baseline))
        self.assertEqual(loaded["provenance"], baseline["provenance"])
        verify_displacement_receipt_hash(loaded)

    def test_rejects_zero_kv_reference(self) -> None:
        with self.assertRaises(CassiQwenDisplacementError):
            load_qwen_displacement_baseline(_baseline_to_file(_baseline_body(qwen_kv_bytes=0)))

    def test_rejects_zero_weight_reference(self) -> None:
        with self.assertRaises(CassiQwenDisplacementError):
            load_qwen_displacement_baseline(_baseline_to_file(_baseline_body(qwen_weight_bytes_loaded=0)))

    def test_rejects_missing_reference_key(self) -> None:
        baseline = _baseline_body()
        del baseline["reference"]["gguf_open_count"]
        with self.assertRaises(CassiQwenDisplacementError):
            load_qwen_displacement_baseline(_baseline_to_file(baseline))

    def test_rejects_invalid_self_hash(self) -> None:
        baseline = _baseline_body()
        baseline["receipt_sha256"] = "f" * 64
        with self.assertRaises(CassiQwenDisplacementError):
            load_qwen_displacement_baseline(_baseline_to_file(baseline))

    def test_rejects_wrong_schema(self) -> None:
        baseline = _baseline_body()
        baseline["schema"] = "not-a-real-schema"
        with self.assertRaises(CassiQwenDisplacementError):
            load_qwen_displacement_baseline(_baseline_to_file(baseline))


class QiNativeBuilderTests(unittest.TestCase):
    """Builder produces a hash-linked zero-Qwen / one-Qi-field receipt for every output symbol."""

    def setUp(self) -> None:
        self.controller = QiFieldController(
            QiFieldConfig(scale_count=2, mode_count=16, alphabet_size=260)
        )
        self.engine = CassiQiTextEngine(self.controller)

    def _result(self, max_output_symbols: int = 4) -> CassiQiTextResult:
        state = self.engine.initial_state(device="cpu")
        return generate_text(
            self.controller,
            state,
            ({"role": "user", "content": "Hi"},),
            max_output_symbols=max_output_symbols,
        )

    def _baseline(self) -> dict[str, Any]:
        return _baseline_body()

    def _receipt(self, **overrides: Any) -> dict[str, Any]:
        result = self._result()
        return build_qi_native_displacement_receipt(
            baseline=self._baseline(),
            config_fingerprint=self.controller.config_fingerprint,
            codebook_fingerprint=self.controller.codebook_fingerprint,
            engine_fingerprint=self.engine.fingerprint,
            field_text_receipt_sha256=result.receipt_sha256,
            committed_output_count=len(result.output_symbols),
            **overrides,
        )

    def test_builder_returns_zero_live_qwen_counts(self) -> None:
        receipt = self._receipt()
        self.assertEqual(receipt["schema"], QI_NATIVE_DISPLACEMENT_SCHEMA)
        for name, value in receipt["qwen_serving"]["counts"].items():
            self.assertEqual(value, 0, f"{name} must be exactly zero")
        self.assertEqual(receipt["teacher"]["called"], False)
        self.assertEqual(receipt["teacher"]["calls"], 0)

    def test_builder_architecture_counters_frozen(self) -> None:
        receipt = self._receipt()
        architecture = receipt["architecture"]
        self.assertEqual(architecture["adaptive_persistent_tensor_count"], 1)
        for key in (
            "learned_parameter_count",
            "neural_layer_count",
            "optimizer_state_bytes",
            "engineered_feature_width",
        ):
            self.assertEqual(architecture[key], 0, f"{key} must be exactly zero")
        self.assertIs(architecture["probabilistic_sampler"], False)
        self.assertEqual(architecture["state_layout"], "[S,9M,B]")

    def test_builder_self_hash_round_trips(self) -> None:
        receipt = self._receipt()
        self.assertEqual(receipt["receipt_sha256"], verify_displacement_receipt_hash(receipt))

    def test_builder_links_baseline(self) -> None:
        baseline = self._baseline()
        result = self._result()
        receipt = build_qi_native_displacement_receipt(
            baseline=baseline,
            config_fingerprint=self.controller.config_fingerprint,
            codebook_fingerprint=self.controller.codebook_fingerprint,
            engine_fingerprint=self.engine.fingerprint,
            field_text_receipt_sha256=result.receipt_sha256,
            committed_output_count=len(result.output_symbols),
        )
        self.assertEqual(receipt["baseline_receipt_hash"], baseline["receipt_sha256"])

    def test_builder_binds_field_fingerprints(self) -> None:
        result = self._result()
        receipt = build_qi_native_displacement_receipt(
            baseline=self._baseline(),
            config_fingerprint=self.controller.config_fingerprint,
            codebook_fingerprint=self.controller.codebook_fingerprint,
            engine_fingerprint=self.engine.fingerprint,
            field_text_receipt_sha256=result.receipt_sha256,
            committed_output_count=len(result.output_symbols),
        )
        identity = receipt["identity"]
        self.assertEqual(identity["config_fingerprint"], self.controller.config_fingerprint)
        self.assertEqual(identity["codebook_fingerprint"], self.controller.codebook_fingerprint)
        self.assertEqual(identity["engine_fingerprint"], self.engine.fingerprint)
        field_text = receipt["field_text"]
        self.assertEqual(field_text["receipt_sha256"], result.receipt_sha256)
        self.assertEqual(field_text["committed_output_count"], len(result.output_symbols))

    def test_builder_records_field_dependence(self) -> None:
        receipt = self._receipt(field_dependence=True)
        self.assertEqual(receipt["field_decision"]["field_dependence"], True)

    def test_builder_field_dependence_null_allowed(self) -> None:
        receipt = self._receipt(field_dependence=None)
        self.assertIsNone(receipt["field_decision"]["field_dependence"])

    def test_builder_rejects_invalid_baseline(self) -> None:
        result = self._result()
        with self.assertRaises(CassiQwenDisplacementError):
            build_qi_native_displacement_receipt(
                baseline={"schema": "nope"},
                config_fingerprint=self.controller.config_fingerprint,
                codebook_fingerprint=self.controller.codebook_fingerprint,
                engine_fingerprint=self.engine.fingerprint,
                field_text_receipt_sha256=result.receipt_sha256,
                committed_output_count=len(result.output_symbols),
            )

    def test_builder_rejects_bad_fingerprint(self) -> None:
        result = self._result()
        with self.assertRaises(CassiQwenDisplacementError):
            build_qi_native_displacement_receipt(
                baseline=self._baseline(),
                config_fingerprint="not-a-digest",
                codebook_fingerprint=self.controller.codebook_fingerprint,
                engine_fingerprint=self.engine.fingerprint,
                field_text_receipt_sha256=result.receipt_sha256,
                committed_output_count=len(result.output_symbols),
            )

    def test_builder_rejects_negative_committed_count(self) -> None:
        with self.assertRaises(CassiQwenDisplacementError):
            build_qi_native_displacement_receipt(
                baseline=self._baseline(),
                config_fingerprint=self.controller.config_fingerprint,
                codebook_fingerprint=self.controller.codebook_fingerprint,
                engine_fingerprint=self.engine.fingerprint,
                field_text_receipt_sha256="d" * 64,
                committed_output_count=-1,
            )

    def test_completion_gates_all_satisfied(self) -> None:
        receipt = self._receipt()
        for gate in (
            "QI_FIELD_EMISSION",
            "KV_REMOVED",
            "RECURRENT_REMOVED",
            "WEIGHTS_NOT_LOADED",
            "ZERO_CLASSICAL_LEARNED",
        ):
            self.assertTrue(receipt["completion"][gate]["satisfied"], gate)

    def test_every_committed_output_field_owned(self) -> None:
        result = self._result()
        self.assertTrue(result.all_outputs_field_owned)
        self.assertEqual(len(result.output_receipts), len(result.output_symbols))
        receipt = self._receipt()
        self.assertIs(receipt["field_text"]["all_outputs_field_owned"], True)


if __name__ == "__main__":
    unittest.main()
