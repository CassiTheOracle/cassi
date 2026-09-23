"""The resident client's error contract at the field boundary.

A field-owned resource wait is not a missing brain.  The client runs inside the
entity, where a wait is the field asking for room while it keeps its
continuation; if the client converts that wait into unavailability, the caller
cannot tell "retry shortly" from "the brain is broken", and a turn that would
have resumed is lost.

These tests drive the real ``ResidentQwenClient.complete`` handler structure
with an injected executor, tokenizer, model package, and swarm, so no weights
are loaded and no field is opened.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
from typing import Any, Mapping, Sequence

import numpy as np
from cassi_field_residency import ResourceWait
from cassi_learning_computer import LearningComputerResidencyWait
from cassi_resident_qwen_client import ResidentQwenClient, ResidentQwenUnavailable
from programs.model.state_backing import SnapshotStore

_MODEL = Path(__file__).resolve().parent.parent / "Qwen3.5-0.8B-Q4_0.gguf"


class _Tokenizer:
    eog_ids = (2,)

    def encode(self, text: str, add_special: bool = False) -> Sequence[int]:
        return [1, 2, 3]


class _Package:
    graph = ("qwen-embedding", "qwen-attention", "qwen-head")


class _Swarm:
    """Minimal field surface: the start path is what these tests exercise."""

    def __init__(self, failure: BaseException) -> None:
        self.failure = failure
        self.starts = 0

    def bind_resident_model(self, source_sha256: str, executor: Any) -> Mapping[str, Any]:
        return {"status": "bound"}

    def start_model(self, member_id: str, package: Any, **kwargs: Any) -> Mapping[str, Any]:
        self.starts += 1
        raise self.failure


class _CompletingSwarm:
    """A field that completes a task, so the reclaim path can be exercised."""

    def __init__(self, release_failure: BaseException) -> None:
        self.release_failure = release_failure
        self.releases = 0

    def bind_resident_model(self, source_sha256: str, executor: Any) -> Mapping[str, Any]:
        return {"status": "bound"}

    def start_model(self, member_id: str, package: Any, **kwargs: Any) -> Mapping[str, Any]:
        return {"status": "submitted"}

    def run_to_boundary(self, member_id: str, **kwargs: Any) -> Mapping[str, Any]:
        return {"status": "yield"}

    def inspect(self, member_id: str, task_id: str | None = None, **kwargs: Any) -> Mapping[str, Any]:
        return {"status": "completed", "result": {"text": "ok", "finish_reason": "stop"}}

    def release_task(self, member_id: str, task_id: str) -> Mapping[str, Any]:
        self.releases += 1
        raise self.release_failure


def _client(directory: str, swarm: Any) -> ResidentQwenClient:
    client = ResidentQwenClient(_MODEL, Path(directory) / "resident")
    client._executor = object()
    client._tokenizer = _Tokenizer()
    client._package_cache = _Package()
    client._swarm = swarm
    client._member_id = "resident-client-test"
    return client


@unittest.skipUnless(_MODEL.is_file(), "the resident GGUF is not present")
class ResidentQwenDeferralContractTests(unittest.TestCase):
    def test_a_deferred_start_is_reported_as_a_wait(self) -> None:
        """The field asking for room must reach the caller as a wait."""

        with TemporaryDirectory() as directory:
            swarm = _Swarm(ResourceWait("ram", 32_768, 0, kind="resident"))
            client = _client(directory, swarm)
            with self.assertRaises(ResourceWait) as raised:
                client.complete(prompt="Hi", max_tokens=1)
            self.assertEqual(raised.exception.kind, "resident")
            self.assertEqual(raised.exception.requested, 32_768)
            self.assertEqual(swarm.starts, 1)

    def test_a_deferred_start_is_never_reported_as_unavailable(self) -> None:
        """The same wait must not be readable as a broken or absent brain."""

        with TemporaryDirectory() as directory:
            swarm = _Swarm(ResourceWait("ram", 32_768, 0, kind="scratch"))
            client = _client(directory, swarm)
            try:
                client.complete(prompt="Hi", max_tokens=1)
            except ResourceWait:
                pass
            except ResidentQwenUnavailable as exc:  # pragma: no cover - the defect
                self.fail(f"a deferred start was reported as unavailability: {exc}")
            else:  # pragma: no cover - the stub always defers
                self.fail("a deferred start completed instead of waiting")

    def test_a_real_start_failure_is_still_reported_as_unavailable(self) -> None:
        """The control: an absent task is a fault, so the wait path can fail."""

        with TemporaryDirectory() as directory:
            swarm = _Swarm(ValueError("field program task is unknown"))
            client = _client(directory, swarm)
            with self.assertRaises(ResidentQwenUnavailable) as raised:
                client.complete(prompt="Hi", max_tokens=1)
            self.assertIn("resident model task start failed", str(raised.exception))
            self.assertEqual(swarm.starts, 1)

    def test_a_deferred_reclaim_is_reported_as_a_wait(self) -> None:
        """Reclaiming a finished task can need room, and that is still a wait.

        The completion itself succeeded; reporting the working brain as
        unavailable because its cleanup had to wait would lose a real result.
        """

        with TemporaryDirectory() as directory:
            swarm = _CompletingSwarm(ResourceWait("ram", 32_768, 0, kind="resident"))
            client = _client(directory, swarm)
            with self.assertRaises(ResourceWait):
                client.complete(prompt="Hi", max_tokens=1)
            self.assertEqual(swarm.releases, 1)

    def test_a_computer_residency_wait_is_reported_as_a_wait(self) -> None:
        """The computer's typed continuation is the same wait in another class.

        A resident stage suspends through the learning computer, which reports
        its own residency continuation rather than the manager's wait.  Both mean
        the field asked for room, so neither may be reported as a broken brain.
        """

        wait = LearningComputerResidencyWait(
            "main",
            wait={"kind": "residency-wait"},
            continuation={"pages": [1, 2]},
            resident_limit=4,
        )
        with TemporaryDirectory() as directory:
            swarm = _Swarm(wait)
            client = _client(directory, swarm)
            with self.assertRaises(LearningComputerResidencyWait) as raised:
                client.complete(prompt="Hi", max_tokens=1)
            self.assertIs(raised.exception, wait)
            self.assertEqual(swarm.starts, 1)

    def test_a_real_reclaim_failure_is_still_reported_as_unavailable(self) -> None:
        """The control: a broken reclaim is a fault, not a wait."""

        with TemporaryDirectory() as directory:
            swarm = _CompletingSwarm(ValueError("field program task is unknown"))
            client = _client(directory, swarm)
            with self.assertRaises(ResidentQwenUnavailable) as raised:
                client.complete(prompt="Hi", max_tokens=1)
            self.assertIn("resident model task release failed", str(raised.exception))
            self.assertEqual(swarm.releases, 1)

    def test_prefix_requires_complete_matching_numerical_boundary(self) -> None:
        """A valid but intermediate snapshot cannot skip the rest of a token."""

        with TemporaryDirectory() as directory:
            client = _client(directory, SimpleNamespace(
                resident_field_state_sha256=lambda _member: "a" * 64,
            ))
            client._package_cache = SimpleNamespace(graph=[
                {"op": "qwen-embedding", "stage": "qwen-embedding"},
                {"op": "qwen-layer", "stage": "qwen-layer", "parameters": {"layer": 3}},
                {"op": "qwen-head", "stage": "qwen-head"},
            ])
            store = SnapshotStore(Path(directory) / "snapshots")
            executor = SimpleNamespace(
                _load_state=lambda request: store.load(request["snapshot"]),
            )
            conversation = "boundary-check"
            tokens = (11, 12)
            base = (client.model_sha256, client.backend, client._member_id, conversation)
            cache_key = (*base, tokens)
            client._latest_resident_prefix[base] = cache_key
            entry = {
                "tokens": tokens,
                "field_epoch_sha256": "a" * 64,
                "boundaries": [],
            }
            client._resident_prefix_cache[cache_key] = entry

            def candidate(stage: str, layer: int | None, backend: str):
                snapshot = store.save(
                    {"hidden": np.array([1.0, 2.0], dtype=np.float32)},
                    {
                        "source_sha256": client.model_sha256,
                        "architecture": client.architecture,
                        "position": 0,
                        "token": 11,
                        "stage": stage,
                        "layer": layer,
                        "backend": backend,
                    },
                )
                entry["boundaries"] = [{
                    "position": 0,
                    "token": 11,
                    "head_executed": False,
                    "snapshot": snapshot,
                }]
                return client._resident_prefix_candidate((11, 12, 13), conversation, executor)

            for stage, layer, backend in (
                ("qwen-embedding", None, "cpu"),
                ("qwen-layer", 2, "cpu"),
                ("qwen-layer", 3, "vulkan"),
            ):
                seed, reason = candidate(stage, layer, backend)
                self.assertIsNone(seed)
                self.assertEqual(reason, "no-matching-stage-boundary")
            seed, reason = candidate("qwen-layer", 3, "cpu")
            self.assertEqual(reason, "eligible-prefix")
            self.assertEqual(seed["prefix_token_count"], 1)
            self.assertEqual(seed["token"], 11)


if __name__ == "__main__":
    unittest.main()
