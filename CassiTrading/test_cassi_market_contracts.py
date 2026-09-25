from __future__ import annotations

import math
import unittest

from cassi_market_contracts import (
    Authority,
    CheckpointManifest,
    ContractError,
    Event,
    Prediction,
    SplitManifest,
    canonical_bytes,
    digest_value,
)


class CanonicalContractTests(unittest.TestCase):
    def test_digest_is_order_independent_but_content_sensitive(self) -> None:
        self.assertEqual(
            canonical_bytes({"b": 2, "a": 1}),
            canonical_bytes({"a": 1, "b": 2}),
        )
        self.assertEqual(
            digest_value({"b": 2, "a": 1}),
            digest_value({"a": 1, "b": 2}),
        )
        self.assertNotEqual(digest_value({"a": 1}), digest_value({"a": 2}))

    def test_event_preserves_availability_boundary(self) -> None:
        event = Event(
            event_id="event-1",
            source_id="coinbase-btcusd",
            source_revision="2025-01",
            observed_at="2025-01-01T10:00:00Z",
            available_at="2025-01-01T10:01:00Z",
            event_type="bar",
            subject_ids=("BTCUSD",),
            payload={"close": 100.0},
            units={"close": "USD"},
        )
        delayed = Event(
            event_id=event.event_id,
            source_id=event.source_id,
            source_revision=event.source_revision,
            observed_at=event.observed_at,
            available_at="2025-01-01T10:02:00Z",
            event_type=event.event_type,
            subject_ids=event.subject_ids,
            payload=event.payload,
            units=event.units,
        )
        self.assertEqual(event.as_dict()["available_at"], "2025-01-01T10:01:00Z")
        self.assertNotEqual(event.content_sha256, delayed.content_sha256)

    def test_split_manifest_rejects_cross_partition_reuse(self) -> None:
        with self.assertRaises(ContractError):
            SplitManifest(
                manifest_id="split-1",
                availability_cutoff="2025-01-01T00:00:00Z",
                partitions={"train": ("event-1",), "holdout": ("event-1",)},
                source_digests={"source": "digest"},
            )

    def test_contracts_reject_nonfinite_values(self) -> None:
        with self.assertRaises(ContractError):
            Event(
                event_id="event-1",
                source_id="source",
                source_revision="rev",
                observed_at="2025-01-01T00:00:00Z",
                available_at="2025-01-01T00:00:00Z",
                event_type="bar",
                subject_ids=("BTCUSD",),
                payload={"close": math.nan},
            )

    def test_prediction_and_checkpoint_are_content_addressed(self) -> None:
        prediction = Prediction(
            prediction_id="prediction-1",
            predecessor_field_sha256="field-before",
            policy_id="policy-1",
            program_id="program-1",
            input_event_ids=("event-1",),
            available_at="2025-01-01T00:00:00Z",
            predicted_outcome={"return": 0.01},
            alternatives=({"return": 0.0},),
            cost_expectation={"bps": 10.0},
            risk_expectation={"drawdown": 0.02},
        )
        checkpoint = CheckpointManifest(
            checkpoint_id="checkpoint-1",
            predecessor_field_sha256="field-before",
            field_sha256="field-after",
            evidence_root="evidence-root",
            program_root="program-root",
            policy_root="policy-root",
            authority_generation="auth-1",
            operation_id="operation-1",
            resource_counters={"bytes": 128},
            recovery_envelope={"state": "prepared"},
        )
        self.assertEqual(len(prediction.content_sha256), 64)
        self.assertEqual(len(checkpoint.content_sha256), 64)

    def test_authority_mode_is_explicit(self) -> None:
        self.assertEqual(
            Authority(
                mode="shadow",
                objective_id="research-objective",
                permission_generation="permission-1",
                revocation_generation="revocation-1",
            ).as_dict()["mode"],
            "shadow",
        )
        with self.assertRaises(ContractError):
            Authority(
                mode="live",
                objective_id="research-objective",
                permission_generation="permission-1",
                revocation_generation="revocation-1",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
