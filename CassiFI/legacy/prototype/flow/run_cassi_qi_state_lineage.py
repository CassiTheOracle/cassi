"""Build and seal the deterministic G12L exact-byte lineage gate."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable, Mapping

from cassi_qi_bootstrap import canonical_hash, canonical_json_bytes
from cassi_qi_field import QiFlowStateV3
from cassi_qi_profile import QiFlowProfile
from cassi_qi_state_lineage import QiParentSessionSnapshot, QiStateLineageError, fork_state_lineage
from verify_cassi_qi_state_lineage import verify_artifact, verify_receipt


ROOT = Path(__file__).resolve().parent
ARTIFACT_ROOT = ROOT / "_diag" / "cassi-qi-state-lineage"
RUN_SCHEMA = "cassi.qi-flow-g12l-state-lineage-run.v1"
STATUS_SCHEMA = "cassi.qi-flow-g12l-state-lineage-status.v1"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return canonical_json_bytes(value)


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(dict(value)) + b"\n")


def _profile(name: str, *, receipt_bytes: int | None = None) -> QiFlowProfile:
    overrides = None if receipt_bytes is None else {"capacity": {"max_receipt_bytes": receipt_bytes}}
    return QiFlowProfile.from_defaults(profile_id=name, overrides=overrides)


def _parent(profile: QiFlowProfile, state_bytes: bytes) -> QiParentSessionSnapshot:
    return QiParentSessionSnapshot(
        session_id="g12l-parent-session",
        head_sha256=_sha256(b"g12l-parent-head"),
        profile=profile,
        state_object_bytes=state_bytes,
        protocol_epoch="g12l-parent-protocol",
        world_id="g12l-parent-world",
        episode_id="g12l-parent-episode",
        source_identity_sha256=_sha256(b"g12l-parent-source"),
        clock_sha256=_sha256(b"g12l-parent-clock"),
    )


def _fork(parent: QiParentSessionSnapshot, child_profile: QiFlowProfile):
    return fork_state_lineage(
        parent,
        new_profile=child_profile,
        new_session_id="g12l-child-session",
        reason="operator-approved exact-byte state fork",
        new_protocol_epoch="g12l-child-protocol",
        new_world_id="g12l-child-world",
        new_episode_id="g12l-child-episode",
        new_source_identity_sha256=_sha256(b"g12l-child-source"),
        new_clock_sha256=_sha256(b"g12l-child-clock"),
        operator_id="g12l-runner",
        creation_timestamp_ns_telemetry=0,
    )


def _rejection_controls(parent: QiParentSessionSnapshot, child_profile: QiFlowProfile, receipt: dict[str, Any]) -> list[dict[str, str]]:
    controls: list[tuple[str, Callable[[], None]]] = []

    def reject(name: str, call: Callable[[], None]) -> None:
        controls.append((name, call))

    reject("state-consuming-profile-drift", lambda: _fork(parent, _profile("g12l-drift", receipt_bytes=32769)))
    reject("mutated-state-object", lambda: _fork(_parent(parent.profile, parent.state_object_bytes[:-1] + bytes([parent.state_object_bytes[-1] ^ 1])), child_profile))
    reject("in-place-session-reuse", lambda: fork_state_lineage(
        parent,
        new_profile=child_profile,
        new_session_id=parent.session_id,
        reason="rejected reuse",
        new_protocol_epoch="g12l-new-protocol",
        new_world_id="g12l-new-world",
        new_episode_id="g12l-new-episode",
        new_source_identity_sha256=_sha256(b"g12l-other-source"),
        new_clock_sha256=_sha256(b"g12l-other-clock"),
        operator_id="g12l-runner",
    ))
    reject("pending-world-continuity", lambda: _fork(QiParentSessionSnapshot(
        session_id=parent.session_id,
        head_sha256=parent.head_sha256,
        profile=parent.profile,
        state_object_bytes=parent.state_object_bytes,
        protocol_epoch=parent.protocol_epoch,
        world_id=parent.world_id,
        episode_id=parent.episode_id,
        source_identity_sha256=parent.source_identity_sha256,
        clock_sha256=parent.clock_sha256,
        pending_outbox_sha256="pending",
    ), child_profile))
    reject("indeterminate-sealed-parent", lambda: _fork(QiParentSessionSnapshot(
        session_id=parent.session_id,
        head_sha256=parent.head_sha256,
        profile=parent.profile,
        state_object_bytes=parent.state_object_bytes,
        protocol_epoch=parent.protocol_epoch,
        world_id=parent.world_id,
        episode_id=parent.episode_id,
        source_identity_sha256=parent.source_identity_sha256,
        clock_sha256=parent.clock_sha256,
        lineage_status="indeterminate_sealed",
    ), child_profile))

    for field, value in (
        ("parent_head_sha256", "f" * 64),
        ("parent_state_object_sha256", "0" * 64),
        ("parent_state_contract_sha256", "1" * 64),
        ("child_state_object_sha256", "2" * 64),
        ("state_consuming_subhashes", [
            {"name": "state_contract_sha256", "parent_sha256": "0" * 64, "child_sha256": "1" * 64},
            *copy.deepcopy(receipt["state_consuming_subhashes"][1:]),
        ]),
        ("layout_identity_sha256", "3" * 64),
        ("operator_identity_sha256", "4" * 64),
        ("schema_identity_sha256", "5" * 64),
        ("backend_identity_sha256", "6" * 64),
        ("source_profile_identity_sha256", "7" * 64),
        ("old_source_identity_sha256", "8" * 64),
        ("new_source_identity_sha256", "9" * 64),
        ("compatibility_proof", {"schema": "tampered-proof"}),
        ("reset_reason", "tampered fork reason"),
        ("differing_profile_leaves", [{"json_pointer": "/profile_id", "old": "wrong", "new": "wrong"}]),
        ("parent_session_id", "tampered-parent"),
    ):
        def mutate(field: str = field, value: Any = value) -> None:
            tampered = copy.deepcopy(receipt)
            tampered[field] = value
            verify_receipt(tampered)

        reject(f"receipt-mutation-{field}", mutate)

    rows: list[dict[str, str]] = []
    for name, call in controls:
        try:
            call()
        except (QiStateLineageError, ValueError, TypeError, KeyError):
            observed = "REJECT"
        else:
            observed = "ACCEPT"
        rows.append({"control_id": name, "mutation": name, "expected": "REJECT", "observed": observed})
        if observed != "REJECT":
            raise RuntimeError(f"G12L rejection control accepted: {name}")
    return rows


def _objects(root: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda item: item.relative_to(root).as_posix().encode("utf-8")):
        raw = path.read_bytes()
        rows.append({"path": path.relative_to(root).as_posix(), "bytes": len(raw), "sha256": _sha256(raw)})
    return rows


def run(*, output_root: str | Path | None = None) -> dict[str, Any]:
    parent_profile = _profile("g12l-parent-profile")
    child_profile = _profile("g12l-child-profile")
    state_bytes = QiFlowStateV3.create(parent_profile, batch_lanes=1).dump_bytes(parent_profile)
    parent = _parent(parent_profile, state_bytes)
    fork = _fork(parent, child_profile)
    receipt = fork.receipt.payload()
    verify_receipt(receipt)
    controls = _rejection_controls(parent, child_profile, receipt)
    artifact_core: dict[str, Any] = {
        "schema": "cassi.qi-flow-g12l-state-lineage.v1",
        "run_id": "",
        "parent_session_id": receipt["parent_session_id"],
        "new_session_id": receipt["new_session_id"],
        "parent_head_sha256": receipt["parent_head_sha256"],
        "receipt": receipt,
        "profile_difference_projection": receipt["differing_profile_leaves"],
        "compatibility_proof": receipt["compatibility_proof"],
        "mutation_controls": controls,
        "status": "PASS",
    }
    artifact_core["run_id"] = canonical_hash(
        {key: value for key, value in artifact_core.items() if key != "run_id"},
        RUN_SCHEMA + ".id",
    )
    artifact = dict(artifact_core)
    artifact["self_sha256"] = canonical_hash(artifact, "cassi.qi-flow-g12l-state-lineage.v1")
    root = Path(output_root) if output_root is not None else ARTIFACT_ROOT
    root.mkdir(parents=True, exist_ok=True)
    destination = root / artifact["run_id"]
    if destination.exists():
        verify_artifact(destination)
    else:
        with tempfile.TemporaryDirectory(prefix=f".{artifact['run_id']}-", dir=str(root)) as temporary:
            stage = Path(temporary)
            gate = stage / "gates" / "g12l-state-lineage"
            (gate / "state").mkdir(parents=True, exist_ok=True)
            (gate / "state" / "parent-state.bin").write_bytes(state_bytes)
            (gate / "state" / "child-state.bin").write_bytes(fork.state_object_bytes)
            _write_json(gate / "lineage.json", artifact)
            _write_json(gate / "status.json", {
                "schema": STATUS_SCHEMA,
                "status": "PASS",
                "lineage_sha256": artifact["self_sha256"],
                "receipt_sha256": receipt["self_sha256"],
            })
            index_core = {
                "schema": RUN_SCHEMA,
                "run_id": artifact["run_id"],
                "status": "PASS",
                "lineage_sha256": artifact["self_sha256"],
                "objects": _objects(stage),
            }
            index = dict(index_core)
            index["self_sha256"] = canonical_hash(index, RUN_SCHEMA)
            _write_json(stage / "index.json", index)
            os.replace(stage, destination)
        verify_artifact(destination)
    try:
        artifact_name = destination.relative_to(ROOT).as_posix()
    except ValueError:
        artifact_name = str(destination)
    return {
        "status": "PASS_G12L",
        "run_id": artifact["run_id"],
        "artifact": artifact_name,
        "lineage_sha256": artifact["self_sha256"],
        "receipt_sha256": receipt["self_sha256"],
        "mutation_control_count": len(controls),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = run(output_root=args.output_root)
    if args.json:
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    else:
        print(f"PASS_G12L {result['artifact']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
