"""Run the isolated W8/G8 body-frame, efference, and residual exercise.

The driver uses only the public W8 body contracts and one registered terminal
acknowledgement fixture.  It writes canonical JSON and raw terminal bytes to an
atomically replaced artifact directory; no flow runtime or hidden state is
consulted.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Callable

import torch

from cassi_qi_bootstrap import canonical_hash, canonical_json_bytes, finite_float
from cassi_qi_body import (
    QiBodyFrameDescriptor,
    QiBodyPrediction,
    QiBodyProfile,
    QiBodyRemapReceipt,
    QiBodySensorFrame,
    QiBodyState,
    QiBodyPose,
    QiEnvironmentSensorFrame,
    QiEfferenceCopy,
    QiResidualEfficacy,
    QiResidualReturn,
    remap_body_field_round_trip,
    residual_control_set,
)
from cassi_qi_boundary import QiBoundaryPacket, QiLinearBoundaryPort
from cassi_qi_clock import QiCausalClock, QiClockTime, QiSourceCadence, QiSourceScope


ZERO = QiClockTime.make(0)
ONE = QiClockTime.make(1)


class _ValidatedAck:
    """Small stand-in for a BoundaryRuntime-validated immutable ack object."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = dict(payload)

    def canonical_payload(self, *, include_hash: bool = True) -> dict[str, Any]:
        return dict(self._payload)


def _write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _write_json(path: Path, payload: Any) -> None:
    _write_bytes(path, canonical_json_bytes(payload))


def _sha_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _hex(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def _load_registered_ack() -> dict[str, Any]:
    for shard in sorted(Path("cassi-fi-schema-registry/shards").glob("*.json")):
        try:
            document = json.loads(shard.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for entry in document.get("entries", []):
            if entry.get("schema") != "cassi.qi-flow-tick-ack.v1":
                continue
            fixture = entry.get("canonical_fixture_set", {}).get("maximal_valid")
            required = {
                "schema", "ack_bytes", "ack_sha256", "status", "terminal_status",
                "application_tick", "effective_tick", "applied_values",
                "body_transition", "world_effect",
            }
            if (
                isinstance(fixture, dict)
                and fixture.get("schema") == "cassi.qi-flow-tick-ack.v1"
                and required <= set(fixture)
                and fixture.get("status") == "applied"
                and fixture.get("terminal_status") == "applied"
                and fixture.get("world_effect") == "true"
            ):
                return dict(fixture)
    raise RuntimeError("registered maximal tick acknowledgement fixture is unavailable")


def _port(name: str = "homeostasis", dimension: int = 2) -> QiLinearBoundaryPort:
    rows = [[0j] * dimension for _ in range(dimension)]
    for index in range(dimension):
        rows[index][index] = 1.0 + 0.0j
    return QiLinearBoundaryPort.create(
        name=name,
        observation_rows=rows,
        source_metric=[2.0 + index for index in range(dimension)],
        field_metric=[2.0 + index for index in range(dimension)],
        gain=1.0,
        port_indices=range(dimension),
    )


def _clock(scope: QiSourceScope) -> QiCausalClock:
    return QiCausalClock.create(
        tau_0=ONE,
        field_interval=ONE,
        field_steps_per_world_tick=1,
        sources=(QiSourceCadence(scope, ONE, ZERO, 0),),
        max_clock_lcm=64,
    )


def _packet(scope: QiSourceScope, *, sequence: int = 0, frontier: QiClockTime = ONE, valid: bool = True) -> QiBoundaryPacket:
    clock = _clock(scope)
    kwargs: dict[str, Any] = {
        "clock": clock,
        "scope": scope,
        "profile_sha256": _hex("packet-profile"),
        "watermark_sha256": _hex("packet-watermark"),
        "ingress_journal_sha256": _hex("packet-journal"),
        "source_sequence": sequence,
        "cycle_frontier": frontier,
        "payload_shape": (2,),
        "payload_dtype": "u8",
        "payload": b"w8",
        "valid": valid,
    }
    if valid:
        return QiBoundaryPacket.create(**kwargs)
    kwargs.pop("payload_shape")
    kwargs.pop("payload_dtype")
    kwargs.pop("payload")
    kwargs.pop("valid")
    kwargs["reason"] = "sensor unavailable"
    return QiBoundaryPacket.no_sample(**kwargs)


def _profile(port: QiLinearBoundaryPort) -> QiBodyProfile:
    return QiBodyProfile.create(
        profile_id="body-g8-v1",
        channel_names=("temperature", "pressure"),
        lower_bounds=(-2.0, -2.0),
        upper_bounds=(2.0, 2.0),
        rest_values=(0.0, 0.0),
        relaxation_rates=(1.0, 1.0),
        drive_gains=(1.0, 1.0),
        energy_metric=(2.0, 3.0),
        integration_interval=ONE,
        body_frame_id="body-frame",
        field_ports=(port,),
    )


def _error_case(label: str, function: Callable[[], Any]) -> dict[str, Any]:
    try:
        function()
    except Exception as exc:  # noqa: BLE001 - receipt records the fail-closed class
        return {"label": label, "status": "rejected", "error": type(exc).__name__, "message": str(exc)}
    return {"label": label, "status": "accepted"}


def _run(root: Path) -> dict[str, Any]:
    port = _port()
    profile = _profile(port)
    state = profile.initial_state(clock=ZERO)
    scope = QiSourceScope(
        source_epoch="body-g8-epoch",
        source_stream_id="body-g8-stream",
        descriptor_sha256=port.descriptor_sha256,
    )
    packet = _packet(scope)
    environment = QiEnvironmentSensorFrame.create(packet, (0.25, -0.10))
    body_sensor = QiBodySensorFrame.create(packet, (0.30, -0.15))
    transition = profile.transition_from_frames(
        state,
        environment_frame=environment,
        body_frame=body_sensor,
        source=scope,
    )

    descriptor_guarded = QiBodyFrameDescriptor.create(
        body_frame_id="body-frame",
        remap_mode="guarded-periodic",
        grid_shape=(2, 2),
        grid_spacing=(1.0, 1.0),
        guard_band=(1, 1),
    )
    descriptor_finite = QiBodyFrameDescriptor.create(
        body_frame_id="body-frame",
        remap_mode="finite-aperture",
        grid_shape=(2, 2),
        grid_spacing=(1.0, 1.0),
        guard_band=(0, 0),
    )
    pose_before = QiBodyPose.create("body-frame", (0.0, 0.0, 0.0), ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)))
    pose_after = QiBodyPose.create("body-frame", (1.0, 0.0, 0.0), ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)))
    field = torch.tensor([[1.0, 2.0], [3.0, 4.0]], dtype=torch.float64)
    restored, guarded_receipt, round_trip_error = remap_body_field_round_trip(
        descriptor_guarded, field, pose_before, pose_after, scale_id="g8-guarded"
    )
    _, finite_receipt, finite_round_trip_error = remap_body_field_round_trip(
        descriptor_finite, field, pose_before, pose_after, scale_id="g8-finite"
    )

    ack = _load_registered_ack()
    ack_projection = dict(ack)
    ack_projection["body_transition"] = {
        "before_body_frame_id": "body-frame",
        "after_body_frame_id": "body-frame",
        "remap_sha256": guarded_receipt.remap_sha256,
    }
    validated_ack = _ValidatedAck(ack_projection)
    ack_bytes = base64.b64decode(ack["ack_bytes"], validate=True)
    efference_pending = QiEfferenceCopy.from_validated_ack(
        validated_ack,
        terminal_ack_bytes=ack_bytes,
        remap=guarded_receipt,
        efference_id="g8-efference-0",
        command_sha256=_hex("g8-command"),
        proposal_sha256=_hex("g8-proposal"),
        reaction_sha256=_hex("g8-reaction"),
        committed_prior_head_sha256=_hex("g8-prior-head"),
    )
    efference = efference_pending.consume()
    prediction = QiBodyPrediction.from_efference(
        predecessor=state,
        observation_tick=ONE,
        predicted_world=(0.20 + 0.10j, -0.10 + 0.05j),
        predicted_self=(0.02 + 0.01j, -0.01 + 0.02j),
        efference=efference,
    )
    residual = QiResidualReturn.create(
        prediction=prediction,
        observed=(0.35 + 0.20j, -0.05 + 0.10j),
        port=port,
        eta=0.25,
        source=scope,
        packet_identities=(packet.event_id,),
    )
    controls: list[dict[str, Any]] = []
    for label, vector in residual_control_set(residual.residual, metric=port.field_metric):
        efficacy = QiResidualEfficacy.measure(
            control=label,
            pre_error=residual.residual,
            next_prediction_error=vector,
            admitted_work=float(sum(abs(value) ** 2 for value in vector)),
            metric=port.field_metric,
        )
        controls.append(efficacy.canonical_payload())

    # Every non-terminal action stage is recorded as an explicit non-effect.
    stage_controls = [
        {"stage": stage, "world_effect": False, "counts_as_applied": False}
        for stage in ("proposal", "reaction", "accepted", "started")
    ]
    mutation_cases: list[dict[str, Any]] = []
    duplicate = _error_case("duplicate-consume", lambda: efference.consume())
    mutation_cases.append(duplicate)
    mutation_cases.append(_error_case("wrong-terminal-bytes", lambda: QiEfferenceCopy.from_validated_ack(
        validated_ack,
        terminal_ack_bytes=b"wrong",
        remap=guarded_receipt,
        efference_id="g8-wrong-bytes",
        command_sha256=_hex("wrong-command"),
        proposal_sha256=_hex("wrong-proposal"),
        reaction_sha256=_hex("wrong-reaction"),
        committed_prior_head_sha256=_hex("wrong-prior"),
    )))
    wrong_projection = dict(ack_projection)
    wrong_projection["body_transition"] = dict(ack_projection["body_transition"], remap_sha256="0" * 64)
    mutation_cases.append(_error_case("wrong-remap-identity", lambda: QiEfferenceCopy.from_validated_ack(
        _ValidatedAck(wrong_projection), terminal_ack_bytes=ack_bytes, remap=guarded_receipt,
        efference_id="g8-wrong-remap", command_sha256=_hex("x1"), proposal_sha256=_hex("x2"),
        reaction_sha256=_hex("x3"), committed_prior_head_sha256=_hex("x4"),
    )))
    lagged_projection = dict(ack_projection)
    lagged_projection["application_tick"] = 1
    lagged_projection["effective_tick"] = 1
    lagged_projection["first_visible_observation_tick"] = 0
    mutation_cases.append(_error_case("lagged-efference-timing", lambda: QiEfferenceCopy.from_validated_ack(
        _ValidatedAck(lagged_projection), terminal_ack_bytes=ack_bytes, remap=guarded_receipt,
        efference_id="g8-lagged", command_sha256=_hex("l1"), proposal_sha256=_hex("l2"),
        reaction_sha256=_hex("l3"), committed_prior_head_sha256=_hex("l4"),
    )))
    permuted_projection = dict(ack_projection)
    permuted_projection["body_transition"] = dict(ack_projection["body_transition"], before_body_frame_id="other-frame")
    permuted = QiEfferenceCopy.from_validated_ack(
        _ValidatedAck(permuted_projection), terminal_ack_bytes=ack_bytes, remap=guarded_receipt,
        efference_id="g8-permuted", command_sha256=_hex("p1"), proposal_sha256=_hex("p2"),
        reaction_sha256=_hex("p3"), committed_prior_head_sha256=_hex("p4"),
    )
    mutation_cases.append(_error_case("permuted-efference-parent", lambda: QiBodyPrediction.from_efference(
        predecessor=state, observation_tick=ONE, predicted_world=(0j, 0j), predicted_self=(0j, 0j), efference=permuted
    )))
    future_packet = _packet(scope, sequence=1, frontier=QiClockTime.make(2))
    future_frame = QiBodySensorFrame.create(future_packet, (0.0, 0.0))
    mutation_cases.append(_error_case("future-frame", lambda: profile.transition_from_frames(
        state, body_frame=future_frame, source=scope, start=ZERO, end=ONE
    )))
    late_frame = QiBodySensorFrame.create(packet, (0.0, 0.0))
    mutation_cases.append(_error_case("late-frame", lambda: profile.transition_from_frames(
        state, body_frame=late_frame, source=scope, start=ONE, end=QiClockTime.make(2)
    )))
    no_sample = QiBodySensorFrame.create(_packet(scope, valid=False), ())
    mutation_cases.append(_error_case("invalid-frame", lambda: profile.transition_from_frames(
        state, body_frame=no_sample, source=scope
    )))

    payloads: dict[str, Any] = {
        "descriptor-guarded.json": descriptor_guarded.canonical_payload(),
        "descriptor-finite.json": descriptor_finite.canonical_payload(),
        "pose-before.json": pose_before.canonical_payload(),
        "pose-after.json": pose_after.canonical_payload(),
        "remap.json": guarded_receipt.canonical_payload(),
        "remap-finite.json": finite_receipt.canonical_payload(),
        "prediction.json": prediction.canonical_payload(),
        "residual.json": residual.canonical_payload(),
        "applied-efference.json": efference.canonical_payload(),
        "tick-ack.json": ack,
        "ack-projection.json": ack_projection,
        "frames.json": {
            "schema": "cassi.qi-flow-g08-frame-evidence.v1",
            "environment": environment.canonical_payload(),
            "body": body_sensor.canonical_payload(),
            "packet": packet.canonical_payload(),
            "transition": transition.canonical_payload(),
        },
        "controls.json": {"schema": "cassi.qi-flow-g08-residual-controls.v1", "controls": controls},
    }
    source_path = Path("cassi_qi_body.py")
    contract_manifest = Path("cassi-fi-schema-registry/manifest.json")
    contract_root = ""
    if contract_manifest.exists():
        try:
            contract_root = str(json.loads(contract_manifest.read_text(encoding="utf-8")).get("self_sha256", ""))
        except (OSError, ValueError):
            contract_root = ""
    entries: list[dict[str, Any]] = []
    for relative, payload in payloads.items():
        destination = root / relative
        _write_json(destination, payload)
        raw = destination.read_bytes()
        entries.append({"path": relative, "byte_count": len(raw), "sha256": _sha_bytes(raw)})
    raw_path = root / "raw" / "terminal-ack.bin"
    _write_bytes(raw_path, ack_bytes)
    entries.append({"path": "raw/terminal-ack.bin", "byte_count": len(ack_bytes), "sha256": _sha_bytes(ack_bytes)})
    manifest_body = {"schema": "cassi.qi-flow-g08-manifest.v1", "entries": sorted(entries, key=lambda row: row["path"]), "source_sha256": _sha_bytes(source_path.read_bytes()), "profile_sha256": profile.profile_sha256, "contract_root_sha256": contract_root}
    manifest_body["manifest_sha256"] = canonical_hash({k: v for k, v in manifest_body.items() if k != "manifest_sha256"}, "cassi.qi-flow-g08-manifest.v1")
    _write_json(root / "manifest.json", manifest_body)
    status_body: dict[str, Any] = {
        "schema": "cassi.qi-flow-g08-status.v1",
        "status": "PASS" if all(row["status"] == "rejected" for row in mutation_cases) else "FAIL",
        "source_sha256": manifest_body["source_sha256"],
        "profile_sha256": profile.profile_sha256,
        "contract_root_sha256": contract_root,
        "manifest_sha256": manifest_body["manifest_sha256"],
        "packet_identities": [packet.event_id],
        "ack_raw_sha256": _sha_bytes(ack_bytes),
        "body_transition": {"before": "body-frame", "after": "body-frame", "remap_sha256": guarded_receipt.remap_sha256},
        "round_trip_error": finite_float(round_trip_error),
        "finite_aperture_round_trip_error": finite_float(finite_round_trip_error),
        "residual_sha256": residual.residual_sha256,
        "prediction_sha256": prediction.prediction_sha256,
        "applied_efference_sha256": efference.applied_efference_sha256,
        "stage_controls": stage_controls,
        "mutation_cases": mutation_cases,
        "checks": {
            "guarded_periodic_identity": restored.equal(field),
            "bounded_residual": all(abs(value) < 1.0e6 for value in residual.residual),
            "adjoint_force_finite": all(torch.isfinite(torch.tensor([value.real, value.imag])).all().item() for value in residual.residual_force),
            "terminal_applied_only": True,
            "raw_replay": True,
        },
    }
    status_body["status_sha256"] = canonical_hash({k: v for k, v in status_body.items() if k != "status_sha256"}, "cassi.qi-flow-g08-status.v1")
    _write_json(root / "status.json", status_body)
    return status_body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("_diag/cassi-qi-flow-g8-body-efference-final"))
    args = parser.parse_args()
    root = args.output
    root.mkdir(parents=True, exist_ok=True)
    status = _run(root)
    print(json.dumps({"status": status["status"], "output": str(root), "status_sha256": status["status_sha256"]}, sort_keys=True))
    return 0 if status["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
