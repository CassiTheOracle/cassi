#!/usr/bin/env python3
"""Publish one canonical native Qi state to the CassiCosmos read-only mirror.

The native field remains authoritative. This tool validates the exact raw-F32
boundary, publishes a hash-bound monotonic snapshot over loopback TCP, and
independently checks the engine's top-mode projection before writing a receipt.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import socket
import struct
import sys
from pathlib import Path
from typing import Any

SCHEMA = "cassi.qi.native-state.v1"
CONTRACT_SCHEMA = "cassi.qi.native-contract.v1"
CANONICAL_CONTRACT_SHA256 = "fd34a9ac52df28e3c292080053ecde18d742cf6049e840209add2d82f433d320"
CANONICAL_CONTRACT_FILE_SHA256 = "90ae65d322a0fc697a63a2949546e141f195f954b9221e617cce4222960fb32f"
MODE_COUNT = 6144
WAVE_MODE_COUNT = 3072
SCALE_COUNT = 4
PLANE_COUNT = 9
STATE_FLOATS = SCALE_COUNT * MODE_COUNT * PLANE_COUNT
STATE_BYTES = STATE_FLOATS * 4


class BridgeClient:
    def __init__(self, host: str, port: int, timeout: float) -> None:
        self._socket = socket.create_connection((host, port), timeout=timeout)
        self._socket.settimeout(timeout)
        self._reader = self._socket.makefile("rb")

    def request(self, payload: dict[str, Any]) -> dict[str, Any]:
        wire = json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\n"
        self._socket.sendall(wire)
        response = self._reader.readline()
        if not response:
            raise ConnectionError("mind engine closed the connection")
        decoded = json.loads(response)
        if not isinstance(decoded, dict):
            raise RuntimeError("mind engine returned a non-object response")
        return decoded

    def close(self) -> None:
        self._reader.close()
        self._socket.close()

    def __enter__(self) -> BridgeClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_contract(path: Path) -> tuple[dict[str, Any], str, str]:
    raw = path.read_bytes()
    contract_file_hash = sha256(raw)
    if contract_file_hash != CANONICAL_CONTRACT_FILE_SHA256:
        raise ValueError("contract file is not the pinned canonical artifact")
    contract = json.loads(raw)
    if not isinstance(contract, dict) or contract.get("schema") != CONTRACT_SCHEMA:
        raise ValueError(f"unsupported contract schema in {path}")
    declared_hash = contract.get("contract_sha256")
    if not isinstance(declared_hash, str) or len(declared_hash) != 64:
        raise ValueError("contract_sha256 must be a 64-character hex digest")
    declared_hash = declared_hash.lower()
    if declared_hash != CANONICAL_CONTRACT_SHA256:
        raise ValueError("contract_sha256 is not the pinned canonical contract")
    layout = contract.get("layout", {})
    if layout.get("state_shape_native") != [1, SCALE_COUNT, MODE_COUNT, PLANE_COUNT]:
        raise ValueError("contract native state shape is not [1,4,6144,9]")
    if layout.get("state_mode_count") != MODE_COUNT:
        raise ValueError("contract state mode count is not 6144")
    return contract, declared_hash, contract_file_hash


def load_state(path: Path) -> bytes:
    state = path.read_bytes()
    if len(state) != STATE_BYTES:
        raise ValueError(
            f"state must be exactly {STATE_BYTES} bytes ({STATE_FLOATS} raw F32 values), "
            f"got {len(state)}"
        )
    for (value,) in struct.iter_unpack("<f", state):
        if not math.isfinite(value):
            raise ValueError("state contains a non-finite F32 value")
    return state


def project_state(state: bytes, k: int) -> list[dict[str, float | int]]:
    modes: list[dict[str, float | int]] = []
    for mode in range(WAVE_MODE_COUNT):
        offset = mode * PLANE_COUNT * 4  # scale zero, [mode, plane]
        p0, p1 = struct.unpack_from("<ff", state, offset)
        modes.append({"mode": mode, "p0": p0, "p1": p1, "q": p0 * p0 + p1 * p1})
    modes.sort(key=lambda item: (-float(item["q"]), int(item["mode"])))
    return modes[:k]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def validate_metadata(reply: dict[str, Any], revision: int, state_hash: str,
                      contract_hash: str, command: str) -> None:
    require(reply.get("ok") is True, f"{command} failed: {reply}")
    require(reply.get("cmd") == command, f"{command} returned wrong cmd")
    require(reply.get("schema") == SCHEMA, f"{command} returned wrong schema")
    require(reply.get("available") is True, f"{command} did not retain a state")
    require(reply.get("revision") == revision, f"{command} returned wrong revision")
    require(reply.get("state_sha256") == state_hash, f"{command} returned wrong state hash")
    require(reply.get("contract_sha256") == contract_hash,
            f"{command} returned wrong contract hash")
    require(reply.get("state_bytes") == STATE_BYTES, f"{command} returned wrong byte count")
    require(reply.get("mode_count") == MODE_COUNT, f"{command} returned wrong mode count")
    require(reply.get("wave_mode_count") == WAVE_MODE_COUNT,
            f"{command} returned wrong wave-mode count")
    require(reply.get("scale_count") == SCALE_COUNT, f"{command} returned wrong scale count")
    require(reply.get("plane_count") == PLANE_COUNT, f"{command} returned wrong plane count")


def validate_projection(actual: dict[str, Any], expected: list[dict[str, float | int]],
                        revision: int, state_hash: str, contract_hash: str) -> None:
    validate_metadata(actual, revision, state_hash, contract_hash, "qi_project")
    modes = actual.get("modes")
    require(isinstance(modes, list) and len(modes) == len(expected),
            "qi_project returned the wrong number of modes")
    for position, (got, want) in enumerate(zip(modes, expected, strict=True)):
        require(isinstance(got, dict), f"qi_project mode {position} is not an object")
        require(got.get("mode") == want["mode"],
                f"qi_project mode mismatch at position {position}")
        for key in ("p0", "p1", "q"):
            got_value = float(got.get(key, math.nan))
            want_value = float(want[key])
            tolerance = 1.0e-6 * max(1.0, abs(want_value))
            require(math.isfinite(got_value) and abs(got_value - want_value) <= tolerance,
                    f"qi_project {key} mismatch at position {position}: "
                    f"{got_value} != {want_value}")


def write_receipt(path: Path, receipt: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True,
                        help="raw canonical [1,4,6144,9] little-endian F32 state")
    parser.add_argument("--contract", type=Path, required=True,
                        help="cassi.qi.native-contract.v1 JSON")
    parser.add_argument("--revision", type=int, required=True)
    parser.add_argument("--project-k", type=int, default=8)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7599)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--receipt", type=Path,
                        default=Path(__file__).resolve().parents[1]
                        / "_diag" / "qi_state_bridge_receipt.json")
    return parser.parse_args()


def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.revision < 0:
        raise ValueError("revision must be non-negative")
    if not 1 <= args.project_k <= WAVE_MODE_COUNT:
        raise ValueError(f"project-k must be in [1,{WAVE_MODE_COUNT}]")

    state_path = args.state.resolve()
    contract_path = args.contract.resolve()
    state = load_state(state_path)
    _, contract_hash, contract_file_hash = load_contract(contract_path)
    state_hash = sha256(state)
    expected_projection = project_state(state, args.project_k)
    request = {
        "cmd": "qi_snapshot",
        "schema": SCHEMA,
        "revision": args.revision,
        "state_sha256": state_hash,
        "contract_sha256": contract_hash,
        "state_f32_base64": base64.b64encode(state).decode("ascii"),
    }

    with BridgeClient(args.host, args.port, args.timeout) as client:
        snapshot = client.request(request)
        validate_metadata(snapshot, args.revision, state_hash, contract_hash, "qi_snapshot")
        duplicate = client.request(request)
        validate_metadata(duplicate, args.revision, state_hash, contract_hash, "qi_snapshot")
        require(duplicate.get("idempotent") is True,
                "duplicate Qi snapshot was not acknowledged as idempotent")
        state_reply = client.request({"cmd": "qi_state"})
        validate_metadata(state_reply, args.revision, state_hash, contract_hash, "qi_state")
        projection = client.request({"cmd": "qi_project", "k": args.project_k})
        validate_projection(projection, expected_projection, args.revision,
                            state_hash, contract_hash)

    return {
        "schema": "cassi.qi.cosmos-bridge-receipt.v1",
        "verdict": "PASS",
        "authority": "native_canonical_qi_state",
        "mirror": "cassi_cosmos_read_only",
        "host": args.host,
        "port": args.port,
        "revision": args.revision,
        "state_path": str(state_path),
        "state_bytes": len(state),
        "state_sha256": state_hash,
        "contract_path": str(contract_path),
        "contract_sha256": contract_hash,
        "contract_file_sha256": contract_file_hash,
        "project_k": args.project_k,
        "expected_projection": expected_projection,
        "actual_projection": projection["modes"],
        "snapshot_idempotent_on_first_write": bool(snapshot.get("idempotent", False)),
        "duplicate_idempotent": True,
        "model_or_sampler_state_written_by_cosmos": False,
    }


def main() -> int:
    args = parse_args()
    try:
        receipt = run(args)
    except Exception as error:  # receipt is required even on a failed handoff
        receipt = {
            "schema": "cassi.qi.cosmos-bridge-receipt.v1",
            "verdict": "FAIL",
            "error": f"{type(error).__name__}: {error}",
        }
    write_receipt(args.receipt.resolve(), receipt)
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0 if receipt["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
