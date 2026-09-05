"""Focused observable contracts for the standalone Cassi Qi v2 daemon."""

from __future__ import annotations

import hashlib
import json
import socket
import tempfile
import threading
from pathlib import Path
import sys

_CASSI_FI_ROOT = Path(__file__).resolve().parents[1]
for _path in (_CASSI_FI_ROOT, _CASSI_FI_ROOT / "training", _CASSI_FI_ROOT / "verification"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
from typing import Any, Mapping

import torch

from cassi_field_daemon import (
    CassiFieldDaemon,
    CassiFieldTCPServer,
    FIELD_DAEMON_HOST,
    FIELD_DAEMON_PROFILE,
    FIELD_DAEMON_PROTOCOL,
)


_METRIC_NAMES = {
    "q",
    "q_max",
    "chi",
    "cross_scale_coherence",
    "read_gate",
    "write_gate",
    "consolidation_gate",
    "j_temporal",
    "j_scale",
    "rho",
}
_FORBIDDEN_KEYS = {"field", "field_b64", "wave", "residual", "teacher", "logits", "kv"}


def _daemon() -> CassiFieldDaemon:
    return CassiFieldDaemon(max_batch_size=8)


def _wave(batch_size: int) -> list[list[list[float]]]:
    return [[[0.25, -0.125] for _ in range(256)] for _ in range(batch_size)]


def _assert_response(response: Mapping[str, Any]) -> None:
    assert response["protocol"] == FIELD_DAEMON_PROTOCOL
    assert response["profile"] == FIELD_DAEMON_PROFILE
    assert isinstance(response["ok"], bool)
    assert response["finite"] is True
    # The response must be safe to put on the JSON-lines transport.
    json.dumps(response, allow_nan=False, separators=(",", ":"))
    for key in response:
        assert key not in _FORBIDDEN_KEYS
    for key in ("config_fingerprint", "codebook_fingerprint"):
        if key in response:
            assert isinstance(response[key], str) and len(response[key]) == 64


def _assert_metrics(response: Mapping[str, Any], batch_size: int) -> None:
    metrics = response["metrics"]
    assert _METRIC_NAMES.issubset(metrics)
    assert len(metrics["available"]) == batch_size
    for name in _METRIC_NAMES:
        values = metrics[name]
        assert isinstance(values, list)
        assert len(values) == batch_size
        assert all(torch.isfinite(torch.tensor(value, dtype=torch.float32)).item() for value in values)


def _state(daemon: CassiFieldDaemon, session: str = "default") -> torch.Tensor:
    return daemon._sessions[session].field.detach().clone()


def test_ping_profile_and_default_identity() -> None:
    daemon = _daemon()
    response = daemon.handle({"cmd": "ping"})
    _assert_response(response)
    assert response["scale_count"] == 4
    assert response["mode_count"] == 512
    assert response["wave_mode_count"] == 256
    assert response["alphabet_size"] == 260
    assert daemon.handle({"cmd": "ping", "unexpected": 1})["ok"] is False


def test_zero_state_is_unavailable_with_zero_read_gate() -> None:
    daemon = _daemon()
    initialized = daemon.handle({"cmd": "init", "session": "zero", "batch_size": 2})
    _assert_response(initialized)
    assert initialized["state_shape"] == [4, 9 * 512, 2]
    emitted = daemon.handle({"cmd": "emit", "session": "zero"})
    _assert_response(emitted)
    _assert_metrics(emitted, 2)
    assert emitted["scores"] == [[0.0] * 260, [0.0] * 260]
    assert emitted["available"] == [False, False]
    assert emitted["symbols"] == [-1, -1]
    assert emitted["metrics"]["read_gate"] == [0.0, 0.0]


def test_trusted_sense_evolve_consolidate_emit_and_low_trust_rejection() -> None:
    daemon = _daemon()
    daemon.handle({"cmd": "clear", "session": "trusted", "batch_size": 2})
    daemon.handle({"cmd": "clear", "session": "low", "batch_size": 1})
    trusted = daemon.handle(
        {
            "cmd": "sense_wave",
            "session": "trusted",
            "wave": _wave(2),
            "structured_source": [1.0, 1.0],
        }
    )
    _assert_response(trusted)
    _assert_metrics(trusted, 2)
    assert all(value > 0.0 for value in trusted["metrics"]["write_gate"])

    evolved = daemon.handle({"cmd": "evolve", "session": "trusted", "steps": 2})
    _assert_response(evolved)
    _assert_metrics(evolved, 2)
    consolidated = daemon.handle({"cmd": "consolidate", "session": "trusted"})
    _assert_response(consolidated)
    _assert_metrics(consolidated, 2)
    emitted = daemon.handle({"cmd": "emit", "session": "trusted"})
    _assert_response(emitted)
    _assert_metrics(emitted, 2)
    assert len(emitted["scores"]) == 2
    assert all(len(row) == 260 for row in emitted["scores"])

    low_trust = daemon.handle(
        {
            "cmd": "sense",
            "session": "low",
            "wave": _wave(1),
            "source_trust": 0.0,
        }
    )
    _assert_response(low_trust)
    _assert_metrics(low_trust, 1)
    assert low_trust["write_gate"] == [0.0]
    assert low_trust["metrics"]["write_gate"] == [0.0]
    assert torch.count_nonzero(_state(daemon, "low")).item() == 0


def test_strict_wave_shape_and_nonfinite_requests_fail_closed() -> None:
    daemon = _daemon()
    daemon.handle({"cmd": "clear", "session": "strict", "batch_size": 1})
    assert daemon.handle({"cmd": "sense", "session": "strict", "wave": _wave(1)[0]})["ok"] is False
    nonfinite = _wave(1)
    nonfinite[0][0][0] = float("nan")
    response = daemon.handle({"cmd": "sense", "session": "strict", "wave": nonfinite})
    _assert_response(response)
    assert response["ok"] is False
    assert daemon.handle({"cmd": "sense", "session": "strict", "wave": _wave(2)})["ok"] is False
    assert daemon.handle({"cmd": "step", "session": "strict", "steps": 0})["ok"] is False
    assert daemon.handle({"cmd": "state", "session": "../../escape"})["ok"] is False


def test_reset_preserve_false_and_true_have_full_controller_semantics() -> None:
    daemon = _daemon()
    daemon.handle({"cmd": "clear", "session": "reset", "batch_size": 1})
    daemon.handle(
        {
            "cmd": "sense",
            "session": "reset",
            "wave": _wave(1),
            "structured_source": 1.0,
        }
    )
    daemon.handle({"cmd": "step", "session": "reset", "steps": 3})
    daemon.handle({"cmd": "consolidate", "session": "reset"})
    before = _state(daemon, "reset")
    assert torch.count_nonzero(before).item() > 0

    cleared = daemon.handle({"cmd": "reset", "session": "reset", "preserve_memory": False})
    _assert_response(cleared)
    _assert_metrics(cleared, 1)
    assert torch.count_nonzero(_state(daemon, "reset")).item() == 0

    daemon.handle(
        {
            "cmd": "sense",
            "session": "reset",
            "wave": _wave(1),
            "structured_source": 1.0,
        }
    )
    daemon.handle({"cmd": "step", "session": "reset", "steps": 3})
    daemon.handle({"cmd": "consolidate", "session": "reset"})
    before_preserve = _state(daemon, "reset")
    preserved = daemon.handle({"cmd": "reset", "session": "reset", "preserve_memory": True})
    _assert_response(preserved)
    _assert_metrics(preserved, 1)
    after_preserve = _state(daemon, "reset")
    assert torch.count_nonzero(after_preserve[0]).item() == 0
    assert torch.count_nonzero(after_preserve[1:]).item() > 0
    # Slow positional condensates survive while transient velocities are reset.
    assert torch.allclose(after_preserve[1:, : 4 * 512, :], before_preserve[1:, : 4 * 512, :])


def test_exact_save_load_identity_and_v1_rejection() -> None:
    daemon = _daemon()
    daemon.handle({"cmd": "clear", "session": "checkpoint", "batch_size": 1})
    daemon.handle(
        {
            "cmd": "sense",
            "session": "checkpoint",
            "wave": _wave(1),
            "structured_source": 1.0,
        }
    )
    daemon.handle({"cmd": "step", "session": "checkpoint", "steps": 2})
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        path = root / "qi-state.pt"
        saved = daemon.handle({"cmd": "save", "session": "checkpoint", "path": str(path)})
        _assert_response(saved)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert saved["sha256"] == digest
        expected = _state(daemon, "checkpoint")
        daemon.handle({"cmd": "clear", "session": "checkpoint", "batch_size": 1})
        loaded = daemon.handle({"cmd": "load", "session": "checkpoint", "path": str(path)})
        _assert_response(loaded)
        _assert_metrics(loaded, 1)
        assert loaded["sha256"] == digest
        assert torch.equal(_state(daemon, "checkpoint"), expected)

        old = root / "old-v1.pt"
        torch.save({"schema": "cassi.field-intelligence.state.v1", "field": torch.zeros(1)}, old)
        rejected_old = daemon.handle({"cmd": "load", "session": "checkpoint", "path": str(old)})
        _assert_response(rejected_old)
        assert rejected_old["ok"] is False

        wrong = root / "wrong.pt"
        torch.save({"schema": "cassi.qi.field.state.v2", "config": {}}, wrong)
        rejected_wrong = daemon.handle({"cmd": "load", "session": "checkpoint", "path": str(wrong)})
        _assert_response(rejected_wrong)
        assert rejected_wrong["ok"] is False


def test_bounded_finite_long_sequence_and_forbidden_payloads() -> None:
    daemon = _daemon()
    daemon.handle({"cmd": "init", "session": "long", "batch_size": 2})
    for _ in range(8):
        for command in (
            {
                "cmd": "sense",
                "session": "long",
                "wave": _wave(2),
                "structured_source": [1.0, 1.0],
            },
            {"cmd": "step", "session": "long", "steps": 4},
            {"cmd": "consolidate", "session": "long"},
            {"cmd": "emit", "session": "long"},
        ):
            response = daemon.handle(command)
            _assert_response(response)
            if "metrics" in response:
                _assert_metrics(response, 2)
            assert all(key not in response for key in _FORBIDDEN_KEYS)


def test_loopback_tcp_round_trip_and_shutdown() -> None:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind((FIELD_DAEMON_HOST, 0))
    port = int(probe.getsockname()[1])
    probe.close()
    daemon = CassiFieldDaemon(port=port)
    server = CassiFieldTCPServer(daemon)
    thread = threading.Thread(target=server.serve_forever_bounded, daemon=True)
    thread.start()
    try:
        with socket.create_connection((FIELD_DAEMON_HOST, port), timeout=2.0) as connection:
            reader = connection.makefile("rb")
            try:
                connection.sendall(b'{"cmd":"ping"}\n')
                ping = json.loads(reader.readline())
                _assert_response(ping)
                assert ping["profile"] == FIELD_DAEMON_PROFILE
                connection.sendall(b'{"cmd":"clear","session":"tcp","batch_size":1}\n')
                cleared = json.loads(reader.readline())
                _assert_response(cleared)
                connection.sendall(b'{"cmd":"emit","session":"tcp"}\n')
                emitted = json.loads(reader.readline())
                _assert_response(emitted)
                assert emitted["available"] == [False]
                connection.sendall(b'{"cmd":"shutdown"}\n')
                shutdown = json.loads(reader.readline())
                _assert_response(shutdown)
                assert shutdown["ok"] is True
            finally:
                reader.close()
    finally:
        thread.join(timeout=3.0)
        server.server_close()
    assert not thread.is_alive()


if __name__ == "__main__":
    test_ping_profile_and_default_identity()
    test_loopback_tcp_round_trip_and_shutdown()
    test_zero_state_is_unavailable_with_zero_read_gate()
    test_trusted_sense_evolve_consolidate_emit_and_low_trust_rejection()
    test_strict_wave_shape_and_nonfinite_requests_fail_closed()
    test_reset_preserve_false_and_true_have_full_controller_semantics()
    test_exact_save_load_identity_and_v1_rejection()
    test_bounded_finite_long_sequence_and_forbidden_payloads()
    print("Cassi Qi field daemon v2 tests passed")
