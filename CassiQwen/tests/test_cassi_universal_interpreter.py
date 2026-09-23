#!/usr/bin/env python3
"""Behavioral contracts for the universal interpreter boundary."""

from __future__ import annotations

import hashlib
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import numpy as np

from cassi_raw_event_field import AcquisitionProfile
from cassi_universal_interpreter import (
    ActivationTrace,
    CausalPair,
    ModelIdentity,
    OutputSnapshot,
    UniversalLLMInterpreter,
    WeightSlice,
)


MODEL = ModelIdentity(
    model_id="test-model",
    model_sha256="11" * 32,
    architecture="test-hybrid",
    quantization="f32",
    tokenizer_sha256="22" * 32,
    runtime_id="test-runtime",
    runtime_sha256="33" * 32,
    context_tokens=64,
    embedding_width=8,
    layer_count=4,
    backend="test",
    hook_sites=("layer_input",),
)


class UniversalInterpreterTests(unittest.TestCase):
    @staticmethod
    def _trace(sequence_id: str, values: list[float], *, adapter_key: str | None = "shared-coordinate") -> ActivationTrace:
        logits = np.full(43, -2.0, dtype=np.float32)
        logits[42] = 1.0
        return ActivationTrace(
            model=MODEL,
            site="layer_input",
            layer=2,
            sequence_id=sequence_id,
            position=7,
            values=np.asarray(values, dtype=np.float32),
            expected_token_id=42,
            logits=logits,
            adapter_key=adapter_key,
            prompt_sha256=hashlib.sha256(b"prompt").hexdigest(),
        )

    @staticmethod
    def _profile() -> AcquisitionProfile:
        return AcquisitionProfile(
            wave_width=512,
            payload_limit=16,
            minimum_score=0.58,
            minimum_margin=0.08,
        )
    @classmethod
    def _role_trace(
        cls,
        sequence_id: str,
        values: list[float],
        *,
        coordinate: str,
        role: str,
    ) -> ActivationTrace:
        trace = cls._trace(sequence_id, values, adapter_key=coordinate)
        trace = replace(
            trace,
            capture_sha256=hashlib.sha256(
                f"capture:{sequence_id}".encode("utf-8")
            ).hexdigest(),
        )
        return trace.with_role_attestation(role)

    def test_observatory_trace_is_immutable_and_reads_model_output(self) -> None:
        trace = self._trace("read", [0.25, -0.5, 0.75, 1.0])
        before = trace.values_sha256
        with self.assertRaises(ValueError):
            trace.values[0] = 9.0
        self.assertEqual(trace.values_sha256, before)
        readout = trace.readout()
        self.assertIsNotNone(readout)
        self.assertEqual(readout.top_token_id, 42)
        self.assertGreater(readout.decision_gap, 0.0)
        self.assertEqual(trace.model_next_token_id, 42)
        self.assertEqual(trace.field_coordinate_descriptor()["coordinate_source"], "adapter-key")

    def test_field_prediction_transfers_to_unfamiliar_trace_and_survives_restart(self) -> None:
        training = self._trace(
            "training",
            [0.25, -0.5, 0.75, 1.25, -1.5, 0.125, 0.875, -0.25],
        )
        held_out = self._trace(
            "held-out",
            [-2.0, 1.0, 0.5, -0.125, 1.75, -0.75, 0.375, 0.625],
        )
        meaning = {
            "kind": "correction",
            "next_token_id": 42,
            "text": "42",
            "rule": "field-owned correction",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with UniversalLLMInterpreter(root, model=MODEL, profile=self._profile()) as interpreter:
                initial = interpreter.state_receipt()["field_state_sha256"]
                inspection = interpreter.inspect(training)
                self.assertEqual(inspection["field_state_sha256"], initial)
                learned = interpreter.learn(
                    training,
                    question="Which correction is required?",
                    meaning=meaning,
                )
                self.assertEqual(learned["status"], "learned")
                field_after_learning = learned["field_state_sha256"]
                query = interpreter.query(
                    held_out,
                    question="Which correction is required?",
                )
                self.assertEqual(query["status"], "field-owned")
                self.assertEqual(query["prediction"]["meaning"], meaning)
                self.assertTrue(query["prediction"]["target_token_match"])

            with UniversalLLMInterpreter(root, model=MODEL, profile=self._profile()) as restarted:
                self.assertEqual(
                    restarted.state_receipt()["field_state_sha256"],
                    field_after_learning,
                )
                resumed = restarted.query(
                    held_out,
                    question="Which correction is required?",
                )
                self.assertEqual(resumed["status"], "field-owned")
                self.assertEqual(resumed["prediction"]["meaning"], meaning)
                self.assertFalse(resumed["native_fallback"])

    def test_new_model_requires_explicit_fixed_translation_coordinate(self) -> None:
        other_model = ModelIdentity(
            model_id="other-model",
            model_sha256="44" * 32,
            architecture="other-hybrid",
            quantization="q4",
            tokenizer_sha256="55" * 32,
            runtime_id="other-runtime",
            runtime_sha256="66" * 32,
            context_tokens=64,
            embedding_width=8,
            layer_count=4,
            backend="test",
            hook_sites=("layer_input",),
        )
        trace = ActivationTrace(
            model=other_model,
            site="layer_input",
            layer=2,
            sequence_id="other",
            position=1,
            values=np.ones(8, dtype=np.float32),
        )
        with tempfile.TemporaryDirectory() as directory:
            with UniversalLLMInterpreter(
                Path(directory), model=MODEL, profile=self._profile()
            ) as interpreter:
                with self.assertRaisesRegex(ValueError, "adapter_key"):
                    interpreter.inspect(trace)
                translated = ActivationTrace(
                    model=other_model,
                    site=trace.site,
                    layer=trace.layer,
                    sequence_id=trace.sequence_id,
                    position=trace.position,
                    values=trace.values,
                    adapter_key="other-adapter/fixed-coordinate-v1",
                )
                inspected = interpreter.inspect(translated)
                self.assertEqual(inspected["trace"]["field_coordinate"]["coordinate_source"], "adapter-key")

    def test_role_gate_rejects_tampered_provenance_before_field_access(self) -> None:
        registry = {
            "correction-coordinate": {
                "semantic_role": "correction",
                "model_fingerprint": MODEL.fingerprint,
            },
            "delay-coordinate": {
                "semantic_role": "delay",
                "model_fingerprint": MODEL.fingerprint,
            },
        }
        training = self._role_trace(
            "role-training",
            [0.25, -0.5, 0.75, 1.25, -1.5, 0.125, 0.875, -0.25],
            coordinate="correction-coordinate",
            role="correction",
        )
        held_out = self._role_trace(
            "role-held-out",
            [-2.0, 1.0, 0.5, -0.125, 1.75, -0.75, 0.375, 0.625],
            coordinate="correction-coordinate",
            role="correction",
        )
        unknown = self._role_trace(
            "role-unknown",
            [0.5, 0.25, -0.75, 1.5, -1.25, 0.375, 0.625, -0.125],
            coordinate="unknown-coordinate",
            role="unknown",
        )
        mismatched = self._role_trace(
            "role-mismatched",
            [0.5, 0.25, -0.75, 1.5, -1.25, 0.375, 0.625, -0.125],
            coordinate="delay-coordinate",
            role="correction",
        )
        altered_capture = replace(held_out, capture_sha256="00" * 32)
        other_model = replace(
            MODEL,
            model_id="other-model",
            model_sha256="44" * 32,
            tokenizer_sha256="55" * 32,
            runtime_id="other-runtime",
            runtime_sha256="66" * 32,
        )
        cross_model = replace(
            held_out,
            model=other_model,
            role_attestation=None,
        ).with_role_attestation("correction")
        meaning = {"kind": "role-bound-correction", "value": 11}

        def marker(interpreter: UniversalLLMInterpreter) -> dict[str, object]:
            state = interpreter.state_receipt()
            return {
                key: state[key]
                for key in (
                    "field_state_sha256",
                    "event_count",
                    "active_event_count",
                    "meaning_count",
                    "model_count",
                )
            }

        with tempfile.TemporaryDirectory() as directory:
            with UniversalLLMInterpreter(
                Path(directory),
                model=MODEL,
                profile=self._profile(),
                role_registry=registry,
            ) as interpreter:
                learned = interpreter.learn(
                    training,
                    question="Which correction is required?",
                    meaning=meaning,
                )
                self.assertEqual(learned["status"], "learned")
                query = interpreter.query(
                    held_out,
                    question="Which correction is required?",
                )
                self.assertEqual(query["status"], "field-owned")
                self.assertEqual(query["prediction"]["meaning"], meaning)

                for trace, message in (
                    (unknown, "unregistered role coordinate"),
                    (mismatched, "native role-coordinate mismatch"),
                    (altered_capture, "invalid role attestation"),
                    (cross_model, "role coordinate model mismatch"),
                ):
                    before = marker(interpreter)
                    with self.assertRaisesRegex(ValueError, message):
                        interpreter.query(
                            trace,
                            question="Which correction is required?",
                        )
                    self.assertEqual(marker(interpreter), before)

    def test_native_role_manifest_rejects_semantic_misbinding_before_field_access(self) -> None:
        registry = {
            "correction-coordinate": {
                "semantic_role": "correction",
                "model_fingerprint": MODEL.fingerprint,
            },
            "delay-coordinate": {
                "semantic_role": "delay",
                "model_fingerprint": MODEL.fingerprint,
            },
        }
        correction = self._role_trace(
            "manifest-correction",
            [0.25, -0.5, 0.75, 1.25, -1.5, 0.125, 0.875, -0.25],
            coordinate="correction-coordinate",
            role="correction",
        )
        manifest = [
            {
                "model_fingerprint": MODEL.fingerprint,
                "prompt_sha256": correction.prompt_sha256,
                "capture_sha256": correction.capture_sha256,
                "native_role": "correction",
                "semantic_source": "independent-native-prompt-classifier-v1",
            }
        ]
        semantically_misbound = replace(
            correction,
            adapter_key="delay-coordinate",
            role_attestation=None,
        ).with_role_attestation("delay")
        unregistered_evidence = replace(
            correction,
            prompt_sha256=hashlib.sha256(b"unregistered-native-prompt").hexdigest(),
            role_attestation=None,
        ).with_role_attestation("correction")

        def marker(interpreter: UniversalLLMInterpreter) -> dict[str, object]:
            state = interpreter.state_receipt()
            return {
                key: state[key]
                for key in (
                    "field_state_sha256",
                    "event_count",
                    "active_event_count",
                    "meaning_count",
                    "model_count",
                )
            }

        with tempfile.TemporaryDirectory() as directory:
            with UniversalLLMInterpreter(
                Path(directory),
                model=MODEL,
                profile=self._profile(),
                role_registry=registry,
                native_role_manifest=manifest,
            ) as interpreter:
                learned = interpreter.learn(
                    correction,
                    question="Which correction is required?",
                    meaning={"kind": "manifest-checked-correction"},
                )
                self.assertEqual(learned["status"], "learned")
                before = marker(interpreter)
                for trace, message in (
                    (semantically_misbound, "native role evidence mismatch"),
                    (unregistered_evidence, "unregistered native role evidence"),
                ):
                    with self.assertRaisesRegex(ValueError, message):
                        interpreter.query(
                            trace,
                            question="Which correction is required?",
                        )
                    self.assertEqual(marker(interpreter), before)

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "requires role_registry"):
                UniversalLLMInterpreter(
                    Path(directory),
                    model=MODEL,
                    profile=self._profile(),
                    native_role_manifest=manifest,
                )

    def test_causal_pair_distinguishes_graph_execution_from_offline_counterfactual(self) -> None:
        common = {
            "model": MODEL,
            "site": "layer_input",
            "layer": 2,
            "sequence_id": "causal",
            "position": 5,
            "prompt_sha256": hashlib.sha256(b"prompt").hexdigest(),
            "executed": True,
            "capture_id": "pair",
        }
        baseline = OutputSnapshot(
            logits=np.asarray([0.0, 2.0, 1.0], dtype=np.float32),
            route="graph-native",
            **common,
        )
        lesion = OutputSnapshot(
            logits=np.asarray([0.0, 0.5, 1.5], dtype=np.float32),
            route="graph-native",
            **common,
        )
        graph_result = CausalPair(baseline=baseline, lesion=lesion).assess()
        self.assertEqual(graph_result["status"], "causal-effect")
        self.assertTrue(graph_result["decision_flip"])
        offline_result = CausalPair(
            baseline=OutputSnapshot(
                logits=baseline.logits,
                route="activation-space-counterfactual",
                **common,
            ),
            lesion=OutputSnapshot(
                logits=lesion.logits,
                route="activation-space-counterfactual",
                **common,
            ),
        ).assess()
        self.assertEqual(offline_result["status"], "counterfactual-only")
        self.assertFalse(offline_result["graph_native_executed"])

    def test_weight_slice_has_bounded_shape_and_nonrecursive_receipt(self) -> None:
        slice_ = WeightSlice.from_array(
            np.asarray([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32),
            model=MODEL,
            tensor_name="output.weight",
            tensor_shape=(8, 8),
            row_start=2,
            column_start=3,
        )
        receipt = slice_.as_dict()
        self.assertEqual(receipt["values_shape"], [2, 2])
        self.assertEqual(receipt["raw_bytes_touched"], 16)
        self.assertEqual(len(receipt["fingerprint"]), 64)
        with self.assertRaises(ValueError):
            WeightSlice.from_array(
                np.zeros((2, 2), dtype=np.float32),
                model=MODEL,
                tensor_name="bad",
                tensor_shape=(8, 8),
                row_start=7,
                column_start=7,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
