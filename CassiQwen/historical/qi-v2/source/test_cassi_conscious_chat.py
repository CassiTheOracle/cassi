from __future__ import annotations

import contextlib
import inspect
import io
import json
import tempfile
import unittest
from pathlib import Path

from cassi_field_language import qi_state_sha256
from cassi_conscious_chat import (
    CHAT_CONFIG_SCHEMA,
    CHAT_TURN_SCHEMA,
    DEFAULT_CONFIG_PATH,
    DEFAULT_STATE_DIR,
    CassiChatTurn,
    CassiConsciousChatConfig,
    CassiConsciousChatError,
    CassiConsciousChatRuntime,
    StateDirectoryLock,
)

_PACKAGE_ROOT = Path(__file__).resolve().parent
_QI_CONFIG_PATH = _PACKAGE_ROOT / "cassi-qi-language.json"

_ZERO_OWNERSHIP = {
    "field_owned": True,
    "live_qwen_dynamic_state": 0,
    "live_qwen_graph_executions": 0,
    "live_qwen_output_rows": 0,
    "live_qwen_weight_bytes_loaded": 0,
    "learned_parameter_count": 0,
    "neural_layer_count": 0,
    "optimizer_state_bytes": 0,
    "engineered_feature_width": 0,
    "probabilistic_sampler": False,
}


class CassiConsciousChatTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.config_path = self.root / "chat.json"
        self._write_config(self.config_path)
        self.runtime: CassiConsciousChatRuntime | None = None

    def tearDown(self) -> None:
        if self.runtime is not None:
            self.runtime.close()
        self.temporary.cleanup()

    def _write_config(self, path: Path) -> None:
        source = {
            "schema": CHAT_CONFIG_SCHEMA,
            "qi_config_path": str(_QI_CONFIG_PATH.resolve()),
            "state_dir": str((self.root / "state").resolve()),
            "session_id": "test-session",
            "max_output_symbols": 16,
            "device": "cpu",
            "runtime": {"max_input_bytes": 4096},
        }
        path.write_text(
            json.dumps(source, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )

    def open_runtime(
        self,
        *,
        name: str = "state",
        session_id: str | None = None,
        state_dir: Path | None = None,
    ) -> CassiConsciousChatRuntime:
        self._write_config(self.config_path)
        runtime = CassiConsciousChatRuntime.open(
            config_path=self.config_path,
            state_dir=state_dir if state_dir is not None else self.root / name,
            device="cpu",
            session_id=session_id if session_id is not None else "test-session",
            max_output_symbols=16,
        )
        self.runtime = runtime
        return runtime

    def test_defaults_are_field_only_and_path_stable(self) -> None:
        self.assertEqual(DEFAULT_CONFIG_PATH, _PACKAGE_ROOT / "conscious-chat.json")
        self.assertEqual(DEFAULT_STATE_DIR, _PACKAGE_ROOT / "_diag/cassi-qi-native/chat")
        parameters = inspect.signature(CassiConsciousChatRuntime.open).parameters
        self.assertNotIn("organism_checkpoint", parameters)
        self.assertNotIn("world_checkpoint", parameters)
        self.assertNotIn("qwen_gguf", parameters)
        self.assertNotIn("model_id", parameters)
        self.assertNotIn("base_url", parameters)
        config = CassiConsciousChatConfig.load(self.config_path)
        self.assertEqual(config.session_id, "test-session")
        self.assertEqual(config.device, "cpu")
        self.assertEqual(config.max_output_symbols, 16)

    def test_turn_is_field_owned_with_zero_classical_counters(self) -> None:
        runtime = self.open_runtime()
        turn = runtime.chat("probe")
        self.assertIsInstance(turn, CassiChatTurn)
        receipt = turn.as_dict()
        self.assertEqual(receipt["schema"], CHAT_TURN_SCHEMA)
        self.assertEqual(receipt["status"], "ok")
        self.assertEqual(receipt["ownership"], _ZERO_OWNERSHIP)
        architecture = receipt["architecture"]
        self.assertEqual(architecture["adaptive_persistent_tensor_count"], 1)
        self.assertEqual(architecture["learned_parameter_count"], 0)
        self.assertEqual(architecture["neural_layer_count"], 0)
        self.assertEqual(architecture["optimizer_state_bytes"], 0)
        self.assertEqual(architecture["engineered_feature_width"], 0)
        self.assertFalse(architecture["probabilistic_sampler"])
        self.assertEqual(architecture["state_layout"], "[S,9M,B]")
        self.assertGreaterEqual(turn.next_sequence, 1)

    def test_deterministic_continuation_and_checkpoint_reload(self) -> None:
        first = self.open_runtime()
        alpha = first.chat("alpha")
        beta = first.chat("beta")
        reloaded_state_sha = beta.final_state_sha256
        first_sequence = beta.next_sequence
        self.assertEqual(first_sequence, 2)
        first.close()
        self.runtime = None

        # The transcript is rebuilt from the persisted state across restart.
        second = self.open_runtime()
        gamma = second.chat("gamma")
        self.assertGreaterEqual(gamma.next_sequence, 1)
        self.assertEqual(gamma.initial_state_sha256, reloaded_state_sha)
        second.close()
        self.runtime = None

        # A fresh state directory must reproduce the same first turn exactly.
        third = self.open_runtime(name="fresh", session_id="fresh-session")
        again = third.chat("alpha")
        self.assertEqual(again.initial_state_sha256, alpha.initial_state_sha256)
        self.assertEqual(again.final_state_sha256, alpha.final_state_sha256)
        self.assertEqual(again.field_text_receipt_sha256, alpha.field_text_receipt_sha256)

    def test_runtime_overrides_persist_under_the_selected_session(self) -> None:
        state_dir = self.root / "override-state"
        first_runtime = CassiConsciousChatRuntime.open(
            config_path=self.config_path,
            state_dir=state_dir,
            session_id="override-session",
        )
        first = first_runtime.chat("alpha")
        first_runtime.close()
        self.assertEqual(first.session_id, "override-session")

        second_runtime = CassiConsciousChatRuntime.open(
            config_path=self.config_path,
            state_dir=state_dir,
            session_id="override-session",
        )
        try:
            self.assertEqual(
                qi_state_sha256(second_runtime.controller, second_runtime.state),
                first.final_state_sha256,
            )
            second = second_runtime.chat("beta")
            self.assertEqual(second.next_sequence, 2)
        finally:
            second_runtime.close()

    def test_generation_reaches_only_field_engine(self) -> None:
        runtime = self.open_runtime()
        turn = runtime.chat("context carry")
        self.assertIsInstance(turn.reply, str)
        self.assertNotIn("world", type(runtime).__module__ or "")
        self.assertFalse(hasattr(runtime, "agent"))
        self.assertFalse(hasattr(runtime, "store") and hasattr(runtime.store, "replay"))
        self.assertNotIsInstance(runtime.controller, type(None))
        self.assertEqual(runtime.state.__class__.__name__, "QiFieldState")

    def test_input_bounds_and_closed_runtime_fail_visibly(self) -> None:
        runtime = self.open_runtime()
        with self.assertRaises(CassiConsciousChatError):
            runtime.chat("")
        with self.assertRaises(CassiConsciousChatError):
            runtime.chat("x" * (runtime.config.max_input_bytes + 1))
        runtime.close()
        self.runtime = None
        with self.assertRaises(CassiConsciousChatError):
            runtime.chat("x")

    def test_lock_refuses_second_runtime(self) -> None:
        runtime = self.open_runtime(name="locked")
        with self.assertRaises(CassiConsciousChatError):
            CassiConsciousChatRuntime.open(
                config_path=self.config_path,
                state_dir=self.root / "locked",
                session_id="test-session",
                max_output_symbols=16,
            )
        runtime.close()
        self.runtime = None
        lock = StateDirectoryLock(self.root / "locked")
        lock.acquire()
        lock.close()

    def test_one_shot_cli_emits_plain_text_and_qi_ownership_receipt(self) -> None:
        from run_cassi_conscious_chat import main

        common = [
            "--runtime-config",
            str(self.config_path),
            "--state-dir",
            str(self.root / "cli-plain"),
            "--prompt",
            "probe",
            "--session-id",
            "cli-session",
            "--max-output-symbols",
            "16",
        ]
        plain = io.StringIO()
        with contextlib.redirect_stdout(plain):
            code = main([*common])
        self.assertEqual(code, 0)
        plain.getvalue().encode("utf-8", errors="strict")

        rendered = io.StringIO()
        with contextlib.redirect_stdout(rendered):
            code = main(["--state-dir", str(self.root / "cli-json"), "--json", *common])
        self.assertEqual(code, 0)
        receipt = json.loads(rendered.getvalue())
        self.assertEqual(receipt["schema"], CHAT_TURN_SCHEMA)
        self.assertTrue(receipt["ownership"]["field_owned"])
        self.assertEqual(receipt["ownership"]["learned_parameter_count"], 0)
        self.assertEqual(receipt["architecture"]["neural_layer_count"], 0)
        self.assertFalse(receipt["architecture"]["probabilistic_sampler"])

    def test_config_rejects_unknown_and_missing_keys(self) -> None:
        source = json.loads(self.config_path.read_text(encoding="utf-8"))
        source["bogus"] = True
        bad = self.root / "bad.json"
        bad.write_text(json.dumps(source), encoding="utf-8")
        with self.assertRaises(CassiConsciousChatError):
            CassiConsciousChatConfig.load(bad)

        source = json.loads(self.config_path.read_text(encoding="utf-8"))
        del source["qi_config_path"]
        missing = self.root / "missing.json"
        missing.write_text(json.dumps(source), encoding="utf-8")
        with self.assertRaises(CassiConsciousChatError):
            CassiConsciousChatConfig.load(missing)


if __name__ == "__main__":
    unittest.main()
