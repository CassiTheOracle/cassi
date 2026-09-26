"""Resident client and executor contracts at the field boundary.

A field-owned resource wait preserves its continuation. Native image tokens
keep the last accepted input snapshot through an atomic field batch so a
retried stage reads the same activations, then retire it on publication.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch
import contextlib
import threading
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
from typing import Any, Mapping, Sequence

import numpy as np
import backend_policy
from cassi_work_trace import trace_work
from cassi_field_residency import ResourceLimits, ResourceWait
from cassi_learning_computer import LearningComputerResidencyWait
from cassi_programmable_swarm import ProgrammableSwarm, ProgrammableSwarmError
from cassi_resident_qwen_client import (
    RESIDENT_RESOURCE_FEEDBACK_SCHEMA,
    ResidentQwenCancelled,
    ResidentQwenClient,
    ResidentQwenUnavailable,
    _resident_context_scope,
)
from programs.model.state_backing import SnapshotStore
from programs.model.qwen_executor import ResidentQwenError, ResidentQwenExecutor

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




class _SegmentSwarm:
    def __init__(self, run_wait: BaseException | None = None) -> None:
        self.run_wait = run_wait
        self.tasks: dict[str, dict[str, Any]] = {}
        self.started: list[Mapping[str, Any]] = []
        self.bindings: list[tuple[str, Any]] = []
        self.released: list[str] = []

    def bind_resident_model(self, source_sha256: str, executor: Any) -> Mapping[str, Any]:
        self.bindings.append((source_sha256, executor))
        return {"status": "bound"}

    def start_model(self, member_id: str, package: Any, **kwargs: Any) -> Mapping[str, Any]:
        task_id = str(kwargs["task_id"])
        self.started.append(dict(kwargs))
        self.tasks[task_id] = {"status": "running", "segments": 0}
        return {"status": "submitted"}

    def run_to_boundary(self, member_id: str, *, task_id: str, **kwargs: Any) -> Mapping[str, Any]:
        if self.run_wait is not None:
            raise self.run_wait
        task = self.tasks[task_id]
        task["segments"] += 1
        if task["segments"] == 2:
            task["status"] = "completed"
        return {"view": self.inspect(member_id, task_id=task_id)}

    def inspect(self, member_id: str, task_id: str | None = None, **kwargs: Any) -> Mapping[str, Any]:
        task = self.tasks[str(task_id)]
        result = (
            {"text": "done", "finish_reason": "stop", "field_policies": {}}
            if task["status"] == "completed"
            else None
        )
        return {
            "status": task["status"],
            "result": result,
            "resident_model": {},
        }

    def release_task(self, member_id: str, task_id: str) -> Mapping[str, Any]:
        task = self.tasks[task_id]
        if task["status"] == "running":
            task["status"] = "cancelled"
        self.released.append(task_id)
        return {"status": "released"}

    def resident_field_state_sha256(self, member_id: str) -> str:
        return "c" * 64


def _segment_client(swarm: _SegmentSwarm) -> ResidentQwenClient:
    client = object.__new__(ResidentQwenClient)
    client.model_id = "shared-qwen.gguf"
    client.model_sha256 = "a" * 64
    client.architecture = "qwen35"
    client.requested_backend = "cpu"
    client.source_id = "shared-qwen.gguf"
    client.model_metadata = {}
    client._manifest = {"tensors": []}
    client._resource_limits = None
    client._resource_limit_source = None
    client._resource_manager = None
    client._physical_admission = None
    client._bank_reservation = None
    client._bank_reserved_bytes = 0
    client._activity_reservations = {}
    client._activity_reservation_bytes = {}
    client._trunk_depth = None
    client._context_length = 32_768
    client._program_id = "resident-qwen"
    client._placement = None
    client._stage_dispatch_priority = lambda *args, **kwargs: contextlib.nullcontext()
    client._executor_lock = threading.RLock()
    client._prefix_lock = threading.RLock()
    client._vision_lock = threading.RLock()
    client._projector_path = None
    client._projector_sha256 = None
    client._ngram_table_path = None
    client.backend = "cpu"
    client._closed = False
    client._executor = object()
    client._tokenizer = _Tokenizer()
    client._package_cache = _Package()
    client._swarm = swarm
    client._member_id = "shared-member"
    client._resident_prefix_cache = {}
    client._latest_resident_prefix = {}
    client._vision_encoder = None
    client._ngram_table = None
    client._pending_visual = {}
    client._visual_attempts = {}
    return client


class ResidentBackendPlacementTests(unittest.TestCase):
    def test_auto_uses_native_capacity_and_pins_the_first_loaded_bank(self) -> None:
        client = object.__new__(ResidentQwenClient)
        client.requested_backend = client.backend = "auto"
        client.library_path = None
        client._resource_limits = ResourceLimits(
            device="auto", vram_bytes=10_000, vram_headroom_bytes=100,
            scratch_bytes=100,
        )
        client._manifest = {"tensors": [
            {"gguf_dimensions": [16, 16], "byte_length": 1000},
            {"gguf_dimensions": [16, 16, 8], "byte_length": 7000},
        ]}
        client._closed = False
        client._executor = None
        client._executor_lock = threading.RLock()
        client._ngram_table_path = None
        client.model_path = Path("verified.gguf")
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        client.state_directory = Path(directory.name)
        client.model_sha256 = "a" * 64
        client.threads = 1
        client._projector_path = None
        loaded: list[str] = []

        def open_bank(*args: Any, backend: str, **kwargs: Any) -> object:
            loaded.append(backend)
            return object()

        with patch("programs.model.weight_bank.vulkan_memory", return_value=(5000, 8000)) as memory, patch(
            "programs.model.qwen_executor.ResidentQwenExecutor", side_effect=open_bank
        ):
            first = client._ensure_executor()
            memory.return_value = (0, 8000)
            self.assertIs(client._ensure_executor(), first)
        self.assertEqual(loaded, ["vulkan"])
        self.assertEqual(client._placement["device_placement"]["weight_bank"], "vulkan")
        self.assertIsNone(
            client._placement["device_placement"]["physical_adapter_identity"]
        )
        self.assertEqual(
            client._placement["device_placement"]["physical_adapter_identity_status"],
            "unavailable-from-resident-qwen-runtime",
        )
        self.assertEqual(client.backend, "vulkan")
        self.assertEqual(client._placement["estimated_dense_weights_and_scratch_bytes"], 1100)
        self.assertEqual(client._placement["measured_vulkan_free_bytes"], 5000)
        restarted = object.__new__(ResidentQwenClient)
        restarted.requested_backend = restarted.backend = "auto"
        restarted.state_directory = client.state_directory
        restarted.model_sha256 = client.model_sha256
        restarted._resource_limits = client._resource_limits
        with patch("programs.model.weight_bank.vulkan_memory") as query:
            pinned_backend, pin_placement = restarted._select_backend()
            self.assertEqual(pinned_backend, "vulkan")
            self.assertEqual(pin_placement["reason"], "restart-bank-pin")
            self.assertEqual(
                pin_placement["device_placement"],
                client._placement["device_placement"],
            )
            self.assertEqual(
                pin_placement["capacity_evidence"]["measured_vulkan_free_bytes"],
                5000,
            )
            query.assert_not_called()
        restarted._swarm = SimpleNamespace(list_tasks=lambda _member: ())
        restarted._member_id = "shared-member"
        restarted._manifest = client._manifest
        restarted.library_path = None
        with patch("programs.model.weight_bank.vulkan_memory", return_value=(100, 8000)):
            backend, placement = restarted._select_backend()
        self.assertEqual(backend, "cpu")
        self.assertEqual(placement["reason"], "vulkan-capacity-insufficient")

    def test_auto_rejects_gpu_when_policy_or_physical_room_is_too_small(self) -> None:
        client = object.__new__(ResidentQwenClient)
        client.requested_backend = client.backend = "auto"
        client.library_path = None
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        client.state_directory = Path(directory.name)
        client.model_sha256 = "b" * 64
        client._manifest = {"tensors": [{"gguf_dimensions": [16, 16], "byte_length": 1000}]}
        client._resource_limits = ResourceLimits(
            device="cpu", vram_bytes=10_000, vram_headroom_bytes=100, scratch_bytes=100,
        )
        policy = [client._resource_limits]
        client._resource_limit_source = (lambda _computer_id: policy[0], "field")
        with patch("programs.model.weight_bank.vulkan_memory") as query:
            self.assertEqual(client._select_backend()[1]["reason"], "field-device-policy")
            query.assert_not_called()
        policy[0] = ResourceLimits(
            device="auto", vram_bytes=10_000, vram_headroom_bytes=100, scratch_bytes=100,
        )
        with patch("programs.model.weight_bank.vulkan_memory", return_value=(1000, 8000)):
            backend, decision = client._select_backend()
        self.assertEqual(backend, "cpu")
        self.assertEqual(decision["reason"], "vulkan-capacity-insufficient")
        self.assertEqual(decision["measured_vulkan_free_bytes"], 1000)


    def test_durable_snapshot_crosses_banks_with_exact_values_and_model_identity(self) -> None:
        with TemporaryDirectory() as directory:
            store = SnapshotStore(Path(directory))
            snapshot = store.save(
                {"hidden": np.array([1.0], dtype=np.float32)},
                {"source_sha256": "a" * 64, "backend": "cpu"},
            )
            executor = object.__new__(ResidentQwenExecutor)
            executor.backend = "vulkan"
            executor._model = SimpleNamespace(source_sha256="a" * 64)
            executor._snapshots = store
            executor._working_snapshot = None
            executor._working_arrays = None
            executor._working_metadata = None
            arrays, metadata = executor._load_state({"snapshot": snapshot})
            self.assertEqual(arrays["hidden"].tobytes(), np.array([1.0], dtype=np.float32).tobytes())
            self.assertEqual(metadata["backend"], "cpu")
            wrong = object.__new__(ResidentQwenExecutor)
            wrong.backend = "vulkan"
            wrong._model = SimpleNamespace(source_sha256="b" * 64)
            wrong._snapshots = store
            wrong._working_snapshot = wrong._working_arrays = wrong._working_metadata = None
            with self.assertRaisesRegex(ResidentQwenError, "source identity"):
                wrong._load_state({"snapshot": snapshot})
            executor._working_arrays = None
            del arrays



class ResidentQwenScopedSchedulingTests(unittest.TestCase):
    def test_resident_stage_wait_yields_then_continues_to_completion(self) -> None:
        class StageYieldSwarm(_SegmentSwarm):
            def __init__(self) -> None:
                super().__init__()
                self.stage_yielded = False

            def run_to_boundary(self, member_id: str, *, task_id: str, **kwargs: Any) -> Mapping[str, Any]:
                if not self.stage_yielded:
                    self.stage_yielded = True
                    return {
                        "view": {
                            "status": "waiting",
                            "unfinished_reason": "resident-model-stage",
                        },
                        "receipt": {"operation_id": "stage-0"},
                    }
                return super().run_to_boundary(member_id, task_id=task_id, **kwargs)

        swarm = StageYieldSwarm()
        client = _segment_client(swarm)
        progress: list[Mapping[str, Any]] = []
        result = client.complete(
            prompt="continue", max_tokens=1, segment_callback=progress.append,
        )
        self.assertEqual(result["content"], "done")
        self.assertTrue(any(row["status"] == "waiting" for row in progress))
        self.assertEqual(len(swarm.released), 1)

    def test_whole_request_receipt_cites_the_active_work_trace(self) -> None:
        client = _segment_client(_SegmentSwarm())
        with trace_work() as trace:
            trace.record("projection", "fixture.weight", 2_000_000, rows=2, items=1)
            receipt = client.complete(prompt="trace", max_tokens=1)
        cited = receipt["server_cassi_receipt"]["work_trace"]
        self.assertEqual(cited["schema"], "cassifi.work-trace-summary.v1")
        self.assertEqual(cited["trace_schema"], "cassifi.work-trace.v1")
        self.assertEqual(cited["row_count"], 2)
        measured = {(entry["kind"], entry["name"]): entry for entry in cited["groups"]}
        self.assertEqual(measured[("projection", "fixture.weight")]["duration_ms"], 2.0)
        self.assertGreaterEqual(cited["total_duration_ms"], 2.0)
        self.assertEqual(cited["trace_sha256"], trace.summary()["trace_sha256"])
        kinds = {(entry["kind"], entry["name"]) for entry in cited["groups"]}
        self.assertIn(("request", "resident-qwen"), kinds)
        self.assertIn(("projection", "fixture.weight"), kinds)
        untraced = client.complete(prompt="plain", max_tokens=1)
        self.assertIsNone(untraced["server_cassi_receipt"]["work_trace"])

    def test_scoped_activities_share_model_but_not_cached_context(self) -> None:
        backend_policy.LEDGER.clear()
        self.addCleanup(backend_policy.LEDGER.clear)
        with TemporaryDirectory() as directory:
            swarm = _SegmentSwarm()
            client = _segment_client(swarm)
            store = SnapshotStore(Path(directory) / "snapshots")
            client._executor = SimpleNamespace(
                _load_state=lambda request: store.load(request["snapshot"])
            )
            client._package_cache = SimpleNamespace(
                graph=[
                    {"op": "qwen-embedding", "stage": "qwen-embedding"},
                    {
                        "op": "qwen-layer",
                        "stage": "qwen-layer",
                        "parameters": {"layer": 3},
                    },
                    {"op": "qwen-head", "stage": "qwen-head"},
                ]
            )
            context_a = _resident_context_scope("conversation", "program:alpha")
            context_b = _resident_context_scope("conversation", "program:beta")
            self.assertNotEqual(context_a, context_b)
            snapshot = store.save(
                {"hidden": np.array([1.0, 2.0], dtype=np.float32)},
                {
                    "source_sha256": client.model_sha256,
                    "architecture": client.architecture,
                    "position": 0,
                    "token": 1,
                    "stage": "qwen-layer",
                    "layer": 3,
                    "backend": client.backend,
                },
            )
            base = client._resident_prefix_base_key(context_a)
            cache_key = (*base, (1, 2))
            client._latest_resident_prefix[base] = cache_key
            client._resident_prefix_cache[cache_key] = {
                "tokens": (1, 2),
                "field_epoch_sha256": "c" * 64,
                "boundaries": [
                    {
                        "position": 0,
                        "token": 1,
                        "head_executed": False,
                        "snapshot": snapshot,
                    }
                ],
            }

            first_progress: list[Mapping[str, Any]] = []
            first = client.complete(
                prompt="continue",
                max_tokens=1,
                conversation_id="conversation",
                activity_id="program:alpha",
                segment_callback=first_progress.append,
            )
            second = client.complete(
                prompt="continue",
                max_tokens=1,
                conversation_id="conversation",
                activity_id="program:beta",
            )
        self.assertEqual(len(first_progress), 1)
        self.assertEqual(first_progress[0]["status"], "running")

        self.assertEqual(len(swarm.bindings), 2)
        self.assertIs(swarm.bindings[0][1], swarm.bindings[1][1])
        self.assertEqual(swarm.bindings[0][0], client.model_sha256)
        self.assertIsNotNone(swarm.started[0]["resident_prefix"])
        self.assertEqual(swarm.started[0]["resident_prefix"]["conversation_id"], context_a)
        self.assertIsNone(swarm.started[1]["resident_prefix"])
        first_receipt = first["server_cassi_receipt"]
        second_receipt = second["server_cassi_receipt"]
        self.assertNotEqual(first_receipt["operation_id"], second_receipt["operation_id"])
        self.assertEqual(first_receipt["prefix_reuse"]["context_scope_id"], context_a)
        self.assertEqual(second_receipt["prefix_reuse"]["context_scope_id"], context_b)
        self.assertTrue(
            client.advance_resident_prefix_epoch(
                "conversation",
                activity_id="program:alpha",
                expected_epoch_sha256="c" * 64,
                next_epoch_sha256="d" * 64,
            )
        )
        self.assertFalse(
            client.advance_resident_prefix_epoch(
                "conversation",
                activity_id="program:beta",
                expected_epoch_sha256="c" * 64,
                next_epoch_sha256="e" * 64,
            )
        )
        self.assertEqual(first_receipt["activity_id"], "program:alpha")
        self.assertEqual(second_receipt["activity_id"], "program:beta")
        self.assertEqual(
            first["resource_feedback"]["schema"],
            RESIDENT_RESOURCE_FEEDBACK_SCHEMA,
        )
        self.assertEqual(first["resource_feedback"]["source_sha256"], client.model_sha256)
        self.assertEqual(first["resource_feedback"]["measured"]["segment_count"], 2)
        measured = first["resource_feedback"]["measured"]
        self.assertGreater(measured["whole_request_cost_ns"], 0)
        self.assertGreaterEqual(measured["whole_request_cost_ns"], measured["warm_request_cost_ns"])
        cost_evidence = first_receipt["backend_cost_evidence"]
        self.assertTrue(measured["cost_sample_admitted"])
        self.assertTrue(cost_evidence["recorded"])
        self.assertEqual(cost_evidence["scope"], measured["cost_scope"])
        profile = cost_evidence["scope_profile"]
        self.assertEqual(profile["source_sha256"], client.model_sha256)
        self.assertEqual(profile["intervention_shape"], {})
        self.assertEqual(profile["output_token_count"], 0)
        observed = backend_policy.observed_cost(
            "cpu", scope=measured["cost_scope"]
        )
        self.assertIsNotNone(observed)
        self.assertEqual(observed["work"], measured["request_work_units"])
        self.assertGreater(observed["use_seconds"], 0)

    def test_cancellation_at_a_segment_fences_the_completed_result(self) -> None:
        swarm = _SegmentSwarm()
        client = _segment_client(swarm)
        cancellation = threading.Event()
        progress: list[Mapping[str, Any]] = []

        def cancel_after_first_boundary(row: Mapping[str, Any]) -> None:
            progress.append(row)
            cancellation.set()

        with self.assertRaises(ResidentQwenCancelled) as raised:
            client.complete(
                prompt="stop me",
                max_tokens=1,
                activity_id="program:cancel",
                cancel_event=cancellation,
                segment_callback=cancel_after_first_boundary,
            )

        self.assertEqual(len(progress), 1)
        self.assertEqual(progress[0]["segment_index"], 1)
        self.assertEqual(len(swarm.started), 1)
        self.assertEqual(swarm.tasks[raised.exception.task_id]["status"], "cancelled")
        self.assertEqual(swarm.released, [raised.exception.task_id])

    def test_resource_wait_remains_the_original_typed_wait(self) -> None:
        wait = ResourceWait("ram", 4096, 0, kind="resident")
        swarm = _SegmentSwarm(run_wait=wait)
        client = _segment_client(swarm)

        with self.assertRaises(ResourceWait) as raised:
            client.complete(
                prompt="wait",
                max_tokens=1,
                activity_id="program:wait",
            )

        self.assertIs(raised.exception, wait)
        self.assertEqual(raised.exception.requested, 4096)
        self.assertEqual(swarm.released, [])

def _client(directory: str, swarm: Any) -> ResidentQwenClient:
    client = ResidentQwenClient(_MODEL, Path(directory) / "resident")
    client._executor = object()
    client._tokenizer = _Tokenizer()
    client._package_cache = _Package()
    client._swarm = swarm
    client._member_id = "resident-client-test"
    client._stage_dispatch_priority = lambda *args, **kwargs: contextlib.nullcontext()
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
            base = client._resident_prefix_base_key(conversation)
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
            ):
                seed, reason = candidate(stage, layer, backend)
                self.assertIsNone(seed)
                self.assertEqual(reason, "no-matching-stage-boundary")
            seed, reason = candidate("qwen-layer", 3, "cpu")
            self.assertEqual(reason, "eligible-prefix")
            self.assertEqual(seed["prefix_token_count"], 1)
            self.assertEqual(seed["token"], 11)
            client.backend = "vulkan"
            seed, reason = client._resident_prefix_candidate((11, 12, 13), conversation, executor)
            self.assertEqual(reason, "eligible-prefix")
            self.assertEqual(seed["backend"], "vulkan")
            self.assertEqual(seed["snapshot"], entry["boundaries"][0]["snapshot"])

class ResidentInterleavedRopeTests(unittest.TestCase):
    def test_interleaved_positions_rotate_split_half_pairs(self) -> None:
        executor = object.__new__(ResidentQwenExecutor)
        executor._model = SimpleNamespace(
            architecture="qwen35moe",
            metadata={"qwen35moe.rope.dimension_count": 8},
        )
        x = np.arange(1, 9, dtype=np.float32)
        rotated = executor._rope(x, (1, 2, 3, 4), [1, 1, 1, 1], 10000.0)
        theta = np.array(
            [position * 10000.0 ** (-2 * pair / 8)
             for pair, position in enumerate((1, 2, 3, 4))],
            dtype=np.float32,
        )
        expected = np.concatenate((
            x[:4] * np.cos(theta) - x[4:] * np.sin(theta),
            x[:4] * np.sin(theta) + x[4:] * np.cos(theta),
        ))
        np.testing.assert_allclose(rotated, expected, atol=1e-6)


class ResidentRecurrentCausalityTests(unittest.TestCase):
    def test_newest_input_uses_final_convolution_tap(self) -> None:
        executor = object.__new__(ResidentQwenExecutor)
        executor._model = SimpleNamespace(
            architecture="qwen35",
            metadata={
                "qwen35.ssm.group_count": 1,
                "qwen35.ssm.state_size": 1,
                "qwen35.ssm.inner_size": 2,
                "qwen35.ssm.time_step_rank": 1,
            },
        )
        executor._norm = lambda x, *args: x
        executor._exchange = lambda kind, x, **kwargs: x
        executor._weight = lambda stem, *args, **kwargs: (
            "causal-kernel" if stem == "ssm_conv1d" else None
        )
        executor._tensor = lambda name: np.tile(
            np.array([0, 0, 0, 1], dtype=np.float32), (4, 1),
        )
        executor._tensor_shapes = {"causal-kernel": {"shape": [4, 4]}}
        executor._vec = lambda *args, **kwargs: None
        executor._mat = lambda stem, x, layer, **kwargs: x
        executor._mat_many = lambda names, x, layer, **kwargs: (
            (np.array([1, 1, 3, 5], dtype=np.float32),
             np.ones(2, dtype=np.float32))
            if names[0][0] == "attn_qkv"
            else (np.zeros(1, dtype=np.float32), np.zeros(1, dtype=np.float32))
        )
        projected = executor._recurrent_attention(
            np.ones(2, dtype=np.float32), {}, 0, 0,
        )
        self.assertTrue(np.all(projected > 0.5))
        self.assertGreater(float(projected[1]), float(projected[0]))


class ResidentQueryGateTests(unittest.TestCase):
    def test_interleaved_query_gates_and_grouped_values_follow_head_layout(self) -> None:
        executor = object.__new__(ResidentQwenExecutor)
        executor._model = SimpleNamespace(
            architecture="qwen35moe",
            metadata={
                "qwen35moe.attention.head_count": 2,
                "qwen35moe.attention.head_count_kv": 2,
                "qwen35moe.attention.key_length": 2,
                "qwen35moe.attention.value_length": 2,
                "qwen35moe.rope.dimension_sections": [2],
            },
        )
        executor._norm = lambda x, *args: x
        executor._vec = lambda *args, **kwargs: None
        executor._exchange = lambda kind, x, **kwargs: x
        executor._rope = lambda x, *args: x
        executor._mat = lambda stem, x, layer, **kwargs: x if stem == "attn_out" else None
        q = np.array([1, 0, -20, -20, 0, 1, 20, 20], dtype=np.float32)
        k = np.array([1, 0, 0, 1], dtype=np.float32)
        v = np.array([2, 3, 5, 7], dtype=np.float32)
        executor._mat_many = lambda names, x, layer: (q, k, v)

        projected = executor._full_attention(
            np.ones(4, dtype=np.float32), {}, 0, 0,
        )
        np.testing.assert_allclose(projected, [0, 0, 5, 7], atol=1e-5)
        executor._model.metadata["qwen35moe.attention.head_count"] = 4
        q = np.tile(np.array([1, 0, 20, 20], dtype=np.float32), 4)
        projected = executor._full_attention(
            np.ones(4, dtype=np.float32), {}, 0, 0,
        )
        np.testing.assert_allclose(
            projected, [2, 3, 2, 3, 5, 7, 5, 7], atol=1e-5,
        )


class ResidentVisualSnapshotTests(unittest.TestCase):
    def test_replayed_visual_stage_reads_previous_and_batch_input(self) -> None:
        executor = object.__new__(ResidentQwenExecutor)
        executor.backend = "cpu"
        executor._model = SimpleNamespace(source_sha256="a" * 64, architecture="qwen35moe")
        executor._visual_embedding_sets = {"visual-example": np.zeros((1, 2), dtype=np.float32)}
        executor._volatile_visual_snapshots = {}
        executor._volatile_visual_previous = {}
        executor._volatile_visual_checkpoints = {}
        executor._volatile_snapshot_sequence = 0
        executor._working_snapshot = None
        executor._working_arrays = None
        executor._working_metadata = None
        executor.working_snapshot_hits = 0
        request = {
            "position": 0,
            "token": 1,
            "stage": "qwen-layer",
            "layer": 0,
            "parameters": {"visual_embedding_id": "visual-example"},
        }

        def save(value: float) -> Mapping[str, Any]:
            return executor._save_state(
                {"hidden": np.array([value, value + 1], dtype=np.float32)},
                request,
            )

        input_snapshot = save(1)
        executor.retain_visual_snapshot("visual-example", input_snapshot)
        previous_snapshot = save(3)
        latest_snapshot = save(5)
        previous_arrays, _ = executor._load_state({"snapshot": previous_snapshot})
        input_arrays, _ = executor._load_state({"snapshot": input_snapshot})
        np.testing.assert_array_equal(previous_arrays["hidden"], [3, 4])
        np.testing.assert_array_equal(input_arrays["hidden"], [1, 2])

        executor.commit_visual_snapshot("visual-example")
        np.testing.assert_array_equal(executor._load_state({"snapshot": input_snapshot})[0]["hidden"], [1, 2])
        np.testing.assert_array_equal(executor._load_state({"snapshot": previous_snapshot})[0]["hidden"], [3, 4])
        executor.retain_visual_snapshot("visual-example", latest_snapshot)
        save(7)
        executor.commit_visual_snapshot("visual-example")
        with self.assertRaises(ResidentQwenError):
            executor._load_state({"snapshot": input_snapshot})
        with self.assertRaises(ResidentQwenError):
            executor._load_state({"snapshot": previous_snapshot})



if __name__ == "__main__":
    unittest.main()
