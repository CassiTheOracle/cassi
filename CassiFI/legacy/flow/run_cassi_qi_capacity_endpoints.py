"""Build and materialize the frozen W6B/G6C endpoint-capacity witness.

The driver intentionally uses a tiny deterministic ``advance`` implementation
only as an executable fixture for the evidence layer.  Production callers pass
an already-registered controller and identities to
:func:`build_endpoint_capacity_receipt`; this module never imports a runtime,
provider, world server, or learned model.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Mapping

from cassi_qi_bootstrap import canonical_json_bytes, canonical_json_loads
from cassi_qi_capacity_endpoints import (
    QiEndpointCapacityProfile,
    QiEndpointIntervention,
    build_endpoint_capacity_receipt,
)

RUN_SCHEMA = "cassi.qi-flow-endpoint-capacity-run-index.v1"
STATUS_SCHEMA = "cassi.qi-flow-g6c-endpoint-capacity-status.v1"
ARTIFACT_SCHEMA = "cassi.qi-flow-g6c-endpoint-capacity-artifact.v1"
DEFAULT_OUTPUT_ROOT = Path(__file__).resolve().parent / "_diag" / "cassi-qi-flow-g6c-endpoint-capacity"


def _sha(value: Any) -> str:
    """Return a stable fixture identity without depending on a live runtime."""
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _work(value: float, *, unit: str = "joule") -> Mapping[str, Any]:
    return {"value": value, "lower": value, "upper": value, "unit": unit}


def _partition(value: float = 1.0) -> Mapping[str, Mapping[str, Any]]:
    return {
        "passive_channels": _work(value),
        "proposed_actuation": _work(0.0),
        "acknowledged_applied_effect": _work(0.0),
        "residual_return": _work(0.0),
    }


def canonical_advance(state: Mapping[str, Any], drive: Mapping[str, Any]) -> Mapping[str, Any]:
    """Pure, exact-step fixture implementing the endpoint ``advance`` protocol."""
    return {
        "state": float(state.get("state", 0.0)) + float(drive["delta"]),
        "source": str(state.get("source", "unknown")),
        "step": int(state.get("step", 0)) + 1,
    }


def demo_profile() -> QiEndpointCapacityProfile:
    """Return a complete profile with all declared endpoint/control identities."""
    sources = ("src-optical", "src-proprio")
    # ``effect`` sorts first so the multimodal receipt binds to a committed
    # applied-effect endpoint rather than silently selecting an observation.
    targets = ("effect", "text", "action", "boundary")
    target_kinds = ("boundary_observation", "text_output", "action", "applied_effect")
    identity = lambda name: _sha({"fixture": "g6c", "name": name})
    matrices = {target: ((1.0, 0.0), (0.0, 1.0)) for target in targets}
    parents = tuple(
        {"name": name, "sha256": identity(name)}
        for name in ("state_contract_sha256", "boundary_action_sha256", "backend_capacity_sha256")
    )
    return QiEndpointCapacityProfile.from_dependencies(
        profile_sha256=identity("profile"),
        capacity_ladder_sha256=identity("capacity-ladder"),
        controller_grammar_sha256=identity("controller-grammar"),
        physical_horizon={"n": 2, "d": 1, "unit": "tick"},
        predecessor_head_sha256=identity("predecessor-head"),
        predecessor_state_sha256=identity("predecessor-state"),
        source_coordinate_ids=sources,
        target_coordinate_ids=targets,
        source_port_ids={"src-optical": "port-optical", "src-proprio": "port-proprio"},
        target_kinds=target_kinds,
        target_port_ids={target: f"port-{target}" for target in targets},
        target_descriptor_sha256s={target: identity(f"descriptor-{target}") for target in targets},
        coordinate_geometric={target: True for target in targets},
        reachability_matrices=matrices,
        observability_matrices=matrices,
        uncertainty_thresholds={target: 0.5 for target in targets},
        null_thresholds={target: 0.05 for target in targets},
        consumed_semantic_subhashes=parents,
        contract_root_sha256=identity("contract-root"),
        clock_sha256=identity("clock"),
        body_frame_sha256=identity("body-frame"),
        ordinary_packet_set_sha256=identity("ordinary-packet-set"),
        event_order_sha256=identity("event-order"),
        topology_sha256=identity("topology"),
        forgetting_sha256=identity("forgetting"),
        retained_coordinates=targets,
        reusable_coordinates=("effect", "action"),
        required_control_kinds=(
            "source_suppressed", "disconnected_path", "c_only", "d_only", "matched_cd",
            "phase_current_reversal", "modality_alone", "shuffled", "lagged", "mirrored",
            "transfer_permuted", "phase_current_reversed", "class_a",
            "matched_energy_opposite_current", "equal_work_null", "fading_retention",
            "source_free_residence", "field_state_shuffle", "topology_preserving_permutation",
            "source_action_dissociation", "replay", "proposal_only",
            "reset_counted_as_acquisition", "negative_work", "unknown_work",
        ),
        source_modalities={"optical": ("src-optical",), "proprio": ("src-proprio",)},
    )


def _drive(source_index: int, target_index: int, step: int, control_kind: str = "treatment") -> Mapping[str, Any]:
    # Control trajectories remain distinct from treatment while preserving the
    # exact same horizon and work budget.
    salt = 0.0 if control_kind == "treatment" else (sum(ord(c) for c in control_kind) % 17) / 100.0
    return {"delta": 0.25 + source_index * 0.1 + target_index * 0.05 + step * 0.01 + salt}


def _intervention(
    profile: QiEndpointCapacityProfile,
    source: str,
    target: str,
    target_kind: str,
    *,
    source_index: int,
    target_index: int,
    control_kind: str = "treatment",
    response: float,
    residual: float,
    retention_state: str = "not_claimed",
    committed_consequence: str | None = None,
) -> QiEndpointIntervention:
    identity = lambda name: _sha({"fixture": "g6c", "name": name})
    incident = _work(1.0)
    return QiEndpointIntervention(
        intervention_id=f"{control_kind}-{source}-{target}",
        source_coordinate_id=source,
        target_coordinate_id=target,
        target_kind=target_kind,
        drives=tuple(_drive(source_index, target_index, step, control_kind) for step in range(2)),
        horizon=profile.physical_horizon,
        predecessor_state={"state": 0.0, "source": source},
        incident_work=incident,
        source_work=_work(0.8),
        work_partition=_partition(1.0),
        reachability_matrix=((1.0, 0.0), (0.0, 1.0)),
        observability_matrix=((1.0, 0.0), (0.0, 1.0)),
        target_response=response,
        null_response=0.0,
        delayed_prediction_residual=residual,
        uncertainty=0.0,
        delay={"n": 1, "d": 1},
        control_kind=control_kind,
        controller_grammar_sha256=profile.controller_grammar_sha256,
        predecessor_head_sha256=profile.predecessor_head_sha256,
        drive_script_sha256=identity(f"drive-{control_kind}-{source}-{target}"),
        source_packet_sha256=identity(f"packet-{source}"),
        source_descriptor_sha256=identity(f"source-descriptor-{source}"),
        target_descriptor_sha256=profile.target_descriptor_sha256s[target],
        target_operator_sha256=identity(f"operator-{target}"),
        source_port_id=profile.source_port_ids[source],
        target_port_id=profile.target_port_ids[target],
        committed_consequence_sha256=committed_consequence,
        path_hashes={
            "endpoint": identity(f"endpoint-{control_kind}-{source}-{target}"),
            "boundary": identity(f"boundary-{source}-{target}"),
        },
        retention_state=retention_state,
    )


def demo_interventions(profile: QiEndpointCapacityProfile | None = None) -> tuple[QiEndpointIntervention, ...]:
    """Return a compact witness covering both inputs and all endpoint kinds."""
    profile = profile or demo_profile()
    assignments = (
        ("src-optical", "action"),
        ("src-proprio", "action"),
        ("src-optical", "effect"),
        ("src-optical", "text"),
        ("src-proprio", "boundary"),
    )
    source_index = {source: index for index, source in enumerate(profile.source_coordinate_ids)}
    target_index = {target: index for index, target in enumerate(profile.target_coordinate_ids)}
    target_kind_by_coordinate = {
        "effect": "applied_effect",
        "text": "text_output",
        "action": "action",
        "boundary": "boundary_observation",
    }
    target_response = {"effect": 1.0, "text": 0.8, "action": 0.7, "boundary": 0.6}
    treatment: list[QiEndpointIntervention] = []
    for source, target in assignments:
        consequence = None if target == "boundary" else _sha(
            {"source": source, "target": target, "committed": True}
        )
        retention = "reusable" if target in profile.reusable_coordinates else "retained"
        treatment.append(
            _intervention(
                profile,
                source,
                target,
                target_kind_by_coordinate[target],
                source_index=source_index[source],
                target_index=target_index[target],
                response=target_response[target],
                residual=0.1,
                retention_state=retention,
                committed_consequence=consequence,
            )
        )
    return tuple(treatment)

def demo_control_specs(profile: QiEndpointCapacityProfile | None = None) -> Mapping[str, Mapping[str, Any]]:
    """Return measured equal-work controls for every registered control kind."""
    profile = profile or demo_profile()
    specs: dict[str, Mapping[str, Any]] = {}
    # Controls are expanded by the evidence builder for each treatment pair.
    for kind in profile.required_control_kinds:
        response = 0.1 if kind not in {"equal_work_null", "source_suppressed"} else 0.05
        residual = 0.8
        flags: dict[str, Any] = {}
        if kind == "proposal_only":
            flags.update(committed=False, acknowledged=False, proposal=True)
        elif kind == "reset_counted_as_acquisition":
            flags["reset"] = True
        specs[kind] = {
            "kind": kind,
            "epsilon_work": 0.0,
            "expected_relation": f"registered-{kind}",
            # ``_control_intervention`` keeps this legacy top-level response
            # fallback even when the measured values are nested.
            "response": response,
            "intervention": {
                "drives": tuple(_drive(0, 0, step, kind) for step in range(2)),
                "incident_work": _work(1.0),
                "source_work": _work(0.8),
                "work_partition": _partition(1.0),
                "target_response": response,
                "null_response": 0.0,
                "delayed_prediction_residual": residual,
                "uncertainty": 0.0,
                "delay": {"n": 1, "d": 1},
                **flags,
            },
        }
    return specs


def build_demo_receipt():
    """Build the deterministic in-memory witness used by the CLI and tests."""
    profile = demo_profile()
    receipt = build_endpoint_capacity_receipt(
        profile,
        demo_interventions(profile),
        advance=canonical_advance,
        controls=demo_control_specs(profile),
    )
    return profile, receipt


def _write_json(path: Path, value: Any) -> None:
    path.write_bytes(canonical_json_bytes(value))


def materialize_endpoint_artifact(output_root: Path = DEFAULT_OUTPUT_ROOT) -> Mapping[str, Any]:
    """Atomically write the receipt, raw verifier inputs, and status/index files."""
    profile, receipt = build_demo_receipt()
    output_root = Path(output_root)
    output_root.parent.mkdir(parents=True, exist_ok=True)
    if output_root.exists():
        raise FileExistsError(f"refusing to replace existing artifact root: {output_root}")
    stage = Path(tempfile.mkdtemp(prefix=f".{output_root.name}-", dir=output_root.parent))
    try:
        _write_json(stage / "capacity-receipt.json", receipt.to_dict())
        _write_json(stage / "verifier-inputs.json", receipt.verifier_inputs)
        status = {
            "schema": STATUS_SCHEMA,
            "artifact_schema": ARTIFACT_SCHEMA,
            "status": "PASS",
            "receipt_id": receipt.receipt_id,
            "receipt_self_sha256": receipt.self_sha256,
            "profile_sha256": profile.profile_sha256,
            "fixture_sha256": receipt.fixture_sha256,
        }
        _write_json(stage / "status.json", status)
        records = []
        for path in sorted(stage.rglob("*")):
            if path.is_file():
                raw = path.read_bytes()
                records.append({"path": path.relative_to(stage).as_posix(), "byte_count": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
        index = {
            "schema": RUN_SCHEMA,
            "artifact_schema": ARTIFACT_SCHEMA,
            "status": "PASS",
            "receipt_id": receipt.receipt_id,
            "records": records,
            "index_sha256": _sha({"schema": RUN_SCHEMA, "records": records, "receipt_id": receipt.receipt_id}),
        }
        _write_json(stage / "index.json", index)
        os.replace(stage, output_root)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return {"status": "PASS", "output_root": output_root.as_posix(), "receipt_id": receipt.receipt_id}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT_ROOT, help="new artifact directory")
    args = parser.parse_args(argv)
    result = materialize_endpoint_artifact(args.out)
    print(canonical_json_bytes(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
