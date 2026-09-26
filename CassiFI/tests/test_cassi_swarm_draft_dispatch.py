from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
import sys

_CASSI_FI_ROOT = Path(__file__).resolve().parents[1]
if str(_CASSI_FI_ROOT) not in sys.path:
    sys.path.insert(0, str(_CASSI_FI_ROOT))

import pytest
import cassi_programmable_swarm as swarm_module  # type: ignore[reportMissingImports]


class _RecordingRuntime:
    """Stands in for the native runtime so the dispatch shape is visible."""

    def __init__(self) -> None:
        self.service_generation = 7
        self.calls: list[tuple[str, tuple[int, ...], dict[str, Any]]] = []

    def step_model(
        self,
        task_id: str,
        source_sha256: str,
        tokens: Sequence[int],
        **kwargs: Any,
    ) -> Mapping[str, Any]:
        self.calls.append(("step", tuple(tokens), {"task_id": task_id, **kwargs}))
        return {
            "status": "model-step",
            "token": 700 + len(self.calls),
            "sampled_token": 700 + len(self.calls),
            "end_of_generation": False,
            "token_count": len(tokens) + 1,
            "replay_sha256": "1" * 64,
            "stage_trace_sha256": "2" * 64,
            "exact_stages": 50,
            "embedding_stages": 1,
            "attention_stages": 24,
            "ffn_stages": 24,
            "head_stages": 1,
            "ggml_nodes": 1846,
            "logical_weight_bytes": 552075584,
            "sampler": {"mode": kwargs["sampler_mode"]},
            "sampler_sha256": "3" * 64,
            "native_operation_id": kwargs["native_operation_id"],
        }

    def verify_model_draft(
        self,
        task_id: str,
        source_sha256: str,
        tokens: Sequence[int],
        draft_tokens: Sequence[int],
        **kwargs: Any,
    ) -> Mapping[str, Any]:
        self.calls.append(
            (
                "draft",
                tuple(tokens),
                {"task_id": task_id, "draft_tokens": tuple(draft_tokens), **kwargs},
            )
        )
        rows = [
            {
                "status": "model-step",
                "token": int(token),
                "sampled_token": int(token),
                "end_of_generation": False,
                "token_count": len(tokens) + index + 1,
                "replay_sha256": f"{index + 1:064x}",
                "stage_trace_sha256": f"{index + 11:064x}",
                "exact_stages": 50,
                "embedding_stages": 1,
                "attention_stages": 24,
                "ffn_stages": 24,
                "head_stages": 1,
                "ggml_nodes": 1846,
                "logical_weight_bytes": 552075584,
                "sampler": {"mode": kwargs["sampler_mode"]},
                "sampler_sha256": "3" * 64,
                "native_operation_id": kwargs["operation_ids"][index],
                "position": len(tokens) + index,
                "draft_matched": index < len(draft_tokens),
            }
            for index, token in enumerate([*draft_tokens, 4242])
        ]
        return {
            "status": "model-draft-rows",
            "rows": rows,
            "committed": len(rows),
            "accepted_token_id": rows[-1]["token"],
        }


def _record(runtime: _RecordingRuntime, *, run: Mapping[str, Any] | None) -> dict[str, Any]:
    return {
        "member_id": "member-1",
        "task_id": "task-1",
        "native_task_id": "native-task-1",
        "row_identity": "member-1:task-1",
        "runtime": runtime,
        "source_sha256": "a" * 64,
        "history": (9707, 11, 1879, 374, 283),
        "sampler": {"mode": "greedy", "temperature": 1.0, "top_k": 0, "draw": 0.0},
        "sequence_id": "task-1-seq",
        "operation_id": "op-0",
        "stop_tokens": (2,),
        "site": ("local", 0),
        "run": run,
        "owner_history": {"graph_receipts": (), "accepted_steps": [], "payload": b""},
        "history_sync": {"status": "native-history-current"},
    }


def _prepared_swarm(
    monkeypatch: pytest.MonkeyPatch,
    captured: dict[str, Any],
) -> swarm_module.ProgrammableSwarm:
    swarm = swarm_module.ProgrammableSwarm()
    monkeypatch.setattr(swarm, "_release_native_seats", lambda *args, **kwargs: ())
    monkeypatch.setattr(
        swarm,
        "_ensure_native_task_history",
        lambda record, history, require_cache: {"status": "native-history-current"},
    )
    monkeypatch.setattr(swarm, "_prepare_native_graph_site_dispatch", lambda record: None)

    def continue_wait(
        record: Mapping[str, Any],
        result: Mapping[str, Any] | None,
        registration: Mapping[str, Any],
        prior_receipt: Mapping[str, Any] | None,
        **kwargs: Any,
    ) -> Mapping[str, Any]:
        captured["result"] = result
        steps = result.get("steps") if isinstance(result, Mapping) else None
        if not steps:
            return {"status": "serviced", "native_model": {"step": result, "run": None}}
        return {
            "status": "serviced",
            "native_model": {
                "step": steps[-1] if steps else None,
                "run": {"length": len(steps), "tokens": [step["token"] for step in steps]},
            },
        }

    monkeypatch.setattr(swarm, "_continue_native_model_wait", continue_wait)
    return swarm


def test_singleton_commits_a_draft_run_in_one_verification_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _RecordingRuntime()
    captured: dict[str, Any] = {}
    swarm = _prepared_swarm(monkeypatch, captured)
    record = _record(
        runtime,
        run={
            "bound": 4,
            "operation_ids": ("op-0", "op-1", "op-2", "op-3"),
            "draws": (0.0, 0.25, 0.5, 0.75),
            "draft_tokens": (220, 16, 15),
        },
    )

    serviced = swarm._service_native_singleton(
        record, {"registration": "one"}, None, incompatible=(), fallback_reason="", cleanup=False
    )

    assert [call[0] for call in runtime.calls] == ["draft"]
    kind, tokens, kwargs = runtime.calls[0]
    assert tokens == (9707, 11, 1879, 374, 283)
    assert kwargs["draft_tokens"] == (220, 16, 15)
    assert kwargs["draws"] == (0.0, 0.25, 0.5, 0.75)
    assert kwargs["operation_ids"] == ("op-0", "op-1", "op-2", "op-3")
    assert kwargs["sequence_id"] == "task-1-seq"
    assert kwargs["stop_tokens"] == (2,)
    assert captured["result"] is not None
    assert [step["token"] for step in captured["result"]["steps"]] == [220, 16, 15, 4242]
    group = serviced["native_group"]
    assert group["status"] == "singleton-dispatched"
    assert group["cohort"][0]["token"] == 4242
    assert group["cohort"][0]["run"] == {"length": 4, "tokens": [220, 16, 15, 4242]}


def test_singleton_steps_a_run_without_a_draft_one_token_at_a_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _RecordingRuntime()
    captured: dict[str, Any] = {}
    swarm = _prepared_swarm(monkeypatch, captured)
    record = _record(
        runtime,
        run={
            "bound": 3,
            "operation_ids": ("op-0", "op-1", "op-2"),
            "draws": (0.0, 0.0, 0.0),
        },
    )

    serviced = swarm._service_native_singleton(
        record, {"registration": "one"}, None, incompatible=(), fallback_reason="", cleanup=False
    )

    assert [call[0] for call in runtime.calls] == ["step", "step", "step"]
    assert [call[2]["native_operation_id"] for call in runtime.calls] == [
        "op-0",
        "op-1",
        "op-2",
    ]
    assert captured["result"] is not None
    assert [step["token"] for step in captured["result"]["steps"]] == [701, 702, 703]
    assert serviced["native_group"]["cohort"][0]["token"] == 703


def test_singleton_commits_one_token_when_a_graph_site_defers_the_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _RecordingRuntime()
    captured: dict[str, Any] = {}
    swarm = _prepared_swarm(monkeypatch, captured)
    record = _record(
        runtime,
        run={
            "bound": 4,
            "operation_ids": ("op-0", "op-1", "op-2", "op-3"),
            "draws": (0.0, 0.25, 0.5, 0.75),
            "draft_tokens": (220, 16, 15),
        },
    )
    record["native_graph_site_deferred"] = True

    swarm._service_native_singleton(
        record, {"registration": "one"}, None, incompatible=(), fallback_reason="", cleanup=False
    )

    assert [call[0] for call in runtime.calls] == ["step"]
    assert captured["result"] is not None
    assert "steps" not in captured["result"]
    assert captured["result"]["token"] == 701
