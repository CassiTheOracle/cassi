from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import sys

_CASSI_FI_ROOT = Path(__file__).resolve().parents[1]
for _path in (
    _CASSI_FI_ROOT,
    _CASSI_FI_ROOT / "training",
    _CASSI_FI_ROOT / "verification",
):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
from unittest import mock

import torch

from cassi_field_language import (
    FIELD_ALPHABET_SIZE,
    CassiFieldLanguageError,
    CassiFieldTextCodec,
    CassiQiSessionStore,
    CassiQiTextEngine,
    CassiQiTrajectoryLaw,
    save_trajectory_checkpoint,
)
from cassi_qi_field import QiFieldConfig, QiFieldController
from cassi_fi_paths import CONFIG_DIR
from train_cassi_field_language import train_corpus, train_manifest
from verify_cassi_corpus_language import verify


class TrajectoryLanguageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.config_path = CONFIG_DIR / "cassi-qi-corpus-language.json"
        cls.corpus_path = cls.root / "episodes.txt"
        cls.corpus_path.write_text(
            "Once upon a time the field learned to speak.\n"
            "Light flows through the quiet world.\n"
            "Water moves and minds begin to dream.\n"
            "The river remembers every stone it touches.\n"
            "A quiet mind can listen before it answers.\n"
            "The field carries a question until an answer forms.\n",
            encoding="utf-8",
        )
        cls.artifact_dir = cls.root / "trained"
        cls.training_receipt = train_corpus(
            cls.corpus_path,
            cls.config_path,
            cls.artifact_dir,
            holdout_bytes=64,
            episodes_per_source=4,
            heldout_episodes_per_source=1,
            max_episode_bytes=128,
        )
        config = QiFieldConfig.from_dict(
            json.loads(cls.config_path.read_text(encoding="utf-8"))
        )
        cls.controller = QiFieldController(config)
        cls.engine = CassiQiTextEngine(
            cls.controller,
            checkpoint_path=cls.artifact_dir / "field-state.pt",
            max_output_symbols=128,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def _first_training_example(self) -> dict[str, object]:
        return self.training_receipt["generation"]["training_examples"][0]

    def test_fixed_codec_is_raw_utf8_plus_four_controls(self) -> None:
        codec = CassiFieldTextCodec()
        self.assertEqual(codec.alphabet_size, 260)
        self.assertEqual(FIELD_ALPHABET_SIZE, 260)
        symbols = codec.encode_messages(({"role": "user", "content": "Qi 水"},))
        self.assertEqual(symbols[0], codec.user_symbol)
        self.assertEqual(symbols[-1], codec.end_turn_symbol)
        raw, text = codec.decode_symbols(tuple("Qi 水".encode("utf-8")))
        self.assertEqual(raw, "Qi 水".encode("utf-8"))
        self.assertEqual(text, "Qi 水")

    def test_training_split_preserves_utf8_codepoints(self) -> None:
        corpus = self.root / "utf8-episodes.txt"
        corpus.write_text("水水水水水\n" * 8, encoding="utf-8")
        receipt = train_corpus(
            corpus,
            self.config_path,
            self.root / "utf8-trained",
            holdout_bytes=32,
            episodes_per_source=1,
            heldout_episodes_per_source=1,
            max_episode_bytes=64,
        )
        example = receipt["generation"]["training_examples"][0]
        self.assertNotIn("\ufffd", example["prompt"])
        self.assertEqual(example["actual"], example["expected"])

    def test_checkpoint_owns_one_field_tensor_and_no_lattice(self) -> None:
        payload = torch.load(
            self.artifact_dir / "field-state.pt",
            map_location="cpu",
            weights_only=True,
        )
        self.assertEqual(payload["schema"], "cassi.qi-trajectory-field.v1")
        self.assertEqual([key for key, value in payload.items() if torch.is_tensor(value)], ["field"])
        self.assertFalse(any("lattice" in key for key in payload))
        self.assertNotIn("counts", payload)
        self.assertEqual(tuple(self.engine.initial_state().__dataclass_fields__), ("field",))

    def test_learned_trajectory_generates_the_recorded_continuation(self) -> None:
        example = self._first_training_example()
        result = self.engine.generate(
            self.engine.initial_state(),
            ({"role": "user", "content": example["prompt"]},),
        )
        self.assertEqual(result.text, example["expected"])
        self.assertEqual(result.stop_reason, "end_turn")
        self.assertTrue(result.all_outputs_field_owned)

    def test_output_is_active_reaction_not_inbound_self_sensing(self) -> None:
        example = self._first_training_example()
        result = self.engine.generate(
            self.engine.initial_state(),
            ({"role": "user", "content": example["prompt"]},),
        )
        self.assertTrue(result.output_receipts)
        prior = result.prompt_receipts[-1].state_after_sha256
        for symbol, receipt in zip(result.output_symbols, result.output_receipts, strict=True):
            self.assertEqual(receipt.emission.symbol, symbol)
            self.assertEqual(receipt.emission.state_sha256, prior)
            self.assertEqual(receipt.commitment.state_before_sha256, prior)
            self.assertEqual(receipt.commitment.boundary_direction, "outbound")
            self.assertLess(receipt.commitment.boundary_work, 0.0)
            prior = receipt.commitment.state_after_sha256
        self.assertIsNotNone(result.terminal_receipt)
        self.assertEqual(result.terminal_receipt.commitment.boundary_direction, "outbound")
        self.assertEqual(prior, result.terminal_receipt.emission.state_sha256)
        self.assertEqual(result.final_state_sha256, result.terminal_receipt.commitment.state_after_sha256)

    def test_generation_preserves_trained_memory_but_changes_live_state(self) -> None:
        example = self._first_training_example()
        initial = self.engine.initial_state()
        initial_hash = self.engine.state_sha256(initial)
        result = self.engine.generate(
            initial,
            ({"role": "user", "content": example["prompt"]},),
        )
        self.assertNotEqual(initial_hash, result.final_state_sha256)
        self.assertEqual(result.corpus_memory_sha256, self.engine.corpus_memory_sha256)
        self.assertEqual(
            self.engine.law.memory_sha256(result.state),
            self.engine.corpus_memory_sha256,
        )

    def test_replay_is_deterministic(self) -> None:
        example = self._first_training_example()
        messages = ({"role": "user", "content": example["prompt"]},)
        first = self.engine.generate(self.engine.initial_state(), messages)
        second = self.engine.generate(self.engine.initial_state(), messages)
        self.assertEqual(first.output_symbols, second.output_symbols)
        self.assertEqual(first.final_state_sha256, second.final_state_sha256)
        self.assertEqual(first.receipt_sha256, second.receipt_sha256)

    def test_zero_memory_field_chooses_silence(self) -> None:
        law = CassiQiTrajectoryLaw(self.controller)
        state = law.initial_state()
        path = self.root / "zero-field.pt"
        save_trajectory_checkpoint(
            path,
            law=law,
            state=state,
            corpus_identity="0" * 64,
            training_episode_count=0,
            training_event_count=0,
        )
        engine = CassiQiTextEngine(
            self.controller,
            checkpoint_path=path,
            max_output_symbols=8,
        )
        result = engine.generate(
            engine.initial_state(),
            ({"role": "user", "content": "Nothing learned"},),
        )
        self.assertEqual(result.stop_reason, "field_abstained")
        self.assertEqual(result.output_symbols, ())

    def test_live_phase_counterfactual_never_changes_memory(self) -> None:
        initial = self.engine.initial_state()
        changed = self.engine.law.rotate_live_context(initial, 1.0)
        self.assertNotEqual(self.engine.state_sha256(initial), self.engine.state_sha256(changed))
        self.assertEqual(
            self.engine.law.memory_sha256(initial),
            self.engine.law.memory_sha256(changed),
        )

    def test_live_context_exposes_exact_bounded_event_ages(self) -> None:
        law = self.engine.law
        state = self.engine.initial_state()
        memory_sha256 = law.memory_sha256(state)
        expected: list[int] = []
        for symbol in (17, 83, 201, 83, 41, 59, 131, 223):
            state, _ = law.sense_event(state, symbol)
            for _ in range(16):
                state = law.dwell(state)
            expected.insert(0, symbol)
            del expected[7:]
            self.assertEqual(law.read_recent_symbols(state, 7), tuple(expected))
        for _ in range(128):
            state = law.dwell(state)
        self.assertEqual(law.read_recent_symbols(state, 7), tuple(expected))
        self.assertEqual(law.memory_sha256(state), memory_sha256)

    def test_exact_field_episodes_age_boundedly_and_round_trip(self) -> None:
        law = CassiQiTrajectoryLaw(self.controller)
        initial = law.initial_state()
        initial_memory = law.memory_sha256(initial)
        sequences = [
            (258, 40 + index, 80 + index, 259)
            for index in range(12)
        ]
        state = initial
        for sequence in sequences:
            state = law.learn_sequence(state, sequence)
        self.assertNotEqual(law.memory_sha256(state), initial_memory)

        state, retired = law.age_exact_sequences(state, sequences, steps=10)
        self.assertEqual(retired, ())
        store = CassiQiSessionStore(
            self.root / "aging-sessions",
            self.controller,
            engine_fingerprint=self.engine.fingerprint,
        )
        store.save("aging", state, {"episodes": len(sequences)})
        loaded = store.load("aging")
        self.assertIsNotNone(loaded)
        loaded_state, metadata, _ = loaded
        self.assertEqual(metadata, {"episodes": len(sequences)})
        self.assertEqual(
            self.engine.state_sha256(loaded_state),
            self.engine.state_sha256(state),
        )

        aged, retired = law.age_exact_sequences(
            loaded_state,
            sequences,
            steps=max(law.history_limits) - 9,
        )
        self.assertEqual(set(retired), set(sequences))
        self.assertEqual(law.memory_sha256(aged), initial_memory)

    def test_session_round_trip_preserves_exact_successor(self) -> None:
        example = self._first_training_example()
        result = self.engine.generate(
            self.engine.initial_state(),
            ({"role": "user", "content": example["prompt"]},),
        )
        store = CassiQiSessionStore(
            self.root / "sessions",
            self.controller,
            engine_fingerprint=self.engine.fingerprint,
        )
        path, _ = store.save("trajectory-session", result.state, {"turn": 1})
        loaded = store.load("trajectory-session")
        self.assertIsNotNone(loaded)
        state, metadata, loaded_path = loaded
        self.assertEqual(path, loaded_path)
        self.assertEqual(metadata, {"turn": 1})
        self.assertEqual(self.engine.state_sha256(state), result.final_state_sha256)

    def test_session_save_failure_leaves_previous_state_intact(self) -> None:
        store = CassiQiSessionStore(
            self.root / "rollback-sessions",
            self.controller,
            engine_fingerprint=self.engine.fingerprint,
        )
        path, _ = store.save("rollback", self.engine.initial_state(), {"turn": 0})
        before = path.read_bytes()
        with mock.patch("cassi_field_language.os.replace", side_effect=OSError("blocked")):
            with self.assertRaises(OSError):
                store.save("rollback", self.engine.initial_state(), {"turn": 1})
        self.assertEqual(path.read_bytes(), before)

    def test_independent_reconstruction_replays_generation(self) -> None:
        receipt = verify(
            config_path=self.config_path,
            artifact_dir=self.artifact_dir,
            output_path=self.artifact_dir / "verification-receipt.json",
        )
        self.assertEqual(receipt["status"], "PASS")
        self.assertTrue(receipt["reconstruction"]["memory_bit_exact"])
        self.assertEqual(
            receipt["generation"],
            self.training_receipt["generation"]["training_examples"],
        )

    def test_source_mutation_invalidates_reconstruction(self) -> None:
        original = self.corpus_path.read_bytes()
        try:
            self.corpus_path.write_bytes(original + b"mutation")
            with self.assertRaises(RuntimeError):
                verify(
                    config_path=self.config_path,
                    artifact_dir=self.artifact_dir,
                    output_path=self.root / "invalid-verification.json",
                )
        finally:
            self.corpus_path.write_bytes(original)

    def test_manifest_combines_sources_into_one_field(self) -> None:
        first = self.root / "first.txt"
        second = self.root / "second.txt"
        first.write_text(
            "".join(
                f"First river trajectory {index} continues into dawn.\n"
                for index in range(8)
            ),
            encoding="utf-8",
        )
        second.write_text(
            "".join(
                f"Second field trajectory {index} continues into night.\n"
                for index in range(8)
            ),
            encoding="utf-8",
        )
        manifest = self.root / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "holdout_fraction_denominator": 4,
                    "minimum_holdout_bytes": 32,
                    "schema": "cassi.qi-corpus-manifest.v1",
                    "sources": [
                        {
                            "id": "first",
                            "path": str(first),
                            "sha256": hashlib.sha256(first.read_bytes()).hexdigest(),
                        },
                        {
                            "id": "second",
                            "path": str(second),
                            "sha256": hashlib.sha256(second.read_bytes()).hexdigest(),
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        receipt = train_manifest(
            manifest,
            self.config_path,
            self.root / "manifest-field",
            episodes_per_source=2,
            heldout_episodes_per_source=1,
            max_episode_bytes=96,
        )
        self.assertEqual(receipt["experience"]["training_episode_count"], 4)
        self.assertEqual(len(receipt["corpus"]["sources"]), 2)
        payload = torch.load(
            self.root / "manifest-field" / "field-state.pt",
            map_location="cpu",
            weights_only=True,
        )
        self.assertEqual([key for key, value in payload.items() if torch.is_tensor(value)], ["field"])


if __name__ == "__main__":
    unittest.main()
