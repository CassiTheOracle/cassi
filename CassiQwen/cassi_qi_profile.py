"""Cassi Qi Flow W1 contract root, exact profile, and semantic identities.

The contract root is independent of concrete profile instances.  It binds the
isolated canonical bootstrap, complete schema/projection registries, exact
profile schema, and materialized default map.  A selected profile first binds
that root and only then computes every semantic projection.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Sequence

import cassi_qi_bootstrap as _bootstrap
from cassi_qi_bootstrap import (
    CANONICAL_CODEC_SCHEMA,
    CONTRACT_ROOT_BOOTSTRAP_SCHEMA,
    MAX_CANONICAL_BYTES,
    CanonicalCodecError,
    bootstrap_fixture_set_sha256,
    bootstrap_self_test,
    canonical_codec_descriptor,
    canonical_fixture_corpus,
    canonical_hash,
    canonical_json_bytes,
    canonical_json_loads,
    finite_bits,
    finite_float,
)

CONTRACT_ROOT_SCHEMA = "cassi.qi-flow-contract-root.v1"
PROFILE_SCHEMA = "cassi.qi-flow-profile.v1"
SCHEMA_REGISTRY_SCHEMA = "cassi.qi-flow-schema-registry.v1"
PROJECTION_REGISTRY_SCHEMA = "cassi.qi-flow-profile-projections.v1"
PROFILE_SCHEMA_DOCUMENT_SCHEMA = "cassi.qi-flow-schema-document.v1"
PROFILE_DEFAULTS_SCHEMA = "cassi.qi-flow-profile-defaults.v1"
DEFAULTS_POLICY = "release-explicit-no-omission-v1"
W0_RUN_ID = "6594761eeaf97fcc839d5b931908ff7990dd7d853094b7b94c0fad2b2fac8d47"
W0_HISTORICAL_MANIFEST_SHA256 = "98814b75591d73174c8aaac9a23f5717c656ddabe94b2776b1ea79dff10feba8"
SCHEMA_DOCUMENT_HASH_DOMAIN = "cassi.qi-flow-schema-document.v1"
SCHEMA_FIXTURE_SET_HASH_DOMAIN = "cassi.qi-flow-schema-fixture-set.v1"
SCHEMA_MUTATION_CONTROLS_HASH_DOMAIN = "cassi.qi-flow-schema-mutation-controls.v1"
SCHEMA_REGISTRY_ENTRY_HASH_DOMAIN = "cassi.qi-flow-schema-registry-entry.v1"
SCHEMA_REGISTRY_ENTRY_KEYS = (
    "schema",
    "version",
    "object_class",
    "lifecycle",
    "max_encoded_bytes",
    "max_fanout",
    "semantic_parent_names",
    "schema_document",
    "schema_document_sha256",
    "fixture_id",
    "canonical_fixture_set",
    "canonical_fixture_set_sha256",
    "mutation_controls",
    "mutation_controls_sha256",
    "hash_domain",
    "self_hash_field",
    "independent_verifier",
    "migration_policy",
)
SCHEMA_OBJECT_CLASSES = frozenset(
    {
        "bootstrap-object",
        "profile-contract",
        "immutable-spec",
        "runtime-state",
        "checkpoint",
        "protocol-object",
        "indexed-receipt",
        "manifest",
        "gate-artifact",
    }
)

SEMANTIC_PROJECTIONS = (
    "state_contract_sha256",
    "boundary_action_sha256",
    "world_protocol_sha256",
    "session_storage_sha256",
    "provider_api_sha256",
    "backend_capacity_sha256",
    "security_evidence_sha256",
)

COMPONENT_ORDER = (
    "Y_re",
    "Y_im",
    "I_re",
    "I_im",
    "VY_re",
    "VY_im",
    "VI_re",
    "VI_im",
    "epsilon2_ema",
)


class PROFILE_MISMATCH(ValueError):
    """Raised when profile/root/schema/state identities do not agree."""


def _self_hash(payload: Mapping[str, Any], domain: str) -> str:
    body = dict(payload)
    body.pop("self_sha256", None)
    return canonical_hash(body, domain)


def _sha(value: Any, domain: str) -> str:
    return canonical_hash(value, domain)


def _bootstrap_source_path() -> Path:
    return Path(_bootstrap.__file__).resolve()


def _bootstrap_source_sha256() -> str:
    return hashlib.sha256(_bootstrap_source_path().read_bytes()).hexdigest()


def bootstrap_identity() -> dict[str, Any]:
    codec = canonical_codec_descriptor()
    return {
        "schema": CONTRACT_ROOT_BOOTSTRAP_SCHEMA,
        "source_path": "cassi_qi_bootstrap.py",
        "source_sha256": _bootstrap_source_sha256(),
        "toolchain": "python-stdlib-strict-utf8-finite-bit-v1",
        "fixture_set_sha256": bootstrap_fixture_set_sha256(),
        "codec_descriptor_sha256": canonical_hash(codec, CANONICAL_CODEC_SCHEMA),
    }


def _operator_identity(operator_id: str, payload: Mapping[str, Any]) -> str:
    return canonical_hash(
        {"operator_id": operator_id, "specification": dict(payload)},
        "cassi.qi-flow.operator-specification.v1",
    )


_ZERO = finite_bits(0.0)
_HALF = finite_bits(0.5)
_ONE = finite_bits(1.0)
_PHI = finite_bits((1.0 + 5.0**0.5) / 2.0)
_DX = finite_bits(0.001)
_DY = finite_bits(0.001)
_LX = finite_bits(0.008)
_LY = finite_bits(0.004)
_CELL_AREA = finite_bits(1.0e-6)

_SHEET_SPEC = {
    "active_shape": [4, 8],
    "active_site_count": 32,
    "storage_mode_count": 32,
    "packing": "m=y*N_x+x",
    "axis_order": ["y", "x"],
    "vector_component_order": ["x", "y"],
    "handedness": "right-handed-x-y-z-out.v1",
    "origin_m": [_ZERO, _ZERO],
    "spacing_m": {"dy": _DY, "dx": _DX},
    "extent_m": {"L_y": _LY, "L_x": _LX},
    "metric_cell_area": _CELL_AREA,
    "signed_frequency_bins": {
        "y": [0, 1, -2, -1],
        "x": [0, 1, 2, 3, -4, -3, -2, -1],
        "even_nyquist": "literal-negative",
    },
    "oversampling": {
        "factors": [2, 2],
        "shape": [8, 16],
        "injection": "complete-signed-frequency.v1",
        "alpha": finite_bits(2.0),
        "restriction": "weighted-adjoint.v1",
    },
}

_TRANSFORM_SPEC = {
    "phi": _PHI,
    "forward": {"D": "EY-phi*EI", "C": "(phi*EY+EI)/(1+phi^2)"},
    "inverse": {"EY": "phi*C+D/(1+phi^2)", "EI": "C-phi*D/(1+phi^2)"},
    "velocity_forward": {"V_D": "VY-phi*VI", "V_C": "(phi*VY+VI)/(1+phi^2)"},
    "velocity_inverse": {"VY": "phi*V_C+V_D/(1+phi^2)", "VI": "V_C-phi*V_D/(1+phi^2)"},
    "weights": {"w_D": "1/(1+phi^2)", "w_C": "1+phi^2"},
}

_P_SPEC = {
    "mode": "temporal-full-rank",
    "restriction": "identity-low-pass.v1",
    "adjoint": "metric-restricted-adjoint.v1",
    "active_ranks": [32, 32, 32, 32],
    "nullspace_dimensions": [0, 0, 0, 0],
}

_GEOMETRY_OPERATOR_SPEC = {
    "schema": "cassi.qi-flow-periodic-sheet-geometry.v1",
    "sheets": [{"scale_index": index, **deepcopy(_SHEET_SPEC)} for index in range(4)],
    "boundary_condition": "periodic",
    "spectral_transform": "unitary-fft2.v1",
    "normalization": "ortho",
    "derivative_symbol": "literal-i-k.v1",
    "laplacian_symbol": "-(kx^2+ky^2).v1",
    "gather_scatter": "active-prefix-zero-tail.v1",
    "positive_scalar_remap": "positive-conservative-overlap.v1",
    "coordinate_transform": deepcopy(_TRANSFORM_SPEC),
    "cross_scale": deepcopy(_P_SPEC),
}
_GEOMETRY_OPERATOR_SHA256 = _operator_identity("periodic-sheet-geometry.v1", _GEOMETRY_OPERATOR_SPEC)
_TRANSFORM_SHA256 = _operator_identity("yang-yin-dc-transform.v1", _TRANSFORM_SPEC)
_P_SHA256 = _operator_identity("temporal-full-rank-p.v1", _P_SPEC)
_P_ADJOINT_SHA256 = _operator_identity("temporal-full-rank-p-adjoint.v1", _P_SPEC)
_METRIC_SHA256 = _sha(
    {"cell_area": [_CELL_AREA] * 4, "coordinate_weights": _TRANSFORM_SPEC["weights"]},
    "cassi.qi-flow.metric.v1",
)

_SOURCE_DESCRIPTOR_BASE = {
    "schema": "cassi.qi-flow-source-identity.v1",
    "enabled_source_epochs": ["w1-static-zero-source-epoch.v1"],
    "enabled_streams": [],
    "source_priority": [],
    "replay_policy": "exact-journal-order-v1",
    "world_id": "reference-world-v1",
    "clock_id": "physical-rational-seconds-v1",
    "journal_schema": "cassi.qi-flow-source-journal.v1",
    "maximum_source_bytes_per_step": 0,
}
_SOURCE_IDENTITY_SHA256 = _sha(_SOURCE_DESCRIPTOR_BASE, "cassi.qi-flow-source-identity.v1")
_SOURCE_DESCRIPTOR = {**_SOURCE_DESCRIPTOR_BASE, "self_sha256": _SOURCE_IDENTITY_SHA256}


def _stage(
    ordinal: int,
    stage_id: str,
    operator_id: str,
    *,
    transition_kind: str,
    clock_increment: tuple[int, int],
    effective_duration: tuple[int, int],
    evaluate_from: str,
    read_slices: Sequence[str],
    write_slices: Sequence[str],
    drive_classes: Sequence[str],
    work_rows: Sequence[str],
    phase_charge_rows: Sequence[str],
    bound_checks: Sequence[str],
    synchronization_points: Sequence[str],
    failure_codes: Sequence[str],
) -> dict[str, Any]:
    if transition_kind not in {
        "timed",
        "timed_phase_slip",
        "finite_map",
        "diagnostic",
        "port_reaction",
        "retention_reset",
    }:
        raise RuntimeError(f"unknown stage transition kind: {transition_kind}")
    stage = {
        "schema": "cassi.qi-flow-stage-spec.v1",
        "ordinal": ordinal,
        "stage_id": stage_id,
        "operator_id": operator_id,
        "transition_kind": transition_kind,
        "clock_increment_num": clock_increment[0],
        "clock_increment_den": clock_increment[1],
        "effective_duration_num": effective_duration[0],
        "effective_duration_den": effective_duration[1],
        "evaluate_from": evaluate_from,
        "read_slices": list(read_slices),
        "write_slices": list(write_slices),
        "drive_classes": list(drive_classes),
        "work_rows": list(work_rows),
        "phase_charge_rows": list(phase_charge_rows),
        "bound_checks": list(bound_checks),
        "synchronization_points": list(synchronization_points),
        "failure_codes": list(failure_codes),
    }
    stage["operator_sha256"] = _operator_identity(
        operator_id,
        {key: value for key, value in stage.items() if key not in {"schema", "operator_sha256"}},
    )
    return stage


_STAGE_REGISTRY = [
    _stage(
        0,
        "validate-and-derive",
        "validate-and-derive.v1",
        transition_kind="diagnostic",
        clock_increment=(0, 1),
        effective_duration=(0, 1),
        evaluate_from="predecessor_state",
        read_slices=["predecessor.field", "profile", "drive_bundle", "source_frontiers", "session_head"],
        write_slices=["candidate.context"],
        drive_classes=["registered-source", "registered-boundary", "registered-action", "registered-reset"],
        work_rows=[],
        phase_charge_rows=[],
        bound_checks=["profile-identity", "predecessor-state", "source-frontier", "drive-budget", "backend-capacity"],
        synchronization_points=["profile-open", "source-frontier-open"],
        failure_codes=["PROFILE_MISMATCH", "INVALID_SOURCE", "RESOURCE_LIMIT"],
    ),
    _stage(
        1,
        "applied-efference-and-body-remap",
        "applied-efference-body-remap.v1",
        transition_kind="finite_map",
        clock_increment=(0, 1),
        effective_duration=(0, 1),
        evaluate_from="predecessor_state",
        read_slices=["candidate.position", "candidate.velocity", "applied_efference", "body_frame"],
        write_slices=["candidate.position", "candidate.velocity"],
        drive_classes=["applied-efference", "body-remap"],
        work_rows=["W_remap"],
        phase_charge_rows=["Delta_Q_remap"],
        bound_checks=["finite-remap", "invertible-remap", "topology-transport", "remap-work-closure"],
        synchronization_points=["remap-complete"],
        failure_codes=["INVALID_REMAP", "TOPOLOGY_UNRESOLVED", "WORK_CLOSURE"],
    ),
    _stage(
        2,
        "external-half-forces-a",
        "external-half-forces-a.v1",
        transition_kind="finite_map",
        clock_increment=(0, 1),
        effective_duration=(1, 2),
        evaluate_from="current_candidate",
        read_slices=["candidate.position", "registered_sensory_force", "registered_residual_force", "registered_port_reaction"],
        write_slices=["candidate.velocity"],
        drive_classes=["sensory", "residual", "port-reaction"],
        work_rows=["W_sensory_a", "W_residual_a", "W_port_reaction_a"],
        phase_charge_rows=["R_sensory_a", "R_residual_a", "R_port_a"],
        bound_checks=["source-work-budget", "force-cap", "candidate-velocity-bound"],
        synchronization_points=["external-kick-a-complete"],
        failure_codes=["SOURCE_BUDGET", "FORCE_BOUND", "STATE_BOUND"],
    ),
    _stage(
        3,
        "conservative-half-forces-a",
        "conservative-half-forces-a.v1",
        transition_kind="finite_map",
        clock_increment=(0, 1),
        effective_duration=(1, 2),
        evaluate_from="current_candidate",
        read_slices=["candidate.position", "composition_operator", "link_operator", "retention_operator"],
        write_slices=["candidate.velocity"],
        drive_classes=[],
        work_rows=[],
        phase_charge_rows=["R_composition_a", "K_D_a", "K_C_a", "R_retention_a"],
        bound_checks=["potential-gradient", "hessian-envelope", "candidate-velocity-bound"],
        synchronization_points=["conservative-kick-a-complete"],
        failure_codes=["OPERATOR_MISMATCH", "STABILITY_BREACH", "STATE_BOUND"],
    ),
    _stage(
        4,
        "exact-damped-spectral-half-a",
        "exact-damped-spectral-half-a.v1",
        transition_kind="timed",
        clock_increment=(1, 2),
        effective_duration=(1, 2),
        evaluate_from="current_candidate",
        read_slices=["candidate.position", "candidate.velocity", "spectral_symbols"],
        write_slices=["candidate.position", "candidate.velocity"],
        drive_classes=[],
        work_rows=["Q_damp_a"],
        phase_charge_rows=["R_damping_a"],
        bound_checks=["spectral-branch", "finite-mode", "intermediate-state-bound"],
        synchronization_points=["spectral-half-a-complete"],
        failure_codes=["SPECTRAL_BRANCH", "NONFINITE", "STATE_BOUND"],
    ),
    _stage(
        5,
        "frozen-q-conversion",
        "frozen-q-conversion-center.v1",
        transition_kind="finite_map",
        clock_increment=(0, 1),
        effective_duration=(1, 1),
        evaluate_from="frozen_stage_copy",
        read_slices=["candidate.position", "predecessor.epsilon2_ema", "conversion_profile"],
        write_slices=["candidate.position"],
        drive_classes=[],
        work_rows=["W_conversion", "Q_conversion"],
        phase_charge_rows=["R_conversion"],
        bound_checks=["frozen-q", "local-density", "full-hamiltonian-conversion", "topology-transport", "state-bound"],
        synchronization_points=["conversion-copy-frozen", "conversion-complete"],
        failure_codes=["CONVERSION_ENERGY_UNRESOLVED", "TOPOLOGY_UNRESOLVED", "STATE_BOUND"],
    ),
    _stage(
        6,
        "exact-damped-spectral-half-b",
        "exact-damped-spectral-half-b.v1",
        transition_kind="timed",
        clock_increment=(1, 2),
        effective_duration=(1, 2),
        evaluate_from="current_candidate",
        read_slices=["candidate.position", "candidate.velocity", "spectral_symbols"],
        write_slices=["candidate.position", "candidate.velocity"],
        drive_classes=[],
        work_rows=["Q_damp_b"],
        phase_charge_rows=["R_damping_b"],
        bound_checks=["spectral-branch", "finite-mode", "intermediate-state-bound"],
        synchronization_points=["spectral-half-b-complete"],
        failure_codes=["SPECTRAL_BRANCH", "NONFINITE", "STATE_BOUND"],
    ),
    _stage(
        7,
        "conservative-half-forces-b",
        "conservative-half-forces-b.v1",
        transition_kind="finite_map",
        clock_increment=(0, 1),
        effective_duration=(1, 2),
        evaluate_from="current_candidate",
        read_slices=["candidate.position", "composition_operator", "link_operator", "retention_operator"],
        write_slices=["candidate.velocity"],
        drive_classes=[],
        work_rows=[],
        phase_charge_rows=["R_composition_b", "K_D_b", "K_C_b", "R_retention_b"],
        bound_checks=["potential-gradient", "hessian-envelope", "candidate-velocity-bound"],
        synchronization_points=["conservative-kick-b-complete"],
        failure_codes=["OPERATOR_MISMATCH", "STABILITY_BREACH", "STATE_BOUND"],
    ),
    _stage(
        8,
        "external-half-forces-b",
        "external-half-forces-b.v1",
        transition_kind="finite_map",
        clock_increment=(0, 1),
        effective_duration=(1, 2),
        evaluate_from="current_candidate",
        read_slices=["candidate.position", "registered_port_reaction", "registered_residual_force", "registered_sensory_force"],
        write_slices=["candidate.velocity"],
        drive_classes=["port-reaction", "residual", "sensory"],
        work_rows=["W_port_reaction_b", "W_residual_b", "W_sensory_b"],
        phase_charge_rows=["R_port_b", "R_residual_b", "R_sensory_b"],
        bound_checks=["source-work-budget", "force-cap", "candidate-velocity-bound"],
        synchronization_points=["external-kick-b-complete"],
        failure_codes=["SOURCE_BUDGET", "FORCE_BOUND", "STATE_BOUND"],
    ),
    _stage(
        9,
        "coordinate-reconstruction-and-ema",
        "coordinate-reconstruction-ema.v1",
        transition_kind="finite_map",
        clock_increment=(0, 1),
        effective_duration=(1, 1),
        evaluate_from="current_candidate",
        read_slices=["candidate.D", "candidate.C", "candidate.V_D", "candidate.V_C", "predecessor.epsilon2_ema"],
        write_slices=["candidate.Y", "candidate.I", "candidate.VY", "candidate.VI", "candidate.epsilon2_ema"],
        drive_classes=[],
        work_rows=[],
        phase_charge_rows=[],
        bound_checks=["coordinate-roundtrip", "ema-positive", "candidate-complete-bound"],
        synchronization_points=["physical-coordinate-reconstruction", "ema-updated-once"],
        failure_codes=["COORDINATE_MISMATCH", "EMA_BOUND", "STATE_BOUND"],
    ),
    _stage(
        10,
        "diagnostics-and-ledger-preflight",
        "diagnostics-ledger-preflight.v1",
        transition_kind="diagnostic",
        clock_increment=(0, 1),
        effective_duration=(0, 1),
        evaluate_from="current_candidate",
        read_slices=["predecessor.field", "candidate.field", "stage_evidence", "source_frontiers"],
        write_slices=["evidence.diagnostics", "evidence.ledger", "evidence.decision"],
        drive_classes=[],
        work_rows=["W_total", "Q_total", "R_H"],
        phase_charge_rows=["Delta_Q_D", "Delta_Q_C", "R_Q"],
        bound_checks=["finite-candidate", "all-state-bounds", "energy-ledger", "phase-charge-ledger", "topology-path", "resource-budget"],
        synchronization_points=["all-stage-evidence-visible", "candidate-decision-complete"],
        failure_codes=["NONFINITE", "STATE_BOUND", "WORK_CLOSURE", "PHASE_CLOSURE", "TOPOLOGY_UNRESOLVED", "RESOURCE_LIMIT"],
    ),
]


def _schedule_object(
    schedule_id: str,
    transition_kind: str,
    stages: Sequence[Mapping[str, Any]],
    *,
    base_schedule_sha256: str | None = None,
    observer_sha256: str | None = None,
) -> dict[str, Any]:
    advance = sum(
        (
            Fraction(stage["clock_increment_num"], stage["clock_increment_den"])
            for stage in stages
        ),
        Fraction(0, 1),
    )
    body = {
        "schema": "cassi.qi-flow-execution-schedule.v1",
        "schedule_id": schedule_id,
        "transition_kind": transition_kind,
        "stages": deepcopy(list(stages)),
        "total_clock_increment_num": advance.numerator,
        "total_clock_increment_den": advance.denominator,
        "base_schedule_sha256": base_schedule_sha256,
        "observer_sha256": observer_sha256,
    }
    body["self_sha256"] = _self_hash(
        body,
        "cassi.qi-flow-execution-schedule.v1",
    )
    return body


_TIMED_SCHEDULE = _schedule_object("timed-step-v1", "timed", _STAGE_REGISTRY)
_PORT_REACTION_SCHEDULE = _schedule_object(
    "port-reaction-v1",
    "port_reaction",
    [
        _stage(
            0,
            "characteristic-port-reaction",
            "characteristic-port-reaction.v1",
            transition_kind="port_reaction",
            clock_increment=(0, 1),
            effective_duration=(0, 1),
            evaluate_from="predecessor_state",
            read_slices=["predecessor.field", "registered_port_incident"],
            write_slices=["candidate.velocity"],
            drive_classes=["port-reaction"],
            work_rows=["W_port_reaction"],
            phase_charge_rows=["R_port_reaction"],
            bound_checks=["port-metric", "scattering-closure", "candidate-state-bound"],
            synchronization_points=["port-reaction-complete"],
            failure_codes=["INVALID_PORT", "SCATTERING_CLOSURE", "STATE_BOUND"],
        )
    ],
)
_RETENTION_RESET_SCHEDULE = _schedule_object(
    "retention-reset-v1",
    "retention_reset",
    [
        _stage(
            0,
            "authenticated-retention-reset",
            "authenticated-retention-reset.v1",
            transition_kind="retention_reset",
            clock_increment=(0, 1),
            effective_duration=(0, 1),
            evaluate_from="predecessor_state",
            read_slices=["predecessor.slow_scale", "authenticated_reset_command", "retention_profile"],
            write_slices=["candidate.slow_scale.psi_topo", "candidate.slow_scale.V_psi_topo"],
            drive_classes=["retention-reset"],
            work_rows=["W_reset"],
            phase_charge_rows=["R_reset"],
            bound_checks=["reset-authorization", "reset-operator", "candidate-state-bound"],
            synchronization_points=["retention-reset-complete"],
            failure_codes=["UNAUTHORIZED_RESET", "INVALID_RESET", "STATE_BOUND"],
        )
    ],
)
_PHASE_SLIP_OBSERVER_SHA256 = _sha(
    {
        "observer_id": "topology-refinement-observer.v1",
        "state_writes": [],
        "measurement": "path-resolved-winding-and-barrier.v1",
        "unresolved": "reject",
    },
    "cassi.qi-flow.phase-slip-observer.v1",
)
_TIMED_PHASE_SLIP_SCHEDULE = _schedule_object(
    "timed-phase-slip-v1",
    "timed_phase_slip",
    _STAGE_REGISTRY,
    base_schedule_sha256=_TIMED_SCHEDULE["self_sha256"],
    observer_sha256=_PHASE_SLIP_OBSERVER_SHA256,
)
_AUXILIARY_SCHEDULES = {
    "port_reaction": _PORT_REACTION_SCHEDULE,
    "retention_reset": _RETENTION_RESET_SCHEDULE,
    "timed_phase_slip": _TIMED_PHASE_SLIP_SCHEDULE,
}

_COMPARISON_FIXTURES = {
    "schema": "cassi.qi-flow-scale-geometry-comparison-fixtures.v1",
    "fixture_ids": ["four-scale-plane-wave", "localized-packet", "cross-scale-adjoint", "active-capacity"],
}
_COMPARISON_FIXTURES_SHA256 = _sha(_COMPARISON_FIXTURES, _COMPARISON_FIXTURES["schema"])
_COMPARISON_PREREG = {
    "candidate_mode_ids": ["temporal-full-rank", "spatiotemporal-pyramid"],
    "common_fixture_set_sha256": _COMPARISON_FIXTURES_SHA256,
    "thresholds": {
        "adjoint_error_max": finite_bits(1.0e-10),
        "roundtrip_error_max": finite_bits(1.0e-10),
        "packet_energy_drift_max": finite_bits(1.0e-6),
        "minimum_active_rank": 1,
    },
    "selection_rule": "first-candidate-passing-all-registered-thresholds-v1",
}
_COMPARISON_PREREG_SHA256 = _sha(_COMPARISON_PREREG, "cassi.qi-flow-scale-geometry-comparison-prereg.v1")


def _edge_registry_spec(shape: Sequence[int]) -> dict[str, Any]:
    ny, nx = int(shape[0]), int(shape[1])
    return {
        "schema": "cassi.qi-flow-oriented-edge-registry.v1",
        "sheet_shape": [ny, nx],
        "packing": "m=y*N_x+x",
        "orientation": ["+x", "+y"],
        "edges": [
            {
                "edge_id": f"{axis}:{y}:{x}",
                "source": y * nx + x,
                "target": (
                    y * nx + ((x + 1) % nx)
                    if axis == "x"
                    else ((y + 1) % ny) * nx + x
                ),
                "axis": axis,
                "weight": _ONE,
            }
            for axis in ("x", "y")
            for y in range(ny)
            for x in range(nx)
        ],
    }


def _torus_registry_spec(shape: Sequence[int]) -> dict[str, Any]:
    ny, nx = int(shape[0]), int(shape[1])
    return {
        "schema": "cassi.qi-flow-torus-cycle-plaquette-registry.v1",
        "sheet_shape": [ny, nx],
        "x_cycles": [[y * nx + x for x in range(nx)] for y in range(ny)],
        "y_cycles": [[y * nx + x for y in range(ny)] for x in range(nx)],
        "plaquette_origins": [y * nx + x for y in range(ny) for x in range(nx)],
        "orientation": "counterclockwise-+x-+y.v1",
    }


_SLOW_SHEET_SHAPE = (4, 8)
_EDGE_REGISTRY_SPEC = _edge_registry_spec(_SLOW_SHEET_SHAPE)
_EDGE_ROWS = _EDGE_REGISTRY_SPEC["edges"]
_EDGE_REGISTRY_SHA256 = _sha(
    _EDGE_REGISTRY_SPEC,
    _EDGE_REGISTRY_SPEC["schema"],
)
_TORUS_REGISTRY_SPEC = _torus_registry_spec(_SLOW_SHEET_SHAPE)
_TORUS_REGISTRY_SHA256 = _sha(
    _TORUS_REGISTRY_SPEC,
    _TORUS_REGISTRY_SPEC["schema"],
)


_STATE_ADMISSION_PREDICATE = (
    "exact-shape-finite-declared-bounds-zero-inactive-tail.v1"
)
_STATE_BOUNDS_DEFAULTS = {
    "component_abs_max": [finite_bits(0.5)] * 9,
    "complex_amplitude_max": [finite_bits(0.5)] * 4,
    "density_max": finite_bits(1.0),
    "epsilon2_ema_max": finite_bits(0.5),
    "inactive_tail_value": _ZERO,
}
_FIELD_DEFAULTS = {
    "scale_count": 4,
    "mode_count": 32,
    "component_count": 9,
    "batch_limit": 4,
    "dtype": "float64",
    "byte_order": "little",
    "layout_id": "cassi.qi-flow-state-layout.v3",
    "component_order": list(COMPONENT_ORDER),
    "active_shapes": [[4, 8], [4, 8], [4, 8], [4, 8]],
    "active_site_counts": [32, 32, 32, 32],
    "state_byte_limit": 1 << 20,
    "state_bounds": deepcopy(_STATE_BOUNDS_DEFAULTS),
}


def _state_bounds_layout_body(field: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": "cassi.qi-flow-state-bounds-layout.v1",
        "shape_formula": "[S,9M,B]",
        "scale_count": field["scale_count"],
        "mode_count": field["mode_count"],
        "component_count": field["component_count"],
        "batch_limit": field["batch_limit"],
        "dtype": field["dtype"],
        "byte_order": field["byte_order"],
        "layout_id": field["layout_id"],
        "component_order": deepcopy(field["component_order"]),
        "active_shapes": deepcopy(field["active_shapes"]),
        "active_site_counts": deepcopy(field["active_site_counts"]),
        "state_byte_limit": field["state_byte_limit"],
        "state_bounds": deepcopy(field["state_bounds"]),
        "admission_predicate": _STATE_ADMISSION_PREDICATE,
    }


def _state_bounds_layout_sha256(field: Mapping[str, Any]) -> str:
    body = _state_bounds_layout_body(field)
    return _sha(body, body["schema"])


_CLOCK_SPEC = {
    "schema": "cassi.qi-flow-clock-time.v1",
    "unit": "second",
    "h_min": {"numerator": 1, "denominator": 1000},
    "h_max": {"numerator": 1, "denominator": 100},
    "runtime_membership": "reduced-positive-rational-closed-interval.v1",
    "selection": "request-rational-within-profile-interval.v1",
    "advance_rule": "accepted-forward-commit-only.v1",
}


def _conversion_domain_body(
    field: Mapping[str, Any],
    clock: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema": "cassi.qi-flow-conversion-domain.v1",
        "state_bounds_layout_sha256": _state_bounds_layout_sha256(field),
        "state_admission_predicate": _STATE_ADMISSION_PREDICATE,
        "h_interval": [deepcopy(clock["h_min"]), deepcopy(clock["h_max"])],
        "h_membership": clock["runtime_membership"],
    }


def _stability_conversion_domain_sha256(
    field: Mapping[str, Any],
    clock: Mapping[str, Any],
) -> str:
    body = _conversion_domain_body(field, clock)
    return _sha(body, body["schema"])
_STABILITY_ENVELOPE_BODY = {
    "schema": "cassi.qi-flow-stability-envelope.v1",
    "envelope_id": "qi-flow-development-analytic-envelope-v1",
    "clock_bounds": {
        "h_min": deepcopy(_CLOCK_SPEC["h_min"]),
        "h_max": deepcopy(_CLOCK_SPEC["h_max"]),
    },
    "component_abs_max": deepcopy(_FIELD_DEFAULTS["state_bounds"]["component_abs_max"]),
    "active_amplitude_max": deepcopy(_FIELD_DEFAULTS["state_bounds"]["complex_amplitude_max"]),
    "active_density_max": _FIELD_DEFAULTS["state_bounds"]["density_max"],
    "admitted_work_abs_max": finite_bits(16.0),
    "intermediate_component_abs_max": finite_bits(0.75),
    "metric_normalized_hessian_upper": [finite_bits(1.0)] * 4,
    "spectral_operator_norm_upper": [
        finite_bits(value)
        for value in (3.0e5, 1.4e5, 3.5e4, 8.8e3)
    ],
    "remap_amplification_upper": _ONE,
    "exact_propagator_branches": [
        "zero-frequency",
        "underdamped",
        "critical",
        "overdamped",
    ],
    "state_bounds_layout_sha256": _state_bounds_layout_sha256(_FIELD_DEFAULTS),
    "state_admission_predicate": _STATE_ADMISSION_PREDICATE,
    "conversion_domain_sha256": _stability_conversion_domain_sha256(
        _FIELD_DEFAULTS,
        _CLOCK_SPEC,
    ),
    "numerical_uncertainty_abs": finite_bits(1.0e-10),
    "strict_safety_margin": finite_bits(0.25),
    "rounding": "outward-binary64.v1",
    "bound_policy": "reject-before-allocation-or-candidate-write.v1",
    "derivation_sha256": _sha(
        {
            "method": "termwise-analytic-interval-enclosure.v1",
            "geometry_sha256": _GEOMETRY_OPERATOR_SHA256,
            "metric_sha256": _METRIC_SHA256,
            "transform_sha256": _TRANSFORM_SHA256,
            "branch_method": "exact-damped-modal.v1",
        },
        "cassi.qi-flow.stability-derivation.v1",
    ),
    "certificate_extension_sha256": None,
}
_STABILITY_ENVELOPE_BODY["self_sha256"] = _self_hash(
    _STABILITY_ENVELOPE_BODY,
    "cassi.qi-flow-stability-envelope.v1",
)




def _stability_derivation_sha256(
    geometry_sha256: str,
    metric_sha256: str,
    transform_sha256: str,
) -> str:
    return _sha(
        {
            "method": "termwise-analytic-interval-enclosure.v1",
            "geometry_sha256": geometry_sha256,
            "metric_sha256": metric_sha256,
            "transform_sha256": transform_sha256,
            "branch_method": "exact-damped-modal.v1",
        },
        "cassi.qi-flow.stability-derivation.v1",
    )


def _rebind_stability_envelope(
    envelope: Mapping[str, Any],
    *,
    field: Mapping[str, Any],
    clock: Mapping[str, Any],
    geometry_sha256: str,
    metric_sha256: str,
    transform_sha256: str,
) -> dict[str, Any]:
    body = deepcopy(dict(envelope))
    body.pop("self_sha256", None)
    state_bounds = field["state_bounds"]
    body["clock_bounds"] = {
        "h_min": deepcopy(clock["h_min"]),
        "h_max": deepcopy(clock["h_max"]),
    }
    body["component_abs_max"] = deepcopy(state_bounds["component_abs_max"])
    body["active_amplitude_max"] = deepcopy(state_bounds["complex_amplitude_max"])
    body["active_density_max"] = state_bounds["density_max"]
    body["state_bounds_layout_sha256"] = _state_bounds_layout_sha256(field)
    body["state_admission_predicate"] = _STATE_ADMISSION_PREDICATE
    body["conversion_domain_sha256"] = _stability_conversion_domain_sha256(
        field,
        clock,
    )
    body["derivation_sha256"] = _stability_derivation_sha256(
        geometry_sha256,
        metric_sha256,
        transform_sha256,
    )
    body["self_sha256"] = _self_hash(body, "cassi.qi-flow-stability-envelope.v1")
    return body

# Profile defaults intentionally exclude profile_id.  They are a schema/default
# map, not a concrete selected profile instance.
PROFILE_DEFAULTS: Mapping[str, Any] = MappingProxyType({
    "field": deepcopy(_FIELD_DEFAULTS),
    "spatial": {
        "geometry_schema": "cassi.qi-flow-periodic-sheet-geometry.v1",
        "boundary_condition": "periodic",
        "spectral_transform": "unitary-fft2.v1",
        "normalization": "ortho",
        "derivative_symbol": "literal-i-k.v1",
        "laplacian_symbol": "-(kx^2+ky^2).v1",
        "active_shapes": [[4, 8], [4, 8], [4, 8], [4, 8]],
        "active_site_order": "physical-row-major-yx.v1",
        "per_scale": [{"scale_index": index, **deepcopy(_SHEET_SPEC)} for index in range(4)],
        "metric_cell_area": [_CELL_AREA] * 4,
        "gather_scatter": "active-prefix-zero-tail.v1",
        "restriction": "identity-low-pass.v1",
        "adjoint": "metric-restricted-adjoint.v1",
        "positive_scalar_remap": "positive-conservative-overlap.v1",
        "geometry_operator_sha256": _GEOMETRY_OPERATOR_SHA256,
        "metric_sha256": _METRIC_SHA256,
        "transform_sha256": _TRANSFORM_SHA256,
    },
    "scale_geometry": {
        "state_operator": {
            "scale_geometry_mode": "temporal-full-rank",
            "selected_candidate_id": "temporal-full-rank",
            "selected_operator_sha256": _GEOMETRY_OPERATOR_SHA256,
            "p_operator_sha256": _P_SHA256,
            "p_adjoint_sha256": _P_ADJOINT_SHA256,
            "active_ranks": [32, 32, 32, 32],
            "nullspace_dimensions": [0, 0, 0, 0],
        },
        "capacity": {
            "scale_geometry_mode": "temporal-full-rank",
            "active_sites": [32, 32, 32, 32],
            "padded_sites": [0, 0, 0, 0],
            "active_state_bytes_at_batch_limit": 36864,
            "padded_state_bytes_at_batch_limit": 0,
            "rank_identity_sha256": _sha(_P_SPEC, "cassi.qi-flow.scale-rank.v1"),
            "cost_model_sha256": _sha({"fft2_cells_per_scale": [32, 32, 32, 32], "scale_count": 4}, "cassi.qi-flow.scale-cost.v1"),
        },
        "selection_evidence": {
            "status": "engineering-preselection",
            "candidate_mode_ids": list(_COMPARISON_PREREG["candidate_mode_ids"]),
            "comparison_preregistration_sha256": _COMPARISON_PREREG_SHA256,
            "common_fixture_set_sha256": _COMPARISON_FIXTURES_SHA256,
            "thresholds": deepcopy(_COMPARISON_PREREG["thresholds"]),
            "selection_rule": _COMPARISON_PREREG["selection_rule"],
            "decision_identity_sha256": _sha({"status": "engineering-preselection", **_COMPARISON_PREREG}, "cassi.qi-flow.scale-geometry-decision.v1"),
            "comparison_receipt_sha256": None,
        },
    },
    "dynamics": {
        "clock": deepcopy(_CLOCK_SPEC),
        "stability_envelope": deepcopy(_STABILITY_ENVELOPE_BODY),
        "coordinate_transform": deepcopy(_TRANSFORM_SPEC),
        "c_D_m_per_s": [finite_bits(value) for value in (0.15, 0.10, 0.05, 0.025)],
        "omega_D_rad_per_s": [finite_bits(value) for value in (0.08, 0.06, 0.04, 0.02)],
        "gamma_D_per_s": [finite_bits(value) for value in (0.20, 0.15, 0.10, 0.075)],
        "kappa_D": [finite_bits(value) for value in (0.020, 0.015, 0.010, 0.005)],
        "c_C_m_per_s": [finite_bits(value) for value in (0.10, 0.075, 0.05, 0.025)],
        "omega_C_rad_per_s": [finite_bits(value) for value in (0.05, 0.04, 0.03, 0.02)],
        "gamma_C_per_s": [finite_bits(value) for value in (0.10, 0.075, 0.05, 0.025)],
        "kappa_C": [finite_bits(value) for value in (0.010, 0.008, 0.006, 0.004)],
        "rho_floor": finite_bits(1.0e-30),
        "candidate_amplitude_cap": finite_bits(0.5),
        "candidate_numerical_tolerance": finite_bits(1.0e-10),
    },
    "conversion": {
        "schema": "cassi.qi-flow-conversion-profile.v1",
        "admitted_domain": _conversion_domain_body(_FIELD_DEFAULTS, _CLOCK_SPEC),
        "admitted_domain_sha256": _stability_conversion_domain_sha256(
            _FIELD_DEFAULTS,
            _CLOCK_SPEC,
        ),
        "proof_artifact_sha256": None,
        "release_status": "unverified-development",
        "law_id": "cassi.qi-flow-frozen-q-map.v1",
        "conversion_energy_mode": "dissipative-v1",
        "lambda_per_s": finite_bits(40.0),
        "epsilon_memory_time_s": finite_bits(1.0),
        "ema_update_mode": "exponential-physical-time-v1",
        "q_evaluation_count": 1,
        "conversion_count": 1,
        "ema_update_count": 1,
        "numerical_zero_guard": finite_bits(1.0e-9),
    },
    "scale_coupling": {
        "schema": "cassi.qi-flow-scale-coupling-profile.v1",
        "enabled": True,
        "law_id": "distributed-reciprocal-weighted-links.v1",
        "link_pairs": [[0, 1], [1, 2], [2, 3]],
        "p_operator_sha256": _P_SHA256,
        "p_adjoint_sha256": _P_ADJOINT_SHA256,
        "g_D_per_s2": [finite_bits(value) for value in (0.030, 0.020, 0.010)],
        "g_C_per_s2": [finite_bits(value) for value in (0.020, 0.015, 0.010)],
        "potential_quadrature": "positive-cell-metric.v1",
        "force_pullback": "weighted-adjoint-reciprocal.v1",
        "phase_current_sign": "positive-fine-to-coarse.v1",
        "absent_endpoint_links": "exact-zero.v1",
    },
    "retention": {
        "schema": "cassi.qi-flow-retention-profile.v1",
        "mode": "fading-v1",
        "slow_scale": 3,
        "a_topo": _ZERO,
        "b_topo": _ONE,
        "rotation_normalization": "a_topo^2+b_topo^2=1",
        "production_specialization": "carrier-ring-a0-b1.v1",
        "theta_0_rad": _ZERO,
        "angle_encoding": "atan2-principal-(-pi,pi].v1",
        "energy_unit": "qi-energy",
        "provenance": "cassi-fi-part2-topological-retention.v1",
        "E_topo": finite_bits(0.01),
        "lambda_ph": finite_bits(0.5),
        "lambda_core": finite_bits(0.5),
        "r_core": finite_bits(0.01),
        "rho_ring": finite_bits(0.10),
        "rho_topo": finite_bits(0.02),
        "delta_topo_rad": finite_bits(0.05),
        "delta_topo_int": finite_bits(0.25),
        "radial_curvature_min": finite_bits(2.0e-4),
        "Delta_H_topo_min": finite_bits(1.0e-4),
        "barrier_uncertainty_guard": finite_bits(1.0e-5),
        "edge_registry": {
            **deepcopy(_EDGE_REGISTRY_SPEC),
            "self_sha256": _EDGE_REGISTRY_SHA256,
        },
        "edge_registry_sha256": _EDGE_REGISTRY_SHA256,
        "cycle_registry": {
            **deepcopy(_TORUS_REGISTRY_SPEC),
            "self_sha256": _TORUS_REGISTRY_SHA256,
        },
        "cycle_registry_sha256": _TORUS_REGISTRY_SHA256,
        "edge_weight_sum": finite_bits(float(len(_EDGE_ROWS))),
        "topology_endpoint_subdivision_sha256": _sha(
            {
                "method": "deterministic-lipschitz-interval-refinement.v1",
                "termination": "rho-and-integer-enclosures-decided",
                "unresolved": "reject",
            },
            "cassi.qi-flow.topology-endpoint-subdivision.v1",
        ),
        "phase_slip_subdivision_sha256": _sha(
            {
                "method": "deterministic-outward-interval-refinement.v1",
                "event_time": "exact-rational-bracket.v1",
                "unresolved": "reject",
            },
            "cassi.qi-flow.phase-slip-subdivision.v1",
        ),
        "topology_codebook_sha256": None,
        "barrier_certificate_sha256": None,
        "reset_operator_sha256": _sha(
            {
                "operator_id": "authenticated-topological-retention-reset.v1",
                "target": "psi_topo=rho_ring*exp(i*theta0);V_psi=0",
                "preserve": ["chi_topo", "V_chi_topo"],
            },
            "cassi.qi-flow.retention-reset-operator.v1",
        ),
        "fading_retention_comparator_profile_sha256": None,
        "fading_retention_potential": "exact-zero.v1",
        "zero_clock_transport": "declared-exact-torus-automorphism.v1",
    },
    "boundaries": {
        "descriptor": "periodic-boundary.v1",
        "permeability_profiles": [],
        "source_exposure": "registered-port-only",
        "failure_policy": "reject-before-commit",
    },
    "body_frame": {
        "frame_id": "body-frame-development-v1",
        "remap": "identity-remap.v1",
        "rotation": "identity",
        "translation": [_ZERO, _ZERO],
    },
    "action": {
        "action_contract": "field-only-action.v1",
        "max_candidates": 8,
        "selection": "deterministic-phase-conjugate-boundary.v1",
    },
    "world": {
        "world_protocol": "reference-world-v1",
        "clock_unit": "physical-rational-seconds-v1",
        "event_order": "journal-sequence-v1",
    },
    "backend_contract": {
        "backend": "torch",
        "device": "cpu",
        "dtype": "float64",
        "same_backend_continuation": True,
        "deterministic_fft_mode": "registered-replay-v1",
    },
    "capacity": {
        "max_state_bytes": 1 << 20,
        "max_receipt_bytes": 1 << 16,
        "max_checkpoint_bytes": 2 << 20,
        "max_batch_lanes": 4,
        "max_active_sites": 128,
    },
    "receipts": {
        "domain_separator": "cassi.qi-flow.receipt.v1",
        "max_parents": 16,
        "unknown_fields": "reject",
        "nullable_fields": "schema-declared-only",
    },
    "execution": {
        "clock": deepcopy(_CLOCK_SPEC),
        "schedule": deepcopy(_TIMED_SCHEDULE),
        "auxiliary_schedules": deepcopy(_AUXILIARY_SCHEDULES),
        "source_identity": deepcopy(_SOURCE_DESCRIPTOR),
        "source_identity_sha256": _SOURCE_IDENTITY_SHA256,
        "retry_policy": "same-predecessor-same-input-idempotent-v1",
        "commit_policy": "single-atomic-field-swap-v1",
    },
    "experience": {
        "schema": "cassi.qi-flow-field-experience-plan.v1",
        "adaptive_state": False,
        "measurement_only": True,
        "trajectory_receipts": "raw-predecessor-successor-required",
        "minimum_accepted_intervals": 1,
    },
    "numerical": {
        "schema": "cassi.qi-flow-numerical-certificate.v1",
        "adaptive_state": False,
        "finite_only": True,
        "interval_arithmetic": "outward-binary64-v1",
        "unresolved_policy": "reject-whole-candidate",
        "replay_tolerance": _ZERO,
    },
})


def _leaf_records(value: Any, prefix: str) -> list[dict[str, Any]]:
    if isinstance(value, Mapping):
        result: list[dict[str, Any]] = []
        for key in sorted(value, key=lambda item: item.encode("utf-8")):
            result.extend(_leaf_records(value[key], f"{prefix}/{key}"))
        return result
    if isinstance(value, list):
        value_type = "array"
    elif value is None:
        value_type = "null"
    elif isinstance(value, bool):
        value_type = "boolean"
    elif isinstance(value, int):
        value_type = "integer"
    elif isinstance(value, str) and value.startswith("f32:"):
        value_type = "finite-f32-bits"
    elif isinstance(value, str) and value.startswith("f64:"):
        value_type = "finite-f64-bits"
    elif isinstance(value, str):
        value_type = "string"
    else:
        raise PROFILE_MISMATCH(f"unsupported materialized default at {prefix}")
    return [{"json_pointer": prefix, "value_type": value_type, "nullable": value is None, "value": deepcopy(value)}]


def _leaf_pointers(value: Any, prefix: str) -> list[str]:
    return [row["json_pointer"] for row in _leaf_records(value, prefix)]

def _materialized_default_rows() -> list[dict[str, Any]]:
    return _leaf_records(dict(PROFILE_DEFAULTS), "")


PROFILE_DEFAULTS_BODY = {
    "schema": PROFILE_DEFAULTS_SCHEMA,
    "entries": _materialized_default_rows(),
}
PROFILE_DEFAULTS_BODY["self_sha256"] = _self_hash(
    PROFILE_DEFAULTS_BODY,
    PROFILE_DEFAULTS_SCHEMA,
)
PROFILE_DEFAULTS_OBJECT: Mapping[str, Any] = MappingProxyType(PROFILE_DEFAULTS_BODY)


def _owned(*paths: str) -> list[str]:
    pointers = ["/contract_root_sha256"]
    defaults = dict(PROFILE_DEFAULTS)
    for path in paths:
        parts = path.strip("/").split("/")
        value: Any = defaults
        prefix = ""
        for part in parts:
            value = value[part]
            prefix += "/" + part
        pointers.extend(_leaf_pointers(value, prefix))
    return list(dict.fromkeys(pointers))


_PROJECTION_ROWS = [
    {"name": "state_contract_sha256", "state_consuming": True, "pointers": _owned("field", "spatial", "scale_geometry/state_operator", "dynamics", "conversion", "scale_coupling", "retention", "numerical")},
    {"name": "boundary_action_sha256", "state_consuming": True, "pointers": _owned("boundaries", "body_frame", "action", "experience")},
    {"name": "world_protocol_sha256", "state_consuming": False, "pointers": _owned("world", "execution/source_identity", "experience")},
    {"name": "session_storage_sha256", "state_consuming": False, "pointers": ["/profile_id", *_owned("capacity", "execution", "experience")]},
    {"name": "provider_api_sha256", "state_consuming": False, "pointers": ["/profile_id", *_owned("receipts", "world", "action", "experience")]},
    {"name": "backend_capacity_sha256", "state_consuming": True, "pointers": _owned("backend_contract", "capacity", "field", "spatial", "scale_geometry/state_operator", "scale_geometry/capacity", "dynamics", "conversion", "scale_coupling", "retention", "numerical", "experience")},
    {"name": "security_evidence_sha256", "state_consuming": False, "pointers": ["/profile_id", *_owned("receipts", "execution", "scale_geometry/selection_evidence", "numerical", "experience")]},
]
_PROJECTION_OWNERS: dict[str, list[str]] = {}
for _projection in _PROJECTION_ROWS:
    for _pointer in _projection["pointers"]:
        _PROJECTION_OWNERS.setdefault(_pointer, []).append(_projection["name"])
_PROJECTION_FIELDS = [
    {
        "json_pointer": row["json_pointer"],
        "value_type": row["value_type"],
        "nullable": row["nullable"],
        "consumers": _PROJECTION_OWNERS[row["json_pointer"]],
    }
    for row in [
        {"json_pointer": "/profile_id", "value_type": "string", "nullable": False},
        {"json_pointer": "/contract_root_sha256", "value_type": "sha256", "nullable": False},
        *_materialized_default_rows(),
    ]
]
if any(not row["consumers"] for row in _PROJECTION_FIELDS):
    raise RuntimeError("every profile field must have at least one semantic projection")
PROJECTION_REGISTRY_BODY = {
    "schema": PROJECTION_REGISTRY_SCHEMA,
    "projection_order": list(SEMANTIC_PROJECTIONS),
    "fields": _PROJECTION_FIELDS,
    "projections": _PROJECTION_ROWS,
}
PROJECTION_REGISTRY_BODY["self_sha256"] = _self_hash(PROJECTION_REGISTRY_BODY, PROJECTION_REGISTRY_SCHEMA)
PROJECTION_REGISTRY: Mapping[str, Any] = MappingProxyType(PROJECTION_REGISTRY_BODY)


def _schema_descriptor(value: Any, *, path: str = "$") -> dict[str, Any]:
    if value is None:
        return {"type": "nullable-sha256" if path.endswith("sha256") else "null"}
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, int):
        return {"type": "integer", "minimum": -((1 << 53) - 1), "maximum": (1 << 53) - 1}
    if isinstance(value, str):
        descriptor: dict[str, Any] = {"type": "string"}
        if path.endswith("_sha256") or path.endswith("sha256"):
            descriptor["format"] = "sha256"
        elif value.startswith(("f32:", "f64:")):
            descriptor["format"] = "finite-bits"
        return descriptor
    if isinstance(value, list):
        if path == "$/spatial/per_scale":
            if not value:
                raise PROFILE_MISMATCH("profile schema requires at least one spatial sheet")
            return {
                "type": "array",
                "min_items": len(value),
                "max_items": len(value),
                "items": _schema_descriptor(value[0], path=f"{path}/*"),
            }
        topology_prefix = "$/retention"
        integer_item = {
            "type": "integer",
            "minimum": -((1 << 53) - 1),
            "maximum": (1 << 53) - 1,
        }
        if path == f"{topology_prefix}/edge_registry/edges":
            return {
                "type": "array",
                "min_items": 4,
                "max_items": 2 * int(PROFILE_DEFAULTS["field"]["mode_count"]),
                "items": _schema_descriptor(value[0], path=f"{path}/*"),
            }
        if path in {
            f"{topology_prefix}/cycle_registry/x_cycles",
            f"{topology_prefix}/cycle_registry/y_cycles",
        }:
            return {
                "type": "array",
                "min_items": 2,
                "max_items": int(PROFILE_DEFAULTS["field"]["mode_count"]),
                "items": {
                    "type": "array",
                    "min_items": 2,
                    "max_items": int(PROFILE_DEFAULTS["field"]["mode_count"]),
                    "items": integer_item,
                },
            }
        if path == f"{topology_prefix}/cycle_registry/plaquette_origins":
            return {
                "type": "array",
                "min_items": 4,
                "max_items": int(PROFILE_DEFAULTS["field"]["mode_count"]),
                "items": integer_item,
            }
        if path.endswith("/signed_frequency_bins/y") or path.endswith(
            "/signed_frequency_bins/x"
        ):
            return {
                "type": "array",
                "min_items": 1,
                "max_items": int(PROFILE_DEFAULTS["field"]["mode_count"]),
                "items": {
                    "type": "integer",
                    "minimum": -((1 << 53) - 1),
                    "maximum": (1 << 53) - 1,
                },
            }
        return {
            "type": "array",
            "min_items": len(value),
            "max_items": len(value),
            "tuple_items": [_schema_descriptor(item, path=f"{path}/{index}") for index, item in enumerate(value)],
        }
    if isinstance(value, Mapping):
        keys = sorted(value, key=lambda item: item.encode("utf-8"))
        return {
            "type": "object",
            "required_keys": keys,
            "optional_keys": [],
            "nullable_keys": [key for key in keys if value[key] is None],
            "properties": {key: _schema_descriptor(value[key], path=f"{path}/{key}") for key in keys},
        }
    raise PROFILE_MISMATCH(f"cannot describe profile schema at {path}")


def _profile_template() -> dict[str, Any]:
    body = {"profile_id": "fixture-profile", **deepcopy(dict(PROFILE_DEFAULTS))}
    body["schema"] = PROFILE_SCHEMA
    body["contract_root_sha256"] = "0" * 64
    body["semantic_subhashes"] = [
        {"name": name, "sha256": "0" * 64, "state_consuming": bool(row["state_consuming"])}
        for name, row in zip(SEMANTIC_PROJECTIONS, _PROJECTION_ROWS, strict=True)
    ]
    body["profile_sha256"] = "0" * 64
    return body



_RECEIPT_SCHEMAS = (
    "cassi.qi-flow-receipt.v1",
    "cassi.qi-flow-stage-spec.v1",
    "cassi.qi-flow-stability-envelope.v1",
    "cassi.qi-flow-packet.v1",
    "cassi.qi-flow-action.v1",
    "cassi.qi-flow-remap.v1",
    "cassi.qi-flow-ledger.v1",
    "cassi.qi-flow-step.v1",
    "cassi.qi-flow-decision.v1",
    "cassi.qi-flow-failure.v1",
    "cassi.qi-flow-checkpoint.v1",
    "cassi.qi-flow-session.v3",
    "cassi.qi-flow-backend-receipt.v1",
    "cassi.qi-flow-space-scale-receipt.v1",
    "cassi.qi-flow-hodge-receipt.v1",
    "cassi.qi-flow-retention-receipt.v1",
    "cassi.qi-flow-topology-receipt.v1",
)
_ARTIFACT_SCHEMAS = (
    "cassi.qi-flow-run-index.v1",
    "cassi.qi-flow-gate-candidate-status.v1",
    "cassi.qi-flow-independent-verification.v1",
    "cassi.qi-flow-gate-status.v1",
)
_SCHEMA_NAMES = (
    CONTRACT_ROOT_SCHEMA,
    PROFILE_SCHEMA,
    "cassi.qi-flow-state.v3",
    "cassi.qi-flow-checkpoint.v3",
    *_RECEIPT_SCHEMAS,
    *_ARTIFACT_SCHEMAS,
)

_PARENT_SETS = {
    "cassi.qi-flow-stage-spec.v1": ("state_contract_sha256", "session_storage_sha256", "backend_capacity_sha256"),
    "cassi.qi-flow-stability-envelope.v1": ("state_contract_sha256", "backend_capacity_sha256", "security_evidence_sha256"),
    "cassi.qi-flow-packet.v1": ("boundary_action_sha256", "world_protocol_sha256", "session_storage_sha256"),
    "cassi.qi-flow-action.v1": ("boundary_action_sha256", "world_protocol_sha256", "provider_api_sha256"),
    "cassi.qi-flow-remap.v1": ("state_contract_sha256", "boundary_action_sha256", "backend_capacity_sha256"),
    "cassi.qi-flow-ledger.v1": ("state_contract_sha256", "boundary_action_sha256", "world_protocol_sha256", "session_storage_sha256"),
    "cassi.qi-flow-decision.v1": ("state_contract_sha256", "boundary_action_sha256", "world_protocol_sha256", "provider_api_sha256"),
    "cassi.qi-flow-failure.v1": ("session_storage_sha256", "provider_api_sha256", "security_evidence_sha256"),
    "cassi.qi-flow-checkpoint.v1": ("state_contract_sha256", "session_storage_sha256", "backend_capacity_sha256", "security_evidence_sha256"),
    "cassi.qi-flow-session.v3": ("state_contract_sha256", "world_protocol_sha256", "session_storage_sha256", "security_evidence_sha256"),
    "cassi.qi-flow-backend-receipt.v1": ("state_contract_sha256", "backend_capacity_sha256", "security_evidence_sha256"),
    "cassi.qi-flow-space-scale-receipt.v1": ("state_contract_sha256", "backend_capacity_sha256"),
    "cassi.qi-flow-hodge-receipt.v1": ("state_contract_sha256", "backend_capacity_sha256"),
    "cassi.qi-flow-retention-receipt.v1": ("state_contract_sha256", "boundary_action_sha256", "backend_capacity_sha256"),
    "cassi.qi-flow-topology-receipt.v1": ("state_contract_sha256", "boundary_action_sha256", "backend_capacity_sha256"),
}


def _object_document(schema: str, properties: Mapping[str, Any], *, optional: Sequence[str] = (), nullable: Sequence[str] = ()) -> dict[str, Any]:
    optional_set = set(optional)
    return {
        "schema": PROFILE_SCHEMA_DOCUMENT_SCHEMA,
        "object_schema": schema,
        "required_keys": [key for key in properties if key not in optional_set],
        "optional_keys": list(optional),
        "nullable_keys": list(nullable),
        "properties": dict(properties),
    }


def _receipt_document(schema: str) -> dict[str, Any]:
    parent_descriptor = {
        "type": "object",
        "required_keys": ["name", "sha256"],
        "optional_keys": [],
        "nullable_keys": [],
        "properties": {"name": {"type": "string"}, "sha256": {"type": "string", "format": "sha256"}},
    }
    properties: dict[str, Any] = {
        "schema": {"type": "string", "enum": [schema]},
        "domain": {"type": "string"},
        "contract_root_sha256": {"type": "string", "format": "sha256"},
        "profile_sha256": {"type": "string", "format": "sha256"},
        "consumed_semantic_subhashes": {"type": "array", "min_items": 0, "max_items": 7, "items": parent_descriptor},
        "receipt_kind": {"type": "string"},
        "artifact_schema": {"type": "string"},
        "profile_state_sha256": {"type": "string", "format": "sha256"},
        "self_sha256": {"type": "string", "format": "sha256"},
    }
    if schema == "cassi.qi-flow-checkpoint.v1":
        properties.update({
            "state_schema": {"type": "string", "enum": ["cassi.qi-flow-state.v3"]},
            "checkpoint_schema": {"type": "string", "enum": ["cassi.qi-flow-checkpoint.v3"]},
            "state_sha256": {"type": "string", "format": "sha256"},
            "source_raw_sha256": {"type": "string", "format": "sha256"},
            "raw_byte_count": {"type": "integer", "minimum": 0, "maximum": MAX_CANONICAL_BYTES},
            "max_raw_bytes": {"type": "integer", "minimum": 1, "maximum": MAX_CANONICAL_BYTES},
        })
    return _object_document(schema, properties)


def _root_document() -> dict[str, Any]:
    component = {
        "type": "object",
        "required_keys": ["schema", "sha256"],
        "optional_keys": [],
        "nullable_keys": [],
        "properties": {"schema": {"type": "string"}, "sha256": {"type": "string", "format": "sha256"}},
    }
    ordered_component = {
        "type": "object",
        "required_keys": ["name", "schema", "sha256"],
        "optional_keys": [],
        "nullable_keys": [],
        "properties": {
            "name": {"type": "string"},
            "schema": {"type": "string"},
            "sha256": {"type": "string", "format": "sha256"},
        },
    }
    properties = {
        "schema": {"type": "string", "enum": [CONTRACT_ROOT_SCHEMA]},
        "contract_root_id": {"type": "string"},
        "bootstrap_codec": component,
        "canonical_codec": component,
        "schema_registry": component,
        "projection_registry": component,
        "profile_schema": component,
        "profile_defaults": component,
        "ordered_components": {
            "type": "array",
            "min_items": 6,
            "max_items": 6,
            "items": ordered_component,
        },
        "defaults_policy": {"type": "string", "enum": [DEFAULTS_POLICY]},
        "self_sha256": {"type": "string", "format": "sha256"},
    }
    return _object_document(CONTRACT_ROOT_SCHEMA, properties)


def _state_document() -> dict[str, Any]:
    digest = {"type": "string", "format": "sha256"}
    properties = {
        "schema": {"type": "string", "enum": ["cassi.qi-flow-state.v3"]},
        "layout_id": {"type": "string"},
        "profile_sha256": digest,
        "contract_root_sha256": digest,
        "state_contract_sha256": digest,
        "execution_schedule_sha256": digest,
        "topology_sha256": digest,
        "source_identity_sha256": digest,
        "backend": {"type": "string"},
        "dtype": {"type": "string", "enum": ["float32", "float64"]},
        "shape": {"type": "array", "min_items": 3, "max_items": 3, "items": {"type": "integer", "minimum": 1, "maximum": MAX_CANONICAL_BYTES}},
        "raw_byte_count": {"type": "integer", "minimum": 0, "maximum": MAX_CANONICAL_BYTES},
        "source_raw_sha256": digest,
        "state_sha256": digest,
        "self_sha256": digest,
    }
    return _object_document("cassi.qi-flow-state.v3", properties)


def _checkpoint_document() -> dict[str, Any]:
    digest = {"type": "string", "format": "sha256"}
    properties = {
        "schema": {"type": "string", "enum": ["cassi.qi-flow-checkpoint.v3"]},
        "state_schema": {"type": "string", "enum": ["cassi.qi-flow-state.v3"]},
        "state_header_sha256": digest,
        "state_sha256": digest,
        "source_raw_sha256": digest,
        "raw_byte_count": {"type": "integer", "minimum": 0, "maximum": MAX_CANONICAL_BYTES},
        "self_sha256": digest,
    }
    return _object_document("cassi.qi-flow-checkpoint.v3", properties)


def _artifact_document(schema: str) -> dict[str, Any]:
    digest = {"type": "string", "format": "sha256"}
    if schema == "cassi.qi-flow-run-index.v1":
        object_row = {
            "type": "object",
            "required_keys": ["path", "sha256", "byte_count"],
            "optional_keys": [],
            "nullable_keys": [],
            "properties": {
                "path": {"type": "string"},
                "sha256": digest,
                "byte_count": {"type": "integer", "minimum": 0, "maximum": MAX_CANONICAL_BYTES},
            },
        }
        return _object_document(schema, {
            "schema": {"type": "string", "enum": [schema]},
            "objects": {"type": "array", "min_items": 1, "max_items": 4096, "items": object_row},
            "self_sha256": digest,
        })
    if schema == "cassi.qi-flow-gate-candidate-status.v1":
        return _object_document(schema, {
            "schema": {"type": "string", "enum": [schema]},
            "gate": {"type": "string", "enum": ["G1"]},
            "status": {"type": "string", "enum": ["CANDIDATE"]},
            "contract_root_sha256": digest,
            "profile_sha256": digest,
            "identity_sha256": digest,
            "checkpoint_sha256": digest,
            "receipt_count": {"type": "integer", "minimum": 1, "maximum": 65536},
            "self_sha256": digest,
        })
    if schema == "cassi.qi-flow-independent-verification.v1":
        control_row = {
            "type": "object",
            "required_keys": ["control_id", "expected", "observed", "input_sha256", "status", "receipt_sha256"],
            "optional_keys": [],
            "nullable_keys": [],
            "properties": {
                "control_id": {"type": "string"},
                "expected": {"type": "string"},
                "observed": {"type": "string"},
                "input_sha256": digest,
                "status": {"type": "string", "enum": ["PASS"]},
                "receipt_sha256": digest,
            },
        }
        return _object_document(schema, {
            "schema": {"type": "string", "enum": [schema]},
            "gate": {"type": "string", "enum": ["G1"]},
            "status": {"type": "string", "enum": ["PASS"]},
            "run_id": digest,
            "index_sha256": digest,
            "contract_root_sha256": digest,
            "profile_sha256": digest,
            "trusted_bootstrap_source_sha256": digest,
            "verifier_source_sha256": digest,
            "recomputed_controls": {"type": "array", "min_items": 1, "max_items": 256, "items": control_row},
            "self_sha256": digest,
        })
    if schema == "cassi.qi-flow-gate-status.v1":
        return _object_document(schema, {
            "schema": {"type": "string", "enum": [schema]},
            "gate": {"type": "string", "enum": ["G1"]},
            "status": {"type": "string", "enum": ["PASS"]},
            "run_id": digest,
            "index_sha256": digest,
            "verification_sha256": digest,
            "self_sha256": digest,
        })
    raise PROFILE_MISMATCH(f"unknown artifact schema: {schema}")


def _fixture_for(schema: str, parents: Sequence[str]) -> dict[str, Any]:
    if schema in _RECEIPT_SCHEMAS:
        record: dict[str, Any] = {
            "schema": schema,
            "domain": f"cassi.qi-flow.receipt.v1:{schema}",
            "contract_root_sha256": "0" * 64,
            "profile_sha256": "1" * 64,
            "consumed_semantic_subhashes": [{"name": name, "sha256": "2" * 64} for name in parents],
            "receipt_kind": "registry-fixture",
            "artifact_schema": "cassi.qi-flow-registry-fixture.v1",
            "profile_state_sha256": "3" * 64,
        }
        if schema == "cassi.qi-flow-checkpoint.v1":
            record.update({
                "state_schema": "cassi.qi-flow-state.v3",
                "checkpoint_schema": "cassi.qi-flow-checkpoint.v3",
                "state_sha256": "4" * 64,
                "source_raw_sha256": "5" * 64,
                "raw_byte_count": 0,
                "max_raw_bytes": MAX_CANONICAL_BYTES,
            })
        record["self_sha256"] = canonical_hash(record, record["domain"])
        return record
    if schema == CONTRACT_ROOT_SCHEMA:
        record = {
            "schema": schema,
            "contract_root_id": "registry-fixture",
            "bootstrap_codec": {"schema": CONTRACT_ROOT_BOOTSTRAP_SCHEMA, "sha256": "0" * 64},
            "canonical_codec": {"schema": CANONICAL_CODEC_SCHEMA, "sha256": "0" * 64},
            "schema_registry": {"schema": SCHEMA_REGISTRY_SCHEMA, "sha256": "0" * 64},
            "projection_registry": {"schema": PROJECTION_REGISTRY_SCHEMA, "sha256": "0" * 64},
            "profile_schema_sha256": "0" * 64,
            "materialized_defaults": deepcopy(dict(PROFILE_DEFAULTS)),
            "materialized_defaults_sha256": "0" * 64,
            "defaults_policy": DEFAULTS_POLICY,
            "self_sha256": "0" * 64,
        }
        return record
    if schema == PROFILE_SCHEMA:
        return _profile_template()
    if schema == "cassi.qi-flow-state.v3":
        return {
            "schema": schema,
            "layout_id": "cassi.qi-flow-state-layout.v3",
            "profile_sha256": "0" * 64,
            "contract_root_sha256": "0" * 64,
            "state_contract_sha256": "0" * 64,
            "execution_schedule_sha256": "0" * 64,
            "topology_sha256": "0" * 64,
            "source_identity_sha256": "0" * 64,
            "backend": "cpu",
            "dtype": "float64",
            "shape": [4, 288, 1],
            "raw_byte_count": 9216,
            "source_raw_sha256": "0" * 64,
            "state_sha256": "0" * 64,
            "self_sha256": "0" * 64,
        }
    if schema == "cassi.qi-flow-checkpoint.v3":
        return {
            "schema": schema,
            "state_schema": "cassi.qi-flow-state.v3",
            "state_header_sha256": "0" * 64,
            "state_sha256": "0" * 64,
            "source_raw_sha256": "0" * 64,
            "raw_byte_count": 9216,
            "self_sha256": "0" * 64,
        }
    if schema == "cassi.qi-flow-run-index.v1":
        return {"schema": schema, "objects": [{"path": "fixture", "sha256": "0" * 64, "byte_count": 0}], "self_sha256": "0" * 64}
    if schema == "cassi.qi-flow-gate-candidate-status.v1":
        return {"schema": schema, "gate": "G1", "status": "CANDIDATE", "contract_root_sha256": "0" * 64, "profile_sha256": "0" * 64, "identity_sha256": "0" * 64, "checkpoint_sha256": "0" * 64, "receipt_count": 1, "self_sha256": "0" * 64}
    if schema == "cassi.qi-flow-independent-verification.v1":
        return {"schema": schema, "gate": "G1", "status": "PASS", "run_id": "0" * 64, "index_sha256": "0" * 64, "contract_root_sha256": "0" * 64, "profile_sha256": "0" * 64, "trusted_bootstrap_source_sha256": "0" * 64, "verifier_source_sha256": "0" * 64, "recomputed_controls": [{"control_id": "fixture", "expected": "REJECT", "observed": "REJECT", "input_sha256": "0" * 64, "status": "PASS", "receipt_sha256": "0" * 64}], "self_sha256": "0" * 64}
    if schema == "cassi.qi-flow-gate-status.v1":
        return {"schema": schema, "gate": "G1", "status": "PASS", "run_id": "0" * 64, "index_sha256": "0" * 64, "verification_sha256": "0" * 64, "self_sha256": "0" * 64}
    raise PROFILE_MISMATCH(f"unknown schema fixture: {schema}")


_REGISTRY_SOURCE_DIR = Path(__file__).resolve().with_name("cassi-fi-schema-registry")
_REGISTRY_SHARD_SCHEMA = "cassi.qi-flow-schema-registry-shard.v1"


def _load_sharded_schema_registry() -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    try:
        manifest_raw = (_REGISTRY_SOURCE_DIR / "manifest.json").read_bytes()
        manifest = canonical_json_loads(manifest_raw)
    except (OSError, CanonicalCodecError) as exc:
        raise PROFILE_MISMATCH(f"cannot load source schema registry manifest: {exc}") from exc
    expected_manifest_keys = {
        "schema",
        "version",
        "entry_keys",
        "source_hashes",
        "shards",
        "entry_hashes",
        "entry_count",
        "first_schema",
        "last_schema",
        "self_sha256",
    }
    if (
        not isinstance(manifest, Mapping)
        or set(manifest) != expected_manifest_keys
        or manifest.get("schema") != SCHEMA_REGISTRY_SCHEMA
        or manifest.get("version") != 1
        or manifest.get("entry_keys") != list(SCHEMA_REGISTRY_ENTRY_KEYS)
        or canonical_json_bytes(manifest) != manifest_raw
    ):
        raise PROFILE_MISMATCH("source schema registry manifest is not canonical")
    manifest_body = dict(manifest)
    manifest_self = manifest_body.pop("self_sha256")
    if manifest_self != canonical_hash(manifest_body, SCHEMA_REGISTRY_SCHEMA):
        raise PROFILE_MISMATCH("source schema registry manifest self hash mismatch")
    entries: list[dict[str, Any]] = []
    for row in manifest["shards"]:
        if (
            not isinstance(row, Mapping)
            or set(row)
            != {"path", "raw_sha256", "byte_count", "entry_count", "first_schema", "last_schema"}
        ):
            raise PROFILE_MISMATCH("source schema registry shard row is invalid")
        relative = row["path"]
        relative_path = Path(relative) if isinstance(relative, str) else Path()
        if (
            not isinstance(relative, str)
            or relative_path.is_absolute()
            or not relative.startswith("shards/")
            or ".." in relative_path.parts
        ):
            raise PROFILE_MISMATCH("source schema registry shard path is invalid")
        try:
            raw = (_REGISTRY_SOURCE_DIR / relative_path).read_bytes()
            shard = canonical_json_loads(raw)
        except (OSError, CanonicalCodecError) as exc:
            raise PROFILE_MISMATCH(f"cannot load source schema registry shard {relative}: {exc}") from exc
        if (
            hashlib.sha256(raw).hexdigest() != row["raw_sha256"]
            or len(raw) != row["byte_count"]
            or canonical_json_bytes(shard) != raw
            or not isinstance(shard, Mapping)
            or set(shard)
            != {"schema", "entries", "entry_count", "first_schema", "last_schema", "self_sha256"}
            or shard.get("schema") != _REGISTRY_SHARD_SCHEMA
        ):
            raise PROFILE_MISMATCH(f"source schema registry shard {relative} is invalid")
        shard_body = dict(shard)
        shard_self = shard_body.pop("self_sha256")
        if shard_self != canonical_hash(shard_body, _REGISTRY_SHARD_SCHEMA):
            raise PROFILE_MISMATCH(f"source schema registry shard {relative} self hash mismatch")
        shard_entries = shard["entries"]
        if (
            not isinstance(shard_entries, list)
            or len(shard_entries) != row["entry_count"]
            or len(shard_entries) != shard["entry_count"]
            or not shard_entries
            or shard_entries[0].get("schema") != row["first_schema"]
            or shard_entries[-1].get("schema") != row["last_schema"]
        ):
            raise PROFILE_MISMATCH(f"source schema registry shard {relative} range mismatch")
        entries.extend(deepcopy(shard_entries))
    schemas = [entry.get("schema") if isinstance(entry, Mapping) else None for entry in entries]
    expected_hashes = [
        {
            "schema": entry["schema"],
            "sha256": canonical_hash(entry, SCHEMA_REGISTRY_ENTRY_HASH_DOMAIN),
        }
        for entry in entries
        if isinstance(entry, Mapping) and set(entry) == set(SCHEMA_REGISTRY_ENTRY_KEYS)
    ]
    if (
        len(expected_hashes) != len(entries)
        or len(entries) != manifest["entry_count"]
        or schemas != sorted(schemas, key=lambda name: name.encode("utf-8", "strict"))
        or len(schemas) != len(set(schemas))
        or schemas[0] != manifest["first_schema"]
        or schemas[-1] != manifest["last_schema"]
        or expected_hashes != manifest["entry_hashes"]
    ):
        raise PROFILE_MISMATCH("source schema registry inventory or entry hashes mismatch")
    combined = {
        "schema": SCHEMA_REGISTRY_SCHEMA,
        "registry_id": "qi-flow-schema-registry-v1",
        "entries": entries,
        "self_sha256": manifest_self,
    }
    return MappingProxyType(dict(manifest)), MappingProxyType(combined)


SCHEMA_REGISTRY_MANIFEST, SCHEMA_REGISTRY = _load_sharded_schema_registry()
_PROFILE_SCHEMA_ENTRY = next(
    entry for entry in SCHEMA_REGISTRY["entries"] if entry["schema"] == PROFILE_SCHEMA
)
PROFILE_SCHEMA_DOCUMENT = MappingProxyType(deepcopy(_PROFILE_SCHEMA_ENTRY["schema_document"]))
PROFILE_SCHEMA_SHA256 = str(_PROFILE_SCHEMA_ENTRY["schema_document_sha256"])


def _build_root_payload() -> dict[str, Any]:
    codec = canonical_codec_descriptor()
    components = [
        {
            "name": "bootstrap_codec",
            "schema": CONTRACT_ROOT_BOOTSTRAP_SCHEMA,
            "sha256": canonical_hash(bootstrap_identity(), "cassi.qi-flow.bootstrap"),
        },
        {
            "name": "canonical_codec",
            "schema": CANONICAL_CODEC_SCHEMA,
            "sha256": canonical_hash(codec, CANONICAL_CODEC_SCHEMA),
        },
        {
            "name": "schema_registry",
            "schema": SCHEMA_REGISTRY_SCHEMA,
            "sha256": str(SCHEMA_REGISTRY["self_sha256"]),
        },
        {
            "name": "projection_registry",
            "schema": PROJECTION_REGISTRY_SCHEMA,
            "sha256": str(PROJECTION_REGISTRY["self_sha256"]),
        },
        {
            "name": "profile_schema",
            "schema": PROFILE_SCHEMA_DOCUMENT_SCHEMA,
            "sha256": PROFILE_SCHEMA_SHA256,
        },
        {
            "name": "profile_defaults",
            "schema": PROFILE_DEFAULTS_SCHEMA,
            "sha256": str(PROFILE_DEFAULTS_OBJECT["self_sha256"]),
        },
    ]
    root = {
        "schema": CONTRACT_ROOT_SCHEMA,
        "contract_root_id": "qi-flow-contract-root-v1",
        **{
            row["name"]: {"schema": row["schema"], "sha256": row["sha256"]}
            for row in components
        },
        "ordered_components": components,
        "defaults_policy": DEFAULTS_POLICY,
    }
    root["self_sha256"] = _self_hash(root, CONTRACT_ROOT_BOOTSTRAP_SCHEMA)
    return root


@dataclass(frozen=True)
class ContractRoot:
    payload: Mapping[str, Any]

    @property
    def sha256(self) -> str:
        return str(self.payload["self_sha256"])

    def to_dict(self) -> dict[str, Any]:
        return deepcopy(dict(self.payload))


def _json_pointer(profile: Mapping[str, Any], pointer: str) -> Any:
    if not pointer.startswith("/"):
        raise PROFILE_MISMATCH(f"invalid profile pointer: {pointer}")
    current: Any = profile
    for token in pointer[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, Mapping):
            if token not in current:
                raise PROFILE_MISMATCH(f"profile pointer is absent: {pointer}")
            current = current[token]
        elif isinstance(current, list):
            try:
                index = int(token, 10)
            except ValueError as exc:
                raise PROFILE_MISMATCH(f"profile pointer has noninteger array index: {pointer}") from exc
            if index < 0 or index >= len(current):
                raise PROFILE_MISMATCH(f"profile pointer index is absent: {pointer}")
            current = current[index]
        else:
            raise PROFILE_MISMATCH(f"profile pointer descends through scalar: {pointer}")
    return current


def _projection_value(profile: Mapping[str, Any], pointers: Sequence[str]) -> dict[str, Any]:
    return {
        "members": [{"pointer": pointer, "value": _json_pointer(profile, pointer)} for pointer in pointers]
    }


def _validate_descriptor(value: Any, descriptor: Mapping[str, Any], *, path: str) -> None:
    kind = descriptor.get("type")
    if kind == "nullable-sha256":
        if value is not None and (not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value)):
            raise PROFILE_MISMATCH(f"{path} must be null or lowercase sha256")
        return
    if kind == "null":
        if value is not None:
            raise PROFILE_MISMATCH(f"{path} must be null")
        return
    if kind == "boolean":
        if not isinstance(value, bool):
            raise PROFILE_MISMATCH(f"{path} must be boolean")
        return
    if kind == "integer":
        if not isinstance(value, int) or isinstance(value, bool) or not descriptor["minimum"] <= value <= descriptor["maximum"]:
            raise PROFILE_MISMATCH(f"{path} must be bounded integer")
        return
    if kind == "string":
        if not isinstance(value, str):
            raise PROFILE_MISMATCH(f"{path} must be string")
        if "enum" in descriptor and value not in descriptor["enum"]:
            raise PROFILE_MISMATCH(f"{path} is outside its enum")
        if descriptor.get("format") == "sha256" and (len(value) != 64 or any(char not in "0123456789abcdef" for char in value)):
            raise PROFILE_MISMATCH(f"{path} must be lowercase sha256")
        if descriptor.get("format") == "finite-bits":
            finite_float(value, name=path)
        return
    if kind == "array":
        if not isinstance(value, list) or not descriptor["min_items"] <= len(value) <= descriptor["max_items"]:
            raise PROFILE_MISMATCH(f"{path} has wrong array extent")
        if "tuple_items" in descriptor:
            if len(value) != len(descriptor["tuple_items"]):
                raise PROFILE_MISMATCH(f"{path} has wrong tuple extent")
            for index, (item, child) in enumerate(zip(value, descriptor["tuple_items"], strict=True)):
                _validate_descriptor(item, child, path=f"{path}/{index}")
        else:
            for index, item in enumerate(value):
                _validate_descriptor(item, descriptor["items"], path=f"{path}/{index}")
        return
    if kind == "object":
        if not isinstance(value, Mapping):
            raise PROFILE_MISMATCH(f"{path} must be object")
        required = set(descriptor["required_keys"])
        optional = set(descriptor["optional_keys"])
        keys = set(value)
        if required - keys or keys - required - optional:
            raise PROFILE_MISMATCH(f"{path} exact key mismatch: missing={sorted(required-keys)!r} unknown={sorted(keys-required-optional)!r}")
        nullable = set(descriptor["nullable_keys"])
        for key in keys:
            if value[key] is None and key in nullable:
                _validate_descriptor(value[key], descriptor["properties"][key], path=f"{path}/{key}")
            else:
                _validate_descriptor(value[key], descriptor["properties"][key], path=f"{path}/{key}")
        return
    raise PROFILE_MISMATCH(f"{path} has unknown schema descriptor {kind!r}")



def _reduced_fraction(
    value: Mapping[str, Any],
    *,
    name: str,
    allow_zero: bool = False,
) -> Fraction:
    if not isinstance(value, Mapping) or set(value) != {"numerator", "denominator"}:
        raise PROFILE_MISMATCH(f"{name} must be an exact rational object")
    numerator = value["numerator"]
    denominator = value["denominator"]
    if (
        isinstance(numerator, bool)
        or not isinstance(numerator, int)
        or isinstance(denominator, bool)
        or not isinstance(denominator, int)
        or denominator <= 0
        or (numerator < 0 if allow_zero else numerator <= 0)
    ):
        raise PROFILE_MISMATCH(f"{name} has invalid rational signs")
    result = Fraction(numerator, denominator)
    if result.numerator != numerator or result.denominator != denominator:
        raise PROFILE_MISMATCH(f"{name} must be reduced canonically")
    return result


def _validate_geometry_and_laws(profile: Mapping[str, Any]) -> None:
    field = profile["field"]
    spatial = profile["spatial"]
    scale_count = int(field["scale_count"])
    mode_count = int(field["mode_count"])
    if (
        scale_count != 4
        or mode_count < 1
        or field["component_count"] != 9
        or field["component_order"] != list(COMPONENT_ORDER)
        or field["layout_id"] != "cassi.qi-flow-state-layout.v3"
        or field["dtype"] not in {"float32", "float64"}
        or field["byte_order"] != "little"
        or field["state_bounds"]["inactive_tail_value"] != _ZERO
    ):
        raise PROFILE_MISMATCH("invalid canonical one-state storage contract")
    state_bounds = field["state_bounds"]
    if (
        len(state_bounds["component_abs_max"]) != 9
        or len(state_bounds["complex_amplitude_max"]) != 4
        or any(
            finite_float(value, name="component_abs_max") <= 0.0
            for value in state_bounds["component_abs_max"]
        )
        or any(
            finite_float(value, name="complex_amplitude_max") <= 0.0
            for value in state_bounds["complex_amplitude_max"]
        )
        or finite_float(state_bounds["density_max"], name="density_max") <= 0.0
        or finite_float(state_bounds["epsilon2_ema_max"], name="epsilon2_ema_max") <= 0.0
        or state_bounds["inactive_tail_value"] != _ZERO
        or field["state_byte_limit"] != 1 << 20
    ):
        raise PROFILE_MISMATCH("field-state bound contract is incomplete or invalid")
    if (
        len(field["active_shapes"]) != scale_count
        or len(field["active_site_counts"]) != scale_count
        or field["active_shapes"] != spatial["active_shapes"]
        or len(spatial["per_scale"]) != scale_count
    ):
        raise PROFILE_MISMATCH("field/spatial scale geometry extents disagree")

    sheets: list[dict[str, Any]] = []
    active_counts: list[int] = []
    for index, shape in enumerate(field["active_shapes"]):
        if (
            not isinstance(shape, list)
            or len(shape) != 2
            or any(isinstance(item, bool) or not isinstance(item, int) or item < 1 for item in shape)
        ):
            raise PROFILE_MISMATCH("active sheet shapes must be positive [N_y,N_x]")
        ny, nx = shape
        count = ny * nx
        if count != field["active_site_counts"][index] or count > mode_count:
            raise PROFILE_MISMATCH("active shape/count/storage contract mismatch")
        sheet = spatial["per_scale"][index]
        if (
            sheet["scale_index"] != index
            or sheet["active_shape"] != shape
            or sheet["active_site_count"] != count
            or sheet["storage_mode_count"] != mode_count
            or sheet["packing"] != "m=y*N_x+x"
            or sheet["axis_order"] != ["y", "x"]
            or sheet["vector_component_order"] != ["x", "y"]
            or sheet["origin_m"] != [_ZERO, _ZERO]
            or sheet["handedness"] != "right-handed-x-y-z-out.v1"
        ):
            raise PROFILE_MISMATCH("per-scale periodic sheet convention mismatch")
        dx = finite_float(sheet["spacing_m"]["dx"], name="dx")
        dy = finite_float(sheet["spacing_m"]["dy"], name="dy")
        lx = finite_float(sheet["extent_m"]["L_x"], name="L_x")
        ly = finite_float(sheet["extent_m"]["L_y"], name="L_y")
        area = finite_float(sheet["metric_cell_area"], name="metric_cell_area")
        if (
            dx <= 0.0
            or dy <= 0.0
            or lx != dx * nx
            or ly != dy * ny
            or area != dx * dy
            or spatial["metric_cell_area"][index] != sheet["metric_cell_area"]
            or sheet["signed_frequency_bins"]
            != {
                "y": _signed_frequency_bins(ny),
                "x": _signed_frequency_bins(nx),
                "even_nyquist": "literal-negative",
            }
            or sheet["oversampling"]["factors"] != [2, 2]
            or sheet["oversampling"]["shape"] != [2 * ny, 2 * nx]
            or sheet["oversampling"]["injection"] != "complete-signed-frequency.v1"
            or finite_float(sheet["oversampling"]["alpha"], name="oversampling.alpha") != 2.0
            or sheet["oversampling"]["restriction"] != "weighted-adjoint.v1"
        ):
            raise PROFILE_MISMATCH("periodic sheet metric/FFT2/oversampling mismatch")
        sheets.append(deepcopy(dict(sheet)))
        active_counts.append(count)

    transform = profile["dynamics"]["coordinate_transform"]
    if transform != _TRANSFORM_SPEC:
        raise PROFILE_MISMATCH("Qi D/C coordinate transform or weighted metric changed")
    state_operator = profile["scale_geometry"]["state_operator"]
    if (
        state_operator["scale_geometry_mode"] != "temporal-full-rank"
        or state_operator["selected_candidate_id"] != "temporal-full-rank"
    ):
        raise PROFILE_MISMATCH("unimplemented scale geometry mode cannot enter this root")
    padded_counts = [mode_count - count for count in active_counts]
    p_spec = {
        **deepcopy(_P_SPEC),
        "active_ranks": list(active_counts),
        "nullspace_dimensions": list(padded_counts),
    }
    geometry_spec = {
        **deepcopy(_GEOMETRY_OPERATOR_SPEC),
        "sheets": sheets,
        "coordinate_transform": deepcopy(transform),
        "cross_scale": deepcopy(p_spec),
    }
    geometry_sha256 = _operator_identity("periodic-sheet-geometry.v1", geometry_spec)
    p_sha256 = _operator_identity("temporal-full-rank-p.v1", p_spec)
    p_adjoint_sha256 = _operator_identity("temporal-full-rank-p-adjoint.v1", p_spec)
    metric_sha256 = _sha(
        {
            "cell_area": list(spatial["metric_cell_area"]),
            "coordinate_weights": transform["weights"],
        },
        "cassi.qi-flow.metric.v1",
    )
    if (
        spatial["geometry_operator_sha256"] != geometry_sha256
        or spatial["metric_sha256"] != metric_sha256
        or state_operator["selected_operator_sha256"] != geometry_sha256
        or state_operator["p_operator_sha256"] != p_sha256
        or state_operator["p_adjoint_sha256"] != p_adjoint_sha256
        or spatial["transform_sha256"] != _TRANSFORM_SHA256
        or state_operator["active_ranks"] != active_counts
        or state_operator["nullspace_dimensions"] != padded_counts
    ):
        raise PROFILE_MISMATCH("geometry/P/P-adjoint/metric identities are inconsistent")

    capacity = profile["scale_geometry"]["capacity"]
    bytes_per_value = {"float32": 4, "float64": 8}[field["dtype"]]
    active_bytes = sum(active_counts) * int(field["component_count"]) * int(field["batch_limit"]) * bytes_per_value
    padded_bytes = sum(padded_counts) * int(field["component_count"]) * int(field["batch_limit"]) * bytes_per_value
    if (
        capacity["active_sites"] != active_counts
        or capacity["padded_sites"] != padded_counts
        or capacity["active_state_bytes_at_batch_limit"] != active_bytes
        or capacity["padded_state_bytes_at_batch_limit"] != padded_bytes
        or capacity["rank_identity_sha256"] != _sha(p_spec, "cassi.qi-flow.scale-rank.v1")
        or capacity["cost_model_sha256"]
        != _sha(
            {"fft2_cells_per_scale": active_counts, "scale_count": scale_count},
            "cassi.qi-flow.scale-cost.v1",
        )
    ):
        raise PROFILE_MISMATCH("scale capacity/rank/cost declaration mismatch")

    coupling = profile["scale_coupling"]
    expected_links = [[index, index + 1] for index in range(scale_count - 1)]
    if (
        coupling["schema"] != "cassi.qi-flow-scale-coupling-profile.v1"
        or coupling["law_id"] != "distributed-reciprocal-weighted-links.v1"
        or coupling["link_pairs"] != expected_links
        or coupling["p_operator_sha256"] != p_sha256
        or coupling["p_adjoint_sha256"] != p_adjoint_sha256
    ):
        raise PROFILE_MISMATCH("reciprocal scale-link profile mismatch")
    for name in ("g_D_per_s2", "g_C_per_s2"):
        values = coupling[name]
        if len(values) != scale_count - 1 or any(
            finite_float(item, name=name) <= 0.0 for item in values
        ):
            raise PROFILE_MISMATCH("reciprocal scale-link coefficients must be positive")

    dynamics = profile["dynamics"]
    for name in (
        "c_D_m_per_s",
        "omega_D_rad_per_s",
        "gamma_D_per_s",
        "kappa_D",
        "c_C_m_per_s",
        "omega_C_rad_per_s",
        "gamma_C_per_s",
        "kappa_C",
    ):
        values = dynamics[name]
        if len(values) != scale_count or any(
            finite_float(item, name=name) <= 0.0 for item in values
        ):
            raise PROFILE_MISMATCH(f"{name} must contain one positive value per scale")
    if finite_float(dynamics["rho_floor"], name="rho_floor") <= 0.0:
        raise PROFILE_MISMATCH("rho_floor must be positive")
    envelope = dynamics["stability_envelope"]
    expected_envelope = _rebind_stability_envelope(
        envelope,
        field=field,
        clock=dynamics["clock"],
        geometry_sha256=geometry_sha256,
        metric_sha256=metric_sha256,
        transform_sha256=spatial["transform_sha256"],
    )
    certificate_extension = envelope["certificate_extension_sha256"]
    if (
        envelope != expected_envelope
        or envelope["schema"] != "cassi.qi-flow-stability-envelope.v1"
        or not isinstance(envelope["envelope_id"], str)
        or not envelope["envelope_id"]
        or envelope["exact_propagator_branches"]
        != ["zero-frequency", "underdamped", "critical", "overdamped"]
        or envelope["rounding"] != "outward-binary64.v1"
        or envelope["bound_policy"]
        != "reject-before-allocation-or-candidate-write.v1"
        or len(envelope["metric_normalized_hessian_upper"]) != scale_count
        or len(envelope["spectral_operator_norm_upper"]) != scale_count
        or any(
            finite_float(item, name="metric_normalized_hessian_upper") <= 0.0
            for item in envelope["metric_normalized_hessian_upper"]
        )
        or any(
            finite_float(item, name="spectral_operator_norm_upper") <= 0.0
            for item in envelope["spectral_operator_norm_upper"]
        )
        or finite_float(
            envelope["intermediate_component_abs_max"],
            name="intermediate_component_abs_max",
        )
        < max(finite_float(item, name="component_abs_max") for item in state_bounds["component_abs_max"])
        or finite_float(envelope["admitted_work_abs_max"], name="admitted_work_abs_max") <= 0.0
        or finite_float(envelope["remap_amplification_upper"], name="remap_amplification_upper") <= 0.0
        or finite_float(envelope["numerical_uncertainty_abs"], name="numerical_uncertainty_abs") <= 0.0
        or not 0.0
        < finite_float(envelope["strict_safety_margin"], name="strict_safety_margin")
        < 1.0
        or (
            certificate_extension is not None
            and (
                not isinstance(certificate_extension, str)
                or len(certificate_extension) != 64
                or any(character not in "0123456789abcdef" for character in certificate_extension)
            )
        )
    ):
        raise PROFILE_MISMATCH("stability envelope identity/domain/bounds mismatch")

    retention = profile["retention"]
    if (
        retention["mode"] not in {"fading-v1", "topological-v1"}
        or retention["slow_scale"] != scale_count - 1
    ):
        raise PROFILE_MISMATCH("retention mode/slow-scale contract mismatch")
    a_topo = finite_float(retention["a_topo"], name="a_topo")
    b_topo = finite_float(retention["b_topo"], name="b_topo")
    if abs(a_topo * a_topo + b_topo * b_topo - 1.0) > 1.0e-15:
        raise PROFILE_MISMATCH("topological-retention rotation is not normalized")
    slow_shape = field["active_shapes"][retention["slow_scale"]]
    edge_registry = dict(retention["edge_registry"])
    edge_self = edge_registry.pop("self_sha256")
    expected_edge = _edge_registry_spec(slow_shape)
    if (
        edge_registry != expected_edge
        or edge_self != _sha(edge_registry, edge_registry["schema"])
        or retention["edge_registry_sha256"] != edge_self
    ):
        raise PROFILE_MISMATCH("topological-retention oriented-edge registry mismatch")
    cycle_registry = dict(retention["cycle_registry"])
    cycle_self = cycle_registry.pop("self_sha256")
    expected_cycles = _torus_registry_spec(slow_shape)
    if (
        cycle_registry != expected_cycles
        or cycle_self != _sha(cycle_registry, cycle_registry["schema"])
        or retention["cycle_registry_sha256"] != cycle_self
    ):
        raise PROFILE_MISMATCH("topological-retention torus cycle/plaquette registry mismatch")
    positive_topological_retention = (
        "E_topo",
        "lambda_ph",
        "lambda_core",
        "r_core",
        "rho_ring",
        "rho_topo",
        "delta_topo_rad",
        "delta_topo_int",
        "radial_curvature_min",
        "Delta_H_topo_min",
        "barrier_uncertainty_guard",
    )
    values = {
        name: finite_float(retention[name], name=name)
        for name in positive_topological_retention
    }
    if any(value <= 0.0 for value in values.values()):
        raise PROFILE_MISMATCH("topological-retention potential/tolerance values must be positive")
    if (
        values["rho_topo"] > values["rho_ring"]
        or values["delta_topo_int"] >= 0.5
        or values["barrier_uncertainty_guard"] >= values["Delta_H_topo_min"]
        or finite_float(retention["edge_weight_sum"], name="edge_weight_sum")
        != float(len(expected_edge["edges"]))
    ):
        raise PROFILE_MISMATCH("topological-retention topology/barrier inequalities fail")
    if retention["mode"] == "fading-v1":
        if retention["fading_retention_potential"] != "exact-zero.v1":
            raise PROFILE_MISMATCH("fading-retention comparator must have U_topo exact zero")
    elif (
        a_topo != 0.0
        or b_topo != 1.0
        or retention["topology_codebook_sha256"] is None
        or retention["barrier_certificate_sha256"] is None
        or retention["fading_retention_comparator_profile_sha256"] is None
    ):
        raise PROFILE_MISMATCH("release topological retention lacks specialization/certificates")
    conversion = profile["conversion"]
    expected_conversion_domain = _conversion_domain_body(field, dynamics["clock"])
    expected_conversion_domain_sha256 = _stability_conversion_domain_sha256(
        field,
        dynamics["clock"],
    )
    if (
        conversion["law_id"] != "cassi.qi-flow-frozen-q-map.v1"
        or conversion["conversion_energy_mode"] != "dissipative-v1"
        or conversion["q_evaluation_count"] != 1
        or conversion["conversion_count"] != 1
        or conversion["ema_update_count"] != 1
        or finite_float(conversion["lambda_per_s"], name="lambda_per_s") <= 0.0
        or finite_float(conversion["epsilon_memory_time_s"], name="epsilon_memory_time_s") <= 0.0
        or finite_float(conversion["numerical_zero_guard"], name="numerical_zero_guard") <= 0.0
        or conversion["schema"] != "cassi.qi-flow-conversion-profile.v1"
        or conversion["admitted_domain"] != expected_conversion_domain
        or conversion["admitted_domain_sha256"] != expected_conversion_domain_sha256
        or conversion["release_status"]
        not in {"unverified-development", "verified-release"}
        or (
            conversion["release_status"] == "unverified-development"
            and conversion["proof_artifact_sha256"] is not None
        )
        or (
            conversion["release_status"] == "verified-release"
            and conversion["proof_artifact_sha256"] is None
        )
    ):
        raise PROFILE_MISMATCH("frozen-Q/EMA conversion contract mismatch")

def _validate_profile_payload(profile: Mapping[str, Any], *, complete: bool) -> None:
    template = _profile_template() if complete else {"profile_id": "fixture-profile", **deepcopy(dict(PROFILE_DEFAULTS))}
    descriptor = _schema_descriptor(template)
    _validate_descriptor(profile, descriptor, path="$")
    _validate_geometry_and_laws(profile)
    source = profile["execution"]["source_identity"]
    source_body = dict(source)
    source_self = source_body.pop("self_sha256")
    if source_self != canonical_hash(source_body, source["schema"]) or source_self != profile["execution"]["source_identity_sha256"]:
        raise PROFILE_MISMATCH("runtime source identity is not self-consistent")
    clock = profile["execution"]["clock"]
    if clock != profile["dynamics"]["clock"]:
        raise PROFILE_MISMATCH("execution and dynamics clocks disagree")
    h_min = _reduced_fraction(clock["h_min"], name="clock.h_min")
    h_max = _reduced_fraction(clock["h_max"], name="clock.h_max")
    if h_max < h_min:
        raise PROFILE_MISMATCH("runtime rational clock interval is reversed")
    schedule_object = profile["execution"]["schedule"]
    schedule_body = dict(schedule_object)
    schedule_self = schedule_body.pop("self_sha256")
    if (
        schedule_self
        != canonical_hash(schedule_body, "cassi.qi-flow-execution-schedule.v1")
        or schedule_object != _TIMED_SCHEDULE
    ):
        raise PROFILE_MISMATCH("timed execution schedule identity/order mismatch")
    auxiliary = profile["execution"]["auxiliary_schedules"]
    if auxiliary != _AUXILIARY_SCHEDULES:
        raise PROFILE_MISMATCH("auxiliary schedule registry mismatch")
    for schedule_name, registered in auxiliary.items():
        registered_body = dict(registered)
        registered_self = registered_body.pop("self_sha256")
        if registered_self != canonical_hash(
            registered_body,
            "cassi.qi-flow-execution-schedule.v1",
        ):
            raise PROFILE_MISMATCH(
                f"auxiliary schedule {schedule_name} identity mismatch"
            )

    schedule = schedule_object["stages"]
    if [stage["ordinal"] for stage in schedule] != list(range(11)):
        raise PROFILE_MISMATCH("stage schedule ordinals must be exactly 0..10")
    clock_advances: list[Fraction] = []
    for stage in schedule:
        advance = _reduced_fraction(
            {
                "numerator": stage["clock_increment_num"],
                "denominator": stage["clock_increment_den"],
            },
            name=f"stage[{stage['ordinal']}].clock_increment",
            allow_zero=True,
        )
        effective = _reduced_fraction(
            {
                "numerator": stage["effective_duration_num"],
                "denominator": stage["effective_duration_den"],
            },
            name=f"stage[{stage['ordinal']}].effective_duration",
            allow_zero=True,
        )
        if effective > 1:
            raise PROFILE_MISMATCH("stage effective duration exceeds one accepted step")
        if (stage["transition_kind"] == "timed") != (advance > 0):
            raise PROFILE_MISMATCH("only timed stages may advance the physical clock")
        if stage["evaluate_from"] not in {
            "predecessor_state",
            "current_candidate",
            "frozen_stage_copy",
        }:
            raise PROFILE_MISMATCH("stage evaluation source is not frozen")
        clock_advances.append(advance)
        stage_body = {
            key: value
            for key, value in stage.items()
            if key not in {"schema", "operator_sha256"}
        }
        if stage["operator_sha256"] != _operator_identity(
            stage["operator_id"],
            stage_body,
        ):
            raise PROFILE_MISMATCH("stage operator identity mismatch")
    if sum(clock_advances, Fraction(0, 1)) != Fraction(1, 1):
        raise PROFILE_MISMATCH("stage schedule does not advance exactly one h")
    if schedule_object["total_clock_increment_num"] != 1 or schedule_object[
        "total_clock_increment_den"
    ] != 1:
        raise PROFILE_MISMATCH("timed schedule total clock declaration is not one h")


@dataclass(frozen=True)
class QiFlowProfile:
    payload: Mapping[str, Any]
    contract_root: ContractRoot
    profile_sha256: str
    semantic_subhashes: Mapping[str, str]
    state_layout: Mapping[str, Any]

    @property
    def contract_root_sha256(self) -> str:
        return self.contract_root.sha256

    @property
    def state_contract_sha256(self) -> str:
        return self.semantic_subhashes["state_contract_sha256"]

    @property
    def state_bounds_layout_sha256(self) -> str:
        return str(
            self.payload["dynamics"]["stability_envelope"][
                "state_bounds_layout_sha256"
            ]
        )

    @property
    def conversion_domain_sha256(self) -> str:
        return str(self.payload["conversion"]["admitted_domain_sha256"])

    @property
    def execution_schedule_sha256(self) -> str:
        return str(self.payload["execution"]["schedule"]["self_sha256"])

    @property
    def topology_sha256(self) -> str:
        return canonical_hash(
            {"spatial": self.payload["spatial"], "scale_geometry": self.payload["scale_geometry"]["state_operator"]},
            "cassi.qi-flow.topology",
        )

    @property
    def source_identity_sha256(self) -> str:
        return str(self.payload["execution"]["source_identity_sha256"])

    @property
    def backend_sha256(self) -> str:
        return canonical_hash(self.payload["backend_contract"], "cassi.qi-flow.backend")

    @classmethod
    def from_defaults(
        cls,
        *,
        profile_id: str = "qi-flow-development-v1",
        overrides: Mapping[str, Any] | None = None,
    ) -> "QiFlowProfile":
        if not isinstance(profile_id, str) or not profile_id:
            raise PROFILE_MISMATCH("profile_id must be nonempty")
        profile = deepcopy(dict(PROFILE_DEFAULTS))
        if overrides:
            _deep_merge(profile, overrides)
            _materialize_linked_profile_fields(profile, overrides)
        profile = json.loads(canonical_json_bytes(profile))
        profile["profile_id"] = profile_id
        _validate_profile_payload(profile, complete=False)
        root = ContractRoot(MappingProxyType(_build_root_payload()))
        profile["schema"] = PROFILE_SCHEMA
        profile["contract_root_sha256"] = root.sha256
        semantic: dict[str, str] = {}
        for projection in PROJECTION_REGISTRY["projections"]:
            value = {
                "projection": projection["name"],
                **_projection_value(profile, projection["pointers"]),
            }
            semantic[projection["name"]] = canonical_hash(value, "cassi.qi-flow.projection." + projection["name"])
        profile["semantic_subhashes"] = [
            {
                "name": name,
                "sha256": semantic[name],
                "state_consuming": bool(next(item for item in PROJECTION_REGISTRY["projections"] if item["name"] == name)["state_consuming"]),
            }
            for name in SEMANTIC_PROJECTIONS
        ]
        profile["profile_sha256"] = canonical_hash(profile, PROFILE_SCHEMA)
        _validate_profile_payload(profile, complete=True)
        field = profile["field"]
        layout = MappingProxyType({
            "scale_count": field["scale_count"],
            "mode_count": field["mode_count"],
            "component_count": field["component_count"],
            "shape": [field["scale_count"], field["component_count"] * field["mode_count"], None],
            "dtype": field["dtype"],
            "byte_order": field["byte_order"],
            "layout_id": field["layout_id"],
            "batch_limit": field["batch_limit"],
            "backend": profile["backend_contract"]["device"],
            "state_byte_limit": field["state_byte_limit"],
            "active_shapes": deepcopy(field["active_shapes"]),
            "active_site_counts": list(field["active_site_counts"]),
            "state_bounds": deepcopy(field["state_bounds"]),
        })
        return cls(MappingProxyType(profile), root, profile["profile_sha256"], MappingProxyType(semantic), layout)


def runtime_h_bounds(
    profile: QiFlowProfile | Mapping[str, Any],
) -> tuple[Fraction, Fraction]:
    payload = profile.payload if isinstance(profile, QiFlowProfile) else profile
    clock = payload["dynamics"]["clock"]
    return (
        _reduced_fraction(clock["h_min"], name="clock.h_min"),
        _reduced_fraction(clock["h_max"], name="clock.h_max"),
    )


def validate_runtime_h(
    profile: QiFlowProfile | Mapping[str, Any],
    rational: Mapping[str, Any],
) -> Fraction:
    value = _reduced_fraction(rational, name="runtime_h")
    h_min, h_max = runtime_h_bounds(profile)
    if value < h_min or value > h_max:
        raise PROFILE_MISMATCH("runtime_h lies outside the profile closed interval")
    return value


def _deep_merge(target: dict[str, Any], overrides: Mapping[str, Any], *, path: str = "$") -> None:
    unknown = set(overrides) - set(target)
    if unknown:
        raise PROFILE_MISMATCH(f"unknown profile override at {path}: {sorted(unknown)!r}")
    for key, value in overrides.items():
        if isinstance(target[key], dict) and isinstance(value, Mapping):
            _deep_merge(target[key], value, path=f"{path}/{key}")
        else:
            target[key] = deepcopy(value)


def _materialize_linked_profile_fields(
    profile: dict[str, Any],
    overrides: Mapping[str, Any],
) -> None:
    field_override = overrides.get("field")
    dynamics_override = overrides.get("dynamics")
    spatial_override = overrides.get("spatial")
    backend_override = overrides.get("backend_contract")
    scale_geometry_override = overrides.get("scale_geometry")
    conversion_override = overrides.get("conversion")

    field_changed = isinstance(field_override, Mapping)
    clock_changed = (
        isinstance(dynamics_override, Mapping) and "clock" in dynamics_override
    )
    geometry_changed = isinstance(spatial_override, Mapping)
    if (
        field_changed
        and isinstance(field_override, Mapping)
        and "dtype" in field_override
        and not (
            isinstance(backend_override, Mapping) and "dtype" in backend_override
        )
    ):
        profile["backend_contract"]["dtype"] = profile["field"]["dtype"]

    if field_changed and not (
        isinstance(scale_geometry_override, Mapping)
        and "capacity" in scale_geometry_override
    ):
        field = profile["field"]
        state_operator = profile["scale_geometry"]["state_operator"]
        bytes_per_value = {"float32": 4, "float64": 8}.get(field["dtype"])
        if bytes_per_value is not None:
            active_sites = list(state_operator["active_ranks"])
            padded_sites = list(state_operator["nullspace_dimensions"])
            multiplier = (
                int(field["component_count"])
                * int(field["batch_limit"])
                * bytes_per_value
            )
            profile["scale_geometry"]["capacity"][
                "active_state_bytes_at_batch_limit"
            ] = sum(active_sites) * multiplier
            profile["scale_geometry"]["capacity"][
                "padded_state_bytes_at_batch_limit"
            ] = sum(padded_sites) * multiplier

    if field_changed or clock_changed or geometry_changed:
        explicit_envelope = (
            isinstance(dynamics_override, Mapping)
            and "stability_envelope" in dynamics_override
        )
        if not explicit_envelope:
            profile["dynamics"]["stability_envelope"] = _rebind_stability_envelope(
                profile["dynamics"]["stability_envelope"],
                field=profile["field"],
                clock=profile["dynamics"]["clock"],
                geometry_sha256=profile["spatial"]["geometry_operator_sha256"],
                metric_sha256=profile["spatial"]["metric_sha256"],
                transform_sha256=profile["spatial"]["transform_sha256"],
            )

        explicit_conversion_domain = (
            isinstance(conversion_override, Mapping)
            and (
                "admitted_domain" in conversion_override
                or "admitted_domain_sha256" in conversion_override
            )
        )
        if not explicit_conversion_domain:
            profile["conversion"]["admitted_domain"] = _conversion_domain_body(
                profile["field"],
                profile["dynamics"]["clock"],
            )
            profile["conversion"][
                "admitted_domain_sha256"
            ] = _stability_conversion_domain_sha256(
                profile["field"],
                profile["dynamics"]["clock"],
            )


def _signed_frequency_bins(length: int) -> list[int]:
    if isinstance(length, bool) or not isinstance(length, int) or length < 1:
        raise PROFILE_MISMATCH("periodic sheet extent must be a positive integer")
    return list(range(0, (length + 1) // 2)) + list(range(-(length // 2), 0))


def derive_rectangular_profile_overrides(
    base: QiFlowProfile | Mapping[str, Any],
    active_shapes: Sequence[Sequence[int]],
) -> dict[str, Any]:
    """Derive every duplicated geometry/capacity identity for rectangular sheets.

    This is the only supported way to create an inactive-tail control profile.
    It changes all four physical-sheet/operator/capacity declarations together
    so a smaller active prefix cannot masquerade as the default geometry.
    """

    payload = dict(base.payload) if isinstance(base, QiFlowProfile) else dict(base)
    if "field" not in payload or "spatial" not in payload or "scale_geometry" not in payload:
        raise PROFILE_MISMATCH("rectangular override base lacks field/spatial/scale geometry")
    field = deepcopy(dict(payload["field"]))
    spatial = deepcopy(dict(payload["spatial"]))
    scale_geometry = deepcopy(dict(payload["scale_geometry"]))
    scale_coupling = deepcopy(dict(payload["scale_coupling"]))
    dynamics = deepcopy(dict(payload["dynamics"]))
    conversion = deepcopy(dict(payload["conversion"]))
    retention = deepcopy(dict(payload["retention"]))
    scale_count = int(field["scale_count"])
    mode_count = int(field["mode_count"])
    if len(active_shapes) != scale_count:
        raise PROFILE_MISMATCH("rectangular override must declare one shape per scale")

    normalized: list[list[int]] = []
    sheets: list[dict[str, Any]] = []
    active_counts: list[int] = []
    for scale_index, raw_shape in enumerate(active_shapes):
        if (
            not isinstance(raw_shape, Sequence)
            or isinstance(raw_shape, (str, bytes, bytearray))
            or len(raw_shape) != 2
        ):
            raise PROFILE_MISMATCH("each rectangular active shape must be [N_y,N_x]")
        ny, nx = raw_shape
        if (
            isinstance(ny, bool)
            or not isinstance(ny, int)
            or isinstance(nx, bool)
            or not isinstance(nx, int)
            or ny < 1
            or nx < 1
            or ny * nx > mode_count
        ):
            raise PROFILE_MISMATCH("rectangular active shape exceeds the frozen storage modes")
        shape = [ny, nx]
        count = ny * nx
        sheet = deepcopy(_SHEET_SPEC)
        dx = finite_float(sheet["spacing_m"]["dx"], name="spacing.dx")
        dy = finite_float(sheet["spacing_m"]["dy"], name="spacing.dy")
        sheet.update(
            {
                "scale_index": scale_index,
                "active_shape": shape,
                "active_site_count": count,
                "extent_m": {
                    "L_y": finite_bits(ny * dy),
                    "L_x": finite_bits(nx * dx),
                },
                "signed_frequency_bins": {
                    "y": _signed_frequency_bins(ny),
                    "x": _signed_frequency_bins(nx),
                    "even_nyquist": "literal-negative",
                },
                "oversampling": {
                    **deepcopy(sheet["oversampling"]),
                    "shape": [2 * ny, 2 * nx],
                },
            }
        )
        normalized.append(shape)
        active_counts.append(count)
        sheets.append(sheet)

    p_spec = {
        **deepcopy(_P_SPEC),
        "active_ranks": list(active_counts),
        "nullspace_dimensions": [mode_count - count for count in active_counts],
    }
    geometry_spec = {
        **deepcopy(_GEOMETRY_OPERATOR_SPEC),
        "sheets": sheets,
        "cross_scale": deepcopy(p_spec),
    }
    geometry_sha256 = _operator_identity("periodic-sheet-geometry.v1", geometry_spec)
    p_sha256 = _operator_identity("temporal-full-rank-p.v1", p_spec)
    p_adjoint_sha256 = _operator_identity("temporal-full-rank-p-adjoint.v1", p_spec)
    bytes_per_value = 4 if field["dtype"] == "float32" else 8
    component_count = int(field["component_count"])
    batch_limit = int(field["batch_limit"])
    active_bytes = sum(active_counts) * component_count * batch_limit * bytes_per_value
    padded_counts = [mode_count - count for count in active_counts]
    padded_bytes = sum(padded_counts) * component_count * batch_limit * bytes_per_value

    field["active_shapes"] = deepcopy(normalized)
    field["active_site_counts"] = list(active_counts)
    spatial["active_shapes"] = deepcopy(normalized)
    spatial["per_scale"] = sheets
    spatial["geometry_operator_sha256"] = geometry_sha256
    state_operator = scale_geometry["state_operator"]
    state_operator.update(
        {
            "selected_operator_sha256": geometry_sha256,
            "p_operator_sha256": p_sha256,
            "p_adjoint_sha256": p_adjoint_sha256,
            "active_ranks": list(active_counts),
            "nullspace_dimensions": list(padded_counts),
        }
    )
    capacity = scale_geometry["capacity"]
    capacity.update(
        {
            "active_sites": list(active_counts),
            "padded_sites": list(padded_counts),
            "active_state_bytes_at_batch_limit": active_bytes,
            "padded_state_bytes_at_batch_limit": padded_bytes,
            "rank_identity_sha256": _sha(p_spec, "cassi.qi-flow.scale-rank.v1"),
            "cost_model_sha256": _sha(
                {
                    "fft2_cells_per_scale": list(active_counts),
                    "scale_count": scale_count,
                },
                "cassi.qi-flow.scale-cost.v1",
            ),
        }
    )
    scale_coupling["p_operator_sha256"] = p_sha256
    scale_coupling["p_adjoint_sha256"] = p_adjoint_sha256
    dynamics["stability_envelope"] = _rebind_stability_envelope(
        dynamics["stability_envelope"],
        field=field,
        clock=dynamics["clock"],
        geometry_sha256=geometry_sha256,
        metric_sha256=spatial["metric_sha256"],
        transform_sha256=spatial["transform_sha256"],
    )
    conversion["admitted_domain"] = _conversion_domain_body(field, dynamics["clock"])
    conversion["admitted_domain_sha256"] = _stability_conversion_domain_sha256(
        field,
        dynamics["clock"],
    )
    slow_shape = normalized[int(retention["slow_scale"])]
    edge_registry = _edge_registry_spec(slow_shape)
    cycle_registry = _torus_registry_spec(slow_shape)
    edge_sha256 = _sha(edge_registry, edge_registry["schema"])
    cycle_sha256 = _sha(cycle_registry, cycle_registry["schema"])
    retention["edge_registry"] = {
        **edge_registry,
        "self_sha256": edge_sha256,
    }
    retention["edge_registry_sha256"] = edge_sha256
    retention["cycle_registry"] = {
        **cycle_registry,
        "self_sha256": cycle_sha256,
    }
    retention["cycle_registry_sha256"] = cycle_sha256
    retention["edge_weight_sum"] = finite_bits(float(len(edge_registry["edges"])))
    return {
        "field": field,
        "dynamics": dynamics,
        "conversion": conversion,
        "spatial": spatial,
        "scale_geometry": scale_geometry,
        "scale_coupling": scale_coupling,
        "retention": retention,
    }


def build_contract_root(profile: QiFlowProfile | None = None) -> ContractRoot:
    root = ContractRoot(MappingProxyType(_build_root_payload()))
    if profile is not None:
        if not isinstance(profile, QiFlowProfile) or profile.contract_root_sha256 != root.sha256:
            raise PROFILE_MISMATCH("profile/root identity mismatch")
    return root


def validate_contract_root(payload_or_bytes: ContractRoot | Mapping[str, Any] | bytes | bytearray | memoryview) -> ContractRoot:
    bootstrap_self_test()
    if isinstance(payload_or_bytes, ContractRoot):
        root = deepcopy(dict(payload_or_bytes.payload))
    elif isinstance(payload_or_bytes, Mapping):
        root = deepcopy(dict(payload_or_bytes))
    else:
        root = canonical_json_loads(payload_or_bytes)
        if not isinstance(root, dict):
            raise PROFILE_MISMATCH("contract root must be object")
    expected = _build_root_payload()
    if canonical_json_bytes(root) != canonical_json_bytes(expected):
        raise PROFILE_MISMATCH("contract root differs from the source-pinned bootstrap/root registries")
    return ContractRoot(MappingProxyType(root))


def validate_profile(profile: QiFlowProfile | Mapping[str, Any] | bytes | bytearray | memoryview) -> QiFlowProfile:
    if isinstance(profile, QiFlowProfile):
        candidate = deepcopy(dict(profile.payload))
    elif isinstance(profile, Mapping):
        candidate = deepcopy(dict(profile))
    else:
        candidate = canonical_json_loads(profile)
        if not isinstance(candidate, Mapping):
            raise PROFILE_MISMATCH("profile must be object")
        candidate = dict(candidate)
    _validate_profile_payload(candidate, complete=True)
    if candidate["contract_root_sha256"] != build_contract_root().sha256:
        raise PROFILE_MISMATCH("profile contract root mismatch")
    expected = QiFlowProfile.from_defaults(
        profile_id=str(candidate["profile_id"]),
        overrides={key: value for key, value in candidate.items() if key in PROFILE_DEFAULTS},
    )
    if canonical_json_bytes(candidate) != canonical_json_bytes(expected.payload):
        raise PROFILE_MISMATCH("profile semantic or self identity mismatch")
    return expected


def load_development_profile(path: Path | str = "cassi-qi-flow-development.json") -> QiFlowProfile:
    payload = canonical_json_loads(Path(path).read_bytes())
    if not isinstance(payload, Mapping) or set(payload) != {"schema", "w0_run_id", "historical_manifest_sha256", "profile"}:
        raise PROFILE_MISMATCH("development profile has wrong exact config shape")
    if payload.get("schema") != "cassi.qi-flow-development-config.v1":
        raise PROFILE_MISMATCH("legacy or unknown development profile schema")
    if payload.get("w0_run_id") != W0_RUN_ID or payload.get("historical_manifest_sha256") != W0_HISTORICAL_MANIFEST_SHA256:
        raise PROFILE_MISMATCH("development profile has wrong immutable W0 parent")
    profile = payload.get("profile")
    if not isinstance(profile, Mapping):
        raise PROFILE_MISMATCH("development profile lacks materialized profile")
    expected = QiFlowProfile.from_defaults(profile_id=str(profile.get("profile_id", "")))
    defaults_materialization = {"profile_id": expected.payload["profile_id"], **deepcopy(dict(PROFILE_DEFAULTS))}
    if canonical_json_bytes(profile) != canonical_json_bytes(defaults_materialization):
        raise PROFILE_MISMATCH("development profile is not the exact fixed bootstrap materialization")
    return expected


__all__ = [
    "CANONICAL_CODEC_SCHEMA",
    "CONTRACT_ROOT_BOOTSTRAP_SCHEMA",
    "CONTRACT_ROOT_SCHEMA",
    "PROFILE_SCHEMA",
    "SCHEMA_REGISTRY",
    "SCHEMA_DOCUMENT_HASH_DOMAIN",
    "SCHEMA_FIXTURE_SET_HASH_DOMAIN",
    "SCHEMA_MUTATION_CONTROLS_HASH_DOMAIN",
    "SCHEMA_REGISTRY_ENTRY_HASH_DOMAIN",
    "SCHEMA_REGISTRY_ENTRY_KEYS",
    "SCHEMA_OBJECT_CLASSES",
    "PROJECTION_REGISTRY",
    "PROFILE_DEFAULTS",
    "PROFILE_DEFAULTS_OBJECT",
    "PROFILE_SCHEMA_DOCUMENT",
    "PROFILE_SCHEMA_SHA256",
    "CanonicalCodecError",
    "PROFILE_MISMATCH",
    "canonical_json_bytes",
    "canonical_json_loads",
    "canonical_hash",
    "finite_bits",
    "finite_float",
    "canonical_fixture_corpus",
    "canonical_codec_descriptor",
    "bootstrap_identity",
    "bootstrap_fixture_set_sha256",
    "bootstrap_self_test",
    "ContractRoot",
    "QiFlowProfile",
    "COMPONENT_ORDER",
    "runtime_h_bounds",
    "validate_runtime_h",
    "derive_rectangular_profile_overrides",
    "build_contract_root",
    "validate_contract_root",
    "validate_profile",
    "load_development_profile",
]
