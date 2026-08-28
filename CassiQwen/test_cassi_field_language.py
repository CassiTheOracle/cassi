from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import torch

from cassi_field_language import (
    CassiFieldLanguageError,
    CassiFieldTextCodec,
    CassiQiSessionStore,
    CassiQiTextEngine,
    qi_state_sha256,
)
from cassi_qi_field import QiFieldConfig, QiFieldController, QiFieldState


class CassiQiTextEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        torch.set_num_threads(1)

    def setUp(self) -> None:
        self.controller = QiFieldController(QiFieldConfig())
        self.engine = CassiQiTextEngine(self.controller, max_output_symbols=8)
        self.messages = ({"role": "user", "content": "Hello Cassi"},)

    def test_codec_is_fixed_utf8_plus_role_boundary(self) -> None:
        codec = CassiFieldTextCodec()
        symbols = codec.encode_messages(
            (
                {"role": "system", "content": "φ"},
                {"role": "user", "content": "Qi"},
            )
        )
        self.assertEqual(symbols[0], codec.role_symbol("system"))
        self.assertEqual(tuple("φ".encode("utf-8")), symbols[1:3])
        self.assertEqual(symbols[3], codec.end_turn_symbol)
        self.assertEqual(symbols[4], codec.role_symbol("user"))
        self.assertEqual(symbols[-1], codec.end_turn_symbol)
        self.assertEqual(codec.alphabet_size, 260)

    def test_codec_rejects_unbounded_or_unknown_messages(self) -> None:
        codec = CassiFieldTextCodec()
        with self.assertRaises(CassiFieldLanguageError):
            codec.encode_messages(())
        with self.assertRaises(CassiFieldLanguageError):
            codec.encode_messages(({"role": "tool", "content": "x"},))
        with self.assertRaises(CassiFieldLanguageError):
            codec.encode_messages(({"role": "user", "content": 1},))

    def test_generation_uses_one_qi_tensor_and_no_classical_head(self) -> None:
        result = self.engine.generate(self.engine.initial_state(), self.messages)
        architecture = result.receipt_dict()["architecture"]
        self.assertEqual(architecture["adaptive_persistent_tensor_count"], 1)
        self.assertEqual(architecture["state_layout"], "[S,9M,B]")
        self.assertEqual(architecture["learned_parameter_count"], 0)
        self.assertEqual(architecture["neural_layer_count"], 0)
        self.assertEqual(architecture["optimizer_state_bytes"], 0)
        self.assertEqual(architecture["engineered_feature_width"], 0)
        self.assertFalse(architecture["probabilistic_sampler"])
        self.assertEqual(
            architecture["emission"],
            "deterministic-phase-conjugate-resonance-argmax",
        )
        self.assertTrue(result.all_outputs_field_owned)
        result.state.validate(self.controller.config)

    def test_generation_is_byte_and_state_replay_deterministic(self) -> None:
        first = self.engine.generate(self.engine.initial_state(), self.messages)
        second = self.engine.generate(self.engine.initial_state(), self.messages)
        self.assertEqual(first.output_symbols, second.output_symbols)
        self.assertEqual(first.output_bytes, second.output_bytes)
        self.assertEqual(first.receipt_sha256, second.receipt_sha256)
        self.assertEqual(first.final_state_sha256, second.final_state_sha256)
        self.assertTrue(torch.equal(first.state.field, second.state.field))

    def test_every_emitted_symbol_is_committed_through_qi(self) -> None:
        result = self.engine.generate(self.engine.initial_state(), self.messages)
        self.assertGreaterEqual(len(result.output_symbols), 1)
        self.assertEqual(len(result.output_symbols), len(result.output_receipts))
        prior = result.prompt_receipts[-1].state_after_sha256
        for symbol, receipt in zip(
            result.output_symbols,
            result.output_receipts,
            strict=True,
        ):
            self.assertEqual(receipt.emission.symbol, symbol)
            self.assertEqual(receipt.emission.state_sha256, prior)
            self.assertEqual(receipt.commitment.state_before_sha256, prior)
            prior = receipt.commitment.state_after_sha256
        self.assertEqual(prior, result.final_state_sha256)

    def test_protocol_obeys_direct_field_boundary_without_allowlist_sampling(self) -> None:
        result = self.engine.generate(self.engine.initial_state(), self.messages)
        self.assertEqual(result.output_symbols, (self.engine.codec.end_turn_symbol,))
        self.assertEqual(result.output_bytes, b"")
        self.assertEqual(result.text, "")
        self.assertEqual(result.stop_reason, "end_turn")
        self.assertTrue(result.utf8_valid)
        self.assertEqual(result.replacement_count, 0)

    def test_input_state_is_not_mutated(self) -> None:
        initial = self.engine.initial_state()
        before = initial.field.clone()
        result = self.engine.generate(initial, self.messages)
        self.assertTrue(torch.equal(initial.field, before))
        self.assertFalse(torch.equal(result.state.field, before))
        self.assertEqual(
            qi_state_sha256(self.controller, initial),
            result.initial_state_sha256,
        )

    def test_live_state_with_autograd_graph_is_rejected(self) -> None:
        initial = self.engine.initial_state()
        differentiable = QiFieldState(initial.field.detach().clone().requires_grad_(True))
        with self.assertRaisesRegex(
            CassiFieldLanguageError,
            "must not carry an autograd graph",
        ):
            self.engine.generate(differentiable, self.messages)

    def test_session_store_round_trips_only_qi_state(self) -> None:
        result = self.engine.generate(self.engine.initial_state(), self.messages)
        with tempfile.TemporaryDirectory() as directory:
            store = CassiQiSessionStore(
                Path(directory),
                self.controller,
                engine_fingerprint=self.engine.fingerprint,
            )
            path, checkpoint_sha256 = store.save(
                "session-a",
                result.state,
                {"receipt_sha256": result.receipt_sha256, "turn": 1},
            )
            self.assertTrue(path.is_file())
            self.assertEqual(len(checkpoint_sha256), 64)
            payload = torch.load(path, map_location="cpu", weights_only=True)
            self.assertEqual(
                set(payload),
                {
                    "codebook_fingerprint",
                    "config_fingerprint",
                    "engine_fingerprint",
                    "metadata",
                    "schema",
                    "session_id",
                    "state_bytes",
                    "state_sha256",
                },
            )
            self.assertIsInstance(payload["state_bytes"], bytes)
            self.assertIsInstance(payload["metadata"], bytes)
            self.assertFalse(any(torch.is_tensor(value) for value in payload.values()))
            loaded = store.load("session-a")
            self.assertIsNotNone(loaded)
            assert loaded is not None
            state, metadata, loaded_path = loaded
            self.assertEqual(loaded_path, path)
            self.assertEqual(metadata["receipt_sha256"], result.receipt_sha256)
            self.assertEqual(metadata["turn"], 1)
            self.assertTrue(torch.equal(state.field, result.state.field))
            self.assertEqual(
                qi_state_sha256(self.controller, state),
                result.final_state_sha256,
            )

    def test_session_store_fails_closed_on_engine_mismatch(self) -> None:
        result = self.engine.generate(self.engine.initial_state(), self.messages)
        with tempfile.TemporaryDirectory() as directory:
            store = CassiQiSessionStore(
                Path(directory),
                self.controller,
                engine_fingerprint=self.engine.fingerprint,
            )
            store.save("session-a", result.state, {"turn": 1})
            other = CassiQiSessionStore(
                Path(directory),
                self.controller,
                engine_fingerprint="0" * 64,
            )
            with self.assertRaises(CassiFieldLanguageError):
                other.load("session-a")


if __name__ == "__main__":
    unittest.main()
