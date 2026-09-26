from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from cassi_f5_provider import (
    BASELINE_MODE,
    FIELD_DAEMON_PROFILE,
    FIELD_DAEMON_PROTOCOL,
    FIELD_MODE,
    F5_PROFILE,
    PROTOCOL,
    CassiF5Provider,
    ProviderConfig,
    ProviderError,
    SessionCheckpointStore,
    VERSION,
    _fixed_boundary_symbol,
    _qi_available,
    _qi_scalar,
    _rerank_candidates,
)



class F5ProviderTest(unittest.TestCase):
    def config(self, root: Path, **overrides: object) -> ProviderConfig:
        values: dict[str, object] = {
            "model_path": root / "model.gguf",
            "dll_dir": root,
            "state_dir": root / "state",
            "context_size": 128,
            "n_batch": 64,
            "n_ubatch": 64,
            "gpu_layers": 0,
        }
        values.update(overrides)
        return ProviderConfig(**values)  # type: ignore[arg-type]

    def test_config_is_default_off_and_health_is_finite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self.config(Path(directory))
            self.assertFalse(config.enable_f5)
            provider = CassiF5Provider(config)
            health = provider.health()
            self.assertFalse(health["ok"])
            self.assertFalse(health["field_enabled"])
            self.assertTrue(health["finite"])
            self.assertEqual(health["protocol"], PROTOCOL)
            self.assertEqual(health["version"], VERSION)
            self.assertEqual(health["profile"], F5_PROFILE)
            self.assertEqual(health["field_protocol"], FIELD_DAEMON_PROTOCOL)

    def test_loopback_only_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ProviderError):
                self.config(Path(directory), host="0.0.0.0")
            with self.assertRaises(ProviderError):
                self.config(Path(directory), field_host="192.0.2.1")

    def test_field_mode_requires_explicit_enable_before_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            provider = CassiF5Provider(self.config(Path(directory)))
            with self.assertRaisesRegex(ProviderError, "field mode is disabled"):
                provider.complete({"messages": [{"role": "user", "content": "x"}], "cassi_field_mode": FIELD_MODE})
            with self.assertRaisesRegex(ProviderError, "provider is not started"):
                provider.complete({"messages": [{"role": "user", "content": "x"}], "cassi_field_mode": BASELINE_MODE})

    def test_fixed_boundary_symbol_and_deterministic_rerank(self) -> None:
        self.assertIsNone(_fixed_boundary_symbol(b""))
        self.assertEqual(_fixed_boundary_symbol(b"a"), 97)
        self.assertEqual(_fixed_boundary_symbol(b"abc"), 201)
        self.assertEqual(_fixed_boundary_symbol("é".encode("utf-8")), 156)
        self.assertEqual(_fixed_boundary_symbol("ĠOrbit".encode("utf-8")), 8)
        scores = [0.0] * 260
        scores[66] = 1.0
        rows = [
            {"token_id": 5, "logit": 1.0},
            {"token_id": 3, "logit": 0.9},
        ]
        selected, detail = _rerank_candidates(rows, scores, [65, 66], field_weight=0.2)
        self.assertEqual(selected, 3)
        self.assertEqual(detail["covered_count"], 2)
        self.assertEqual(detail["collision_count"], 0)
        selected_collision, collision_detail = _rerank_candidates(
            rows, scores, [65, 65], field_weight=0.0
        )
        self.assertEqual(selected_collision, 5)
        self.assertEqual(collision_detail["collision_count"], 1)

    def test_qi_scalar_and_availability_validate_single_batch_metrics(self) -> None:
        response = {
            "available": [False],
            "metrics": {
                "q": [0.25],
                "q_max": [0.75],
                "chi": [0.5],
                "cross_scale_coherence": [0.125],
                "read_gate": [0.0],
            },
            "scores": [[0.0] * 260],
        }
        metrics = response["metrics"]
        self.assertEqual(_qi_scalar(metrics, "q"), 0.25)
        self.assertEqual(_qi_scalar(metrics, "read_gate"), 0.0)
        self.assertFalse(_qi_available(response))

        with self.assertRaisesRegex(ProviderError, "not single-batch"):
            _qi_scalar({"q": [0.1, 0.2]}, "q")
        with self.assertRaisesRegex(ProviderError, "malformed"):
            _qi_scalar({"read_gate": [True]}, "read_gate")
        with self.assertRaisesRegex(ProviderError, "malformed"):
            _qi_scalar({"read_gate": True}, "read_gate")
        with self.assertRaisesRegex(ProviderError, "non-finite"):
            _qi_scalar({"q": [float("nan")]}, "q")
        with self.assertRaisesRegex(ProviderError, "malformed"):
            _qi_available({"available": [0]})
        with self.assertRaisesRegex(ProviderError, "malformed"):
            _qi_available({"available": True})

    def test_field_metadata_allows_hash_but_rejects_model_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = SessionCheckpointStore(root / "state", model_sha256="a" * 64)
            field_bytes = b"field-only-placeholder"
            field_path = store.field_path("demo")
            field_path.write_bytes(field_bytes)
            field_sha256 = hashlib.sha256(field_bytes).hexdigest()
            value = {
                "protocol": PROTOCOL,
                "version": VERSION,
                "profile": F5_PROFILE,
                "field_protocol": FIELD_DAEMON_PROTOCOL,
                "field_profile": FIELD_DAEMON_PROFILE,
                "field_config_fingerprint": "d" * 64,
                "field_codebook_fingerprint": "e" * 64,
                "session_id": "demo",
                "model_sha256": "a" * 64,
                "field_checkpoint_path": str(field_path),
                "field_checkpoint_sha256": field_sha256,
                "checkpoint_identity": store.checkpoint_identity,
                "event_count": 2,
                "last_prompt_sha256": "c" * 64,
                "updated_at": 1.0,
            }
            self.assertEqual(len(value["field_config_fingerprint"]), 64)
            self.assertEqual(len(value["field_codebook_fingerprint"]), 64)
            store.save("demo", value)
            self.assertEqual(store.load("demo")["event_count"], 2)
            self.assertEqual(
                value["field_checkpoint_sha256"],
                hashlib.sha256(field_path.read_bytes()).hexdigest(),
            )
            field_path.write_bytes(field_bytes + b"-tampered")
            with self.assertRaisesRegex(ProviderError, "checkpoint hash mismatch"):
                store.load("demo")
            forbidden = dict(value)
            with self.assertRaisesRegex(ProviderError, "forbidden"):
                store.save("demo", {**forbidden, "logits": [1.0]})


if __name__ == "__main__":
    unittest.main()
