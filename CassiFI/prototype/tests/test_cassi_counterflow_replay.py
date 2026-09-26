from __future__ import annotations

import json
from pathlib import Path

from cassi_counterflow_runtime import DerivedCounterflowRuntime


FIXTURE = Path(__file__).parent / "fixtures" / "counterflow_replay_v2.json"


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def test_durable_counterflow_replays_are_exact_across_restarts() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert fixture["schema"] == "cassi.counterflow.replay.v2"

    for scenario in fixture["scenarios"]:
        assert len(scenario["requests"]) == len(scenario["expected"]), scenario["name"]
        for request, expected in zip(
            scenario["requests"],
            scenario["expected"],
            strict=True,
        ):
            first = DerivedCounterflowRuntime().plan(
                request,
                primary_field_sha256=fixture["primary_field_sha256"],
            )
            restarted = DerivedCounterflowRuntime().plan(
                json.loads(_canonical(request)),
                primary_field_sha256=fixture["primary_field_sha256"],
            )

            assert _canonical(restarted) == _canonical(first), scenario["name"]
            assert first["schema"] == "cassi.counterflow.derived-runtime.v2"
            assert first["schema_version"] == 2
            assert first["status"] == expected["status"]
            assert (first["action_proposal"] is not None) is expected["proposal"]
            abstention = first["abstention"]
            assert (
                None if abstention is None else abstention["code"]
            ) == expected["abstention"]
            assert first["primary_field_sha256"] == fixture["primary_field_sha256"]
            if request["observations"]:
                assert first["inference_memory_frozen"] is True
