"""Focused W14A backend contract checks.

The project gate runner owns execution; this file remains a small unittest
contract surface rather than a benchmark or release suite.
"""

from __future__ import annotations

import unittest

import torch

from cassi_qi_backend import (
    ADVANCE_OPERATOR_ID,
    FIXED_OPERATOR_ID,
    QiBackendCapacityError,
    QiBackendConfigurationError,
    QiBackendUnavailable,
    QiCapacityProfile,
    QiDriveBundle,
    QiParityGuardBands,
    QiRuntimeConfig,
    TorchFlowBackend,
    compare_candidate_trajectories,
    compare_termwise_parity,
)
from cassi_qi_field import QiFlowStateV3
from cassi_qi_profile import load_development_profile


class BackendContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profile = load_development_profile()

    def cpu_backend(self, **kwargs: object) -> TorchFlowBackend:
        return TorchFlowBackend(self.profile, device="cpu", dtype=torch.float64, **kwargs)

    def test_cpu_determinism_and_probe_does_not_claim_parity(self) -> None:
        first = self.cpu_backend(seed=17)
        second = self.cpu_backend(seed=17)
        first_fixed = first.prepare(self.profile, 1, operator_id=FIXED_OPERATOR_ID)
        second_fixed = second.prepare(self.profile, 1, operator_id=FIXED_OPERATOR_ID)
        first_advance = first.prepare(self.profile, 1)
        second_advance = second.prepare(self.profile, 1)
        state = QiFlowStateV3.create(self.profile, batch_lanes=1, device="cpu")
        first_probe = first.fixed_operator_probe(state, prepared=first_fixed)
        second_probe = second.fixed_operator_probe(state, prepared=second_fixed)
        self.assertTrue(first_probe.executed)
        self.assertEqual(first_probe.parity_status, "NOT_RUN")
        self.assertEqual(first_probe.state_hashes, second_probe.state_hashes)
        first_step = first.execute_advance(state, QiDriveBundle(transaction_id="deterministic", prepared=first_advance))
        second_step = second.execute_advance(state, QiDriveBundle(transaction_id="deterministic", prepared=second_advance))
        self.assertEqual(first_step.candidate.state_sha256(self.profile), second_step.candidate.state_sha256(self.profile))
        self.assertEqual(first_step.predecessor.state_sha256(self.profile), state.state_sha256(self.profile))

    def test_adapter_identity_and_capability_receipts_are_exactly_addressed(self) -> None:
        backend = self.cpu_backend(seed=3)
        self.assertEqual(backend.identity.backend, "torch")
        self.assertEqual(backend.identity.device_type, "cpu")
        self.assertEqual(backend.identity.dtype, "float64")
        self.assertEqual(backend.identity.fallback_count, 0)
        self.assertEqual(backend.identity.capability_sha256, backend.capabilities.capability_sha256)
        self.assertEqual(backend.identity_receipt["identity_sha256"], backend.identity.content_sha256)
        self.assertEqual(backend.capability_receipt["capability_sha256"], backend.capabilities.capability_sha256)

    def test_serialization_is_canonical_and_round_trips_across_cpu_adapters(self) -> None:
        left = self.cpu_backend()
        right = self.cpu_backend()
        state = left.initial_state()
        payload = left.serialize_state(state)
        restored = right.deserialize_state(payload)
        self.assertEqual(payload, right.serialize_state(restored))
        self.assertEqual(state.state_sha256(self.profile), restored.state_sha256(self.profile))

    def test_requested_gpu_unavailability_is_visible_and_never_falls_back(self) -> None:
        with self.assertRaises(QiBackendUnavailable):
            TorchFlowBackend(
                self.profile,
                device="cuda",
                dtype=torch.float64,
                capability_probe=lambda _device: {"available": False},
            )

    def test_bounded_memory_rejection_happens_before_fork(self) -> None:
        capacity = QiCapacityProfile.from_profile(self.profile, working_memory_budget=1)
        backend = self.cpu_backend(capacity=capacity)
        state = QiFlowStateV3.create(self.profile, batch_lanes=1, device="cpu")
        with self.assertRaises(QiBackendCapacityError):
            backend.fork(state, 1)

    def test_dtype_device_mismatch_and_no_silent_fallback(self) -> None:
        with self.assertRaises(QiBackendConfigurationError):
            TorchFlowBackend(self.profile, device="cpu", dtype=torch.float32)
        with self.assertRaises(QiBackendConfigurationError):
            TorchFlowBackend(
                self.profile,
                device="cuda",
                dtype=torch.float64,
                capability_probe=lambda _device: {"available": True},
            )
        backend = self.cpu_backend()
        prepared = backend.prepare(self.profile, 1)
        state = backend.initial_state()
        wrong_dtype = torch.zeros_like(state.field, dtype=torch.float32)
        with self.assertRaises(QiBackendConfigurationError):
            backend.execute_advance(state, QiDriveBundle(delta=wrong_dtype, prepared=prepared))
        with self.assertRaises(QiBackendConfigurationError):
            backend.execute_advance(state, QiDriveBundle(delta=0.0))
    def test_prepared_handle_is_content_bound_and_cache_is_bounded(self) -> None:
        backend = self.cpu_backend()
        first = backend.prepare(self.profile, 1)
        second = backend.prepare(self.profile, 1)
        self.assertIs(first, second)
        self.assertEqual(first.operator_id, ADVANCE_OPERATOR_ID)
        self.assertEqual(first.backend_identity_sha256, backend.identity.content_sha256)
        self.assertEqual(len(backend.prepared_cache), 1)
        memory = backend.memory_receipt()
        self.assertEqual(memory.prepared_cache_entries, 1)
        self.assertEqual(memory.prepared_cache_hits, 1)
        self.assertEqual(memory.prepared_cache_misses, 1)

    def test_termwise_parity_is_explicit_and_candidate_trajectories_can_abstain(self) -> None:
        candidate_profile = self.profile.from_defaults(overrides={"field": {"dtype": "float32"}})
        oracle = self.cpu_backend()
        candidate = TorchFlowBackend(candidate_profile, device="cpu", dtype=torch.float32)
        bands = QiParityGuardBands.from_profile(self.profile)
        zeros = torch.zeros(3, dtype=torch.float64)
        oracle_terms = {
            "current": zeros,
            "momentum": zeros,
            "work": 0.0,
            "topology": {"winding": 0},
            "receipt": {"status": "COMMITTED"},
            "state": zeros,
        }
        candidate_terms = {
            "current": zeros.to(dtype=torch.float32),
            "momentum": zeros.to(dtype=torch.float32),
            "work": 0.0,
            "topology": {"winding": 0},
            "receipt": {"status": "COMMITTED"},
            "state": zeros.to(dtype=torch.float32),
        }
        not_run = compare_termwise_parity(self.profile, oracle, candidate, oracle_terms, candidate_terms)
        self.assertEqual(not_run.parity_status, "NOT_RUN")
        near = compare_candidate_trajectories(
            self.profile,
            [zeros],
            [zeros + bands.terms["state"] * 0.9],
            guard_bands=bands,
            executed=True,
        )
        self.assertEqual(near.parity_status, "ABSTAIN")

    def test_runtime_config_round_trip_is_strict(self) -> None:
        config = QiRuntimeConfig()
        payload = config.to_payload()
        restored = QiRuntimeConfig.from_payload(payload)
        self.assertEqual(restored.to_payload(), payload)
        payload["unexpected"] = 1
        with self.assertRaises(QiBackendConfigurationError):
            QiRuntimeConfig.from_payload(payload)


if __name__ == "__main__":
    unittest.main()
