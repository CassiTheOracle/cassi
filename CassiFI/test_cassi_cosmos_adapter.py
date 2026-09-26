from __future__ import annotations

import json
import socket
import threading
from pathlib import Path
from typing import Any

import pytest

from cassi_cosmos_adapter import (
    CassiCosmos7599Adapter,
    CassiCosmosSeedController,
    CassiCosmosWorldFactoryController,
    authorize_cassicosmos_seed,
)
from cassi_field_cognition import semantic_cognition_state
from cassi_field_atlas import FieldIntelligenceError
from cassi_field_owner import (
    FieldIntelligenceOwner,
    FieldIntelligenceSurface,
    RPC_SCHEMA,
)


def _serve_once(raw_response: bytes, received: list[bytes]) -> tuple[int, threading.Thread]:
    ready = threading.Event()
    port_box: list[int] = []

    def run() -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            port_box.append(server.getsockname()[1])
            ready.set()
            connection, _ = server.accept()
            with connection:
                buffer = bytearray()
                while b"\n" not in buffer:
                    chunk = connection.recv(4096)
                    if not chunk:
                        return
                    buffer.extend(chunk)
                received.append(bytes(buffer).split(b"\n", 1)[0])
                if raw_response:
                    connection.sendall(raw_response + b"\n")

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    assert ready.wait(5.0)
    assert port_box
    return port_box[0], thread


def _serve_sequence(
    raw_responses: list[bytes],
    received: list[bytes],
) -> tuple[int, threading.Thread]:
    ready = threading.Event()
    port_box: list[int] = []

    def run() -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("127.0.0.1", 0))
            server.listen(len(raw_responses))
            port_box.append(server.getsockname()[1])
            ready.set()
            for raw_response in raw_responses:
                connection, _ = server.accept()
                with connection:
                    buffer = bytearray()
                    while b"\n" not in buffer:
                        chunk = connection.recv(4096)
                        if not chunk:
                            return
                        buffer.extend(chunk)
                    received.append(bytes(buffer).split(b"\n", 1)[0])
                    connection.sendall(raw_response + b"\n")

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    assert ready.wait(5.0)
    assert port_box
    return port_box[0], thread


def _owner_call(owner: FieldIntelligenceOwner, operation_id: str, action: str, **arguments: Any):
    return FieldIntelligenceSurface(owner).handle(
        {
            "schema": RPC_SCHEMA,
            "request_id": operation_id,
            "operation": "computer",
            "params": {
                "operation_id": operation_id,
                "computer_id": "main",
                "action": action,
                "arguments": arguments,
            },
        }
    )["result"]


def _state_request() -> dict[str, Any]:
    return {
        "cmd": "state",
        "fields": ["mean_ey", "max_eps2"],
    }


def _project_response(
    *,
    step: int,
    t: float,
    cell: dict[str, Any],
    scale: float,
    include_phase_winding: bool = False,
) -> bytes:
    bins = [
        {
            "bin": index,
            "x_min": -1.0 + index / 8.0,
            "x_max": -1.0 + (index + 1) / 8.0,
            "x": -0.9375 + index / 8.0,
            "cell_count": 16_384,
            "q_sum": scale * (index + 1),
            "current_x_sum": scale * (index - 7.5),
            "current_x_abs_sum": scale * (index + 0.5),
        }
        for index in range(16)
    ]
    response: dict[str, Any] = {
        "ok": True,
        "cmd": "project",
        "step": step,
        "t": t,
        "cells": [cell],
        "phase_profile": {
            "axis": "x",
            "bin_count": 16,
            "bins": bins,
        },
        "phase_topology_bins": 4,
        "phase_topology": [
            {
                "bin": index,
                "bx": index // 16,
                "by": (index // 4) % 4,
                "bz": index % 4,
                "q": scale * (index + 1),
                "jx": scale * (index - 31.5),
                "jy": scale * (31.5 - index),
                "jz": scale * ((index % 4) - 1.5),
            }
            for index in range(64)
        ],
    }
    if include_phase_winding:
        response["phase_winding"] = {
            "schema": "cassi.phase-winding-native.v1",
            "grid_n": 64,
            "center": {"gx": 32, "gy": 32, "gz": 32},
            "radii_cells": [2, 4, 8],
            "planes": ["xy", "xz", "yz"],
            "rows": [
                {
                    "plane": plane,
                    "radius_cells": radius,
                    "winding_number": scale * (1.0 if plane == "xy" else 0.25),
                    "phase_circulation": scale * 2.0,
                    "current_circulation": scale * 3.0,
                    "q_min": scale * 0.5,
                }
                for plane in ("xy", "xz", "yz")
                for radius in (2, 4, 8)
            ],
        }
    return json.dumps(
        response,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def test_scheduled_world_native_phase_winding_is_explicit_opt_in(
    tmp_path: Path,
):
    received: list[bytes] = []
    port, server = _serve_sequence(
        [
            b'{"ok":true,"cmd":"clear"}',
            b'{"ok":true,"cmd":"step","step":4,"t":0.02}',
            b'{"ok":true,"cmd":"state","step":4,"t":0.02,"mean_ey":0.1,"mean_ei":0.2,"max_eps2":0.3}',
            _project_response(
                step=4,
                t=0.02,
                cell={
                    "i": 7,
                    "gx": 32,
                    "gy": 32,
                    "gz": 32,
                    "x": 0.0,
                    "y": 0.0,
                    "z": 0.0,
                    "ey": 0.4,
                    "ei": 0.2,
                    "q": 0.2,
                    "phase_current_x": 0.01,
                },
                scale=0.25,
                include_phase_winding=True,
            ),
        ],
        received,
    )
    controller = CassiCosmosWorldFactoryController(
        authorization=authorize_cassicosmos_seed("scheduled-native-winding"),
        port=port,
        timeout=2.0,
    )
    controller.bind_durable_journal(tmp_path / "native-winding-journal")

    result = controller.execute_scheduled_world(
        operation_id="reality:native-winding:one",
        segments=[{"deposits": [], "steps": 4}],
        phase_winding_probe=1,
    )
    server.join(5.0)

    assert result.status == "succeeded"
    assert result.context["phase_winding_probe"] == 1
    assert result.observed_values["h4_phase_winding_xy_r02"] == 0.25
    assert result.observed_values["h4_phase_winding_circ_xy_r02"] == 0.5
    assert result.observed_values["h4_phase_winding_current_xy_r02"] == 0.75
    assert result.observed_values["h4_phase_winding_qmin_xy_r02"] == 0.125
    project_request = json.loads(received[-1])
    assert project_request["phase_bins"] == 0
    assert project_request["topology_bins"] == 0
    assert project_request["winding_probe"] == 1


def test_cassicosmos_project_exposes_bounded_distributed_phase_flow(
    tmp_path: Path,
):
    raw_response = _project_response(
        step=17,
        t=0.085,
        cell={
            "i": 7,
            "gx": 1,
            "gy": 2,
            "gz": 3,
            "x": -0.5,
            "y": 0.0,
            "z": 0.5,
            "ey": 0.4,
            "ei": 0.2,
            "q": 0.2,
            "phase_current_x": 0.01,
        },
        scale=0.25,
    )
    received: list[bytes] = []
    port, server = _serve_once(raw_response, received)
    adapter = CassiCosmos7599Adapter(port=port, timeout=2.0)
    adapter.bind_durable_journal(tmp_path / "phase-profile-journal")
    request = {
        "cmd": "project",
        "fields": [
            "top_q",
            "phase_q_x00",
            "phase_jx_x08",
            "phase_abs_jx_x15",
        ],
        "k": 4,
        "phase_bins": 16,
    }

    result = adapter.execute_once(
        operation_id="cosmos-project:distributed-phase",
        action="observe",
        target="cosmos:project",
        payload={"request": request},
    )
    server.join(5.0)

    assert result.status == "succeeded"
    assert result.observed_values == {
        "top_q": 0.2,
        "phase_q_x00": 0.25,
        "phase_jx_x08": 0.125,
        "phase_abs_jx_x15": 3.875,
    }
    assert json.loads(received[0]) == request


def test_cassicosmos_state_observation_is_read_only_and_replayable(tmp_path: Path):
    raw_response = b'{"ok":true,"cmd":"state","step":17,"t":0.085,"mean_ey":1.25,"mean_ei":-0.5,"max_eps2":0.75}'
    received: list[bytes] = []
    port, server = _serve_once(raw_response, received)
    adapter = CassiCosmos7599Adapter(port=port, timeout=2.0)
    adapter.bind_durable_journal(tmp_path / "journal")

    first = adapter.execute_once(
        operation_id="cosmos-state:adapter",
        action="observe",
        target="cosmos:state",
        payload={"request": _state_request()},
    )
    server.join(5.0)

    assert first.status == "succeeded"
    assert first.operation_id == "cosmos-state:adapter"
    assert first.observed_values == {"mean_ey": 1.25, "max_eps2": 0.75}
    assert first.source_content == raw_response
    assert json.loads(received[0].decode("utf-8")) == _state_request()
    assert adapter.execute_count == 1

    replay = adapter.execute_once(
        operation_id="cosmos-state:adapter",
        action="observe",
        target="cosmos:state",
        payload={"request": _state_request()},
    )
    assert replay == first
    assert adapter.execute_count == 1

    with pytest.raises(FieldIntelligenceError):
        adapter.execute_once(
            operation_id="cosmos-deposit:adapter",
            action="observe",
            target="cosmos:state",
            payload={
                "request": {
                    "cmd": "deposit",
                    "fields": ["mean_ey"],
                }
            },
        )


def test_owner_authorized_seed_path_is_separate_and_replayable(tmp_path: Path):
    raw_responses = [
        b'{"ok":true,"cmd":"deposit"}',
        b'{"ok":true,"cmd":"step","step":8,"t":0.04}',
    ]
    received: list[bytes] = []
    port, server = _serve_sequence(raw_responses, received)
    controller = CassiCosmosSeedController(
        authorization=authorize_cassicosmos_seed("physics-watch"),
        port=port,
        timeout=2.0,
    )
    controller.bind_durable_journal(tmp_path / "seed-journal")
    deposits = [
        {
            "x": 0.2,
            "y": -0.1,
            "z": 0.3,
            "cy": 1.0,
            "ci": 0.4,
            "sigma": 0.5,
        }
    ]

    first = controller.seed_and_advance(
        operation_id="physics-watch:seed",
        deposits=deposits,
        steps=8,
    )
    server.join(5.0)

    assert first.status == "succeeded"
    assert first.observed_values == {
        "step": 8.0,
        "t": 0.04,
        "deposit_count": 1.0,
        "advanced_steps": 8.0,
    }
    assert [json.loads(raw)["cmd"] for raw in received] == [
        "deposit",
        "step",
    ]
    assert controller.execute_count == 1

    replay = controller.seed_and_advance(
        operation_id="physics-watch:seed",
        deposits=deposits,
        steps=8,
    )
    assert replay == first
    assert controller.execute_count == 1

    with pytest.raises(FieldIntelligenceError):
        CassiCosmosSeedController(
            authorization="physics-watch",  # type: ignore[arg-type]
            port=port,
        )


def test_authorized_world_factory_clears_steps_observes_and_replays(
    tmp_path: Path,
):
    raw_responses = [
        b'{"ok":true,"cmd":"clear"}',
        b'{"ok":true,"cmd":"deposit","pending":1}',
        b'{"ok":true,"cmd":"step","step":1,"t":0.005}',
        b'{"ok":true,"cmd":"state","step":1,"t":0.005,"mean_ey":0.1,"mean_ei":0.2,"max_eps2":0.3}',
        _project_response(
            step=1,
            t=0.005,
            cell={"i": 7, "gx": 1, "gy": 2, "gz": 3, "x": -0.5, "y": 0.0, "z": 0.5, "ey": 0.4, "ei": 0.2, "q": 0.2, "phase_current_x": 0.01},
            scale=0.1,
        ),
        b'{"ok":true,"cmd":"step","step":4,"t":0.02}',
        b'{"ok":true,"cmd":"state","step":4,"t":0.02,"mean_ey":0.11,"mean_ei":0.19,"max_eps2":0.31}',
        _project_response(
            step=4,
            t=0.02,
            cell={"i": 8, "gx": 2, "gy": 3, "gz": 4, "x": -0.25, "y": 0.25, "z": 0.75, "ey": 0.5, "ei": 0.1, "q": 0.26, "phase_current_x": -0.02},
            scale=0.2,
        ),
    ]
    received: list[bytes] = []
    port, server = _serve_sequence(raw_responses, received)
    controller = CassiCosmosWorldFactoryController(
        authorization=authorize_cassicosmos_seed("reality-residency"),
        port=port,
        timeout=2.0,
    )
    controller.bind_durable_journal(tmp_path / "world-journal")
    deposits = [
        {
            "x": -0.5,
            "y": 0.0,
            "z": 0.5,
            "cy": 1.0,
            "ci": 0.4,
            "sigma": 1.0,
        }
    ]

    first = controller.execute_world(
        operation_id="reality:world:one",
        deposits=deposits,
        horizons=[1, 4],
        projection_k=4,
        phase_profile_bins=16,
    )
    server.join(5.0)

    assert first.status == "succeeded"
    assert first.observed_values["h1_step"] == 1.0
    assert first.observed_values["h1_top_x"] == -0.5
    assert first.observed_values["h1_top_phase_current_x"] == 0.01
    assert first.observed_values["h1_phase_q_x00"] == 0.1
    assert first.observed_values["h4_phase_abs_jx_x15"] == 3.1
    assert first.observed_values["h4_step"] == 4.0
    assert first.observed_values["h4_top_q"] == 0.26
    assert [json.loads(raw)["cmd"] for raw in received] == [
        "clear",
        "deposit",
        "step",
        "state",
        "project",
        "step",
        "state",
        "project",
    ]
    assert json.loads(received[5])["n"] == 3
    assert controller.execute_count == 1

    replay = controller.execute_world(
        operation_id="reality:world:one",
        deposits=deposits,
        horizons=[1, 4],
        projection_k=4,
        phase_profile_bins=16,
    )
    assert replay == first
    assert controller.execute_count == 1


def test_world_factory_schedules_delayed_deposits_and_replays(
    tmp_path: Path,
):
    raw_responses = [
        b'{"ok":true,"cmd":"clear"}',
        b'{"ok":true,"cmd":"deposit","pending":1}',
        b'{"ok":true,"cmd":"step","step":4,"t":0.02}',
        b'{"ok":true,"cmd":"state","step":4,"t":0.02,"mean_ey":0.1,"mean_ei":0.2,"max_eps2":0.3}',
        _project_response(
            step=4,
            t=0.02,
            cell={"i": 7, "gx": 1, "gy": 2, "gz": 3, "x": -0.5, "y": 0.0, "z": 0.5, "ey": 0.4, "ei": 0.2, "q": 0.2, "phase_current_x": 0.01},
            scale=0.3,
        ),
        b'{"ok":true,"cmd":"deposit","pending":1}',
        b'{"ok":true,"cmd":"step","step":12,"t":0.06}',
        b'{"ok":true,"cmd":"state","step":12,"t":0.06,"mean_ey":0.3,"mean_ei":0.1,"max_eps2":0.5}',
        _project_response(
            step=12,
            t=0.06,
            cell={"i": 9, "gx": 4, "gy": 5, "gz": 6, "x": 0.5, "y": 0.25, "z": -0.5, "ey": 0.6, "ei": 0.3, "q": 0.45, "phase_current_x": -0.03},
            scale=0.4,
        ),
    ]
    received: list[bytes] = []
    port, server = _serve_sequence(raw_responses, received)
    controller = CassiCosmosWorldFactoryController(
        authorization=authorize_cassicosmos_seed("scheduled-reality"),
        port=port,
        timeout=2.0,
    )
    controller.bind_durable_journal(tmp_path / "scheduled-world-journal")
    first = controller.execute_scheduled_world(
        operation_id="reality:scheduled:one",
        segments=[
            {
                "deposits": [
                    {
                        "x": -0.5,
                        "y": 0.0,
                        "z": 0.5,
                        "cy": 1.0,
                        "ci": 0.4,
                        "sigma": 1.0,
                    }
                ],
                "steps": 4,
            },
            {
                "deposits": [
                    {
                        "x": 0.5,
                        "y": 0.25,
                        "z": -0.5,
                        "cy": -0.5,
                        "ci": 0.8,
                        "sigma": 1.0,
                    }
                ],
                "steps": 8,
            },
        ],
        projection_k=4,
        phase_profile_bins=16,
    )
    server.join(5.0)

    assert first.status == "succeeded"
    assert first.observed_values["h4_mean_ey"] == 0.1
    assert first.observed_values["h12_top_x"] == 0.5
    assert first.observed_values["h12_top_phase_current_x"] == -0.03
    assert first.observed_values["h4_phase_jx_x08"] == 0.15
    assert first.observed_values["h12_phase_q_x15"] == 6.4
    commands = [json.loads(raw) for raw in received]
    assert [command["cmd"] for command in commands] == [
        "clear",
        "deposit",
        "step",
        "state",
        "project",
        "deposit",
        "step",
        "state",
        "project",
    ]
    assert commands[2]["n"] == 4
    assert commands[4]["phase_bins"] == 16
    assert commands[8]["phase_bins"] == 16
    assert commands[6]["n"] == 8
    assert first.context["horizons"] == [4, 12]
    assert first.context["phase"] == "scheduled-world-observed"
    assert controller.execute_count == 1

    replay = controller.execute_scheduled_world(
        operation_id="reality:scheduled:one",
        segments=[
            {
                "deposits": [
                    {
                        "x": -0.5,
                        "y": 0.0,
                        "z": 0.5,
                        "cy": 1.0,
                        "ci": 0.4,
                        "sigma": 1.0,
                    }
                ],
                "steps": 4,
            },
            {
                "deposits": [
                    {
                        "x": 0.5,
                        "y": 0.25,
                        "z": -0.5,
                        "cy": -0.5,
                        "ci": 0.8,
                        "sigma": 1.0,
                    }
                ],
                "steps": 8,
            },
        ],
        projection_k=4,
        phase_profile_bins=16,
    )
    assert replay == first
    assert controller.execute_count == 1


def test_scheduled_world_distributed_profile_is_explicit_opt_in(
    tmp_path: Path,
):
    received: list[bytes] = []
    port, server = _serve_sequence(
        [
            b'{"ok":true,"cmd":"clear"}',
            b'{"ok":true,"cmd":"step","step":4,"t":0.02}',
            b'{"ok":true,"cmd":"state","step":4,"t":0.02,"mean_ey":0.1,"mean_ei":0.2,"max_eps2":0.3}',
            _project_response(
                step=4,
                t=0.02,
                cell={
                    "i": 7,
                    "gx": 1,
                    "gy": 2,
                    "gz": 3,
                    "x": -0.5,
                    "y": 0.0,
                    "z": 0.5,
                    "ey": 0.4,
                    "ei": 0.2,
                    "q": 0.2,
                    "phase_current_x": 0.01,
                },
                scale=0.3,
            ),
        ],
        received,
    )
    controller = CassiCosmosWorldFactoryController(
        authorization=authorize_cassicosmos_seed("scheduled-bounded-readout"),
        port=port,
        timeout=2.0,
    )
    controller.bind_durable_journal(tmp_path / "bounded-readout-journal")

    result = controller.execute_scheduled_world(
        operation_id="reality:bounded-readout:one",
        segments=[{"deposits": [], "steps": 4}],
    )
    server.join(5.0)

    assert result.status == "succeeded"
    assert result.context["phase_profile_bins"] == 0
    assert not any("phase_q_x" in key for key in result.observed_values)
    assert json.loads(received[-1])["phase_bins"] == 0


def test_scheduled_world_phase_topology_is_explicit_opt_in(tmp_path: Path):
    received: list[bytes] = []
    port, server = _serve_sequence(
        [
            b'{"ok":true,"cmd":"clear"}',
            b'{"ok":true,"cmd":"step","step":4,"t":0.02}',
            b'{"ok":true,"cmd":"state","step":4,"t":0.02,"mean_ey":0.1,"mean_ei":0.2,"max_eps2":0.3}',
            _project_response(
                step=4,
                t=0.02,
                cell={
                    "i": 7,
                    "gx": 1,
                    "gy": 2,
                    "gz": 3,
                    "x": -0.5,
                    "y": 0.0,
                    "z": 0.5,
                    "ey": 0.4,
                    "ei": 0.2,
                    "q": 0.2,
                    "phase_current_x": 0.01,
                },
                scale=0.25,
            ),
        ],
        received,
    )
    controller = CassiCosmosWorldFactoryController(
        authorization=authorize_cassicosmos_seed("scheduled-topology-readout"),
        port=port,
        timeout=2.0,
    )
    controller.bind_durable_journal(tmp_path / "topology-readout-journal")

    result = controller.execute_scheduled_world(
        operation_id="reality:topology-readout:one",
        segments=[{"deposits": [], "steps": 4}],
        phase_topology_bins=4,
    )
    server.join(5.0)

    assert result.status == "succeeded"
    assert result.context["phase_profile_bins"] == 0
    assert result.context["phase_topology_bins"] == 4
    assert result.observed_values["h4_phase_topology_q_b63"] == 16.0
    assert result.observed_values["h4_phase_topology_jx_b00"] == -7.875
    assert not any("phase_q_x" in key for key in result.observed_values)
    project_request = json.loads(received[-1])
    assert project_request["phase_bins"] == 0
    assert project_request["topology_bins"] == 4


def test_scheduled_world_rejects_a_drifting_clock(tmp_path: Path):
    received: list[bytes] = []
    port, server = _serve_sequence(
        [
            b'{"ok":true,"cmd":"clear"}',
            b'{"ok":true,"cmd":"step","step":5,"t":0.025}',
        ],
        received,
    )
    controller = CassiCosmosWorldFactoryController(
        authorization=authorize_cassicosmos_seed("scheduled-exact-horizons"),
        port=port,
        timeout=2.0,
    )
    controller.bind_durable_journal(tmp_path / "scheduled-clock-journal")

    result = controller.execute_scheduled_world(
        operation_id="reality:scheduled-clock:one",
        segments=[{"deposits": [], "steps": 4}],
    )
    server.join(5.0)

    assert result.status == "unknown"
    assert result.context["phase"] == "non-deterministic-world-clock"
    assert result.context["expected_step"] == 4
    assert result.context["observed_step"] == 5
    assert [json.loads(raw)["cmd"] for raw in received] == ["clear", "step"]


def test_world_factory_rejects_an_auto_stepped_clock(tmp_path: Path):
    received: list[bytes] = []
    port, server = _serve_sequence(
        [
            b'{"ok":true,"cmd":"clear"}',
            b'{"ok":true,"cmd":"step","step":2,"t":0.01}',
        ],
        received,
    )
    controller = CassiCosmosWorldFactoryController(
        authorization=authorize_cassicosmos_seed("exact-horizons"),
        port=port,
        timeout=2.0,
    )
    controller.bind_durable_journal(tmp_path / "world-journal")

    result = controller.execute_world(
        operation_id="reality:clock:one",
        deposits=[],
        horizons=[1],
    )
    server.join(5.0)

    assert result.status == "unknown"
    assert result.context["phase"] == "non-deterministic-world-clock"
    assert result.context["expected_step"] == 1
    assert result.context["observed_step"] == 2
    assert [json.loads(raw)["cmd"] for raw in received] == ["clear", "step"]

def test_cassicosmos_transport_unknown_is_terminal_and_replays(tmp_path: Path):
    received: list[bytes] = []
    port, server = _serve_once(b"", received)
    adapter = CassiCosmos7599Adapter(port=port, timeout=2.0)
    adapter.bind_durable_journal(tmp_path / "journal")

    first = adapter.execute_once(
        operation_id="cosmos-unknown:adapter",
        action="observe",
        target="cosmos:state",
        payload={"request": _state_request()},
    )
    server.join(5.0)

    assert first.status == "unknown"
    assert first.observed_values == {}
    assert adapter.execute_count == 1
    replay = adapter.resolve("cosmos-unknown:adapter")
    assert replay == first
    assert len(received) == 1


def test_owner_admits_real_adapter_observation_as_supported_evidence(tmp_path: Path):
    raw_response = b'{"ok":true,"cmd":"state","step":4,"t":0.02,"mean_ey":0.125,"mean_ei":-0.25,"max_eps2":0.5}'
    received: list[bytes] = []
    port, server = _serve_once(raw_response, received)
    adapter = CassiCosmos7599Adapter(
        port=port,
        timeout=2.0,
        adapter_id="cassi-cosmos-test",
    )

    request = _state_request()
    selected = {
        "channel_id": "cosmos:state",
        "goal": {"kind": "live-state"},
        "provides": ["mean_ey", "max_eps2"],
        "request": request,
    }
    with FieldIntelligenceOwner(tmp_path / "owner") as owner:
        _owner_call(owner, "cosmos-owner-configure", "configure")
        _owner_call(
            owner,
            "cosmos-owner-seed",
            "submit",
            kernel="cognition.field",
            state=semantic_cognition_state(),
            arguments={
                "operation": "observe",
                "operation_id": "cosmos-owner-seed",
                "delivery_id": "delivery:cosmos-owner-seed",
                "event_id": "event:cosmos-owner-seed",
                "observations": [
                    {
                        "binding_id": "binding:cosmos-seed",
                        "subject": "cosmos",
                        "attribute": "seed",
                        "value": 0.0,
                    }
                ],
            },
            steps=1,
        )
        _owner_call(
            owner,
            "cosmos-owner-seed-advance",
            "advance",
            steps=16,
        )
        result = owner.execute_observation_request(
            operation_id="cosmos-owner-observe",
            observation_request=selected,
            adapter=adapter,
            expected_state_sha256=owner.state.state_sha256,
        )
        assert result["status"] == "supported"
        assert result["acknowledgment"]["observed_values"] == {
            "mean_ey": 0.125,
            "max_eps2": 0.5,
        }
        assert result["observation"]["status"] == "supported"
        assert result["evidence"]["source"]["status"] == "active"
        assert adapter.execute_count == 1
    server.join(5.0)
    assert json.loads(received[0].decode("utf-8")) == request
