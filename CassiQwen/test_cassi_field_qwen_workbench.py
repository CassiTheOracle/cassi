#!/usr/bin/env python3
"""Focused behavioral coverage for the current-CassiFI Qwen workbench boundary."""

from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from typing import Mapping

from cassi_field_qwen_workbench import (
    CassiFieldWorkMemory,
    LocalQwenClient,
    WorkMemoryRecord,
)
from run_cassi_field_qwen_workcases import server_identity


class CassiFieldWorkMemoryTests(unittest.TestCase):
    def _record(
        self,
        source_id: str,
        context: Mapping[str, object],
        payload: Mapping[str, object],
        timestamp: str,
    ) -> WorkMemoryRecord:
        return WorkMemoryRecord(
            source_id=source_id,
            context=context,
            payload=payload,
            observed_timestamp=timestamp,
            labels=("local-evaluation",),
        )

    def test_typed_selection_correction_and_exact_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            release = {"workspace": "atlas", "topic": "release"}
            invoice = {"workspace": "atlas", "topic": "invoice"}
            first = self._record(
                "atlas.release.region",
                release,
                {"region": "eu-west-3"},
                "2026-09-07T00:00:00Z",
            )
            second = self._record(
                "atlas.release.canary",
                release,
                {"canary_percent": 7},
                "2026-09-07T00:01:00Z",
            )
            distractor = self._record(
                "atlas.invoice.tax",
                invoice,
                {"tax_percent": 17},
                "2026-09-07T00:02:00Z",
            )

            with CassiFieldWorkMemory(root) as memory:
                first_receipt = memory.learn(first)
                second_receipt = memory.learn(second)
                memory.learn(distractor)
                recall = memory.recall(release, operation_label="release-before-restart")
                self.assertEqual(recall["status"], "supported")
                self.assertEqual(
                    [row["source_id"] for row in recall["records"]],
                    ["atlas.release.canary", "atlas.release.region"],
                )
                self.assertNotIn(
                    distractor.source_id,
                    {row["source_id"] for row in recall["records"]},
                )
                state_before_restart = memory.state_receipt()
                regional_before_restart = memory.regional_field_receipt()
                self.assertEqual(
                    regional_before_restart["semantic_active_bindings"],
                    3,
                )
                self.assertEqual(
                    regional_before_restart["semantic_family_counts"]["Binding"],
                    3,
                )

            with CassiFieldWorkMemory(root) as restarted:
                self.assertEqual(restarted.state_receipt(), state_before_restart)
                correction = restarted.learn(
                    self._record(
                        "atlas.release.canary",
                        release,
                        {"canary_percent": 11},
                        "2026-09-07T00:03:00Z",
                    )
                )
                self.assertEqual(correction["status"], "corrected")
                self.assertEqual(
                    correction["superseded_revision_id"],
                    second_receipt["source_revision_id"],
                )
                corrected = restarted.recall(release, operation_label="release-after-correction")
                payloads = {row["source_id"]: row["payload"] for row in corrected["records"]}
                self.assertEqual(payloads["atlas.release.canary"], {"canary_percent": 11})
                self.assertEqual(payloads["atlas.release.region"], {"region": "eu-west-3"})
                self.assertNotIn(
                    second_receipt["source_revision_id"],
                    corrected["selected_source_revision_ids"],
                )
                self.assertIn(
                    first_receipt["source_revision_id"],
                    corrected["selected_source_revision_ids"],
                )
                unknown = restarted.recall(
                    {"workspace": "atlas", "topic": "unseen"},
                    operation_label="unknown-context",
                )
                self.assertEqual(unknown["records"], [])
                state = restarted.state_receipt()
                self.assertTrue(state["all_finite"])
                self.assertGreater(state["generation"], 0)
                self.assertEqual(state["active_source_revisions"], 3)
                self.assertEqual(state["all_source_revisions"], 4)
                self.assertEqual(state["revocation_generation"], 0)
                self.assertEqual(state["evidence_events"], 4)
                self.assertEqual(state["semantic_state_schema"], "cassifi.semantic-cognition-state.v1")
                self.assertEqual(state["semantic_active_bindings"], 3)

    def test_regional_field_identity_is_current_and_persistent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with CassiFieldWorkMemory(root) as memory:
                first = memory.learn(
                    self._record(
                        "atlas.release.region",
                        {"workspace": "atlas", "topic": "release"},
                        {"region": "eu-west-3"},
                        "2026-09-07T00:00:00Z",
                    )
                )
                second = memory.learn(
                    self._record(
                        "atlas.invoice.tax",
                        {"workspace": "atlas", "topic": "invoice"},
                        {"tax_percent": 17},
                        "2026-09-07T00:01:00Z",
                    )
                )
                regional = memory.regional_field_receipt()
                self.assertEqual(regional["schema"], "cassi.field-qwen.regional-field-receipt.v2")
                self.assertEqual(regional["kernel"], "cognition.field")
                self.assertEqual(regional["computer_schema"], "cassifi.learning-computer.v3")
                self.assertEqual(regional["semantic_state_schema"], "cassifi.semantic-cognition-state.v1")
                self.assertEqual(regional["semantic_active_bindings"], 2)
                self.assertEqual(regional["semantic_family_counts"]["Binding"], 2)
                self.assertEqual(regional["profile"]["mode_count"], 196608)
                self.assertEqual(regional["profile"]["directory_capacity"], 256)
                self.assertEqual(regional["task_capacity_words"], 294912)
                self.assertLess(
                    regional["task_used_words"],
                    regional["task_capacity_words"],
                )
                self.assertEqual(len(regional["profile_sha256"]), 64)
                self.assertEqual(len(regional["catalog_sha256"]), 64)
                self.assertLessEqual(
                    regional["semantic_active_bindings"],
                    regional["semantic_bounds"]["max_records"],
                )
                self.assertLessEqual(
                    regional["semantic_transitions"],
                    regional["semantic_bounds"]["max_operations"],
                )
                self.assertTrue(regional["all_finite"])
                self.assertTrue(regional["field_bytes"] > 0)

            with CassiFieldWorkMemory(root) as restarted:
                self.assertEqual(restarted.regional_field_receipt(), regional)



if __name__ == "__main__":
    unittest.main(verbosity=2)

class LocalQwenClientRequestPolicyTests(unittest.TestCase):
    """The request body is the policy a receipt later claims it used."""

    class _Recorder(LocalQwenClient):
        def __init__(self, model_path: Path) -> None:
            self.sent: list[Mapping[str, object]] = []
            super().__init__("http://127.0.0.1:8084", model_path=model_path)

        def request(self, method, path, body=None, *, timeout=600.0):
            if method == "GET":
                return 200, {"data": [{"id": str(self.model_path)}]}, "{}"
            self.sent.append(dict(body))
            return (
                200,
                {
                    "choices": [
                        {
                            "message": {
                                "content": '{"sum":21}',
                                "reasoning_content": "weigh the rows",
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"completion_tokens": 5},
                    "timings": {"predicted_n": 5},
                },
                "{}",
            )

    def _client(self, directory: str) -> "LocalQwenClientRequestPolicyTests._Recorder":
        model = Path(directory) / "fixture.gguf"
        model.write_bytes(b"GGUF")
        return self._Recorder(model)

    def test_thinking_is_off_unless_asked_and_the_trace_is_returned(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            client = self._client(directory)
            quiet = client.complete(prompt="p", max_tokens=96)
            self.assertEqual(client.sent[-1]["chat_template_kwargs"], {"enable_thinking": False})
            self.assertEqual(client.sent[-1]["reasoning_format"], "deepseek")
            self.assertFalse(quiet["thinking"])
            self.assertEqual(quiet["generation_parameters"]["max_tokens"], 96)
            self.assertEqual(quiet["generation_parameters"]["temperature"], 0)
            self.assertNotIn("messages", quiet["generation_parameters"])
            self.assertNotIn("model", quiet["generation_parameters"])
            self.assertEqual(quiet["reasoning_content"], "weigh the rows")

            loud = client.complete(prompt="p", max_tokens=512, thinking=True)
            self.assertEqual(client.sent[-1]["chat_template_kwargs"], {"enable_thinking": True})
            self.assertTrue(loud["thinking"])
            self.assertEqual(loud["generation_parameters"]["max_tokens"], 512)
            self.assertEqual(
                loud["generation_parameters"]["chat_template_kwargs"],
                {"enable_thinking": True},
            )
    def test_policy_probe_catches_a_server_that_ignores_the_flag(self) -> None:
        """`/props` reports template text and jinja caps, never the thinking flag."""

        class _Server(LocalQwenClient):
            def __init__(self, model_path: Path, *, honors: bool) -> None:
                self.honors = honors
                super().__init__("http://127.0.0.1:8084", model_path=model_path)

            def request(self, method, path, body=None, *, timeout=600.0):
                if method == "GET" and path == "/v1/models":
                    return 200, {"data": [{"id": str(self.model_path)}]}, "{}"
                if method == "GET" and path == "/props":
                    return 200, {
                        "build_info": "b10472-wip9",
                        "chat_template": "{%- if enable_thinking is false %}<|end|>{%- endif %}",
                        "chat_template_caps": {"supports_tools": True, "supports_reasoning_effort": True},
                    }, "{}"
                thinking = bool((body.get("chat_template_kwargs") or {}).get("enable_thinking"))
                trace = "deliberating" if (self.honors and thinking) else ""
                return 200, {
                    "choices": [
                        {
                            "message": {"content": '{"sum":5}', "reasoning_content": trace},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"completion_tokens": 12 if trace else 4},
                }, "{}"

        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory) / "fixture.gguf"
            model.write_bytes(b"GGUF")
            applied = _Server(model, honors=True).probe_request_policy()
            self.assertTrue(applied["flag_effective"])
            self.assertEqual(applied["probe"]["thinking_off"]["completion_tokens"], 4)
            self.assertEqual(applied["probe"]["thinking_on"]["completion_tokens"], 12)
            self.assertTrue(applied["identity"]["chat_template_has_enable_thinking"])
            self.assertEqual(len(applied["identity"]["chat_template_sha256"]), 64)
            self.assertNotIn("supports_thinking", applied["identity"]["chat_template_caps"])

            ignored = _Server(model, honors=False).probe_request_policy()
            self.assertFalse(ignored["flag_effective"])
            self.assertTrue(ignored["identity"]["chat_template_has_enable_thinking"])

    def test_identity_half_excludes_measurements(self) -> None:
        """The model block is compared across arms, so it may hold only identity."""

        probe = {
            "identity": {"build_info": "b1", "chat_template_sha256": "0" * 64},
            "probe": {"thinking_off": {"completion_tokens": 4}, "thinking_on": {"completion_tokens": 12}},
            "flag_effective": True,
        }
        identity = server_identity(probe)
        self.assertEqual(identity, probe["identity"])
        self.assertEqual(set(identity), {"build_info", "chat_template_sha256"})

        with self.assertRaises(AssertionError):
            server_identity({"identity": {"completion_tokens": 4}})
