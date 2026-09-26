#!/usr/bin/env python3
"""Behavioral coverage for model identity, envelopes, and paired recovery."""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from cassi_field_qwen_workbench import CassiFieldWorkMemory, WorkMemoryRecord
from cassi_model_instrument import (
    AdapterCapabilities,
    CoupledTransactionJournal,
    ModelInstrumentIdentity,
    NumericEnvelope,
    UnsupportedCapability,
)


def digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def identity() -> ModelInstrumentIdentity:
    return ModelInstrumentIdentity(
        adapter_id="test-native",
        adapter_version="1",
        model_sha256=digest("model"),
        architecture="qwen3.5",
        quantization="q4_0",
        tokenizer_sha256=digest("tokenizer"),
        runtime_sha256=digest("runtime"),
        hook_sha256=digest("hook"),
        arithmetic_profile="f32-test",
        context_policy="single-sequence",
        backend="cpu",
    )


def capabilities() -> AdapterCapabilities:
    return AdapterCapabilities(
        profile="latent-instrument",
        structured_requests=True,
        activation_observation_sites=("qwen35.block.3.input",),
        intervention_sites=("qwen35.block.3.input",),
        trial_state="exact-snapshot",
        selective_operations=("qwen-forward",),
        emission_owner="model",
        native_persistence="exact",
        partial_acceptance=False,
        cancellation=True,
        max_elements=16,
    )


def envelope(owner_root: str, producer: str) -> NumericEnvelope:
    return NumericEnvelope.from_f32(
        [1.0, -2.0, 3.0, -4.0],
        shape=(1, 4),
        routing={
            "principal": "principal-a",
            "session": "session-a",
            "episode": "episode-a",
            "operation": "capture-a",
            "sequence": 4,
            "producer_identity": producer,
            "trial_ancestry": [],
            "accepted_prefix": 0,
        },
        meaning={
            "kind": "activation-observation",
            "site": "qwen35.block.3.input",
            "frame": "qwen35-residual-f32",
            "semantic_question": {"kind": "distinguish-role"},
            "epistemic_attribution": "model-instrument-observation",
        },
        state_dependency={
            "field_predecessor": owner_root,
            "native_predecessor": digest("native-before"),
            "adapter_identity": producer,
            "model_identity": digest("model"),
            "profile": "latent-instrument",
            "catalog_identity": digest("catalog"),
            "read_versions": [],
            "write_versions": [],
        },
        work={
            "maximum": 16,
            "consumed": 4,
            "status": "complete",
            "disposition": "committed",
            "continuation_id": "capture-a:done",
        },
        trust={
            "evidence_scope": "principal-a",
            "access_scope": "activation-opt-in",
            "required_capability": "activation-observation",
        },
        max_elements=16,
    )


class ModelInstrumentTests(unittest.TestCase):
    def test_envelope_validates_bytes_identity_and_capability_refusal(self) -> None:
        adapter = identity()
        value = envelope(digest("field-before"), adapter.fingerprint)
        rebuilt = NumericEnvelope.from_dict(value.as_dict())
        self.assertEqual(rebuilt.validate(max_elements=16), value.validate(max_elements=16))
        self.assertEqual(rebuilt.payload_sha256, value.payload_sha256)
        self.assertEqual(value.as_dict()["numeric_payload"]["strides"], [16, 4])
        self.assertTrue(capabilities().supports("activation-observation", site="qwen35.block.3.input"))
        with self.assertRaises(UnsupportedCapability) as caught:
            capabilities().require("partial-acceptance")
        self.assertEqual(caught.exception.result()["status"], "unsupported-adapter-capability")
        changed = value.as_dict()
        changed["numeric_payload"]["payload_bytes"] = 8
        with self.assertRaisesRegex(ValueError, "allocation"):
            NumericEnvelope.from_dict(changed)
        changed_magnitude = value.as_dict()
        changed_magnitude["numeric_payload"]["magnitude_l2"] = 1.0
        with self.assertRaisesRegex(ValueError, "magnitude"):
            NumericEnvelope.from_dict(changed_magnitude)

    def test_coupled_journal_exposes_each_crash_window_and_exact_pair(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            journal = CoupledTransactionJournal(root / "journal")
            adapter = identity()
            field_before = digest("field-before")
            journal.reserve(
                operation_id="op-a",
                routing={"principal": "p", "session": "s", "sequence": 1},
                identity=adapter,
                field_predecessor=field_before,
                native_predecessor={"sha256": digest("native-before")},
                reservation={"field": 2, "native": 8},
                continuation_class="exact-pair",
            )
            self.assertEqual(journal.recover("op-a", field_root=field_before)["status"], "unaccepted-trial")
            journal.stage("op-a", trial={"trial": "a"}, measured_lower=4, measured_upper=4, exact=True)
            self.assertEqual(journal.recover("op-a", field_root=field_before)["status"], "unaccepted-trial")
            native = root / "native-after.bin"
            native.write_bytes(b"native successor")
            field_after = digest("field-after")
            journal.seal(
                "op-a",
                field_successor=field_after,
                native_successor={"path": str(native), "sha256": hashlib.sha256(native.read_bytes()).hexdigest()},
                delivery={"delivery_id": "delivery-a"},
            )
            self.assertEqual(journal.recover("op-a", field_root=field_before)["status"], "publication-reconciliation-required")
            journal.commit("op-a")
            self.assertEqual(journal.recover("op-a", field_root=field_after)["status"], "exact-pair")
            native.write_bytes(b"changed")
            self.assertEqual(journal.recover("op-a", field_root=field_after)["status"], "native-continuation-unavailable")
            self.assertEqual(journal.commit("op-a")["status"], "committed")
            with self.assertRaisesRegex(RuntimeError, "conflicts"):
                journal.reserve(
                    operation_id="op-a",
                    routing={"principal": "different", "session": "s", "sequence": 1},
                    identity=adapter,
                    field_predecessor=field_before,
                    native_predecessor={"sha256": digest("native-before")},
                    reservation={"field": 2, "native": 8},
                    continuation_class="exact-pair",
                )

    def test_workbench_runs_resident_reasoning_development_and_observation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with CassiFieldWorkMemory(Path(directory)) as memory:
                learned = memory.learn(
                    WorkMemoryRecord(
                        source_id="workshop.setting",
                        context={"workspace": "workshop", "topic": "setting"},
                        payload={"setting": 7},
                        observed_timestamp="2026-09-14T00:00:00Z",
                    )
                )
                binding_id = learned["binding_id"]
                reasoned = memory.reason(
                    episode_id="setting-query",
                    question={"binding_id": binding_id},
                    request={
                        "operation": "query",
                        "operation_id": "setting-query-child",
                        "query": {"kind": "binding", "binding_id": binding_id},
                    },
                    allocation={"evidence_reads": 1, "model_calls": 0, "storage_words": 64, "work": 32},
                )
                self.assertEqual(reasoned["status"], "supported")
                self.assertEqual(
                    reasoned["result"]["binding"]["id"],
                    binding_id,
                )
                developed = memory.develop(
                    episode_id="setting-reflection",
                    specification={
                        "capability_target": {"binding_id": binding_id},
                        "diagnosis": "method-selection",
                        "remit": {"purpose": "improve-current-reasoning"},
                        "available_information": {"source_revision_ids": [learned["source_revision_id"]]},
                        "capabilities": {"evidence_reads": True, "model_calls": False, "sandbox": False},
                        "write_classes": [],
                        "allocation": {"evidence_reads": 1, "model_calls": 0, "storage_words": 128, "work": 32},
                        "assessment": {"predicted": {"setting": 7}, "actual": {"setting": 7}},
                        "stopping_condition": {"max_attempts": 1},
                    },
                )
                self.assertEqual(developed["status"], "supported")
                self.assertEqual(developed["selected_skill"], "reflect")
                adapter = identity()
                captured = envelope(
                    memory.owner.state.state_sha256,
                    adapter.fingerprint,
                )
                observed = memory.admit_model_observation(
                    captured,
                    capabilities=capabilities(),
                    identity_sha256=adapter.fingerprint,
                    observed_timestamp="2026-09-14T00:01:00Z",
                )
                replay = memory.admit_model_observation(
                    captured,
                    capabilities=capabilities(),
                    identity_sha256=adapter.fingerprint,
                    observed_timestamp="2026-09-14T00:01:00Z",
                )
                self.assertIn(replay["status"], {"unchanged", "replayed"})
                self.assertEqual(replay["source_revision_id"], observed["source_revision_id"])


if __name__ == "__main__":
    unittest.main()
