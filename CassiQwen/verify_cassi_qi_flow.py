"""Read-only independent verifier for Cassi Qi Flow identity artifacts.

This module deliberately reimplements the fixed bootstrap codec and does not
import the profile, receipt builders, field, or execution stack.  It is an
artifact oracle: every function accepts bytes or immutable-looking mappings,
performs no runtime mutation, and returns freshly materialized dictionaries.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import base64
import binascii
import hashlib
import json
import math
import os
import re
import struct
import sys
import tempfile
from fractions import Fraction
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

MAX_SCHEMA_BYTES = 65_536
MAX_LARGE_JSON_BYTES = 1 << 20
MAX_RAW_STATE_BYTES = 1 << 20
MAX_CHECKPOINT_FRAME_BYTES = 2 << 20
MAX_SCHEMA_FANOUT = 4_096
MAX_REGISTRY_ENTRIES = 45
MAX_JSON_BYTES = MAX_LARGE_JSON_BYTES
MAX_JSON_DEPTH = 64
MAX_SAFE_INTEGER = (1 << 53) - 1

CANONICAL_CODEC_SCHEMA = "cassi.canonical-json.v1"
CANONICAL_FIXTURE_SCHEMA = "cassi.qi-flow-canonical-fixtures.v1"
CONTRACT_ROOT_BOOTSTRAP_SCHEMA = "cassi.qi-flow-contract-root-bootstrap.v1"
CONTRACT_ROOT_SCHEMA = "cassi.qi-flow-contract-root.v1"
SCHEMA_REGISTRY_SCHEMA = "cassi.qi-flow-schema-registry.v1"
SCHEMA_DOCUMENT_SCHEMA = "cassi.qi-flow-schema-document.v1"
PROJECTION_REGISTRY_SCHEMA = "cassi.qi-flow-profile-projections.v1"
PROFILE_SCHEMA = "cassi.qi-flow-profile.v1"
SOURCE_IDENTITY_SCHEMA = "cassi.qi-flow-source-identity.v1"
STATE_SCHEMA_V3 = "cassi.qi-flow-state.v3"
STATE_V3_MAGIC = b"CASSI-QI-FLOW-STATE-V3\x00"
STATE_V3_TENSOR_DOMAIN = "cassi.qi-flow-state-tensor.v3"
MAX_STATE_V3_HEADER_BYTES = 64 * 1024
MAX_STATE_V3_CHECKPOINT_BYTES = 2 * 1024 * 1024
G1_IDENTITY_CANDIDATE_SCHEMA = "cassi.qi-flow-g1-identity-candidate.v1"
G1_CANDIDATE_STATUS_SCHEMA = "cassi.qi-flow-gate-candidate-status.v1"
G1_VERIFICATION_SCHEMA = "cassi.qi-flow-independent-verification.v1"
G1_VERIFICATION_STATUS_SCHEMA = "cassi.qi-flow-gate-status.v1"
PROFILE_DEFAULTS_SCHEMA = "cassi.qi-flow-profile-defaults.v1"
RUN_INDEX_SCHEMA = "cassi.qi-flow-run-index.v1"
RUN_MANIFEST_SCHEMA = "cassi.qi-flow-run-manifest.v1"
SEMANTIC_SUBHASHES_SCHEMA = "cassi.qi-flow-semantic-subhashes.v1"
G1_CANDIDATE_RESULT_SCHEMA = "cassi.qi-flow-candidate-result.v1"
G1_GATE_STATUS_SCHEMA = "cassi.qi-flow-gate-status.v1"
G1_INDEPENDENT_VERIFICATION_SCHEMA = "cassi.qi-flow-independent-verification.v1"
SOURCE_ROOT_SCHEMA = "cassi.qi-flow-contract-root-bootstrap.v1"
REGISTRY_ID = "qi-flow-schema-registry-v1"
DEFAULTS_POLICY = "release-explicit-no-omission-v1"
SCHEMA_REGISTRY_SHARD_SCHEMA = "cassi.qi-flow-schema-registry-shard.v1"
SCHEMA_REGISTRY_ENTRY_HASH_DOMAIN = "cassi.qi-flow-schema-registry-entry.v1"
SCHEMA_FIXTURE_SET_HASH_DOMAIN = "cassi.qi-flow-schema-fixture-set.v1"
SCHEMA_MUTATION_CONTROLS_HASH_DOMAIN = "cassi.qi-flow-schema-mutation-controls.v1"
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
SCHEMA_DOCUMENT_REQUIRED_KEYS = frozenset(
    {
        "schema",
        "object_schema",
        "required_keys",
        "optional_keys",
        "nullable_keys",
        "properties",
        "invariants",
    }
)
SCHEMA_DOCUMENT_KEYS = SCHEMA_DOCUMENT_REQUIRED_KEYS | frozenset(
    {
        "type",
        "rules",
        "object_class",
        "lifecycle",
        "max_encoded_bytes",
        "max_fanout",
        "semantic_parent_names",
        "hash_domain",
        "self_hash_field",
        "version",
        "additional_properties",
        "consumed_semantic_subhashes",
    }
)
ROOT_COMPONENT_SPECS = (
    ("bootstrap_codec", CONTRACT_ROOT_BOOTSTRAP_SCHEMA),
    ("canonical_codec", CANONICAL_CODEC_SCHEMA),
    ("schema_registry", SCHEMA_REGISTRY_SCHEMA),
    ("projection_registry", PROJECTION_REGISTRY_SCHEMA),
    ("profile_schema", SCHEMA_DOCUMENT_SCHEMA),
    ("profile_defaults", PROFILE_DEFAULTS_SCHEMA),
)
INDEPENDENT_VERIFIER_ID = "stdlib-schema-replay-v1"
MIGRATION_POLICY = "new-schema-version-and-contract-root-v1"
_CLOSED_ERROR_CODES = frozenset(
    {
        "SCHEMA_LITERAL_MISMATCH",
        "UNKNOWN_KEY",
        "MISSING_REQUIRED_KEY",
        "FORBIDDEN_NULL",
        "NONCANONICAL_ENCODING",
        "BYTE_LIMIT_EXCEEDED",
        "FANOUT_LIMIT_EXCEEDED",
        "SELF_HASH_MISMATCH",
        "HASH_DOMAIN_MISMATCH",
        "SEMANTIC_PARENT_SET_MISMATCH",
        "SEMANTIC_PARENT_ORDER_MISMATCH",
        "SEMANTIC_PARENT_DIGEST_MISMATCH",
        "FIXTURE_SET_HASH_MISMATCH",
        "MUTATION_CONTROLS_HASH_MISMATCH",
        "OBJECT_CLASS_MISMATCH",
        "LIFECYCLE_MISMATCH",
        "RECEIPT_ID_MISMATCH",
        "RAW_IDENTITY_MISMATCH",
        "STATE_LAYOUT_MISMATCH",
        "CHECKPOINT_FRAME_MISMATCH",
        "UNRESOLVED_REFERENCE",
    }
)
_OBJECT_CLASSES = frozenset(
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
_LIFECYCLES = frozenset(
    {
        "bootstrap",
        "immutable_spec",
        "run_frozen",
        "runtime_ephemeral",
        "content_addressed_frame",
        "transaction_evidence",
        "checkpoint_evidence",
        "gate_evidence",
        "release_evidence",
    }
)
_G1_MUTATION_CONTROLS = frozenset(
    {
        "legacy_v1_rejected",
        "legacy_v2_rejected",
        "truncated_rejected",
        "extra_tensor_rejected",
        "adaptive_map_rejected",
        "scalar_ledger_rejected",
        "profile_mutation_rejected",
        "root_mutation_rejected",
        "backend_mutation_rejected",
        "self_hash_mutation_rejected",
        "raw_mutation_rejected",
        "nonfinite_raw_rejected",
        "out_of_bounds_raw_rejected",
        "negative_epsilon2_ema_rejected",
        "inactive_tail_rejected",
        "predecessor_unchanged",
    }
)
W1_ARTIFACT_SCHEMA = "cassi.qi-flow-w1-artifact.v1"
W1_INDEX_SCHEMA = "cassi.qi-flow-run-index.v1"
BOOTSTRAP_TOOLCHAIN = "python-stdlib-strict-utf8-finite-bit-v1"
W1_SCHEMA_ORDER = (
    CONTRACT_ROOT_SCHEMA,
    PROFILE_SCHEMA,
    STATE_SCHEMA_V3,
    "cassi.qi-flow-checkpoint.v3",
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
    W1_INDEX_SCHEMA,
    G1_CANDIDATE_STATUS_SCHEMA,
    G1_VERIFICATION_SCHEMA,
    G1_VERIFICATION_STATUS_SCHEMA,
)
W2_SCHEMA_REGISTRY_SCHEMA = "cassi.qi-flow-schema-registry.w2"
W2_CONTRACT_ROOT_SCHEMA = "cassi.qi-flow-contract-root.w2"
W2_PROFILE_SCHEMA = "cassi.qi-flow-geometry-profile.w2"
W2_GEOMETRY_CONTRACT_SCHEMA = "cassi.qi-flow-periodic-sheet.w2"
W2_OPERATOR_SEMANTIC_SCHEMA = "cassi.qi-flow-geometry-operators.w2"
W2_PARENT_LINK_SCHEMA = "cassi.qi-flow-parent-link.w2"
W2_SOURCE_IDENTITY_SCHEMA = "cassi.qi-flow-source-identity.w2"
G2_GEOMETRY_CANDIDATE_SCHEMA = "cassi.qi-flow-g2-geometry-candidate.v1"
GATE_STATUS_SCHEMA = "cassi.qi-flow-gate-status.v1"
W2_ARTIFACT_SCHEMA = "cassi.qi-flow-w2-artifact.v1"
W2_INDEX_SCHEMA = "cassi.qi-flow-run-index.v1"
W2_GRID_SHAPE = (2, 4, 4)
W2_MODE_COUNT = 32
W2_AXIS_ORDER = ("Z", "Y", "X")
W2_DOMAIN_LENGTHS_M = (
    "f64:3f60624dd2f1a9fc",
    "f64:3f70624dd2f1a9fc",
    "f64:3f80624dd2f1a9fc",
)
W2_SPACINGS_M = (
    "f64:3f50624dd2f1a9fc",
    "f64:3f50624dd2f1a9fc",
    "f64:3f60624dd2f1a9fc",
)
W2_COORDINATE_ORIGIN_M = (
    "f64:0000000000000000",
    "f64:0000000000000000",
    "f64:0000000000000000",
)
W2_ERROR_TOLERANCE = "f64:3d719799812dea11"
W2_WORKSPACE_BYTE_CAP = 65536
_W2_PARENT_W1 = {
    "kind": "sealed-w1-g1",
    "run_id": "0b32868325822dc50a1e4226b5ada4ce8e1447920561f3feeaa8b8d7e68c3087",
    "path": "_diag/cassi-qi-flow-w1-final/0b32868325822dc50a1e4226b5ada4ce8e1447920561f3feeaa8b8d7e68c3087",
    "index_sha256": "f2dce7ab4005aae2e0a99542f7fc1eb7abe616f844091b48a5e0adcee58708f1",
    "contract_root_sha256": "1ba6e94fb3f996989dd770c61670aceda0e2b1c3049368c79a084e458e6acaab",
    "profile_sha256": "ff29e3b4c2c3315000d80e5f97c68e2bcbce5aa511f61d41814b8bf01753e3df",
}
_W2_GEOMETRY_NYQUIST = {
    "even_grid_first_derivative": "zero-centered-symbol",
    "second_difference": "-4/h^2",
}
_W2_GEOMETRY_DIFFERENTIAL = {
    "gradient": "centered-periodic-roll",
    "divergence": "sum_axis_first_derivatives",
    "curl": "right-handed-[z,y,x]",
    "laplacian": "Dzz+Dyy+Dxx",
    "delta_perp": "Dyy+Dxx",
    "delta_s": "Dzz",
    "delta_identity": "Delta=Delta_perp+Delta_s",
    "first_adjoint": "D_axis^*=-D_axis",
    "laplacian_adjoint": "Delta_axis^*=Delta_axis",
}
_G2_MUTATION_CONTROLS = frozenset(
    {
        "coordinate_contract_mutation_rejected",
        "lane_order_mutation_rejected",
        "operator_semantic_mutation_rejected",
        "memory_cap_mutation_rejected",
        "predecessor_unchanged",
    }
)


def _w3_f64_bits(value: float) -> str:
    """Encode one finite W3 numeric leaf as its required IEEE-754 bit string."""

    if not math.isfinite(value):
        raise ValueError("W3 numeric constants must be finite")
    return "f64:" + struct.pack(">d", 0.0 if value == 0.0 else value).hex()


W3_SCHEMA_REGISTRY_SCHEMA = "cassi.qi-flow-schema-registry.w3"
W3_CONTRACT_ROOT_SCHEMA = "cassi.qi-flow-contract-root.w3"
W3_PROFILE_SCHEMA = "cassi.qi-flow-transport-profile.w3"
W3_TRANSPORT_SEMANTIC_SCHEMA = "cassi.qi-flow-steering-transport.w3"
W3_PARENT_LINK_SCHEMA = "cassi.qi-flow-parent-link.w3"
W3_SOURCE_IDENTITY_SCHEMA = "cassi.qi-flow-source-identity.w3"
W3_G3_CANDIDATE_SCHEMA = "cassi.qi-flow-g3-transport-candidate.v1"
W3_ARTIFACT_DOMAIN = "cassi.qi-flow-w3-artifact.v1"
W3_RUN_INDEX_SCHEMA = "cassi.qi-flow-run-index.v1"
W3_STAGE_SCHEDULE_SCHEMA = "cassi.qi-flow-g3-stage-schedule.v1"
W3_RAW_STATE_SCHEMA = "cassi.qi-flow-g3-raw-state.v1"
W3_DIRECT_IDENTITY_RECEIPT_SCHEMA = "cassi.qi-flow-g3-identity-receipt.v1"
W3_DIAGNOSTICS_SCHEMA = "cassi.qi-flow-g3-transport-diagnostics.v1"
W3_SIMPLE_DIAGNOSTICS_SCHEMA = "cassi.qi-flow-g3-simple-diagnostics.v1"
W3_SOURCE_REQUEST_SCHEMA = "cassi.qi-flow-g3-source-request.v1"
W3_REPLAY_SCHEMA = "cassi.qi-flow-g3-replay.v1"
W3_REFINEMENT_SCHEMA = "cassi.qi-flow-g3-refinement.v1"
W3_LONG_HORIZON_SCHEMA = "cassi.qi-flow-g3-long-horizon.v1"
W3_FAILURE_RECEIPT_SCHEMA = "cassi.qi-flow-g3-failure-receipt.v1"
W3_WORKSPACE_BOUNDS_SCHEMA = "cassi.qi-flow-g3-workspace-bounds.v1"
W3_STABILITY_BOUNDS_SCHEMA = "cassi.qi-flow-g3-stability-bounds.v1"
W3_RAW_STATE_DOMAIN = "cassi.qi-flow-w3-raw-state.v1"
W3_PARENT_IDENTITY_DOMAIN = "cassi.qi-flow-w3-parent-identity.v1"
W3_ROOT_ID = "qi-flow-steering-transport-w3-development-v1"
W3_GRID_SHAPE = W2_GRID_SHAPE
W3_MODE_COUNT = W2_MODE_COUNT
W3_SCALE_COUNT = 4
W3_COMPONENT_COUNT = 9
W3_DTYPE = "float64"
W3_DEVICE = "cpu"
W3_LAYOUT_ID = "[S,9M,B]"
W3_H_S = _w3_f64_bits(1.0e-5)
W3_HALF_H_S = _w3_f64_bits(0.5e-5)
W3_ZERO = _w3_f64_bits(0.0)
W3_RHO_FLOOR = _w3_f64_bits(1.0e-30)
W3_AMPLITUDE_CAP = _w3_f64_bits(1_000_000.0)
W3_CANDIDATE_TOLERANCE = _w3_f64_bits(1.0e-10)
W3_PHI = _w3_f64_bits((1.0 + math.sqrt(5.0)) / 2.0)
W3_C_D_M_PER_S = (
    _w3_f64_bits(0.15),
    _w3_f64_bits(0.10),
    _w3_f64_bits(0.05),
    _w3_f64_bits(0.025),
)
W3_OMEGA_RAD_PER_S = (W3_ZERO, W3_ZERO, W3_ZERO, W3_ZERO)
W3_GAMMA_PER_S = (
    _w3_f64_bits(0.20),
    _w3_f64_bits(0.15),
    _w3_f64_bits(0.10),
    _w3_f64_bits(0.075),
)
W3_KAPPA = (W3_ZERO, W3_ZERO, W3_ZERO, W3_ZERO)
W3_MAX_SOURCE_BYTES = 0
W3_WORKSPACE_BYTE_CAP = W2_WORKSPACE_BYTE_CAP
W3_MAX_RAW_STATE_BYTES = W3_WORKSPACE_BYTE_CAP
W3_REQUIRED_SOURCE_PATHS = (
    "cassi-qi-flow-development.json",
    "cassi_qi_field.py",
    "cassi_qi_geometry.py",
    "cassi_qi_profile.py",
    "cassi_qi_transport.py",
    "run_cassi_qi_flow.py",
    "verify_cassi_qi_flow.py",
)
W3_REQUIRED_FAILURE_CASES = (
    "candidate-amplitude-cap",
    "candidate-nonfinite",
    "source-nonempty",
    "source-nonfinite",
    "source-oversized",
)
W3_G3_DIAGNOSTIC_METRICS = (
    "amplitude_max",
    "amplitude_rate_max_abs",
    "charge",
    "current_max_abs",
    "divergence_max_abs",
    "energy",
    "momentum_max_abs",
    "phase_rate_max_abs",
)
W3_G3_STAGE_ROWS = (
    {
        "ordinal": 1,
        "name": "preflight",
        "duration_s": W3_ZERO,
        "reads": ["predecessor_raw", "source_request"],
        "writes": ["preflight_receipt"],
        "dependencies": [],
        "mode": "active",
    },
    {
        "ordinal": 2,
        "name": "first_local_force_velocity_half_kick",
        "duration_s": W3_HALF_H_S,
        "reads": ["D_0", "V_D_0"],
        "writes": ["V_D_1"],
        "dependencies": ["preflight"],
        "mode": "inactive-kappa-zero",
    },
    {
        "ordinal": 3,
        "name": "first_analytic_damped_spectral_half_propagation",
        "duration_s": W3_HALF_H_S,
        "reads": ["D_0", "V_D_1"],
        "writes": ["D_2", "V_D_2"],
        "dependencies": ["first_local_force_velocity_half_kick"],
        "mode": "active",
    },
    {
        "ordinal": 4,
        "name": "centered_yang_yin_density_conversion",
        "duration_s": W3_H_S,
        "reads": ["D_2", "V_D_2", "C_0", "V_C_0"],
        "writes": ["density_conversion_receipt"],
        "dependencies": ["first_analytic_damped_spectral_half_propagation"],
        "mode": "inactive-w5-unavailable",
    },
    {
        "ordinal": 5,
        "name": "second_analytic_damped_spectral_half_propagation",
        "duration_s": W3_HALF_H_S,
        "reads": ["D_2", "V_D_2"],
        "writes": ["D_3", "V_D_3"],
        "dependencies": ["centered_yang_yin_density_conversion"],
        "mode": "active",
    },
    {
        "ordinal": 6,
        "name": "second_local_force_velocity_half_kick",
        "duration_s": W3_HALF_H_S,
        "reads": ["D_3", "V_D_3"],
        "writes": ["V_D_4"],
        "dependencies": ["second_analytic_damped_spectral_half_propagation"],
        "mode": "inactive-kappa-zero",
    },
    {
        "ordinal": 7,
        "name": "reconstruct_yang_yin_diagnostics_fail_before_commit",
        "duration_s": W3_ZERO,
        "reads": ["D_3", "V_D_4", "C_0", "V_C_0", "epsilon_0"],
        "writes": ["candidate_raw", "diagnostics", "commit_decision"],
        "dependencies": ["second_local_force_velocity_half_kick"],
        "mode": "active",
    },
)
W3_G3_STAGE_SCHEDULE = {
    "schema": W3_STAGE_SCHEDULE_SCHEMA,
    "h_s": W3_H_S,
    "substeps": 1,
    "stages": [dict(row) for row in W3_G3_STAGE_ROWS],
}
W3_G3_CANDIDATE_KEYSET = frozenset(
    {
        "schema",
        "parent_w2",
        "schema_registry_sha256",
        "transport_contract_root_sha256",
        "transport_profile_sha256",
        "transport_semantic_sha256",
        "geometry_contract_root_sha256",
        "geometry_profile_sha256",
        "geometry_contract_sha256",
        "operator_semantic_sha256",
        "parent_link_sha256",
        "source_identity_sha256",
        "state_layout",
        "initial_state",
        "final_state",
        "stage_schedule",
        "stage_schedule_sha256",
        "operator_evidence",
        "identity_receipts",
        "diagnostics",
        "mutation_controls",
        "source_request",
        "replay",
        "refinement",
        "long_horizon",
        "failure_receipts",
        "workspace_bounds",
        "stability_bounds",
        "self_sha256",
    }
)
W3_G3_STATUS_KEYSET = frozenset(
    {
        "schema",
        "gate",
        "status",
        "parent_w2",
        "schema_registry_sha256",
        "transport_contract_root_sha256",
        "transport_profile_sha256",
        "transport_semantic_sha256",
        "geometry_contract_root_sha256",
        "geometry_profile_sha256",
        "geometry_contract_sha256",
        "operator_semantic_sha256",
        "parent_link_sha256",
        "source_identity_sha256",
        "initial_state_sha256",
        "final_state_sha256",
        "candidate_sha256",
        "registered_schema_count",
        "workspace_peak_bytes",
    }
)
W3_G3_CANDIDATE_GRAMMAR = {
    "schema": W3_G3_CANDIDATE_SCHEMA,
    "keyset": tuple(sorted(W3_G3_CANDIDATE_KEYSET)),
    "state_record_keyset": ("path", "byte_count", "raw_sha256", "state_sha256"),
    "stage_schedule": W3_G3_STAGE_SCHEDULE,
    "diagnostic_metrics": W3_G3_DIAGNOSTIC_METRICS,
    "failure_cases": W3_REQUIRED_FAILURE_CASES,
}
_W3_PARENT_W2 = {
    "kind": "sealed-w2-g2",
    "run_id": "74ed3eaca52d71b43d357a115e7fc834ee8f67e6ad5453cfb2ee16242fbf5786",
    "path": "_diag/cassi-qi-flow-w2-final/74ed3eaca52d71b43d357a115e7fc834ee8f67e6ad5453cfb2ee16242fbf5786",
    "index_sha256": "76975f8fe1a22d024edaef79fab1ea9f590b17308ac4c6146a333f3350db714c",
    "contract_root_sha256": "758c38c6965c4702673f36dcca04ae8ec911783911287b74cc07b7c566e72ac6",
    "profile_sha256": "781e27606fea402fc71a69ba85243472a29ccaaa1355429ae5c6feecbe3195d6",
    "geometry_contract_sha256": "862d377360121d71e0efe2f7932e4422aa5c37eafa54fa66d75b520ecc0541aa",
    "operator_semantic_sha256": "da3a724989374a57c8a01d572b9f6664aa03b208d52fcec8be19726d9012f834",
    "candidate_sha256": "19a6777bd6d5991a0913e0cf6954e890d9d00d74713e802a4307e3457f4fa665",
}
_W3_MUTATION_CONTROLS = frozenset(
    {
        "candidate_out_of_place",
        "fail_before_commit",
        "finite_only",
        "amplitude_cap_enforced",
        "no_clipping",
        "no_tanh",
        "no_threshold",
        "no_adaptive_dt",
        "no_fallback",
        "predecessor_unchanged",
        "source_nonempty_rejected",
        "source_oversized_rejected",
        "source_nonfinite_rejected",
        "raw_state_reseal_rejected",
        "diagnostic_reseal_rejected",
        "stage_order_reseal_rejected",
        "operator_semantic_reseal_rejected",
        "index_source_tamper_rejected",
    }
)
PROFILE_DEFAULT_KEYS = (
    "field",
    "spatial",
    "scale_geometry",
    "dynamics",
    "conversion",
    "scale_coupling",
    "retention",
    "boundaries",
    "body_frame",
    "action",
    "world",
    "backend_contract",
    "capacity",
    "receipts",
    "execution",
    "experience",
    "numerical",
)
ROOT_DEFAULT_KEYS = PROFILE_DEFAULT_KEYS
_CANONICAL_FIXTURE_EXPECTATIONS = frozenset(
    {
        "ACCEPT",
        "REJECT_NONCANONICAL",
        "REJECT_DUPLICATE_KEY",
        "REJECT_DECIMAL",
        "REJECT_NONFINITE",
        "REJECT_UTF8",
        "REJECT_NEGATIVE_ZERO",
        "REJECT_INTEGER_RANGE",
        "REJECT_DEPTH",
        "REJECT_SURROGATE",
        "REJECT_TAG",
    }
)
_BOOTSTRAP_FIXTURES = (
    ("canonical-empty", "e30=", "ACCEPT"),
    (
        "canonical-control",
        "eyJ4IjoiXHUwMDAwXHUwMDA5XHUwMDBhXHUwMDFmIn0=",
        "ACCEPT",
    ),
    (
        "unicode-lookalikes",
        "eyJLIjoibGF0aW4iLCLihKoiOiJrZWx2aW4ifQ==",
        "ACCEPT",
    ),
    ("duplicate-key", "eyJ4IjoxLCJ4IjoyfQ==", "REJECT_DUPLICATE_KEY"),
    ("reordered-key", "eyJ6IjowLCJhIjowfQ==", "REJECT_NONCANONICAL"),
    ("short-control-escape", "eyJ4IjoiXG4ifQ==", "REJECT_NONCANONICAL"),
    (
        "uppercase-control-escape",
        "eyJ4IjoiXHUwMDBBIn0=",
        "REJECT_NONCANONICAL",
    ),
    ("whitespace", "eyAieCI6MH0=", "REJECT_NONCANONICAL"),
    ("decimal", "eyJ4IjoxLjB9", "REJECT_DECIMAL"),
    ("exponent", "eyJ4IjoxZTB9", "REJECT_DECIMAL"),
    ("nan-token", "eyJ4IjpOYU59", "REJECT_NONFINITE"),
    ("infinity-token", "eyJ4IjpJbmZpbml0eX0=", "REJECT_NONFINITE"),
    ("invalid-utf8", "/w==", "REJECT_UTF8"),
    ("bom", "77u/e30=", "REJECT_UTF8"),
    ("negative-zero-integer", "eyJ4IjotMH0=", "REJECT_NEGATIVE_ZERO"),
    (
        "negative-zero-tag",
        "eyJ4IjoiZjY0OjgwMDAwMDAwMDAwMDAwMDAifQ==",
        "REJECT_NEGATIVE_ZERO",
    ),
    (
        "nan-tag",
        "eyJ4IjoiZjY0OjdmZjgwMDAwMDAwMDAwMDAifQ==",
        "REJECT_NONFINITE",
    ),
    ("short-tag", "eyJ4IjoiZjY0OjAwMDAifQ==", "REJECT_TAG"),
    (
        "uppercase-tag",
        "eyJ4IjoiZjY0OjNGRjAwMDAwMDAwMDAwMDAifQ==",
        "REJECT_TAG",
    ),
    (
        "integer-too-large",
        "eyJ4Ijo5MDA3MTk5MjU0NzQwOTkyfQ==",
        "REJECT_INTEGER_RANGE",
    ),
    (
        "integer-too-small",
        "eyJ4IjotOTAwNzE5OTI1NDc0MDk5Mn0=",
        "REJECT_INTEGER_RANGE",
    ),
    ("surrogate", "eyJ4IjoiXHVkODAwIn0=", "REJECT_SURROGATE"),
    (
        "excessive-depth",
        "W1tbW1tbW1tbW1tbW1tbW1tbW1tbW1tbW1tbW1tbW1tbW1tbW1tbW1tbW1tbW1tbW1tbW1tbW1tbW1tbW1tbW1tbMF1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXQ==",
        "REJECT_DEPTH",
    ),
)

SEMANTIC_PARENT_ORDER = (
    "state_contract",
    "boundary_action",
    "world_protocol",
    "session_storage",
    "provider_api",
    "backend_capacity",
    "security_evidence",
)
SEMANTIC_PROJECTION_ORDER = tuple(
    f"{name}_sha256" for name in SEMANTIC_PARENT_ORDER
)
SEMANTIC_PARENT_FOR_PROJECTION = dict(
    zip(SEMANTIC_PROJECTION_ORDER, SEMANTIC_PARENT_ORDER, strict=True)
)
SEMANTIC_PROJECTION_FOR_PARENT = dict(
    zip(SEMANTIC_PARENT_ORDER, SEMANTIC_PROJECTION_ORDER, strict=True)
)
STATE_CONSUMING_PROJECTIONS = frozenset(
    {
        "state_contract_sha256",
        "boundary_action_sha256",
        "backend_capacity_sha256",
    }
)

CORE_RECEIPT_SCHEMAS = frozenset(
    {
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
    }
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FLOAT_BITS = re.compile(r"^f(32|64):([0-9a-f]+)$")
_LEGACY_STATE_OR_SESSION = re.compile(
    r"^cassi\.qi-flow-(?:state|checkpoint|session)\.v(?:1|2)$"
)


class VerificationError(ValueError):
    """Raised when independent validation cannot reconstruct an identity."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and _SHA256.fullmatch(value) is not None


def _require_sha256(value: Any, context: str) -> str:
    _require(_is_sha256(value), f"{context} must be a lowercase SHA-256 hex digest")
    return value


def _require_scalar_string(value: str, context: str) -> None:
    try:
        value.encode("utf-8", "strict")
    except UnicodeEncodeError as error:
        raise VerificationError(f"{context} contains an unpaired surrogate") from error
    _require(not value.startswith("\ufeff"), f"{context} must not begin with a UTF-8 BOM")
    for scalar in value:
        codepoint = ord(scalar)
        _require(
            not 0xD800 <= codepoint <= 0xDFFF,
            f"{context} contains an unpaired surrogate",
        )


def _validate_tagged_float(value: str, context: str) -> None:
    if not value.startswith(("f32:", "f64:")):
        return
    match = _FLOAT_BITS.fullmatch(value)
    _require(match is not None, f"{context} has malformed finite-bit scalar")
    width, hexadecimal = match.groups()
    expected_hex_digits = 8 if width == "32" else 16
    _require(len(hexadecimal) == expected_hex_digits, f"{context} has wrong finite-bit width")
    raw = bytes.fromhex(hexadecimal)
    scalar = struct.unpack(">f" if width == "32" else ">d", raw)[0]
    _require(math.isfinite(scalar), f"{context} finite-bit scalar is non-finite")
    sign_mask = 0x80000000 if width == "32" else 0x8000000000000000
    integer_bits = int(hexadecimal, 16)
    _require(
        not (integer_bits & sign_mask and scalar == 0.0),
        f"{context} uses noncanonical negative zero",
    )


def _validate_value(value: Any, context: str = "$", depth: int = 0) -> None:
    _require(depth <= MAX_JSON_DEPTH, "canonical JSON nesting limit exceeded")
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, int):
        _require(
            -MAX_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER,
            f"{context} integer exceeds canonical range",
        )
        return
    if isinstance(value, str):
        _require_scalar_string(value, context)
        _validate_tagged_float(value, context)
        return
    _require(not isinstance(value, float), f"{context} uses a decimal JSON float; finite bits are required")
    if isinstance(value, Mapping):
        seen: set[str] = set()
        for key, child in value.items():
            _require(isinstance(key, str), f"{context} has a non-string object key")
            _require_scalar_string(key, f"{context} object key")
            _require(key not in seen, f"{context} has duplicate object key: {key!r}")
            seen.add(key)
            _validate_value(child, f"{context}/{key}", depth + 1)
        return
    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _validate_value(child, f"{context}[{index}]", depth + 1)
        return
    raise VerificationError(f"{context} has noncanonical JSON type {type(value).__name__}")


def _quote_string(value: str) -> str:
    _require_scalar_string(value, "string")
    pieces: list[str] = ['"']
    for scalar in value:
        codepoint = ord(scalar)
        if scalar == '"':
            pieces.append('\\"')
        elif scalar == "\\":
            pieces.append("\\\\")
        elif codepoint <= 0x1F:
            pieces.append(f"\\u{codepoint:04x}")
        else:
            pieces.append(scalar)
    pieces.append('"')
    return "".join(pieces)


def _encode_canonical(value: Any, depth: int = 0) -> str:
    _require(depth <= MAX_JSON_DEPTH, "canonical JSON nesting limit exceeded")
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int) and not isinstance(value, bool):
        _require(
            -MAX_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER,
            "integer exceeds canonical range",
        )
        return str(value)
    if isinstance(value, str):
        _validate_tagged_float(value, "string")
        return _quote_string(value)
    _require(not isinstance(value, float), "decimal JSON floats are forbidden; use finite-bit strings")
    if isinstance(value, Mapping):
        pairs: list[tuple[bytes, str, Any]] = []
        seen: set[str] = set()
        for key, child in value.items():
            _require(isinstance(key, str), "object key must be a string")
            _require(key not in seen, f"duplicate object key: {key!r}")
            seen.add(key)
            _require_scalar_string(key, "object key")
            pairs.append((key.encode("utf-8"), key, child))
        pairs.sort(key=lambda item: item[0])
        return "{" + ",".join(
            _quote_string(key) + ":" + _encode_canonical(child, depth + 1)
            for _, key, child in pairs
        ) + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_encode_canonical(child, depth + 1) for child in value) + "]"
    raise VerificationError(f"unsupported canonical JSON type: {type(value).__name__}")


def canonical_json_bytes(
    value: Any,
    *,
    max_bytes: int = MAX_JSON_BYTES,
) -> bytes:
    """Encode strict canonical JSON without using runtime codec code."""

    _require(
        isinstance(max_bytes, int) and 0 < max_bytes <= MAX_LARGE_JSON_BYTES,
        "canonical JSON byte cap is invalid",
    )
    _validate_value(value)
    encoded = _encode_canonical(value).encode("utf-8", "strict")
    _require(len(encoded) <= max_bytes, "canonical JSON byte limit exceeded")
    return encoded


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise VerificationError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _parse_integer(token: str) -> int:
    _require(token != "-0", "negative zero integer is noncanonical")
    value = int(token, 10)
    _require(
        -MAX_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER,
        "integer exceeds canonical range",
    )
    return value


def _reject_decimal(token: str) -> Any:
    raise VerificationError(f"decimal/exponent JSON number is forbidden: {token}")


def _reject_constant(token: str) -> Any:
    raise VerificationError(f"nonfinite JSON constant is forbidden: {token}")


def _json_payload_bytes(
    payload: bytes | bytearray | memoryview | str,
    context: str,
    *,
    max_bytes: int = MAX_JSON_BYTES,
) -> bytes:
    if isinstance(payload, (bytes, bytearray, memoryview)):
        raw = bytes(payload)
    elif isinstance(payload, str):
        _require_scalar_string(payload, context)
        try:
            raw = payload.encode("utf-8", "strict")
        except UnicodeEncodeError as error:
            raise VerificationError(f"{context} is not strict UTF-8") from error
    else:
        raise VerificationError(f"{context} must be bytes or str")
    _require(
        not raw.startswith(b"\xef\xbb\xbf"),
        "JSON is not strict UTF-8: UTF-8 BOM is forbidden",
    )
    _require(len(raw) <= max_bytes, "JSON byte limit exceeded")
    try:
        raw.decode("utf-8", "strict")
    except UnicodeDecodeError as error:
        raise VerificationError("JSON is not strict UTF-8") from error
    return raw

def canonical_json_loads(
    payload: bytes | bytearray | memoryview | str,
    *,
    max_bytes: int = MAX_JSON_BYTES,
) -> Any:
    """Decode only strict, bytewise canonical JSON."""

    raw = _json_payload_bytes(payload, "JSON text", max_bytes=max_bytes)
    text = raw.decode("utf-8", "strict")
    try:
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_pairs,
            parse_int=_parse_integer,
            parse_float=_reject_decimal,
            parse_constant=_reject_constant,
        )
    except (json.JSONDecodeError, ValueError, VerificationError) as error:
        if isinstance(error, VerificationError):
            raise
        raise VerificationError(f"malformed JSON: {error}") from error
    _validate_value(value)
    _require(
        canonical_json_bytes(value, max_bytes=max_bytes) == raw,
        "JSON bytes are valid but not canonical",
    )
    return value


def frame(value: bytes) -> bytes:
    _require(isinstance(value, bytes), "framed value must be bytes")
    _require(len(value) <= (1 << 64) - 1, "framed value is too large")
    return len(value).to_bytes(8, "big") + value
def canonical_hash(
    value: Any,
    domain: str = "cassi.qi-flow",
    *,
    max_bytes: int = MAX_JSON_BYTES,
) -> str:
    """Compute the specified framed, domain-separated SHA-256 identity."""

    _require_scalar_string(domain, "hash domain")
    return hashlib.sha256(
        frame(domain.encode("utf-8"))
        + frame(canonical_json_bytes(value, max_bytes=max_bytes))
    ).hexdigest()


def _fixture_outcome(payload: bytes) -> str:
    try:
        canonical_json_loads(payload)
        return "ACCEPT"
    except VerificationError as error:
        message = str(error).lower()
        if "duplicate" in message:
            return "REJECT_DUPLICATE_KEY"
        if "decimal" in message or "exponent" in message:
            return "REJECT_DECIMAL"
        if "nonfinite" in message or "non-finite" in message:
            return "REJECT_NONFINITE"
        if "utf-8" in message or "bom" in message:
            return "REJECT_UTF8"
        if "negative zero" in message:
            return "REJECT_NEGATIVE_ZERO"
        if "integer exceeds" in message:
            return "REJECT_INTEGER_RANGE"
        if "nesting" in message or "depth" in message:
            return "REJECT_DEPTH"
        if "surrogate" in message:
            return "REJECT_SURROGATE"
        if "finite-bit" in message:
            return "REJECT_TAG"
        if "not canonical" in message:
            return "REJECT_NONCANONICAL"
        return "REJECT_NONCANONICAL"


def _expected_fixture_records() -> list[dict[str, str]]:
    return [
        {
            "fixture_id": fixture_id,
            "payload_base64": payload_base64,
            "expected": expected,
        }
        for fixture_id, payload_base64, expected in _BOOTSTRAP_FIXTURES
    ]


def validate_canonical_fixture_corpus(
    payload_or_bytes: Mapping[str, Any] | bytes | str,
) -> dict[str, Any]:
    """Authenticate the fixed adversarial corpus through this independent codec."""

    corpus = _canonical_object(payload_or_bytes, "canonical fixture corpus")
    _require(
        set(corpus) == {"schema", "codec_schema", "fixtures", "self_sha256"},
        "canonical fixture corpus keyset is not sealed",
    )
    _require(
        corpus["schema"] == CANONICAL_FIXTURE_SCHEMA
        and corpus["codec_schema"] == CANONICAL_CODEC_SCHEMA,
        "canonical fixture corpus schema mismatch",
    )
    fixtures = corpus["fixtures"]
    _require(isinstance(fixtures, list), "canonical fixture corpus fixtures must be an array")
    observed: list[dict[str, str]] = []
    for raw_fixture in fixtures:
        fixture = _canonical_object(raw_fixture, "canonical fixture")
        _require(
            set(fixture) == {"fixture_id", "payload_base64", "expected"},
            "canonical fixture keyset is invalid",
        )
        fixture_id = fixture["fixture_id"]
        payload_base64 = fixture["payload_base64"]
        expected = fixture["expected"]
        _require(
            isinstance(fixture_id, str) and fixture_id,
            "canonical fixture id is invalid",
        )
        _require(
            isinstance(payload_base64, str),
            f"canonical fixture payload is invalid: {fixture_id}",
        )
        _require(
            isinstance(expected, str) and expected in _CANONICAL_FIXTURE_EXPECTATIONS,
            f"canonical fixture expectation is invalid: {fixture_id}",
        )
        try:
            payload = base64.b64decode(payload_base64, validate=True)
        except (binascii.Error, ValueError) as error:
            raise VerificationError(
                f"canonical fixture base64 is invalid: {fixture_id}"
            ) from error
        _require(
            base64.b64encode(payload).decode("ascii") == payload_base64,
            f"canonical fixture base64 is not canonical: {fixture_id}",
        )
        _require(
            _fixture_outcome(payload) == expected,
            f"canonical fixture outcome mismatch: {fixture_id}",
        )
        observed.append(
            {
                "fixture_id": fixture_id,
                "payload_base64": payload_base64,
                "expected": expected,
            }
        )
    _require(
        observed == _expected_fixture_records(),
        "canonical fixture corpus is missing, extra, mutated, or reordered",
    )
    self_sha256 = _require_sha256(
        corpus["self_sha256"], "canonical fixture corpus self_sha256"
    )
    without_self = dict(corpus)
    without_self.pop("self_sha256")
    _require(
        canonical_hash(without_self, CANONICAL_FIXTURE_SCHEMA) == self_sha256,
        "canonical fixture corpus self hash mismatch",
    )
    return corpus


def _expected_canonical_codec(fixture_corpus_sha256: str) -> dict[str, Any]:
    return {
        "schema": CANONICAL_CODEC_SCHEMA,
        "version": 1,
        "encoding": "strict-utf8-no-bom",
        "key_order": "utf8-byte-lexicographic",
        "control_escape": "lowercase-u00xx",
        "integer_range": {
            "minimum": -MAX_SAFE_INTEGER,
            "maximum": MAX_SAFE_INTEGER,
        },
        "decimal_numbers": "forbidden-use-f32-f64-bit-tags",
        "finite_bit_tags": [
            {"tag": "f32", "hex_digits": 8},
            {"tag": "f64", "hex_digits": 16},
        ],
        "negative_zero": "forbidden",
        "max_bytes": MAX_JSON_BYTES,
        "max_depth": MAX_JSON_DEPTH,
        "fixture_corpus_schema": CANONICAL_FIXTURE_SCHEMA,
        "fixture_corpus_sha256": fixture_corpus_sha256,
    }


def validate_canonical_codec(
    payload_or_bytes: Mapping[str, Any] | bytes | str,
    *,
    fixture_corpus: Mapping[str, Any] | bytes | str,
) -> dict[str, Any]:
    corpus = validate_canonical_fixture_corpus(fixture_corpus)
    codec = _canonical_object(payload_or_bytes, "canonical codec")
    expected = _expected_canonical_codec(corpus["self_sha256"])
    _require(
        canonical_json_bytes(codec) == canonical_json_bytes(expected),
        "canonical codec contract mismatch",
    )
    return codec


def _canonical_object(
    payload_or_bytes: Mapping[str, Any] | bytes | str,
    context: str,
    *,
    max_bytes: int = MAX_JSON_BYTES,
) -> dict[str, Any]:
    if isinstance(payload_or_bytes, Mapping):
        value = dict(payload_or_bytes)
    else:
        raw = _json_payload_bytes(payload_or_bytes, context, max_bytes=max_bytes)
        value = canonical_json_loads(raw, max_bytes=max_bytes)
        _require(
            canonical_json_bytes(value, max_bytes=max_bytes) == raw,
            f"{context} bytes are not canonical",
        )
    _require(isinstance(value, dict), f"{context} must be a JSON object")
    _validate_value(value, context)
    return value


def _root_component(root: Mapping[str, Any], name: str, schema: str) -> dict[str, Any]:
    component = root.get(name)
    _require(isinstance(component, Mapping), f"contract root missing {name}")
    result = dict(component)
    _require(
        set(result) == {"schema", "sha256"} and result["schema"] == schema,
        f"contract root has invalid {name} component",
    )
    _require_sha256(result["sha256"], f"contract root {name}.sha256")
    return result


def validate_bootstrap_identity(
    payload_or_bytes: Mapping[str, Any] | bytes | str,
    *,
    fixture_corpus: Mapping[str, Any] | bytes | str,
) -> dict[str, Any]:
    """Validate the candidate bootstrap record against the sealed codec corpus."""

    corpus = validate_canonical_fixture_corpus(fixture_corpus)
    identity = _canonical_object(payload_or_bytes, "bootstrap identity")
    _require(
        set(identity)
        == {
            "schema",
            "source_path",
            "source_sha256",
            "toolchain",
            "fixture_set_sha256",
            "codec_descriptor_sha256",
        },
        "bootstrap identity keyset is invalid",
    )
    _require(
        identity["schema"] == CONTRACT_ROOT_BOOTSTRAP_SCHEMA,
        "bootstrap identity has wrong schema",
    )
    _require(
        identity["source_path"] == "cassi_qi_bootstrap.py",
        "bootstrap identity source path is invalid",
    )
    _require_sha256(identity["source_sha256"], "bootstrap source_sha256")
    _require(
        identity["toolchain"] == BOOTSTRAP_TOOLCHAIN,
        "bootstrap toolchain mismatch",
    )
    _require(
        identity["fixture_set_sha256"] == corpus["self_sha256"],
        "bootstrap fixture corpus identity mismatch",
    )
    _require(
        identity["codec_descriptor_sha256"]
        == canonical_hash(
            _expected_canonical_codec(corpus["self_sha256"]),
            CANONICAL_CODEC_SCHEMA,
        ),
        "bootstrap codec descriptor identity mismatch",
    )
    _require_sha256(
        identity["codec_descriptor_sha256"],
        "bootstrap codec_descriptor_sha256",
    )
    return identity


def _validate_contract_root_shape(
    payload_or_bytes: Mapping[str, Any] | bytes | str,
) -> dict[str, Any]:
    root = _canonical_object(payload_or_bytes, "contract root")
    required = {
        "schema",
        "contract_root_id",
        "defaults_policy",
        "ordered_components",
        "self_sha256",
        *(name for name, _ in ROOT_COMPONENT_SPECS),
    }
    _require(set(root) == required, "contract root keyset is not sealed")
    _require(root["schema"] == CONTRACT_ROOT_SCHEMA, "wrong contract-root schema")
    _require(
        root["contract_root_id"] == "qi-flow-contract-root-v1",
        "invalid contract_root_id",
    )
    components = [
        {"name": name, **_root_component(root, name, schema)}
        for name, schema in ROOT_COMPONENT_SPECS
    ]
    _require(
        root["ordered_components"] == components,
        "contract root component order or identity is invalid",
    )
    _require(
        root["defaults_policy"] == DEFAULTS_POLICY,
        "contract root uses unsupported defaults policy",
    )
    self_sha256 = _require_sha256(root["self_sha256"], "root self_sha256")
    without_self = dict(root)
    without_self.pop("self_sha256")
    _require(
        canonical_hash(without_self, CONTRACT_ROOT_BOOTSTRAP_SCHEMA) == self_sha256,
        "contract root self hash mismatch",
    )
    return root


def validate_contract_root(
    payload_or_bytes: Mapping[str, Any] | bytes | str,
    *,
    bootstrap_identity: Mapping[str, Any] | bytes | str,
    fixture_corpus: Mapping[str, Any] | bytes | str,
) -> dict[str, Any]:
    """Validate the profile-independent root and its bootstrap source pin."""

    root = _validate_contract_root_shape(payload_or_bytes)
    bootstrap = root["bootstrap_codec"]
    _require(
        bootstrap["sha256"]
        == canonical_hash(
            validate_bootstrap_identity(
                bootstrap_identity,
                fixture_corpus=fixture_corpus,
            ),
            "cassi.qi-flow.bootstrap",
        ),
        "contract root bootstrap source pin mismatch",
    )
    return root


def _ordered_string_list(
    value: Any,
    context: str,
    *,
    allow_empty: bool = True,
    utf8_sorted: bool = False,
) -> list[str]:
    _require(isinstance(value, list), f"{context} must be an array")
    _require(allow_empty or bool(value), f"{context} must not be empty")
    _require(
        all(isinstance(item, str) and item for item in value)
        and len(value) == len(set(value)),
        f"{context} has duplicate or invalid names",
    )
    if utf8_sorted:
        _require(
            list(value) == sorted(value, key=lambda item: item.encode("utf-8")),
            f"{context} is not UTF-8-byte sorted",
        )
    return list(value)


def _schema_suffix_version(schema: str, context: str) -> int:
    match = re.fullmatch(r".+\.v([1-9][0-9]*)", schema)
    _require(match is not None, f"{context} must end in a positive .vN suffix")
    value = int(match.group(1), 10)
    _require(value <= MAX_SAFE_INTEGER, f"{context} version exceeds canonical range")
    return value


def _validate_schema_descriptor(
    descriptor: Any,
    context: str,
    *,
    depth: int = 0,
) -> dict[str, Any]:
    _require(depth <= MAX_JSON_DEPTH, f"{context} exceeds schema descriptor depth")
    _require(isinstance(descriptor, Mapping), f"{context} must be an object")
    record = dict(descriptor)
    kind = record.get("type")
    _require(isinstance(kind, str), f"{context}.type is invalid")
    if kind == "enum":
        _require(set(record) == {"type", "values"}, f"{context} enum keyset is invalid")
        values = record["values"]
        _require(
            isinstance(values, list)
            and 1 <= len(values) <= MAX_SCHEMA_FANOUT
            and len(canonical_json_bytes(values, max_bytes=MAX_SCHEMA_BYTES))
            == len(canonical_json_bytes(list(values), max_bytes=MAX_SCHEMA_BYTES)),
            f"{context} enum values are invalid",
        )
        for index, value in enumerate(values):
            _require(
                value is None
                or value is True
                or value is False
                or (
                    isinstance(value, int)
                    and not isinstance(value, bool)
                    and -MAX_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER
                )
                or isinstance(value, str),
                f"{context}.values[{index}] is not a canonical scalar",
            )
            if isinstance(value, str):
                _require_scalar_string(value, f"{context}.values[{index}]")
        _require(
            len(
                {
                    canonical_json_bytes(value, max_bytes=MAX_SCHEMA_BYTES)
                    for value in values
                }
            )
            == len(values),
            f"{context} enum values are duplicated",
        )
        return record
    if kind == "string":
        _require(
            set(record) == {"type", "format", "max_bytes"}
            and record["format"]
            in {"plain", "id", "sha256", "json-pointer", "path"}
            and isinstance(record["max_bytes"], int)
            and not isinstance(record["max_bytes"], bool)
            and 1 <= record["max_bytes"] <= MAX_SCHEMA_BYTES,
            f"{context} string descriptor keyset/format is invalid",
        )
        return record
    if kind == "integer":
        _require(
            set(record) == {"type", "minimum", "maximum"},
            f"{context} integer descriptor keyset is invalid",
        )
        minimum = record["minimum"]
        maximum = record["maximum"]
        _require(
            isinstance(minimum, int)
            and not isinstance(minimum, bool)
            and isinstance(maximum, int)
            and not isinstance(maximum, bool)
            and -MAX_SAFE_INTEGER <= minimum <= maximum <= MAX_SAFE_INTEGER,
            f"{context} integer bounds are invalid",
        )
        return record
    if kind == "finite":
        _require(
            set(record) == {"type", "width"} and record["width"] in {"f32", "f64"},
            f"{context} finite descriptor keyset/width is invalid",
        )
        return record
    if kind == "array":
        _require(
            set(record) == {"type", "min_items", "max_items", "items"},
            f"{context} array descriptor keyset is invalid",
        )
        minimum = record["min_items"]
        maximum = record["max_items"]
        _require(
            isinstance(minimum, int)
            and not isinstance(minimum, bool)
            and isinstance(maximum, int)
            and not isinstance(maximum, bool)
            and 0 <= minimum <= maximum <= MAX_SCHEMA_FANOUT,
            f"{context} array bounds are invalid",
        )
        _validate_schema_descriptor(
            record["items"], f"{context}.items", depth=depth + 1
        )
        return record
    if kind == "tuple":
        _require(
            set(record) == {"type", "items"},
            f"{context} tuple descriptor keyset is invalid",
        )
        items = record["items"]
        _require(
            isinstance(items, list) and len(items) <= MAX_SCHEMA_FANOUT,
            f"{context} tuple items are invalid",
        )
        for index, item in enumerate(items):
            _validate_schema_descriptor(
                item, f"{context}.items[{index}]", depth=depth + 1
            )
        return record
    if kind == "object":
        _require(
            set(record)
            == {"type", "required_keys", "optional_keys", "nullable_keys", "properties"},
            f"{context} object descriptor keyset is invalid",
        )
        _validate_schema_object_contract(record, context, depth=depth + 1)
        return record
    if kind == "ref":
        _require(
            set(record) == {"type", "schema", "max_encoded_bytes"}
            and isinstance(record["schema"], str)
            and record["schema"]
            and isinstance(record["max_encoded_bytes"], int)
            and not isinstance(record["max_encoded_bytes"], bool)
            and 1 <= record["max_encoded_bytes"] <= MAX_LARGE_JSON_BYTES,
            f"{context} ref descriptor is invalid",
        )
        return record
    raise VerificationError(f"{context} has unknown descriptor type: {kind!r}")


def _validate_schema_object_contract(
    record: Mapping[str, Any],
    context: str,
    *,
    depth: int,
) -> None:
    required_keys = _ordered_string_list(
        record["required_keys"],
        f"{context}.required_keys",
        utf8_sorted=True,
    )
    optional_keys = _ordered_string_list(
        record["optional_keys"],
        f"{context}.optional_keys",
        utf8_sorted=True,
    )
    nullable_keys = _ordered_string_list(
        record["nullable_keys"],
        f"{context}.nullable_keys",
        utf8_sorted=True,
    )
    all_keys = set(required_keys) | set(optional_keys)
    _require(
        len(required_keys) <= MAX_SCHEMA_FANOUT
        and len(optional_keys) <= MAX_SCHEMA_FANOUT
        and not (set(required_keys) & set(optional_keys))
        and set(nullable_keys) <= all_keys,
        f"{context} presence sets overlap or nullable names are unknown",
    )
    properties = record["properties"]
    _require(
        isinstance(properties, Mapping)
        and len(properties) <= MAX_SCHEMA_FANOUT
        and "self_sha256" not in properties
        and set(properties) == all_keys,
        f"{context}.properties does not exactly cover declared fields",
    )
    property_names = list(properties)
    _require(
        property_names
        == sorted(property_names, key=lambda item: item.encode("utf-8")),
        f"{context}.properties is not UTF-8-byte sorted",
    )
    for name, descriptor in properties.items():
        _require(isinstance(name, str), f"{context}.properties has a non-string name")
        _validate_schema_descriptor(
            descriptor,
            f"{context}.properties.{name}",
            depth=depth + 1,
        )


def _validate_schema_document(
    document: Any,
    context: str,
) -> dict[str, Any]:
    record = _canonical_object(document, context, max_bytes=MAX_LARGE_JSON_BYTES)
    _require(
        set(record)
        == {
            "schema",
            "object_schema",
            "required_keys",
            "optional_keys",
            "nullable_keys",
            "properties",
        }
        and record["schema"] == SCHEMA_DOCUMENT_SCHEMA
        and isinstance(record["object_schema"], str)
        and record["object_schema"],
        f"{context} keyset/schema is invalid",
    )
    _validate_schema_object_contract(record, context, depth=0)
    return record


def _validate_schema_value(
    value: Any,
    descriptor: Mapping[str, Any],
    context: str,
    *,
    nullable: bool = False,
    schema_documents: Mapping[str, Mapping[str, Any]] | None = None,
) -> None:
    if "one_of" in descriptor:
        matches = 0
        for alternative in descriptor["one_of"]:
            try:
                _validate_schema_value(
                    value,
                    alternative,
                    context,
                    schema_documents=schema_documents,
                )
            except VerificationError:
                continue
            matches += 1
        _require(matches == 1, f"{context} does not match exactly one union alternative")
        return
    if "const" in descriptor and "type" not in descriptor:
        expected = descriptor["const"]
        _require(
            type(value) is type(expected)
            and canonical_json_bytes(value, max_bytes=MAX_SCHEMA_BYTES)
            == canonical_json_bytes(expected, max_bytes=MAX_SCHEMA_BYTES),
            f"{context} does not equal its constant",
        )
        return
    kind = descriptor.get("type")
    if value is None:
        _require(nullable or kind == "null", f"{context} is not nullable")
        return
    if kind == "enum":
        _require(
            any(
                canonical_json_bytes(value, max_bytes=MAX_SCHEMA_BYTES)
                == canonical_json_bytes(candidate, max_bytes=MAX_SCHEMA_BYTES)
                for candidate in descriptor["values"]
            ),
            f"{context} is outside its enum",
        )
        return
    if kind in {"string", "finite-f64-bits"}:
        _require(isinstance(value, str), f"{context} must be a string")
        _require_scalar_string(value, context)
        encoded = value.encode("utf-8")
        _require(
            descriptor.get("min_length", 0)
            <= len(value)
            <= descriptor.get("max_length", MAX_SCHEMA_BYTES)
            and descriptor.get("min_bytes", 0)
            <= len(encoded)
            <= descriptor.get("max_bytes", MAX_SCHEMA_BYTES),
            f"{context} string exceeds its bound",
        )
        if "enum" in descriptor:
            _require(value in descriptor["enum"], f"{context} is outside its enum")
        if "const" in descriptor:
            _require(value == descriptor["const"], f"{context} differs from its constant")
        pattern = descriptor.get("pattern")
        _require(
            pattern is None or re.fullmatch(pattern, value) is not None,
            f"{context} does not match its pattern",
        )
        charset = descriptor.get("charset")
        if charset == "ascii":
            try:
                value.encode("ascii", "strict")
            except UnicodeEncodeError as error:
                raise VerificationError(f"{context} is not ASCII") from error
        value_format = descriptor.get("format")
        if value_format in {"id", "identifier-v1"}:
            _require(
                re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", value)
                is not None,
                f"{context} is not an identifier",
            )
        elif value_format == "sha256":
            _require_sha256(value, context)
        elif value_format == "json-pointer":
            _require(
                value == "" or value.startswith("/"),
                f"{context} is not a JSON pointer",
            )
        elif value_format == "path":
            _safe_relative_path(value, context)
        elif kind == "finite-f64-bits" or value_format in {
            "finite-bits",
            "finite-f64",
            "finite-f64-bits",
            "finite_bits",
        }:
            _tagged_finite_value(value, context)
        elif value_format == "base64":
            try:
                decoded = base64.b64decode(value, validate=True)
            except (binascii.Error, ValueError) as error:
                raise VerificationError(f"{context} is not base64") from error
            _require(
                base64.b64encode(decoded).decode("ascii") == value
                and len(decoded)
                <= descriptor.get("max_decoded_bytes", MAX_SCHEMA_BYTES),
                f"{context} base64 is noncanonical or oversized",
            )
        return
    if kind == "integer":
        _require(
            isinstance(value, int)
            and not isinstance(value, bool)
            and descriptor.get("minimum", -MAX_SAFE_INTEGER)
            <= value
            <= descriptor.get("maximum", MAX_SAFE_INTEGER),
            f"{context} is outside its integer bounds",
        )
        if "enum" in descriptor:
            _require(value in descriptor["enum"], f"{context} is outside its enum")
        if "const" in descriptor:
            _require(value == descriptor["const"], f"{context} differs from its constant")
        return
    if kind == "boolean":
        _require(isinstance(value, bool), f"{context} must be boolean")
        if "enum" in descriptor:
            _require(value in descriptor["enum"], f"{context} is outside its enum")
        if "const" in descriptor:
            _require(value is descriptor["const"], f"{context} differs from its constant")
        return
    if kind == "nullable-sha256":
        _require_sha256(value, context)
        return
    if kind == "finite":
        _require(
            isinstance(value, str)
            and value.startswith(f"{descriptor['width']}:")
            and _tagged_finite_value(value, context) is not None,
            f"{context} is not a finite {descriptor['width']} scalar",
        )
        return
    if kind == "canonical-object":
        _require(isinstance(value, Mapping), f"{context} must be an object")
        canonical_json_bytes(value, max_bytes=MAX_SCHEMA_BYTES)
        return
    if kind == "canonical-value":
        canonical_json_bytes(value, max_bytes=MAX_SCHEMA_BYTES)
        return
    if kind == "array":
        _require(isinstance(value, list), f"{context} must be an array")
        _require(
            descriptor.get("min_items", 0)
            <= len(value)
            <= descriptor.get("max_items", MAX_SCHEMA_FANOUT),
            f"{context} array length is out of bounds",
        )
        if "tuple_items" in descriptor:
            child_descriptors = descriptor["tuple_items"]
            _require(
                len(value) == len(child_descriptors),
                f"{context} tuple length is invalid",
            )
        else:
            child_descriptors = [descriptor["items"]] * len(value)
        for index, (item, child_descriptor) in enumerate(
            zip(value, child_descriptors, strict=True)
        ):
            _validate_schema_value(
                item,
                child_descriptor,
                f"{context}[{index}]",
                schema_documents=schema_documents,
            )
        ordered_names = descriptor.get("ordered_name_enum")
        if ordered_names is not None:
            names = [
                item.get("name") if isinstance(item, Mapping) else None
                for item in value
            ]
            _require(
                len(names) == len(set(names))
                and all(name in ordered_names for name in names)
                and names == [name for name in ordered_names if name in names],
                f"{context} ordered names are invalid",
            )
        return
    if kind == "tuple":
        _require(isinstance(value, list), f"{context} must be a tuple array")
        _require(
            len(value) == len(descriptor["items"]),
            f"{context} tuple length is invalid",
        )
        for index, item in enumerate(value):
            _validate_schema_value(
                item,
                descriptor["items"][index],
                f"{context}[{index}]",
                schema_documents=schema_documents,
            )
        return
    if kind == "object":
        _require(isinstance(value, Mapping), f"{context} must be an object")
        required_keys = descriptor["required_keys"]
        optional_keys = descriptor["optional_keys"]
        nullable_keys = set(descriptor["nullable_keys"])
        _require(
            set(value) >= set(required_keys)
            and set(value) <= set(required_keys) | set(optional_keys),
            f"{context} object keyset is invalid",
        )
        for name in value:
            _validate_schema_value(
                value[name],
                descriptor["properties"][name],
                f"{context}.{name}",
                nullable=name in nullable_keys,
                schema_documents=schema_documents,
            )
        return
    if kind == "ref":
        _require(
            isinstance(value, Mapping)
            and set(value) == {"schema", "sha256"}
            and value.get("schema") == descriptor["schema"],
            f"{context} reference keyset/schema is invalid",
        )
        _require_sha256(value.get("sha256"), f"{context}.sha256")
        if schema_documents is not None:
            _require(
                descriptor["schema"] in schema_documents,
                f"{context} reference is unresolved",
            )
        return
    raise VerificationError(f"{context} has an unvalidated descriptor type {kind!r}")


def validate_schema_registry(
    payload_or_bytes: Mapping[str, Any] | bytes | str,
) -> dict[str, dict[str, Any]]:
    """Validate exact recursive schema contracts and their fixtures."""

    record = _canonical_object(payload_or_bytes, "schema registry")
    _require(
        set(record) == {"schema", "entries", "self_sha256"}
        and record["schema"] == SCHEMA_REGISTRY_SCHEMA,
        "schema registry keyset/schema is invalid",
    )
    entries_value = record["entries"]
    _require(isinstance(entries_value, list) and entries_value, "schema registry entries are invalid")
    self_sha256 = _require_sha256(record["self_sha256"], "schema registry self_sha256")
    without_self = dict(record)
    without_self.pop("self_sha256")
    _require(
        canonical_hash(without_self, SCHEMA_REGISTRY_SCHEMA) == self_sha256,
        "schema registry self hash mismatch",
    )
    parent_order = {name: index for index, name in enumerate(SEMANTIC_PARENT_ORDER)}
    entries: dict[str, dict[str, Any]] = {}
    fixture_ids: set[str] = set()
    schemas: list[str] = []
    for raw_entry in entries_value:
        entry = _canonical_object(raw_entry, "schema registry entry")
        _require(
            set(entry)
            == {
                "schema",
                "version",
                "lifecycle",
                "max_bytes",
                "semantic_parents",
                "schema_document",
                "schema_document_sha256",
                "fixture_id",
                "fixture",
                "fixture_sha256",
            },
            "schema registry entry keyset is invalid",
        )
        schema = entry["schema"]
        _require(
            isinstance(schema, str) and schema not in entries,
            "registry schema is missing or duplicate",
        )
        version = entry["version"]
        _require(
            isinstance(version, int)
            and not isinstance(version, bool)
            and version == _schema_suffix_version(schema, f"registry schema {schema}"),
            f"registry version mismatch: {schema}",
        )
        _require(
            entry["lifecycle"] == f"canonical-v{version}",
            f"registry lifecycle mismatch: {schema}",
        )
        max_bytes = entry["max_bytes"]
        expected_max_bytes = (
            MAX_JSON_BYTES if schema in W1_SCHEMA_ORDER[:4] else 65536
        )
        _require(
            isinstance(max_bytes, int)
            and not isinstance(max_bytes, bool)
            and max_bytes == expected_max_bytes,
            f"registry max_bytes invalid: {schema}",
        )
        parents = entry["semantic_parents"]
        _require(isinstance(parents, list), f"registry semantic parents are invalid: {schema}")
        _require(
            all(isinstance(name, str) and name in parent_order for name in parents)
            and len(parents) == len(set(parents))
            and parents == sorted(parents, key=parent_order.__getitem__),
            f"registry semantic parents are missing, duplicate, or reordered: {schema}",
        )
        document = _validate_schema_document(
            entry["schema_document"], f"schema document {schema}"
        )
        _require(
            document["object_schema"] == schema,
            f"schema document selects another object schema: {schema}",
        )
        _require(
            entry["schema_document_sha256"]
            == canonical_hash(document, SCHEMA_DOCUMENT_SCHEMA),
            f"schema document hash mismatch: {schema}",
        )
        _require_sha256(
            entry["schema_document_sha256"], f"schema document sha256: {schema}"
        )
        fixture_id = entry["fixture_id"]
        _require(
            isinstance(fixture_id, str)
            and fixture_id == f"{schema}:registry-fixture"
            and fixture_id not in fixture_ids,
            f"registry fixture id is missing, substituted, or duplicate: {schema}",
        )
        fixture_ids.add(fixture_id)
        _validate_schema_value(
            entry["fixture"],
            {
                "type": "object",
                "required_keys": document["required_keys"],
                "optional_keys": document["optional_keys"],
                "nullable_keys": document["nullable_keys"],
                "properties": document["properties"],
            },
            f"registry fixture {schema}",
        )
        _require(
            entry["fixture_sha256"] == canonical_hash(entry["fixture"], "cassi.qi-flow.fixture"),
            f"registry fixture hash mismatch: {schema}",
        )
        _require_sha256(entry["fixture_sha256"], f"registry fixture sha256: {schema}")
        entries[schema] = entry
        schemas.append(schema)
    _require(
        tuple(schemas) == W1_SCHEMA_ORDER,
        "schema registry entries are missing, extra, or reordered",
    )
    return entries


def _registry_entry(raw_entry: Any) -> dict[str, Any]:
    entry = _canonical_object(
        raw_entry,
        "schema registry entry",
        max_bytes=MAX_LARGE_JSON_BYTES,
    )
    _require(
        set(entry) == set(SCHEMA_REGISTRY_ENTRY_KEYS),
        "schema registry entry keyset is invalid",
    )
    schema = entry["schema"]
    _require(isinstance(schema, str), "registered schema is invalid")
    version = entry["version"]
    _require(
        isinstance(version, int)
        and not isinstance(version, bool)
        and version == _schema_suffix_version(schema, f"registered schema {schema}"),
        f"registered schema version mismatch: {schema}",
    )
    _require(
        entry["object_class"] in _OBJECT_CLASSES,
        f"registered object class is invalid: {schema}",
    )
    _require(
        isinstance(entry["lifecycle"], (str, Mapping)),
        f"registered lifecycle is invalid: {schema}",
    )
    _require(
        isinstance(entry["max_encoded_bytes"], int)
        and not isinstance(entry["max_encoded_bytes"], bool)
        and 0 < entry["max_encoded_bytes"] <= MAX_LARGE_JSON_BYTES,
        f"registered byte limit is invalid: {schema}",
    )
    _require(
        isinstance(entry["max_fanout"], int)
        and not isinstance(entry["max_fanout"], bool)
        and 0 <= entry["max_fanout"] <= MAX_SCHEMA_FANOUT,
        f"registered fanout limit is invalid: {schema}",
    )
    parents = entry["semantic_parent_names"]
    normalised_parents = [
        name.removesuffix("_sha256")
        for name in parents
        if isinstance(name, str) and name.endswith("_sha256")
    ] if isinstance(parents, list) else []
    parent_order = {
        name: index for index, name in enumerate(SEMANTIC_PARENT_ORDER)
    }
    _require(
        isinstance(parents, list)
        and len(normalised_parents) == len(parents)
        and all(name in parent_order for name in normalised_parents)
        and len(normalised_parents) == len(set(normalised_parents))
        and normalised_parents
        == sorted(normalised_parents, key=parent_order.__getitem__),
        f"registered semantic parents are invalid: {schema}",
    )
    document = entry["schema_document"]
    _require(
        isinstance(document, Mapping)
        and SCHEMA_DOCUMENT_REQUIRED_KEYS <= set(document)
        and set(document) <= SCHEMA_DOCUMENT_KEYS
        and document["schema"] == SCHEMA_DOCUMENT_SCHEMA
        and document["object_schema"] == schema
        and document.get("type", "object") == "object"
        and document.get("additional_properties", False) is False
        and isinstance(document["properties"], Mapping),
        f"registered schema document is invalid: {schema}",
    )
    _require(
        canonical_hash(
            document,
            SCHEMA_DOCUMENT_SCHEMA,
            max_bytes=MAX_LARGE_JSON_BYTES,
        )
        == _require_sha256(
            entry["schema_document_sha256"],
            f"registered schema document {schema}",
        ),
        f"registered schema document hash mismatch: {schema}",
    )
    _require(
        isinstance(entry["fixture_id"], str) and entry["fixture_id"],
        f"registered fixture_id is invalid: {schema}",
    )
    fixture_set = entry["canonical_fixture_set"]
    _require(
        isinstance(fixture_set, Mapping)
        and set(fixture_set) == {"minimal_valid", "maximal_valid", "nullable_valid"},
        f"registered fixture set is invalid: {schema}",
    )
    _require(
        canonical_hash(
            fixture_set,
            SCHEMA_FIXTURE_SET_HASH_DOMAIN,
            max_bytes=MAX_LARGE_JSON_BYTES,
        )
        == _require_sha256(
            entry["canonical_fixture_set_sha256"],
            f"registered fixture set {schema}",
        ),
        f"registered fixture-set hash mismatch: {schema}",
    )
    controls = entry["mutation_controls"]
    _require(
        isinstance(controls, list) and controls,
        f"registered mutation controls are invalid: {schema}",
    )
    control_ids: set[str] = set()
    for index, raw_control in enumerate(controls):
        _require(
            isinstance(raw_control, Mapping)
            and set(raw_control)
            == {
                "control_id",
                "base_fixture",
                "operation",
                "pointer",
                "value",
                "expected_error",
            },
            f"registered mutation control is invalid: {schema}[{index}]",
        )
        control_id = raw_control["control_id"]
        _require(
            isinstance(control_id, str)
            and control_id
            and control_id not in control_ids,
            f"registered mutation control id is invalid: {schema}[{index}]",
        )
        control_ids.add(control_id)
        _require(
            raw_control["base_fixture"]
            in {"minimal_valid", "maximal_valid", "nullable_valid"},
            f"registered mutation base fixture is invalid: {schema}[{index}]",
        )
        _require(
            raw_control["operation"] in {"insert", "delete", "replace", "reorder"},
            f"registered mutation operation is invalid: {schema}[{index}]",
        )
        pointer = raw_control["pointer"]
        _require(
            isinstance(pointer, str)
            and (pointer == "" or pointer.startswith("/")),
            f"registered mutation pointer is invalid: {schema}[{index}]",
        )
        _require(
            isinstance(raw_control["expected_error"], str)
            and raw_control["expected_error"],
            f"registered mutation expected error is invalid: {schema}[{index}]",
        )
    _require(
        canonical_hash(
            controls,
            SCHEMA_MUTATION_CONTROLS_HASH_DOMAIN,
            max_bytes=MAX_LARGE_JSON_BYTES,
        )
        == _require_sha256(
            entry["mutation_controls_sha256"],
            f"registered mutation controls {schema}",
        ),
        f"registered mutation-control hash mismatch: {schema}",
    )
    _require(
        isinstance(entry["hash_domain"], str) and entry["hash_domain"],
        f"registered hash domain is invalid: {schema}",
    )
    _require(
        isinstance(entry["self_hash_field"], str) and entry["self_hash_field"],
        f"registered self-hash field is invalid: {schema}",
    )
    _require(
        entry["independent_verifier"] == "stdlib-schema-replay-v1"
        and entry["migration_policy"] == "new-schema-version-and-contract-root-v1",
        f"registered verifier or migration policy is invalid: {schema}",
    )
    return entry


def validate_schema_registry_package(
    manifest_path: Path,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Validate the canonical manifest, every shard, and every entry identity."""

    path = Path(manifest_path).resolve()
    _require(path.is_file() and not path.is_symlink(), "schema registry manifest is missing")
    try:
        manifest_raw = path.read_bytes()
    except OSError as error:
        raise VerificationError(f"cannot read schema registry manifest {path}: {error}") from error
    manifest = _canonical_object(
        manifest_raw,
        "schema registry manifest",
        max_bytes=MAX_LARGE_JSON_BYTES,
    )
    expected_manifest_keys = {
        "schema",
        "version",
        "entry_keys",
        "entry_count",
        "first_schema",
        "last_schema",
        "entry_hashes",
        "shards",
        "source_hashes",
        "self_sha256",
    }
    _require(
        set(manifest) == expected_manifest_keys
        and manifest["schema"] == SCHEMA_REGISTRY_SCHEMA
        and manifest["version"] == 1
        and manifest["entry_keys"] == list(SCHEMA_REGISTRY_ENTRY_KEYS)
        and manifest["entry_count"] == 116,
        "schema registry manifest keyset or inventory is invalid",
    )
    manifest_self = _require_sha256(
        manifest["self_sha256"], "schema registry manifest self_sha256"
    )
    manifest_body = dict(manifest)
    manifest_body.pop("self_sha256")
    _require(
        canonical_hash(
            manifest_body,
            SCHEMA_REGISTRY_SCHEMA,
            max_bytes=MAX_LARGE_JSON_BYTES,
        )
        == manifest_self,
        "schema registry manifest self hash mismatch",
    )
    source_paths: list[str] = []
    for row in manifest["source_hashes"]:
        _require(
            isinstance(row, Mapping)
            and set(row) == {"path", "byte_count", "sha256"}
            and isinstance(row["byte_count"], int)
            and not isinstance(row["byte_count"], bool)
            and row["byte_count"] >= 0,
            "schema registry source row is invalid",
        )
        source_paths.append(_safe_relative_path(row["path"], "schema registry source").as_posix())
        _require_sha256(row["sha256"], "schema registry source sha256")
    _require(
        source_paths
        == sorted(source_paths, key=lambda item: item.encode("utf-8"))
        and len(source_paths) == len(set(source_paths)),
        "schema registry source rows are reordered or duplicated",
    )
    entries: list[dict[str, Any]] = []
    shard_paths: list[str] = []
    for shard_index, raw_row in enumerate(manifest["shards"]):
        _require(
            isinstance(raw_row, Mapping)
            and set(raw_row)
            == {
                "path",
                "raw_sha256",
                "byte_count",
                "entry_count",
                "first_schema",
                "last_schema",
            },
            f"schema registry shard row is invalid: {shard_index}",
        )
        relative = _safe_relative_path(raw_row["path"], "schema registry shard")
        _require(
            relative.parts
            and relative.parts[0] == "shards"
            and len(relative.parts) == 2,
            f"schema registry shard path is invalid: {relative.as_posix()}",
        )
        shard_paths.append(relative.as_posix())
        shard_path = path.parent / relative
        _require(
            shard_path.is_file() and not shard_path.is_symlink(),
            f"schema registry shard is missing: {relative.as_posix()}",
        )
        try:
            shard_raw = shard_path.read_bytes()
        except OSError as error:
            raise VerificationError(f"cannot read schema registry shard {shard_path}: {error}") from error
        _require(
            len(shard_raw) == raw_row["byte_count"]
            and hashlib.sha256(shard_raw).hexdigest()
            == _require_sha256(raw_row["raw_sha256"], "schema registry shard raw_sha256"),
            f"schema registry shard raw identity mismatch: {relative.as_posix()}",
        )
        shard = _canonical_object(
            shard_raw,
            f"schema registry shard {relative.as_posix()}",
            max_bytes=MAX_LARGE_JSON_BYTES,
        )
        _require(
            set(shard)
            == {
                "schema",
                "entries",
                "entry_count",
                "first_schema",
                "last_schema",
                "self_sha256",
            }
            and shard["schema"] == SCHEMA_REGISTRY_SHARD_SCHEMA
            and isinstance(shard["entries"], list)
            and shard["entries"],
            f"schema registry shard structure is invalid: {relative.as_posix()}",
        )
        shard_self = _require_sha256(
            shard["self_sha256"], "schema registry shard self_sha256"
        )
        shard_body = dict(shard)
        shard_body.pop("self_sha256")
        _require(
            canonical_hash(
                shard_body,
                SCHEMA_REGISTRY_SHARD_SCHEMA,
                max_bytes=MAX_LARGE_JSON_BYTES,
            )
            == shard_self,
            f"schema registry shard self hash mismatch: {relative.as_posix()}",
        )
        shard_entries = [
            _registry_entry(entry) for entry in shard["entries"]
        ]
        _require(
            shard["entry_count"]
            == raw_row["entry_count"]
            == len(shard_entries)
            and shard["first_schema"]
            == raw_row["first_schema"]
            == shard_entries[0]["schema"]
            and shard["last_schema"]
            == raw_row["last_schema"]
            == shard_entries[-1]["schema"],
            f"schema registry shard range mismatch: {relative.as_posix()}",
        )
        entries.extend(shard_entries)
    _require(
        shard_paths == sorted(shard_paths, key=lambda item: item.encode("utf-8"))
        and len(shard_paths) == len(set(shard_paths)),
        "schema registry shards are reordered or duplicated",
    )
    schemas = [entry["schema"] for entry in entries]
    entry_hashes = [
        {
            "schema": entry["schema"],
            "sha256": canonical_hash(
                entry,
                SCHEMA_REGISTRY_ENTRY_HASH_DOMAIN,
                max_bytes=MAX_LARGE_JSON_BYTES,
            ),
        }
        for entry in entries
    ]
    _require(
        len(entries) == manifest["entry_count"]
        and schemas == sorted(schemas, key=lambda item: item.encode("utf-8"))
        and len(schemas) == len(set(schemas))
        and schemas[0] == manifest["first_schema"]
        and schemas[-1] == manifest["last_schema"]
        and entry_hashes == manifest["entry_hashes"],
        "schema registry inventory or entry identities are invalid",
    )
    _require(
        "cassi.qi-flow-action-ack.v1" not in schemas,
        "forbidden legacy action-ack alias is registered",
    )
    return manifest, {entry["schema"]: entry for entry in entries}


def _validate_projection_registry(
    payload_or_bytes: Mapping[str, Any] | bytes | str,
) -> dict[str, Any]:
    record = _canonical_object(
        payload_or_bytes,
        "projection registry",
        max_bytes=MAX_LARGE_JSON_BYTES,
    )
    _require(
        set(record)
        == {"schema", "projection_order", "fields", "projections", "self_sha256"}
        and record["schema"] == PROJECTION_REGISTRY_SCHEMA
        and record["projection_order"] == list(SEMANTIC_PROJECTION_ORDER),
        "projection registry keyset/schema is invalid",
    )
    self_sha256 = _require_sha256(
        record["self_sha256"], "projection registry self_sha256"
    )
    without_self = dict(record)
    without_self.pop("self_sha256")
    _require(
        canonical_hash(
            without_self,
            PROJECTION_REGISTRY_SCHEMA,
            max_bytes=MAX_LARGE_JSON_BYTES,
        )
        == self_sha256,
        "projection registry self hash mismatch",
    )
    fields = record["fields"]
    _require(isinstance(fields, list) and fields, "projection field registry is empty")
    field_map: dict[str, dict[str, Any]] = {}
    projection_index = {
        name: index for index, name in enumerate(SEMANTIC_PROJECTION_ORDER)
    }
    for raw_field in fields:
        _require(
            isinstance(raw_field, Mapping)
            and set(raw_field)
            == {"json_pointer", "value_type", "nullable", "consumers"},
            "projection field registry entry keyset is invalid",
        )
        pointer = raw_field["json_pointer"]
        consumers = raw_field["consumers"]
        _require(
            isinstance(pointer, str)
            and pointer.startswith("/")
            and pointer not in field_map
            and isinstance(raw_field["value_type"], str)
            and raw_field["value_type"]
            and isinstance(raw_field["nullable"], bool)
            and isinstance(consumers, list)
            and consumers
            and all(name in projection_index for name in consumers)
            and len(consumers) == len(set(consumers))
            and consumers == sorted(consumers, key=projection_index.__getitem__),
            f"projection field registry entry is invalid: {pointer!r}",
        )
        field_map[pointer] = dict(raw_field)
    field_order = list(field_map)
    _require(
        field_order[:2] == ["/profile_id", "/contract_root_sha256"]
        and field_order[2:]
        == sorted(field_order[2:], key=lambda item: item.encode("utf-8")),
        "projection field registry is reordered",
    )
    projections = record["projections"]
    _require(
        isinstance(projections, list)
        and len(projections) == len(SEMANTIC_PROJECTION_ORDER),
        "projection registry cardinality is invalid",
    )
    names: list[str] = []
    for projection in projections:
        _require(
            isinstance(projection, Mapping)
            and set(projection) == {"name", "state_consuming", "pointers"},
            "projection registry entry keyset is invalid",
        )
        name = projection["name"]
        _require(name in projection_index, "projection registry name is invalid")
        names.append(name)
        _require(
            projection["state_consuming"] == (name in STATE_CONSUMING_PROJECTIONS),
            f"projection registry state-consuming label mismatch: {name}",
        )
        pointers = projection["pointers"]
        expected_pointers = [
            pointer for pointer, field in field_map.items() if name in field["consumers"]
        ]
        _require(
            isinstance(pointers, list)
            and len(pointers) == len(set(pointers))
            and set(pointers) == set(expected_pointers)
            and "/contract_root_sha256" in pointers,
            f"projection registry pointers are invalid: {name}",
        )
    _require(
        tuple(names) == SEMANTIC_PROJECTION_ORDER,
        "projection registry entries are missing, duplicate, or reordered",
    )
    return record


def _resolve_profile_pointer(profile: Mapping[str, Any], pointer: str) -> Any:
    _require(pointer.startswith("/"), f"projection pointer is invalid: {pointer!r}")
    current: Any = profile
    for raw_segment in pointer[1:].split("/"):
        _require(
            raw_segment
            and re.fullmatch(r"(?:[^~]|~[01])+", raw_segment) is not None,
            f"projection pointer is invalid: {pointer!r}",
        )
        segment = raw_segment.replace("~1", "/").replace("~0", "~")
        if isinstance(current, Mapping):
            _require(segment in current, f"projection pointer is unresolved: {pointer}")
            current = current[segment]
        elif isinstance(current, list):
            _require(
                re.fullmatch(r"0|[1-9][0-9]*", segment) is not None,
                f"projection array pointer is invalid: {pointer}",
            )
            index = int(segment, 10)
            _require(index < len(current), f"projection pointer is unresolved: {pointer}")
            current = current[index]
        else:
            raise VerificationError(f"projection pointer descends through scalar: {pointer}")
    return current


def _projection_members(
    profile: Mapping[str, Any],
    pointers: Sequence[str],
) -> dict[str, Any]:
    return {
        "members": [
            {"pointer": pointer, "value": _resolve_profile_pointer(profile, pointer)}
            for pointer in pointers
        ]
    }


def _extract_profile_parents(
    profile: Mapping[str, Any],
    projection_registry: Mapping[str, Any],
) -> dict[str, str]:
    values = profile.get("semantic_subhashes")
    _require(isinstance(values, list), "profile semantic_subhashes must be an array")
    _require(
        len(values) == len(SEMANTIC_PROJECTION_ORDER),
        "profile semantic subhash cardinality mismatch",
    )
    projections = projection_registry["projections"]
    result: dict[str, str] = {}
    names: list[str] = []
    for entry, projection in zip(values, projections, strict=True):
        _require(
            isinstance(entry, Mapping)
            and set(entry) == {"name", "sha256", "state_consuming"},
            "profile semantic subhash record is malformed",
        )
        name = entry["name"]
        _require(
            isinstance(name, str) and name == projection["name"],
            "profile semantic subhash name is invalid or reordered",
        )
        names.append(name)
        digest = _require_sha256(
            entry["sha256"], f"profile semantic subhash {name}"
        )
        _require(
            entry["state_consuming"] == projection["state_consuming"],
            f"profile semantic state-consuming label mismatch: {name}",
        )
        _require(
            digest
            == canonical_hash(
                {
                    "projection": name,
                    **_projection_members(profile, projection["pointers"]),
                },
                f"cassi.qi-flow.projection.{name}",
            ),
            f"profile semantic projection hash mismatch: {name}",
        )
        result[SEMANTIC_PARENT_FOR_PROJECTION[name]] = digest
    _require(
        tuple(names) == SEMANTIC_PROJECTION_ORDER,
        "profile semantic subhashes are missing, duplicate, or reordered",
    )
    return result


def _profile_default_rows(value: Any, prefix: str = "") -> list[dict[str, Any]]:
    if isinstance(value, Mapping):
        rows: list[dict[str, Any]] = []
        for key in sorted(value, key=lambda item: item.encode("utf-8")):
            rows.extend(_profile_default_rows(value[key], f"{prefix}/{key}"))
        return rows
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
        raise VerificationError(f"unsupported materialized default at {prefix}")
    return [
        {
            "json_pointer": prefix,
            "value_type": value_type,
            "nullable": value is None,
            "value": deepcopy(value),
        }
    ]


def _validate_profile_defaults(
    payload_or_bytes: Mapping[str, Any] | bytes | str,
) -> dict[str, Any]:
    defaults = _canonical_object(
        payload_or_bytes,
        "profile defaults",
        max_bytes=MAX_LARGE_JSON_BYTES,
    )
    _require(
        set(defaults) == {"schema", "entries", "self_sha256"}
        and defaults["schema"] == PROFILE_DEFAULTS_SCHEMA
        and isinstance(defaults["entries"], list)
        and defaults["entries"],
        "profile defaults object is invalid",
    )
    pointers: list[str] = []
    for index, row in enumerate(defaults["entries"]):
        _require(
            isinstance(row, Mapping)
            and set(row) == {"json_pointer", "value_type", "nullable", "value"},
            f"profile defaults row is invalid: {index}",
        )
        pointer = row["json_pointer"]
        _require(
            isinstance(pointer, str)
            and pointer.startswith("/")
            and pointer.split("/", 2)[1] in ROOT_DEFAULT_KEYS,
            f"profile defaults pointer is invalid: {index}",
        )
        pointers.append(pointer)
        expected = _profile_default_rows(row["value"], pointer)
        _require(
            len(expected) == 1
            and expected[0]["value_type"] == row["value_type"]
            and expected[0]["nullable"] == row["nullable"],
            f"profile defaults value metadata is invalid: {pointer}",
        )
    _require(
        pointers == sorted(pointers, key=lambda item: item.encode("utf-8"))
        and len(pointers) == len(set(pointers)),
        "profile default pointers are reordered or duplicated",
    )
    self_sha256 = _require_sha256(
        defaults["self_sha256"], "profile defaults self_sha256"
    )
    body = dict(defaults)
    body.pop("self_sha256")
    _require(
        canonical_hash(
            body,
            PROFILE_DEFAULTS_SCHEMA,
            max_bytes=MAX_LARGE_JSON_BYTES,
        )
        == self_sha256,
        "profile defaults self hash mismatch",
    )
    return defaults


def _validate_materialized_defaults(
    profile: Mapping[str, Any],
    defaults: Mapping[str, Any],
) -> None:
    materialized = {key: profile[key] for key in ROOT_DEFAULT_KEYS}
    expected_rows = _profile_default_rows(materialized)
    _require(
        canonical_json_bytes(
            expected_rows,
            max_bytes=MAX_LARGE_JSON_BYTES,
        )
        == canonical_json_bytes(
            defaults["entries"],
            max_bytes=MAX_LARGE_JSON_BYTES,
        ),
        "profile does not exactly materialize the registered defaults",
    )

def _profile_positive_int(value: Any, context: str) -> int:
    _require(
        isinstance(value, int) and not isinstance(value, bool) and value > 0,
        f"{context} must be a positive integer",
    )
    return value

def _reduced_fraction(
    value: Any,
    context: str,
    *,
    allow_zero: bool = False,
) -> Fraction:
    _require(
        isinstance(value, Mapping) and set(value) == {"numerator", "denominator"},
        f"{context} must be a rational mapping",
    )
    numerator = value["numerator"]
    denominator = value["denominator"]
    _require(
        isinstance(numerator, int)
        and not isinstance(numerator, bool)
        and isinstance(denominator, int)
        and not isinstance(denominator, bool)
        and denominator > 0
        and (numerator >= 0 if allow_zero else numerator > 0)
        and math.gcd(numerator, denominator) == 1,
        f"{context} must be a reduced positive rational",
    )
    return Fraction(numerator, denominator)


def _validate_profile_semantics(profile: Mapping[str, Any]) -> None:
    """Replay profile-local identity constraints without importing runtime code."""

    field = profile.get("field")
    spatial = profile.get("spatial")
    dynamics = profile.get("dynamics")
    execution = profile.get("execution")
    conversion = profile.get("conversion")
    _require(
        all(
            isinstance(value, Mapping)
            for value in (field, spatial, dynamics, execution, conversion)
        ),
        "profile semantic sections are missing",
    )
    assert isinstance(field, Mapping)
    assert isinstance(spatial, Mapping)
    assert isinstance(dynamics, Mapping)
    assert isinstance(execution, Mapping)
    assert isinstance(conversion, Mapping)

    scale_count = _profile_positive_int(field.get("scale_count"), "field.scale_count")
    mode_count = _profile_positive_int(field.get("mode_count"), "field.mode_count")
    _require(field.get("component_count") == 9, "profile has no fixed [S,9M,B] state")
    active_shapes = field.get("active_shapes")
    active_counts = field.get("active_site_counts")
    spatial_shapes = spatial.get("active_shapes")
    per_scale = spatial.get("per_scale")
    metric_areas = spatial.get("metric_cell_area")
    _require(
        isinstance(active_shapes, list)
        and isinstance(active_counts, list)
        and isinstance(spatial_shapes, list)
        and isinstance(per_scale, list)
        and isinstance(metric_areas, list)
        and len(active_shapes)
        == len(active_counts)
        == len(spatial_shapes)
        == len(per_scale)
        == len(metric_areas)
        == scale_count
        and active_shapes == spatial_shapes,
        "profile field/spatial active layout is inconsistent",
    )
    sheets: list[dict[str, Any]] = []
    for index, raw_shape in enumerate(active_shapes):
        _require(
            isinstance(raw_shape, list)
            and len(raw_shape) == 2
            and all(
                isinstance(dimension, int)
                and not isinstance(dimension, bool)
                and dimension > 0
                for dimension in raw_shape
            ),
            f"profile active shape is invalid at scale {index}",
        )
        count = raw_shape[0] * raw_shape[1]
        _require(
            active_counts[index] == count <= mode_count,
            f"profile active count is invalid at scale {index}",
        )
        sheet = per_scale[index]
        _require(isinstance(sheet, Mapping), f"profile sheet is invalid at scale {index}")
        _require(
            sheet.get("scale_index") == index
            and sheet.get("active_shape") == raw_shape
            and sheet.get("active_site_count") == count
            and sheet.get("storage_mode_count") == mode_count
            and sheet.get("packing") == "m=y*N_x+x"
            and sheet.get("axis_order") == ["y", "x"]
            and sheet.get("vector_component_order") == ["x", "y"]
            and sheet.get("origin_m") in (
                ["f32:00000000", "f32:00000000"],
                ["f64:0000000000000000", "f64:0000000000000000"],
            )
            and sheet.get("handedness") == "right-handed-x-y-z-out.v1",
            f"profile sheet does not match field layout at scale {index}",
        )
        spacing = sheet.get("spacing_m")
        extent = sheet.get("extent_m")
        _require(
            isinstance(spacing, Mapping) and isinstance(extent, Mapping),
            f"profile sheet metric is invalid at scale {index}",
        )
        dx = _tagged_finite_value(spacing.get("dx"), f"sheet[{index}].spacing_m.dx")
        dy = _tagged_finite_value(spacing.get("dy"), f"sheet[{index}].spacing_m.dy")
        lx = _tagged_finite_value(extent.get("L_x"), f"sheet[{index}].extent_m.L_x")
        ly = _tagged_finite_value(extent.get("L_y"), f"sheet[{index}].extent_m.L_y")
        area = _tagged_finite_value(
            sheet.get("metric_cell_area"), f"sheet[{index}].metric_cell_area"
        )
        _require(
            dx > 0.0
            and dy > 0.0
            and lx == dx * raw_shape[1]
            and ly == dy * raw_shape[0]
            and area == dx * dy
            and metric_areas[index] == sheet.get("metric_cell_area")
            and sheet.get("signed_frequency_bins")
            == {
                "y": _signed_frequency_bins(raw_shape[0]),
                "x": _signed_frequency_bins(raw_shape[1]),
                "even_nyquist": "literal-negative",
            }
            and isinstance(sheet.get("oversampling"), Mapping)
            and sheet["oversampling"].get("factors") == [2, 2]
            and sheet["oversampling"].get("shape")
            == [2 * raw_shape[0], 2 * raw_shape[1]]
            and sheet["oversampling"].get("injection")
            == "complete-signed-frequency.v1"
            and _tagged_finite_value(
                sheet["oversampling"].get("alpha"),
                f"sheet[{index}].oversampling.alpha",
            )
            == 2.0
            and sheet["oversampling"].get("restriction") == "weighted-adjoint.v1",
            f"profile sheet extent/spacing/metric mismatch at scale {index}",
        )
        sheets.append(deepcopy(dict(sheet)))

    transform = dynamics.get("coordinate_transform")
    state_operator = profile.get("scale_geometry", {}).get("state_operator") if isinstance(profile.get("scale_geometry"), Mapping) else None
    capacity = profile.get("scale_geometry", {}).get("capacity") if isinstance(profile.get("scale_geometry"), Mapping) else None
    _require(
        isinstance(transform, Mapping)
        and isinstance(state_operator, Mapping)
        and isinstance(capacity, Mapping)
        and state_operator.get("scale_geometry_mode") == "temporal-full-rank"
        and state_operator.get("selected_candidate_id") == "temporal-full-rank",
        "profile state operator contract is invalid",
    )
    padded_counts = [mode_count - int(count) for count in active_counts]
    p_spec = {
        "mode": "temporal-full-rank",
        "restriction": "identity-low-pass.v1",
        "adjoint": "metric-restricted-adjoint.v1",
        "active_ranks": list(active_counts),
        "nullspace_dimensions": list(padded_counts),
    }
    geometry_spec = {
        "schema": "cassi.qi-flow-periodic-sheet-geometry.v1",
        "sheets": sheets,
        "boundary_condition": spatial.get("boundary_condition"),
        "spectral_transform": spatial.get("spectral_transform"),
        "normalization": spatial.get("normalization"),
        "derivative_symbol": spatial.get("derivative_symbol"),
        "laplacian_symbol": spatial.get("laplacian_symbol"),
        "gather_scatter": spatial.get("gather_scatter"),
        "positive_scalar_remap": spatial.get("positive_scalar_remap"),
        "coordinate_transform": deepcopy(dict(transform)),
        "cross_scale": deepcopy(p_spec),
    }
    geometry_sha256 = _operator_identity("periodic-sheet-geometry.v1", geometry_spec)
    p_sha256 = _operator_identity("temporal-full-rank-p.v1", p_spec)
    p_adjoint_sha256 = _operator_identity("temporal-full-rank-p-adjoint.v1", p_spec)
    metric_sha256 = canonical_hash(
        {
            "cell_area": list(metric_areas),
            "coordinate_weights": transform.get("weights"),
        },
        "cassi.qi-flow.metric.v1",
    )
    _require(
        spatial.get("geometry_operator_sha256") == geometry_sha256
        and spatial.get("metric_sha256") == metric_sha256
        and spatial.get("transform_sha256")
        == _operator_identity("yang-yin-dc-transform.v1", transform)
        and state_operator.get("selected_operator_sha256") == geometry_sha256
        and state_operator.get("p_operator_sha256") == p_sha256
        and state_operator.get("p_adjoint_sha256") == p_adjoint_sha256
        and state_operator.get("active_ranks") == active_counts
        and state_operator.get("nullspace_dimensions") == padded_counts,
        "profile geometry/P/P-adjoint/metric identities are inconsistent",
    )
    scalar_bytes = 8 if field.get("dtype") == "float64" else 4
    active_bytes = sum(int(count) for count in active_counts) * 9 * _profile_positive_int(field.get("batch_limit"), "field.batch_limit") * scalar_bytes
    padded_bytes = sum(padded_counts) * 9 * _profile_positive_int(field.get("batch_limit"), "field.batch_limit") * scalar_bytes
    _require(
        capacity.get("active_sites") == active_counts
        and capacity.get("padded_sites") == padded_counts
        and capacity.get("active_state_bytes_at_batch_limit") == active_bytes
        and capacity.get("padded_state_bytes_at_batch_limit") == padded_bytes
        and capacity.get("rank_identity_sha256")
        == canonical_hash(p_spec, "cassi.qi-flow.scale-rank.v1")
        and capacity.get("cost_model_sha256")
        == canonical_hash(
            {"fft2_cells_per_scale": active_counts, "scale_count": scale_count},
            "cassi.qi-flow.scale-cost.v1",
        ),
        "profile scale capacity/rank/cost identities are inconsistent",
    )
    source = execution.get("source_identity")
    _require(isinstance(source, Mapping), "profile execution source identity is missing")
    source_body = dict(source)
    source_self = _require_sha256(
        source_body.pop("self_sha256", None),
        "profile execution source self_sha256",
    )
    source_schema = source_body.get("schema")
    _require(
        isinstance(source_schema, str)
        and source_self == canonical_hash(source_body, source_schema)
        and source_self == execution.get("source_identity_sha256"),
        "profile execution source identity is inconsistent",
    )

    clock = execution.get("clock")
    dynamics_clock = dynamics.get("clock")
    _require(
        isinstance(clock, Mapping)
        and isinstance(dynamics_clock, Mapping)
        and canonical_json_bytes(clock) == canonical_json_bytes(dynamics_clock),
        "profile execution and dynamics clocks disagree",
    )
    h_min = _reduced_fraction(clock.get("h_min"), "clock.h_min")
    h_max = _reduced_fraction(clock.get("h_max"), "clock.h_max")
    _require(h_max >= h_min, "profile dynamics clock interval is reversed")

    schedule_object = execution.get("schedule")
    _require(
        isinstance(schedule_object, Mapping),
        "profile execution schedule object is missing",
    )
    schedule_body = dict(schedule_object)
    schedule_self = _require_sha256(
        schedule_body.pop("self_sha256", None),
        "profile execution schedule self_sha256",
    )
    _require(
        schedule_self
        == canonical_hash(schedule_body, "cassi.qi-flow-execution-schedule.v1"),
        "profile execution schedule self hash mismatch",
    )
    schedule = schedule_object.get("stages")
    _require(isinstance(schedule, list), "profile execution stages are missing")
    stages: list[Mapping[str, Any]] = []
    for stage in schedule:
        _require(isinstance(stage, Mapping), "profile execution stage is invalid")
        stages.append(stage)
    _require(
        [stage.get("ordinal") for stage in stages] == list(range(11)),
        "profile stage ordinals must be exactly 0..10",
    )
    total_advance = Fraction(0, 1)
    for index, stage in enumerate(stages):
        advance = _reduced_fraction(
            {
                "numerator": stage.get("clock_increment_num"),
                "denominator": stage.get("clock_increment_den"),
            },
            f"profile stage[{index}] clock increment",
            allow_zero=True,
        )
        effective = _reduced_fraction(
            {
                "numerator": stage.get("effective_duration_num"),
                "denominator": stage.get("effective_duration_den"),
            },
            f"profile stage[{index}] effective duration",
            allow_zero=True,
        )
        _require(
            effective <= 1
            and (stage.get("transition_kind") == "timed") == (advance > 0)
            and stage.get("evaluate_from")
            in {
                "predecessor_state",
                "current_candidate",
                "frozen_stage_copy",
            },
            f"profile stage is semantically invalid at ordinal {index}",
        )
        stage_body = {
            key: value
            for key, value in stage.items()
            if key not in {"schema", "operator_sha256"}
        }
        _require(
            isinstance(stage.get("operator_id"), str)
            and stage.get("operator_sha256")
            == _operator_identity(stage["operator_id"], stage_body),
            f"profile stage operator identity mismatch at ordinal {index}",
        )
        total_advance += advance
    _require(
        total_advance == Fraction(1, 1)
        and schedule_object.get("total_clock_increment_num") == 1
        and schedule_object.get("total_clock_increment_den") == 1,
        "profile execution schedule does not advance exactly one h",
    )
    auxiliary = execution.get("auxiliary_schedules")
    _require(
        isinstance(auxiliary, Mapping),
        "profile auxiliary schedule registry is missing",
    )
    for schedule_name, registered in auxiliary.items():
        _require(
            isinstance(schedule_name, str) and isinstance(registered, Mapping),
            "profile auxiliary schedule is invalid",
        )
        registered_body = dict(registered)
        registered_self = _require_sha256(
            registered_body.pop("self_sha256", None),
            f"profile auxiliary schedule {schedule_name} self_sha256",
        )
        _require(
            registered_self
            == canonical_hash(
                registered_body, "cassi.qi-flow-execution-schedule.v1"
            ),
            f"profile auxiliary schedule self hash mismatch: {schedule_name}",
        )
    _require(
        conversion.get("q_evaluation_count") == 1
        and conversion.get("conversion_count") == 1
        and conversion.get("ema_update_count") == 1
        and all(
            _tagged_finite_value(conversion.get(key), f"conversion.{key}") > 0.0
            for key in (
                "lambda_per_s",
                "epsilon_memory_time_s",
                "numerical_zero_guard",
            )
        ),
        "profile frozen Q/conversion/EMA controls are invalid",
    )

def _f64_tag(value: float, context: str) -> str:
    _require(
        math.isfinite(value)
        and not (value == 0.0 and math.copysign(1.0, value) < 0.0),
        f"{context} is not a finite nonnegative-zero f64",
    )
    return f"f64:{struct.pack('>d', value).hex()}"


def _signed_frequency_bins(length: int) -> list[int]:
    _profile_positive_int(length, "frequency-bin length")
    return list(range((length + 1) // 2)) + list(range(-(length // 2), 0))


def _operator_identity(operator_id: str, specification: Mapping[str, Any]) -> str:
    return canonical_hash(
        {"operator_id": operator_id, "specification": dict(specification)},
        "cassi.qi-flow.operator-specification.v1",
    )


def _validate_rectangular_profile_derivation(
    base_profile: Mapping[str, Any],
    derived_profile: Mapping[str, Any],
    active_shapes: Sequence[Sequence[int]],
) -> None:
    """Rebuild the source-defined rectangular geometry override from a base profile."""

    base_field = base_profile.get("field")
    base_spatial = base_profile.get("spatial")
    base_scale_geometry = base_profile.get("scale_geometry")
    base_dynamics = base_profile.get("dynamics")
    derived_field = derived_profile.get("field")
    derived_spatial = derived_profile.get("spatial")
    derived_scale_geometry = derived_profile.get("scale_geometry")
    _require(
        all(
            isinstance(value, Mapping)
            for value in (
                base_field,
                base_spatial,
                base_scale_geometry,
                base_dynamics,
                derived_field,
                derived_spatial,
                derived_scale_geometry,
            )
        ),
        "rectangular profile derivation is missing a geometry section",
    )
    assert isinstance(base_field, Mapping)
    assert isinstance(base_spatial, Mapping)
    assert isinstance(base_scale_geometry, Mapping)
    assert isinstance(base_dynamics, Mapping)
    assert isinstance(derived_field, Mapping)
    assert isinstance(derived_spatial, Mapping)
    assert isinstance(derived_scale_geometry, Mapping)

    scale_count = _profile_positive_int(
        base_field.get("scale_count"), "base field.scale_count"
    )
    mode_count = _profile_positive_int(
        base_field.get("mode_count"), "base field.mode_count"
    )
    batch_limit = _profile_positive_int(
        base_field.get("batch_limit"), "base field.batch_limit"
    )
    _require(
        len(active_shapes) == scale_count,
        "rectangular profile override has the wrong scale count",
    )
    normalized: list[list[int]] = []
    active_counts: list[int] = []
    for index, raw_shape in enumerate(active_shapes):
        _require(
            isinstance(raw_shape, Sequence)
            and not isinstance(raw_shape, (str, bytes, bytearray))
            and len(raw_shape) == 2
            and all(
                isinstance(value, int)
                and not isinstance(value, bool)
                and value > 0
                for value in raw_shape
            ),
            f"rectangular shape is invalid at scale {index}",
        )
        shape = [int(raw_shape[0]), int(raw_shape[1])]
        active_count = shape[0] * shape[1]
        _require(
            active_count <= mode_count,
            f"rectangular active shape exceeds mode capacity at scale {index}",
        )
        normalized.append(shape)
        active_counts.append(active_count)
    padded_counts = [mode_count - active_count for active_count in active_counts]

    base_sheets = base_spatial.get("per_scale")
    _require(
        isinstance(base_sheets, list) and len(base_sheets) == scale_count,
        "base profile sheets are invalid",
    )
    sheets: list[dict[str, Any]] = []
    for index, shape in enumerate(normalized):
        base_sheet = base_sheets[index]
        _require(
            isinstance(base_sheet, Mapping) and base_sheet.get("scale_index") == index,
            f"base sheet is invalid at scale {index}",
        )
        sheet = deepcopy(dict(base_sheet))
        spacing = sheet.get("spacing_m")
        _require(
            isinstance(spacing, Mapping),
            f"base sheet spacing is invalid at scale {index}",
        )
        dy = _tagged_finite_value(
            spacing.get("dy"), f"base sheet[{index}].spacing_m.dy"
        )
        dx = _tagged_finite_value(
            spacing.get("dx"), f"base sheet[{index}].spacing_m.dx"
        )
        _require(dx > 0.0 and dy > 0.0, f"base sheet spacing is not positive at scale {index}")
        sheet.update(
            {
                "active_shape": shape,
                "active_site_count": active_counts[index],
                "storage_mode_count": mode_count,
                "extent_m": {
                    "L_y": _f64_tag(shape[0] * dy, f"derived L_y[{index}]"),
                    "L_x": _f64_tag(shape[1] * dx, f"derived L_x[{index}]"),
                },
                "signed_frequency_bins": {
                    "y": _signed_frequency_bins(shape[0]),
                    "x": _signed_frequency_bins(shape[1]),
                    "even_nyquist": "literal-negative",
                },
                "oversampling": {
                    "factors": [2, 2],
                    "shape": [2 * shape[0], 2 * shape[1]],
                    "injection": "complete-signed-frequency.v1",
                    "alpha": _f64_tag(2.0, f"derived oversampling alpha[{index}]"),
                    "restriction": "weighted-adjoint.v1",
                },
            }
        )
        sheets.append(sheet)

    p_spec = {
        "mode": "temporal-full-rank",
        "restriction": "identity-low-pass.v1",
        "adjoint": "metric-restricted-adjoint.v1",
        "active_ranks": list(active_counts),
        "nullspace_dimensions": list(padded_counts),
    }
    geometry_spec = {
        "schema": "cassi.qi-flow-periodic-sheet-geometry.v1",
        "sheets": deepcopy(sheets),
        "boundary_condition": base_spatial.get("boundary_condition"),
        "spectral_transform": base_spatial.get("spectral_transform"),
        "normalization": base_spatial.get("normalization"),
        "derivative_symbol": base_spatial.get("derivative_symbol"),
        "laplacian_symbol": base_spatial.get("laplacian_symbol"),
        "gather_scatter": base_spatial.get("gather_scatter"),
        "positive_scalar_remap": base_spatial.get("positive_scalar_remap"),
        "coordinate_transform": deepcopy(base_dynamics.get("coordinate_transform")),
        "cross_scale": deepcopy(p_spec),
    }
    geometry_sha256 = _operator_identity(
        "periodic-sheet-geometry.v1", geometry_spec
    )
    p_sha256 = _operator_identity("temporal-full-rank-p.v1", p_spec)
    p_adjoint_sha256 = _operator_identity("temporal-full-rank-p-adjoint.v1", p_spec)
    dtype_name = base_field.get("dtype")
    _require(
        dtype_name in {"float32", "float64"},
        "base profile field dtype is invalid",
    )
    scalar_bytes = 8 if dtype_name == "float64" else 4
    active_bytes = sum(active_counts) * 9 * batch_limit * scalar_bytes
    padded_bytes = sum(padded_counts) * 9 * batch_limit * scalar_bytes

    expected_field = deepcopy(dict(base_field))
    expected_field["active_shapes"] = deepcopy(normalized)
    expected_field["active_site_counts"] = list(active_counts)
    expected_spatial = deepcopy(dict(base_spatial))
    expected_spatial["active_shapes"] = deepcopy(normalized)
    expected_spatial["per_scale"] = sheets
    expected_spatial["geometry_operator_sha256"] = geometry_sha256
    expected_scale_geometry = deepcopy(dict(base_scale_geometry))
    expected_state_operator = dict(expected_scale_geometry["state_operator"])
    expected_state_operator.update(
        {
            "selected_operator_sha256": geometry_sha256,
            "p_operator_sha256": p_sha256,
            "p_adjoint_sha256": p_adjoint_sha256,
            "active_ranks": list(active_counts),
            "nullspace_dimensions": list(padded_counts),
        }
    )
    expected_scale_geometry["state_operator"] = expected_state_operator
    expected_capacity = dict(expected_scale_geometry["capacity"])
    expected_capacity.update(
        {
            "active_sites": list(active_counts),
            "padded_sites": list(padded_counts),
            "active_state_bytes_at_batch_limit": active_bytes,
            "padded_state_bytes_at_batch_limit": padded_bytes,
            "rank_identity_sha256": canonical_hash(
                p_spec, "cassi.qi-flow.scale-rank.v1"
            ),
            "cost_model_sha256": canonical_hash(
                {
                    "fft2_cells_per_scale": list(active_counts),
                    "scale_count": scale_count,
                },
                "cassi.qi-flow.scale-cost.v1",
            ),
        }
    )
    expected_scale_geometry["capacity"] = expected_capacity
    _require(
        canonical_json_bytes(derived_field) == canonical_json_bytes(expected_field)
        and canonical_json_bytes(derived_spatial)
        == canonical_json_bytes(expected_spatial)
        and canonical_json_bytes(derived_scale_geometry)
        == canonical_json_bytes(expected_scale_geometry),
        "derived profile geometry/capacity identities do not match source derivation",
    )


def validate_profile(
    payload_or_bytes: Mapping[str, Any] | bytes | str,
    *,
    contract_root: Mapping[str, Any] | bytes | str,
    profile_defaults: Mapping[str, Any] | bytes | str,
    projection_registry: Mapping[str, Any] | bytes | str,
) -> dict[str, Any]:
    """Validate one complete profile against the authenticated root components."""

    root = _validate_contract_root_shape(contract_root)
    defaults = _validate_profile_defaults(profile_defaults)
    _require(
        defaults["self_sha256"] == root["profile_defaults"]["sha256"],
        "profile defaults identity does not match contract root",
    )
    projections = _validate_projection_registry(projection_registry)
    _require(
        projections["self_sha256"] == root["projection_registry"]["sha256"],
        "profile projection registry identity does not match contract root",
    )
    profile = _canonical_object(
        payload_or_bytes,
        "profile",
        max_bytes=MAX_LARGE_JSON_BYTES,
    )
    required = set(ROOT_DEFAULT_KEYS) | {
        "profile_id",
        "schema",
        "contract_root_sha256",
        "semantic_subhashes",
        "profile_sha256",
    }
    _require(set(profile) == required, "profile keyset is incomplete or mutable")
    _require(profile["schema"] == PROFILE_SCHEMA, "wrong profile schema")
    _require(
        isinstance(profile["profile_id"], str) and profile["profile_id"],
        "profile_id is invalid",
    )
    _require(
        profile["contract_root_sha256"] == root["self_sha256"],
        "profile contract-root identity mismatch",
    )
    _validate_materialized_defaults(profile, defaults)
    _validate_profile_semantics(profile)
    _extract_profile_parents(profile, projections)
    profile_sha256 = _require_sha256(profile["profile_sha256"], "profile_sha256")
    without_self = dict(profile)
    without_self.pop("profile_sha256")
    _require(
        canonical_hash(
            without_self,
            PROFILE_SCHEMA,
            max_bytes=MAX_LARGE_JSON_BYTES,
        )
        == profile_sha256,
        "profile self hash mismatch",
    )
    return profile


def validate_root_components(
    *,
    contract_root: Mapping[str, Any] | bytes | str,
    canonical_codec: Mapping[str, Any] | bytes | str,
    canonical_fixture_corpus: Mapping[str, Any] | bytes | str,
    schema_registry: Path,
    projection_registry: Mapping[str, Any] | bytes | str,
    profile_defaults: Mapping[str, Any] | bytes | str,
    bootstrap_identity: Mapping[str, Any] | bytes | str,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Authenticate every root-bound W1 contract object from frozen bytes."""

    root = validate_contract_root(
        contract_root,
        bootstrap_identity=bootstrap_identity,
        fixture_corpus=canonical_fixture_corpus,
    )
    corpus = validate_canonical_fixture_corpus(canonical_fixture_corpus)
    codec = validate_canonical_codec(
        canonical_codec,
        fixture_corpus=corpus,
    )
    _require(
        canonical_hash(codec, CANONICAL_CODEC_SCHEMA)
        == root["canonical_codec"]["sha256"],
        "canonical codec identity does not match contract root",
    )
    registry, entries = validate_schema_registry_package(schema_registry)
    _require(
        registry["self_sha256"] == root["schema_registry"]["sha256"],
        "schema registry identity does not match contract root",
    )
    projections = _validate_projection_registry(projection_registry)
    _require(
        projections["self_sha256"] == root["projection_registry"]["sha256"],
        "projection registry identity does not match contract root",
    )
    defaults = _validate_profile_defaults(profile_defaults)
    _require(
        defaults["self_sha256"] == root["profile_defaults"]["sha256"],
        "profile defaults identity does not match contract root",
    )
    _require(PROFILE_SCHEMA in entries, "profile schema is not registered")
    _require(
        entries[PROFILE_SCHEMA]["schema_document_sha256"]
        == root["profile_schema"]["sha256"],
        "profile schema document identity does not match contract root",
    )
    return root, entries


def _validate_budget_fields(value: Any, context: str = "$") -> None:
    """Fail closed for the bounded raw/count fields that make receipts safe."""

    if isinstance(value, Mapping):
        values = dict(value)
        for name, child in values.items():
            _validate_budget_fields(child, f"{context}/{name}")
        comparisons = (
            ("byte_count", "max_bytes"),
            ("encoded_byte_count", "max_bytes"),
            ("raw_byte_count", "max_raw_bytes"),
            ("used_bytes", "max_bytes"),
            ("used", "limit"),
            ("consumed", "budget"),
        )
        for actual_key, limit_key in comparisons:
            actual = values.get(actual_key)
            limit = values.get(limit_key)
            if isinstance(actual, int) and not isinstance(actual, bool) and isinstance(limit, int) and not isinstance(limit, bool):
                _require(actual <= limit, f"{context}/{actual_key} exceeds {limit_key}")
        return
    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _validate_budget_fields(child, f"{context}[{index}]")


def _reject_legacy_schema(value: Any, context: str = "$") -> None:
    if isinstance(value, Mapping):
        for name, child in value.items():
            if name in {"schema", "state_schema", "checkpoint_schema", "session_schema"} and isinstance(child, str):
                is_top_level_checkpoint_receipt = (
                    context == "$"
                    and name == "schema"
                    and child == "cassi.qi-flow-checkpoint.v1"
                )
                _require(
                    is_top_level_checkpoint_receipt or _LEGACY_STATE_OR_SESSION.fullmatch(child) is None,
                    f"{context}/{name} accepts a legacy v1/v2 state/checkpoint/session schema",
                )
            _reject_legacy_schema(child, f"{context}/{name}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _reject_legacy_schema(child, f"{context}[{index}]")


def _validate_v3_state_header(
    header: Mapping[str, Any],
    root: Mapping[str, Any],
    profile: Mapping[str, Any] | None,
) -> dict[str, Any]:
    required = {
        "schema",
        "layout_id",
        "profile_sha256",
        "contract_root_sha256",
        "state_contract_sha256",
        "execution_schedule_sha256",
        "topology_sha256",
        "source_identity_sha256",
        "backend",
        "dtype",
        "shape",
        "raw_byte_count",
        "source_raw_sha256",
        "state_sha256",
        "self_sha256",
    }
    record = dict(header)
    _require(
        set(record) == required and record.get("schema") == STATE_SCHEMA_V3,
        "v3 state header keyset/schema mismatch",
    )
    _require(
        isinstance(record["layout_id"], str)
        and isinstance(record["backend"], str)
        and isinstance(record["dtype"], str),
        "v3 state descriptor is invalid",
    )
    _require(
        record["contract_root_sha256"] == root["self_sha256"],
        "v3 state contract-root mismatch",
    )
    if profile is not None:
        _require(
            record["profile_sha256"] == profile["profile_sha256"],
            "v3 state profile mismatch",
        )
    for key in (
        "profile_sha256",
        "contract_root_sha256",
        "state_contract_sha256",
        "execution_schedule_sha256",
        "topology_sha256",
        "source_identity_sha256",
        "source_raw_sha256",
        "state_sha256",
        "self_sha256",
    ):
        _require_sha256(record[key], f"v3 state {key}")
    shape = record["shape"]
    _require(
        isinstance(shape, list)
        and len(shape) == 3
        and all(
            isinstance(item, int) and not isinstance(item, bool) and item > 0
            for item in shape
        )
        and shape[1] % 9 == 0,
        "v3 state shape must be [S,9M,B]",
    )
    _require(
        isinstance(record["raw_byte_count"], int)
        and not isinstance(record["raw_byte_count"], bool)
        and record["raw_byte_count"] >= 0,
        "v3 state raw byte count is invalid",
    )
    without_self = dict(record)
    without_self.pop("self_sha256")
    _require(
        canonical_hash(without_self, STATE_SCHEMA_V3) == record["self_sha256"],
        "v3 state self hash mismatch",
    )
    return record

def _v3_tensor_hash(
    raw: bytes,
    *,
    dtype_name: str,
    shape: Sequence[int],
    state_contract_sha256: str,
) -> str:
    digest = hashlib.sha256()
    digest.update(frame(STATE_V3_TENSOR_DOMAIN.encode("utf-8")))
    digest.update(frame(state_contract_sha256.encode("ascii")))
    digest.update(frame(dtype_name.encode("ascii")))
    digest.update(struct.pack(">I", len(shape)))
    for dimension in shape:
        digest.update(struct.pack(">Q", dimension))
    digest.update(struct.pack(">Q", len(raw)))
    digest.update(raw)
    return digest.hexdigest()


def _validate_v3_raw_finite(raw: bytes, dtype_name: str) -> None:
    format_code = "<f" if dtype_name == "float32" else "<d"
    element_bytes = 4 if dtype_name == "float32" else 8
    _require(len(raw) % element_bytes == 0, "v3 raw field has a partial scalar")
    try:
        for (value,) in struct.iter_unpack(format_code, raw):
            _require(math.isfinite(value), "v3 raw field contains a non-finite value")
    except struct.error as error:
        raise VerificationError(f"v3 raw field cannot be decoded: {error}") from error

def _tagged_finite_value(value: Any, context: str) -> float:
    _require(isinstance(value, str), f"{context} must be a finite-bit tag")
    _validate_tagged_float(value, context)
    prefix, hex_bits = value.split(":", 1)
    try:
        if prefix == "f32":
            decoded = struct.unpack(">f", bytes.fromhex(hex_bits))[0]
        else:
            decoded = struct.unpack(">d", bytes.fromhex(hex_bits))[0]
    except (ValueError, struct.error) as error:
        raise VerificationError(f"{context} cannot be decoded") from error
    _require(math.isfinite(decoded), f"{context} is non-finite")
    return decoded


def _validate_state_layout(
    profile: Mapping[str, Any],
    header: Mapping[str, Any],
) -> tuple[list[int], dict[str, Any]]:
    """Derive and authenticate the fixed [S, 9M, B] layout from profile bytes."""

    field = profile.get("field")
    spatial = profile.get("spatial")
    backend_contract = profile.get("backend_contract")
    _require(isinstance(field, Mapping), "profile field contract is missing")
    _require(isinstance(spatial, Mapping), "profile spatial contract is missing")
    _require(isinstance(backend_contract, Mapping), "profile backend contract is missing")
    required_field = {
        "scale_count",
        "mode_count",
        "component_count",
        "batch_limit",
        "dtype",
        "byte_order",
        "layout_id",
        "component_order",
        "active_shapes",
        "active_site_counts",
        "state_byte_limit",
        "state_bounds",
    }
    _require(
        required_field <= set(field),
        "profile field omits authenticated state controls",
    )
    scale_count = field["scale_count"]
    mode_count = field["mode_count"]
    component_count = field["component_count"]
    batch_limit = field["batch_limit"]
    _require(
        all(
            isinstance(value, int) and not isinstance(value, bool) and value > 0
            for value in (scale_count, mode_count, component_count, batch_limit)
        )
        and component_count == 9,
        "profile field state dimensions are invalid",
    )
    component_order = field["component_order"]
    _require(
        isinstance(component_order, list)
        and component_order
        == [
            "Y_re",
            "Y_im",
            "I_re",
            "I_im",
            "VY_re",
            "VY_im",
            "VI_re",
            "VI_im",
            "epsilon2_ema",
        ],
        "profile component order is invalid",
    )
    shape = header["shape"]
    _require(
        field["byte_order"] == "little"
        and field["dtype"] == header["dtype"]
        and field["layout_id"] == header["layout_id"]
        and header["backend"] == backend_contract.get("device")
        and shape == [scale_count, component_count * mode_count, shape[2]]
        and 0 < shape[2] <= batch_limit,
        "v3 checkpoint does not match fixed little-endian [S,9M,B] layout",
    )
    state_byte_limit = field["state_byte_limit"]
    scalar_bytes = 4 if field["dtype"] == "float32" else 8
    maximum_raw_bytes = (
        scale_count * component_count * mode_count * batch_limit * scalar_bytes
    )
    _require(
        isinstance(state_byte_limit, int)
        and not isinstance(state_byte_limit, bool)
        and maximum_raw_bytes <= state_byte_limit
        and state_byte_limit == profile["capacity"]["max_state_bytes"],
        "profile state byte limit is invalid",
    )
    active_shapes = field["active_shapes"]
    active_counts = field["active_site_counts"]
    _require(
        active_shapes == spatial.get("active_shapes")
        and isinstance(active_shapes, list)
        and isinstance(active_counts, list)
        and len(active_shapes) == len(active_counts) == scale_count,
        "profile active spatial layout is invalid",
    )
    derived_counts: list[int] = []
    for index, active_shape in enumerate(active_shapes):
        _require(
            isinstance(active_shape, list)
            and len(active_shape) == 2
            and all(
                isinstance(dimension, int)
                and not isinstance(dimension, bool)
                and dimension > 0
                for dimension in active_shape
            ),
            f"profile active shape is invalid at scale {index}",
        )
        count = active_shape[0] * active_shape[1]
        _require(
            active_counts[index] == count <= mode_count,
            f"profile active-site count is invalid at scale {index}",
        )
        derived_counts.append(count)
    per_scale = spatial.get("per_scale")
    _require(
        spatial.get("gather_scatter") == "active-prefix-zero-tail.v1"
        and isinstance(per_scale, list)
        and len(per_scale) == scale_count,
        "profile spatial storage contract is invalid",
    )
    expected_tail_counts = [mode_count - count for count in derived_counts]
    for index, (shape_value, active_count, sheet) in enumerate(
        zip(active_shapes, derived_counts, per_scale, strict=True)
    ):
        _require(
            isinstance(sheet, Mapping)
            and sheet.get("scale_index") == index
            and sheet.get("active_shape") == shape_value
            and sheet.get("active_site_count") == active_count
            and sheet.get("storage_mode_count") == mode_count,
            f"profile spatial sheet disagrees with direct field storage at scale {index}",
        )
    scale_geometry = profile.get("scale_geometry")
    _require(
        isinstance(scale_geometry, Mapping),
        "profile scale geometry contract is missing",
    )
    state_operator = scale_geometry.get("state_operator")
    capacity = scale_geometry.get("capacity")
    _require(
        isinstance(state_operator, Mapping) and isinstance(capacity, Mapping),
        "profile scale geometry state/capacity contracts are missing",
    )
    _require(
        state_operator.get("active_ranks") == derived_counts
        and state_operator.get("nullspace_dimensions") == expected_tail_counts,
        "profile state operator disagrees with direct field capacity",
    )
    active_state_bytes = (
        sum(derived_counts) * component_count * batch_limit * scalar_bytes
    )
    padded_state_bytes = (
        sum(expected_tail_counts) * component_count * batch_limit * scalar_bytes
    )
    _require(
        capacity.get("active_sites") == derived_counts
        and capacity.get("padded_sites") == expected_tail_counts
        and capacity.get("active_state_bytes_at_batch_limit") == active_state_bytes
        and capacity.get("padded_state_bytes_at_batch_limit") == padded_state_bytes,
        "profile capacity disagrees with direct field storage",
    )
    state_bounds = field["state_bounds"]
    _require(isinstance(state_bounds, Mapping), "state bounds are missing")
    _require(
        set(state_bounds)
        == {
            "component_abs_max",
            "complex_amplitude_max",
            "density_max",
            "epsilon2_ema_max",
            "inactive_tail_value",
        },
        "state bounds keyset is invalid",
    )
    component_caps = state_bounds["component_abs_max"]
    pair_caps = state_bounds["complex_amplitude_max"]
    _require(
        isinstance(component_caps, list)
        and len(component_caps) == 9
        and isinstance(pair_caps, list)
        and len(pair_caps) == 4,
        "state component/pair bound cardinality is invalid",
    )
    for index, cap in enumerate(component_caps):
        _require(
            _tagged_finite_value(cap, f"component_abs_max[{index}]") > 0.0,
            f"component_abs_max[{index}] must be positive",
        )
    for index, cap in enumerate(pair_caps):
        _require(
            _tagged_finite_value(cap, f"complex_amplitude_max[{index}]") > 0.0,
            f"complex_amplitude_max[{index}] must be positive",
        )
    _require(
        _tagged_finite_value(state_bounds["density_max"], "density_max") > 0.0
        and _tagged_finite_value(state_bounds["epsilon2_ema_max"], "epsilon2_ema_max") > 0.0,
        "density/EMA bounds must be positive",
    )
    tail = state_bounds["inactive_tail_value"]
    _require(
        isinstance(tail, str)
        and tail in {"f32:00000000", "f64:0000000000000000"},
        "inactive tail value must be tagged positive zero",
    )
    return derived_counts, dict(state_bounds)


def _validate_v3_raw_semantics(
    raw: bytes,
    *,
    dtype_name: str,
    shape: Sequence[int],
    active_counts: Sequence[int],
    state_bounds: Mapping[str, Any],
) -> None:
    _require(dtype_name in {"float32", "float64"}, "v3 state dtype is unsupported")
    scalar_bytes = 4 if dtype_name == "float32" else 8
    format_code = "<f" if dtype_name == "float32" else "<d"
    expected_scalars = shape[0] * shape[1] * shape[2]
    _require(
        len(raw) == expected_scalars * scalar_bytes,
        "v3 raw state byte count is inconsistent with shape",
    )
    mode_count = shape[1] // 9
    component_caps = [
        _tagged_finite_value(value, f"component_abs_max[{index}]")
        for index, value in enumerate(state_bounds["component_abs_max"])
    ]
    pair_caps = [
        _tagged_finite_value(value, f"complex_amplitude_max[{index}]")
        for index, value in enumerate(state_bounds["complex_amplitude_max"])
    ]
    density_max = _tagged_finite_value(state_bounds["density_max"], "density_max")
    epsilon_max = _tagged_finite_value(
        state_bounds["epsilon2_ema_max"], "epsilon2_ema_max"
    )
    batch_count = shape[2]
    for scale_index, active_count in enumerate(active_counts):
        for site_index in range(mode_count):
            is_inactive = site_index >= active_count
            for batch_index in range(batch_count):
                components: list[float] = []
                for component_index in range(9):
                    scalar_index = (
                        (scale_index * 9 * mode_count + component_index * mode_count + site_index)
                        * batch_count
                        + batch_index
                    )
                    byte_offset = scalar_index * scalar_bytes
                    raw_scalar = raw[byte_offset:byte_offset + scalar_bytes]
                    if is_inactive:
                        _require(
                            raw_scalar == b"\x00" * scalar_bytes,
                            "v3 state inactive tail is nonzero or negative zero",
                        )
                        continue
                    try:
                        value = struct.unpack(format_code, raw_scalar)[0]
                    except struct.error as error:
                        raise VerificationError("v3 raw field cannot be decoded") from error
                    _require(math.isfinite(value), "v3 raw field contains a non-finite value")
                    _require(
                        abs(value) <= component_caps[component_index],
                        "v3 raw field exceeds its component bound",
                    )
                    components.append(value)
                if is_inactive:
                    continue
                for pair_index, pair_cap in enumerate(pair_caps):
                    real = components[pair_index * 2]
                    imaginary = components[pair_index * 2 + 1]
                    _require(
                        real * real + imaginary * imaginary <= pair_cap * pair_cap,
                        "v3 raw complex amplitude exceeds its bound",
                    )
                _require(
                    math.fsum(value * value for value in components[:8]) <= density_max,
                    "v3 raw density exceeds its bound",
                )
                epsilon_offset = (
                    (scale_index * 9 * mode_count + 8 * mode_count + site_index)
                    * batch_count
                    + batch_index
                ) * scalar_bytes
                _require(
                    components[8] != 0.0
                    or raw[epsilon_offset:epsilon_offset + scalar_bytes]
                    == b"\x00" * scalar_bytes,
                    "v3 raw epsilon2_ema must not use negative zero",
                )
                _require(
                    0.0 <= components[8] <= epsilon_max,
                    "v3 raw epsilon2_ema is negative or exceeds its bound",
                )


def validate_v3_checkpoint(
    payload: bytes,
    *,
    contract_root: Mapping[str, Any],
    profile: Mapping[str, Any],
    projection_registry: Mapping[str, Any] | bytes | str,
) -> dict[str, Any]:
    """Authenticate a little-endian v3 checkpoint before any state allocation."""

    _require(isinstance(payload, bytes), "v3 checkpoint must be bytes")
    _require(
        len(STATE_V3_MAGIC) + 8 <= len(payload) <= MAX_STATE_V3_CHECKPOINT_BYTES,
        "v3 checkpoint byte budget is invalid",
    )
    _require(payload.startswith(STATE_V3_MAGIC), "v3 checkpoint rejects legacy framing")
    offset = len(STATE_V3_MAGIC)
    header_size = struct.unpack(">Q", payload[offset:offset + 8])[0]
    _require(
        0 < header_size <= MAX_STATE_V3_HEADER_BYTES,
        "v3 checkpoint header byte budget is invalid",
    )
    header_start = offset + 8
    header_end = header_start + header_size
    _require(header_end < len(payload), "v3 checkpoint is truncated at header/raw boundary")
    header = _canonical_object(
        payload[header_start:header_end], "v3 checkpoint header"
    )
    raw = payload[header_end:]
    validated = _validate_v3_state_header(header, contract_root, profile)
    active_counts, state_bounds = _validate_state_layout(profile, validated)
    execution = profile.get("execution")
    _require(isinstance(execution, Mapping), "profile execution contract is missing")
    projections = _validate_projection_registry(projection_registry)
    profile_parents = _extract_profile_parents(profile, projections)
    _require(
        validated["state_contract_sha256"] == profile_parents["state_contract"],
        "v3 checkpoint state-contract mismatch",
    )
    schedule = execution.get("schedule")
    _require(
        isinstance(schedule, Mapping)
        and isinstance(schedule.get("schema"), str)
        and validated["execution_schedule_sha256"] == schedule.get("self_sha256"),
        "v3 checkpoint execution-schedule mismatch",
    )
    schedule_body = dict(schedule)
    schedule_self = _require_sha256(
        schedule_body.pop("self_sha256", None),
        "profile execution schedule self_sha256",
    )
    _require(
        canonical_hash(schedule_body, schedule["schema"]) == schedule_self,
        "profile execution schedule self hash mismatch",
    )
    _require(
        validated["topology_sha256"]
        == canonical_hash(
            {
                "spatial": profile.get("spatial"),
                "scale_geometry": profile["scale_geometry"]["state_operator"],
            },
            "cassi.qi-flow.topology",
        ),
        "v3 checkpoint topology mismatch",
    )
    _require(
        validated["source_identity_sha256"] == execution.get("source_identity_sha256"),
        "v3 checkpoint source identity mismatch",
    )
    shape = validated["shape"]
    scalar_bytes = 4 if validated["dtype"] == "float32" else 8
    expected_raw_bytes = shape[0] * shape[1] * shape[2] * scalar_bytes
    _require(
        validated["raw_byte_count"] == expected_raw_bytes == len(raw),
        "v3 checkpoint raw byte count does not match its declared tensor",
    )
    _require(
        len(raw) <= profile["field"]["state_byte_limit"],
        "v3 checkpoint raw bytes exceed profile state budget",
    )
    _validate_v3_raw_semantics(
        raw,
        dtype_name=validated["dtype"],
        shape=shape,
        active_counts=active_counts,
        state_bounds=state_bounds,
    )
    _require(
        hashlib.sha256(raw).hexdigest() == validated["source_raw_sha256"],
        "v3 checkpoint raw digest mismatch",
    )
    _require(
        _v3_tensor_hash(
            raw,
            dtype_name=validated["dtype"],
            shape=shape,
            state_contract_sha256=validated["state_contract_sha256"],
        )
        == validated["state_sha256"],
        "v3 checkpoint state digest mismatch",
    )
    return dict(validated)


def _validate_g1_candidate(
    candidate: Mapping[str, Any],
    *,
    root: Mapping[str, Any],
    profile: Mapping[str, Any],
    checkpoint: Mapping[str, Any],
) -> dict[str, Any]:
    required = {
        "schema", "w1_scope", "parents", "plan_document_set_sha256",
        "profile_sha256", "contract_root_sha256", "state_contract_sha256",
        "execution_schedule_sha256", "topology_sha256", "source_identity_sha256",
        "calibration", "integrated", "exact_restart", "mutation_controls", "self_sha256",
    }
    record = dict(candidate)
    _require(set(record) == required, "G1 identity candidate keyset is not sealed")
    _require(record["schema"] == G1_IDENTITY_CANDIDATE_SCHEMA, "G1 identity candidate schema mismatch")
    _require(record["w1_scope"] == "identity-checkpoint-v3", "G1 identity candidate scope mismatch")
    for name, expected in (
        ("profile_sha256", profile["profile_sha256"]),
        ("contract_root_sha256", root["self_sha256"]),
        ("state_contract_sha256", checkpoint["state_contract_sha256"]),
        ("execution_schedule_sha256", checkpoint["execution_schedule_sha256"]),
        ("topology_sha256", checkpoint["topology_sha256"]),
        ("source_identity_sha256", checkpoint["source_identity_sha256"]),
    ):
        _require(record[name] == expected, f"G1 candidate {name} mismatch")
    calibration = record["calibration"]
    integrated = record["integrated"]
    parents = record["parents"]
    _require(
        isinstance(parents, Sequence)
        and not isinstance(parents, (str, bytes))
        and len(parents) == 1
        and isinstance(parents[0], Mapping)
        and set(parents[0]) == {
            "kind", "path", "artifact_sha256",
            "historical_manifest_sha256", "plan_document_set_sha256",
        }
        and parents[0].get("kind") == "sealed-w0-final",
        "G1 candidate sealed-parent record is malformed",
    )
    for name in (
        "artifact_sha256", "historical_manifest_sha256", "plan_document_set_sha256",
    ):
        _require_sha256(parents[0].get(name), f"G1 candidate parent {name}")
    _require_sha256(record["plan_document_set_sha256"], "G1 candidate plan_document_set_sha256")
    _require(isinstance(calibration, Mapping) and isinstance(integrated, Mapping), "G1 candidate states are malformed")
    _require(
        set(calibration) == {
            "profile_sha256", "contract_root_sha256", "state_contract_sha256",
            "execution_schedule_sha256", "topology_sha256", "source_identity_sha256",
            "state_sha256", "source_raw_sha256", "shape",
        }
        and set(integrated) == {"state_sha256", "source_raw_sha256", "shape"},
        "G1 candidate state records are not sealed",
    )
    for name, expected in (
        ("profile_sha256", profile["profile_sha256"]),
        ("contract_root_sha256", root["self_sha256"]),
        ("state_contract_sha256", checkpoint["state_contract_sha256"]),
        ("execution_schedule_sha256", checkpoint["execution_schedule_sha256"]),
        ("topology_sha256", checkpoint["topology_sha256"]),
        ("source_identity_sha256", checkpoint["source_identity_sha256"]),
    ):
        _require(calibration.get(name) == expected, f"G1 calibration {name} selects another profile")
    expected_calibration_shape = [
        profile["field"]["scale_count"],
        9 * profile["field"]["mode_count"],
        1,
    ]
    _require(calibration.get("shape") == expected_calibration_shape, "G1 calibration shape mismatch")
    _require_sha256(calibration.get("state_sha256"), "G1 calibration state_sha256")
    _require_sha256(calibration.get("source_raw_sha256"), "G1 calibration source_raw_sha256")
    _require(integrated.get("state_sha256") == checkpoint["state_sha256"], "G1 integrated state digest mismatch")
    _require(integrated.get("source_raw_sha256") == checkpoint["source_raw_sha256"], "G1 integrated raw digest mismatch")
    _require(integrated.get("shape") == checkpoint["shape"], "G1 integrated shape mismatch")
    restart = record["exact_restart"]
    _require(isinstance(restart, Mapping), "G1 restart record is malformed")
    _require(
        restart.get("raw_bits_equal") is True
        and restart.get("state_sha256") == checkpoint["state_sha256"]
        and restart.get("same_backend") == checkpoint["backend"],
        "G1 exact restart is not authenticated",
    )
    controls = record["mutation_controls"]
    _require(
        isinstance(controls, Mapping)
        and set(controls) == _G1_MUTATION_CONTROLS
        and all(value is True for value in controls.values()),
        "G1 mutation controls are incomplete or failed",
    )
    self_sha256 = _require_sha256(record["self_sha256"], "G1 candidate self_sha256")
    without_self = dict(record)
    without_self.pop("self_sha256")
    _require(
        canonical_hash(without_self, G1_IDENTITY_CANDIDATE_SCHEMA) == self_sha256,
        "G1 candidate self hash mismatch",
    )
    return record


def _receipt_domain(schema: str) -> str:
    return f"cassi.qi-flow.receipt.v1:{schema}"

def _validate_consumed_parents(
    receipt: Mapping[str, Any],
    expected_names: Sequence[str],
    profile_parents: Mapping[str, str] | None,
) -> None:
    parents = receipt.get("consumed_semantic_subhashes")
    _require(isinstance(parents, Sequence) and not isinstance(parents, (str, bytes)), "receipt parents must be an array")
    _require(len(parents) == len(expected_names), "receipt parent count does not match registry")
    actual_names: list[str] = []
    for index, parent in enumerate(parents):
        _require(isinstance(parent, Mapping), "receipt parent must be an object")
        _require(set(parent) == {"name", "sha256"}, "receipt parent must contain only name and sha256")
        raw_name = parent.get("name")
        _require(
            isinstance(raw_name, str) and raw_name.endswith("_sha256"),
            "receipt parent name must use the canonical sha256 suffix",
        )
        name = raw_name.removesuffix("_sha256")
        actual_names.append(name)
        digest = _require_sha256(parent.get("sha256"), f"receipt parent {raw_name}")
        if profile_parents is not None:
            _require(profile_parents.get(name) == digest, f"receipt parent digest mismatches profile: {raw_name}")
    _require(tuple(actual_names) == tuple(expected_names), "receipt parents are missing, duplicated, or reordered")


_W1_POST_INDEX_ATTESTATIONS = frozenset(
    {"gates/g01-identity/verification.json"}
)


def _safe_relative_path(relative: Any, context: str) -> Path:
    _require(isinstance(relative, str) and relative, f"{context} path is invalid")
    candidate = Path(relative)
    _require(
        "\\" not in relative
        and not candidate.is_absolute()
        and ".." not in candidate.parts
        and candidate.as_posix() == relative,
        f"{context} path is unsafe",
    )
    return candidate


def _outside_run_tree(path: Path, root_path: Path) -> None:
    try:
        path.resolve().relative_to(root_path.resolve())
    except ValueError:
        return
    raise VerificationError("trusted bootstrap source must be outside the candidate run tree")


def _validate_w1_source_identity(
    root_path: Path,
    *,
    contract_root: Mapping[str, Any],
    profile: Mapping[str, Any],
    bootstrap_identity: Mapping[str, Any],
    canonical_fixture_corpus: Mapping[str, Any],
    canonical_codec: Mapping[str, Any],
    schema_registry: Mapping[str, Any],
    projection_registry: Mapping[str, Any],
    trusted_bootstrap_source: Path | str,
) -> dict[str, Any]:
    source_identity = _read_object(root_path / "run-spec" / "source-identity.json")
    required = {
        "schema",
        "bootstrap_source_sha256",
        "sources",
        "runtime_source_identity",
        "runtime_source_identity_sha256",
        "canonical_codec_schema",
        "canonical_codec_sha256",
        "canonical_fixture_schema",
        "canonical_fixture_sha256",
        "schema_registry_schema",
        "schema_registry_sha256",
        "projection_registry_schema",
        "projection_registry_sha256",
        "contract_root_sha256",
        "profile_sha256",
        "self_sha256",
    }
    _require(set(source_identity) == required, "W1 source-identity record is malformed")
    _require(
        source_identity["schema"] == SOURCE_IDENTITY_SCHEMA,
        "W1 source-identity schema mismatch",
    )
    _require(
        source_identity["bootstrap_source_sha256"] == bootstrap_identity["source_sha256"],
        "W1 bootstrap source identity mismatch",
    )
    _require(
        source_identity["canonical_codec_schema"] == CANONICAL_CODEC_SCHEMA
        and source_identity["canonical_codec_sha256"]
        == canonical_hash(canonical_codec, CANONICAL_CODEC_SCHEMA)
        and source_identity["canonical_codec_sha256"]
        == contract_root["canonical_codec"]["sha256"],
        "W1 source identity canonical codec binding mismatch",
    )
    _require(
        source_identity["canonical_fixture_schema"] == CANONICAL_FIXTURE_SCHEMA
        and source_identity["canonical_fixture_sha256"]
        == canonical_fixture_corpus["self_sha256"],
        "W1 source identity canonical fixture binding mismatch",
    )
    registry = _canonical_object(schema_registry, "schema registry")
    projections = _canonical_object(projection_registry, "projection registry")
    _require(
        source_identity["schema_registry_schema"] == SCHEMA_REGISTRY_SCHEMA
        and source_identity["schema_registry_sha256"] == registry["self_sha256"]
        and source_identity["schema_registry_sha256"]
        == contract_root["schema_registry"]["sha256"],
        "W1 source identity schema-registry binding mismatch",
    )
    _require(
        source_identity["projection_registry_schema"] == PROJECTION_REGISTRY_SCHEMA
        and source_identity["projection_registry_sha256"] == projections["self_sha256"]
        and source_identity["projection_registry_sha256"]
        == contract_root["projection_registry"]["sha256"],
        "W1 source identity projection-registry binding mismatch",
    )
    _require(
        source_identity["contract_root_sha256"] == contract_root["self_sha256"]
        and source_identity["profile_sha256"] == profile["profile_sha256"],
        "W1 source identity root/profile binding mismatch",
    )
    runtime_source = source_identity["runtime_source_identity"]
    expected_runtime_source = dict(profile["execution"]["source_identity"])
    expected_runtime_source.pop("self_sha256", None)
    _require(
        isinstance(runtime_source, Mapping)
        and canonical_json_bytes(runtime_source)
        == canonical_json_bytes(expected_runtime_source)
        and source_identity["runtime_source_identity_sha256"]
        == canonical_hash(runtime_source, SOURCE_IDENTITY_SCHEMA)
        and source_identity["runtime_source_identity_sha256"]
        == profile["execution"]["source_identity_sha256"],
        "W1 runtime source identity mismatch",
    )
    source_records = source_identity["sources"]
    _require(isinstance(source_records, list) and source_records, "W1 source records are missing")
    seen: set[str] = set()
    source_paths: list[str] = []
    bootstrap_raw: bytes | None = None
    profile_source_present = False
    for record in source_records:
        _require(
            isinstance(record, Mapping)
            and set(record) == {"path", "byte_count", "sha256"},
            "W1 source record is malformed",
        )
        relative_path = record["path"]
        candidate = _safe_relative_path(relative_path, "W1 source")
        _require(relative_path not in seen, "W1 source path is duplicated")
        _require(
            isinstance(record["byte_count"], int)
            and not isinstance(record["byte_count"], bool)
            and record["byte_count"] >= 0,
            "W1 source byte count is invalid",
        )
        target = root_path / "run-spec" / "sources" / candidate
        _require(target.is_file() and not target.is_symlink(), f"W1 source is missing: {relative_path}")
        raw = target.read_bytes()
        _require(
            len(raw) == record["byte_count"]
            and hashlib.sha256(raw).hexdigest()
            == _require_sha256(record["sha256"], f"W1 source {relative_path}"),
            f"W1 source digest mismatch: {relative_path}",
        )
        seen.add(relative_path)
        source_paths.append(relative_path)
        if relative_path == "cassi_qi_bootstrap.py":
            bootstrap_raw = raw
            _require(
                record["sha256"] == bootstrap_identity["source_sha256"],
                "frozen bootstrap source record does not match bootstrap identity",
            )
        if relative_path == "cassi_qi_profile.py":
            profile_source_present = True
    _require(
        source_paths == sorted(source_paths, key=lambda item: item.encode("utf-8")),
        "W1 source records are reordered",
    )
    actual_source_paths = sorted(
        path.relative_to(root_path / "run-spec" / "sources").as_posix()
        for path in (root_path / "run-spec" / "sources").rglob("*")
        if path.is_file()
    )
    _require(
        source_paths == actual_source_paths and bootstrap_raw is not None and profile_source_present,
        "W1 frozen source manifest is incomplete, extra, or missing bootstrap/profile source",
    )
    trusted_path = Path(trusted_bootstrap_source)
    _require(
        trusted_path.is_file() and not trusted_path.is_symlink(),
        "trusted bootstrap source must be a regular external file",
    )
    _outside_run_tree(trusted_path, root_path)
    trusted_raw = trusted_path.read_bytes()
    trusted_sha256 = hashlib.sha256(trusted_raw).hexdigest()
    _require(
        trusted_sha256 == bootstrap_identity["source_sha256"]
        and trusted_raw == bootstrap_raw,
        "trusted bootstrap source bytes do not exactly match frozen bootstrap source",
    )
    self_sha256 = _require_sha256(
        source_identity["self_sha256"], "W1 source-identity self_sha256"
    )
    without_self = dict(source_identity)
    without_self.pop("self_sha256")
    _require(
        canonical_hash(without_self, SOURCE_IDENTITY_SCHEMA) == self_sha256,
        "W1 source-identity self hash mismatch",
    )
    return source_identity


def _validate_w1_index(
    root_path: Path,
    *,
    contract_root: Mapping[str, Any],
    profile: Mapping[str, Any],
    bootstrap_identity: Mapping[str, Any],
    canonical_fixture_corpus: Mapping[str, Any],
    canonical_codec: Mapping[str, Any],
    schema_registry: Mapping[str, Any],
    projection_registry: Mapping[str, Any],
    trusted_bootstrap_source: Path | str,
) -> dict[str, Any]:
    """Verify the immutable candidate index before reading candidate evidence."""

    index = _read_object(root_path / "index.json")
    _require(
        set(index)
        == {
            "schema",
            "run_id",
            "status",
            "parents",
            "contract_root_sha256",
            "profile_sha256",
            "object_count",
            "objects",
            "self_sha256",
        }
        and index["schema"] == W1_INDEX_SCHEMA
        and index["status"] == "CANDIDATE",
        "W1 index keyset/schema/status is not a provisional candidate",
    )
    run_id = _require_sha256(index["run_id"], "W1 run_id")
    _require(
        run_id == root_path.name,
        "W1 run directory does not match its run_id",
    )
    records = index["objects"]
    _require(isinstance(records, list) and records, "W1 index objects are invalid")
    declared_paths: list[str] = []
    for record in records:
        _require(
            isinstance(record, Mapping)
            and set(record) == {"path", "byte_count", "sha256"},
            "W1 index object record is malformed",
        )
        relative = record["path"]
        candidate = _safe_relative_path(relative, "W1 index object")
        _require(relative not in declared_paths, "W1 index object path is duplicated")
        _require(
            isinstance(record["byte_count"], int)
            and not isinstance(record["byte_count"], bool)
            and record["byte_count"] >= 0,
            "W1 index object byte count is invalid",
        )
        target = root_path / candidate
        _require(
            target.is_file() and not target.is_symlink(),
            f"W1 index object is missing: {relative}",
        )
        raw = target.read_bytes()
        _require(
            len(raw) == record["byte_count"]
            and hashlib.sha256(raw).hexdigest()
            == _require_sha256(record["sha256"], f"W1 index object {relative}"),
            f"W1 index object digest mismatch: {relative}",
        )
        declared_paths.append(relative)
    _require(
        declared_paths == sorted(declared_paths, key=lambda item: item.encode("utf-8")),
        "W1 index objects are reordered",
    )
    _require(
        index["object_count"] == len(records)
        and index["contract_root_sha256"] == contract_root["self_sha256"]
        and index["profile_sha256"] == profile["profile_sha256"],
        "W1 index count or contract identity is invalid",
    )
    parent_link = _read_object(root_path / "run-spec" / "parent-link.json")
    _require(
        set(parent_link) == {"schema", "parents", "normative_document_set"}
        and parent_link["schema"] == "cassi.qi-flow-parent-link.v1"
        and index["parents"] == parent_link["parents"],
        "W1 index parent linkage is invalid",
    )
    run_material = {
        "schema": W1_ARTIFACT_SCHEMA,
        "parents": index["parents"],
        "objects": records,
        "contract_root_sha256": index["contract_root_sha256"],
        "profile_sha256": index["profile_sha256"],
    }
    _require(
        canonical_hash(run_material, W1_ARTIFACT_SCHEMA) == run_id,
        "W1 run_id does not bind the immutable object records",
    )
    actual_paths = sorted(
        path.relative_to(root_path).as_posix()
        for path in root_path.rglob("*")
        if path.is_file() and path != root_path / "index.json"
    )
    observed_post = set(actual_paths) & _W1_POST_INDEX_ATTESTATIONS
    _require(
        observed_post == set() or observed_post == set(_W1_POST_INDEX_ATTESTATIONS),
        "W1 post-index attestations must be absent together or present together",
    )
    immutable_paths = [
        path for path in actual_paths if path not in _W1_POST_INDEX_ATTESTATIONS
    ]
    _require(
        declared_paths == immutable_paths,
        "W1 index does not cover every immutable candidate object",
    )
    self_sha256 = _require_sha256(index["self_sha256"], "W1 index self_sha256")
    without_self = dict(index)
    without_self.pop("self_sha256")
    _require(
        canonical_hash(without_self, W1_INDEX_SCHEMA) == self_sha256,
        "W1 index self hash mismatch",
    )
    _validate_w1_source_identity(
        root_path,
        contract_root=contract_root,
        profile=profile,
        bootstrap_identity=bootstrap_identity,
        canonical_fixture_corpus=canonical_fixture_corpus,
        canonical_codec=canonical_codec,
        schema_registry=schema_registry,
        projection_registry=projection_registry,
        trusted_bootstrap_source=trusted_bootstrap_source,
    )
    return index


def validate_artifact(
    payload_or_bytes: Mapping[str, Any] | bytes | str,
    *,
    contract_root: Mapping[str, Any] | bytes | str,
    canonical_codec: Mapping[str, Any] | bytes | str,
    canonical_fixture_corpus: Mapping[str, Any] | bytes | str,
    schema_registry: Path,
    projection_registry: Mapping[str, Any] | bytes | str,
    profile_defaults: Mapping[str, Any] | bytes | str,
    bootstrap_identity: Mapping[str, Any] | bytes | str,
    profile: Mapping[str, Any] | bytes | str | None = None,
    expected_schema: str | None = None,
) -> dict[str, Any]:
    """Validate one root-bound receipt or structural artifact from canonical bytes."""

    root, entries = validate_root_components(
        contract_root=contract_root,
        canonical_codec=canonical_codec,
        canonical_fixture_corpus=canonical_fixture_corpus,
        schema_registry=schema_registry,
        projection_registry=projection_registry,
        profile_defaults=profile_defaults,
        bootstrap_identity=bootstrap_identity,
    )
    artifact = _canonical_object(
        payload_or_bytes,
        "artifact",
        max_bytes=MAX_LARGE_JSON_BYTES,
    )
    schema = artifact.get("schema")
    _require(isinstance(schema, str), "artifact schema must be a string")
    _reject_legacy_schema(artifact)
    if expected_schema is not None:
        _require(
            schema == expected_schema,
            f"artifact schema mismatch: expected {expected_schema}, got {schema}",
        )
    _require(schema in entries, f"unknown W1 artifact schema: {schema}")
    registration = entries[schema]
    _require(
        len(canonical_json_bytes(artifact, max_bytes=MAX_LARGE_JSON_BYTES))
        <= registration["max_encoded_bytes"],
        "artifact exceeds registered byte budget",
    )
    document = registration["schema_document"]
    _validate_schema_value(
        artifact,
        {
            "type": "object",
            "required_keys": document["required_keys"],
            "optional_keys": document["optional_keys"],
            "nullable_keys": document["nullable_keys"],
            "properties": document["properties"],
        },
        f"artifact {schema}",
    )
    validated_profile = (
        validate_profile(
            profile,
            contract_root=root,
            profile_defaults=profile_defaults,
            projection_registry=projection_registry,
        )
        if profile is not None
        else None
    )
    if schema == STATE_SCHEMA_V3:
        _require(validated_profile is not None, "v3 state header requires a profile")
        return _validate_v3_state_header(artifact, root, validated_profile)
    is_receipt = registration["object_class"] == "indexed-receipt"
    if is_receipt:
        _require(
            validated_profile is not None,
            "root-bound receipt requires a validated profile",
        )
        _require(
            artifact["contract_root_sha256"] == root["self_sha256"]
            and artifact["profile_sha256"] == validated_profile["profile_sha256"],
            "receipt root/profile identity mismatch",
        )
        profile_parents = _extract_profile_parents(
            validated_profile,
            _validate_projection_registry(projection_registry),
        )
        _validate_consumed_parents(
            artifact,
            [
                name.removesuffix("_sha256")
                for name in registration["semantic_parent_names"]
            ],
            profile_parents,
        )
    self_hash_field = registration["self_hash_field"]
    self_sha256 = _require_sha256(
        artifact.get(self_hash_field),
        f"artifact {self_hash_field}",
    )
    without_self = dict(artifact)
    without_self.pop(self_hash_field)
    _require(
        canonical_hash(
            without_self,
            registration["hash_domain"],
            max_bytes=MAX_LARGE_JSON_BYTES,
        )
        == self_sha256,
        "artifact self hash mismatch",
    )
    if is_receipt:
        _validate_budget_fields(artifact)
    return artifact


def validate_fixture(
    payload_or_bytes: Mapping[str, Any] | bytes | str,
    *,
    schema: str,
    schema_registry: Mapping[str, Any],
) -> dict[str, Any]:
    """Check a registry fixture through the independent canonical codec."""

    entries = validate_schema_registry(schema_registry)
    _require(schema in entries, f"unknown fixture schema: {schema}")
    fixture = _canonical_object(payload_or_bytes, "fixture")
    document = entries[schema]["schema_document"]
    _validate_schema_value(
        fixture,
        {
            "type": "object",
            "required_keys": document["required_keys"],
            "optional_keys": document["optional_keys"],
            "nullable_keys": document["nullable_keys"],
            "properties": document["properties"],
        },
        f"fixture {schema}",
    )
    _require(fixture.get("schema") == schema, "fixture schema mismatch")
    expected = entries[schema]["fixture_sha256"]
    actual = canonical_hash(fixture, "cassi.qi-flow.fixture")
    _require(actual == expected, "fixture identity mismatch")
    _require(
        len(canonical_json_bytes(fixture)) <= entries[schema]["max_bytes"],
        "fixture exceeds schema byte budget",
    )
    return fixture


def _read_object(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise VerificationError(f"cannot read {path}: {error}") from error
    return _canonical_object(raw, str(path))


def _w2_exact_mapping(
    value: Any,
    keys: set[str],
    context: str,
) -> dict[str, Any]:
    _require(isinstance(value, Mapping), f"{context} must be an object")
    record = dict(value)
    _require(set(record) == keys, f"{context} keyset is not sealed")
    return record


def _w2_f64(value: Any, context: str) -> float:
    _require(isinstance(value, str), f"{context} must be an f64 finite-bit string")
    match = _FLOAT_BITS.fullmatch(value)
    _require(match is not None and match.group(1) == "64", f"{context} must be an f64 finite-bit string")
    _validate_tagged_float(value, context)
    return struct.unpack(">d", bytes.fromhex(match.group(2)))[0]


def _w2_parent_w1(value: Any, context: str) -> dict[str, Any]:
    record = _w2_exact_mapping(
        value,
        {
            "kind",
            "run_id",
            "path",
            "index_sha256",
            "contract_root_sha256",
            "profile_sha256",
        },
        context,
    )
    _require(
        canonical_json_bytes(record) == canonical_json_bytes(_W2_PARENT_W1),
        f"{context} does not bind the approved sealed W1/G1 parent",
    )
    return record


def _w2_component(
    value: Any,
    *,
    schema: str,
    sha256: str,
    context: str,
) -> dict[str, Any]:
    record = _w2_exact_mapping(value, {"schema", "sha256"}, context)
    _require(record["schema"] == schema, f"{context} schema mismatch")
    _require(
        record["sha256"] == sha256,
        f"{context} digest linkage mismatch",
    )
    return record


def _w2_registry_spec() -> dict[str, tuple[int, tuple[str, ...]]]:
    return {
        W2_CONTRACT_ROOT_SCHEMA: (65536, ()),
        W2_PROFILE_SCHEMA: (
            65536,
            ("geometry_contract_sha256", "operator_semantic_sha256"),
        ),
        W2_GEOMETRY_CONTRACT_SCHEMA: (65536, ()),
        W2_OPERATOR_SEMANTIC_SCHEMA: (65536, ("geometry_contract_sha256",)),
        W2_PARENT_LINK_SCHEMA: (65536, ()),
        W2_SOURCE_IDENTITY_SCHEMA: (65536, ()),
        G2_GEOMETRY_CANDIDATE_SCHEMA: (
            262144,
            ("geometry_contract_sha256", "operator_semantic_sha256"),
        ),
        GATE_STATUS_SCHEMA: (
            65536,
            ("geometry_contract_sha256", "operator_semantic_sha256"),
        ),
        W2_INDEX_SCHEMA: (1048576, ()),
    }


def _validate_w2_schema_registry(registry: Mapping[str, Any]) -> dict[str, int]:
    record = _w2_exact_mapping(registry, {"schema", "entries"}, "W2 schema registry")
    _require(record["schema"] == W2_SCHEMA_REGISTRY_SCHEMA, "W2 schema registry schema mismatch")
    entries = record["entries"]
    _require(isinstance(entries, list), "W2 schema registry entries must be an array")
    specification = _w2_registry_spec()
    expected_schemas = sorted(specification)
    _require(len(entries) == len(expected_schemas), "W2 schema registry entry count mismatch")
    budgets: dict[str, int] = {}
    observed_schemas: list[str] = []
    for entry, expected_schema in zip(entries, expected_schemas, strict=True):
        item = _w2_exact_mapping(
            entry,
            {"schema", "max_bytes", "semantic_parents"},
            "W2 schema registry entry",
        )
        max_bytes, semantic_parents = specification[expected_schema]
        _require(item["schema"] == expected_schema, "W2 schema registry entries are missing, duplicated, or reordered")
        _require(
            isinstance(item["max_bytes"], int)
            and not isinstance(item["max_bytes"], bool)
            and item["max_bytes"] == max_bytes,
            f"W2 schema registry budget mismatch: {expected_schema}",
        )
        _require(
            isinstance(item["semantic_parents"], list)
            and item["semantic_parents"] == list(semantic_parents),
            f"W2 schema registry semantic-parent mismatch: {expected_schema}",
        )
        observed_schemas.append(expected_schema)
        budgets[expected_schema] = max_bytes
    _require(observed_schemas == expected_schemas, "W2 schema registry is not deterministically sorted")
    _require(
        len(canonical_json_bytes(record)) <= 65536,
        "W2 schema registry exceeds its byte budget",
    )
    return budgets


def _w2_within_budget(
    value: Mapping[str, Any],
    *,
    schema: str,
    budgets: Mapping[str, int],
    context: str,
) -> None:
    _require(schema in budgets, f"{context} has an unregistered schema")
    _require(
        len(canonical_json_bytes(value)) <= budgets[schema],
        f"{context} exceeds its schema byte budget",
    )


def _validate_w2_geometry_contract(
    geometry: Mapping[str, Any],
    *,
    budgets: Mapping[str, int],
) -> str:
    record = _w2_exact_mapping(
        geometry,
        {
            "schema",
            "axis_order",
            "grid_shape",
            "mode_count",
            "flattening",
            "units",
            "boundary_condition",
            "domain_lengths_m",
            "spacings_m",
            "coordinate_origin_m",
            "nyquist",
            "differential",
            "workspace_byte_cap",
        },
        "W2 geometry contract",
    )
    _require(record["schema"] == W2_GEOMETRY_CONTRACT_SCHEMA, "W2 geometry contract schema mismatch")
    _require(record["axis_order"] == list(W2_AXIS_ORDER), "W2 geometry axis order mismatch")
    _require(record["grid_shape"] == list(W2_GRID_SHAPE), "W2 geometry grid shape mismatch")
    _require(record["mode_count"] == W2_MODE_COUNT, "W2 geometry mode count mismatch")
    _require(
        isinstance(record["flattening"], Mapping)
        and dict(record["flattening"])
        == {
            "formula": "m=((z*Y)+y)*X+x",
            "axis_order": "Z,Y,X",
            "storage": "[M,B]<->[Z,Y,X,B]",
        },
        "W2 geometry flattening contract mismatch",
    )
    _require(
        isinstance(record["units"], Mapping)
        and dict(record["units"])
        == {
            "coordinate": "m",
            "gradient": "m^-1",
            "laplacian": "m^-2",
        },
        "W2 geometry unit contract mismatch",
    )
    _require(record["boundary_condition"] == "periodic", "W2 geometry boundary contract mismatch")
    _require(
        record["domain_lengths_m"] == list(W2_DOMAIN_LENGTHS_M),
        "W2 geometry physical domain lengths mismatch",
    )
    _require(
        record["spacings_m"] == list(W2_SPACINGS_M),
        "W2 geometry physical spacings mismatch",
    )
    _require(
        record["coordinate_origin_m"] == list(W2_COORDINATE_ORIGIN_M),
        "W2 geometry coordinate origin mismatch",
    )
    _require(
        isinstance(record["nyquist"], Mapping)
        and dict(record["nyquist"]) == _W2_GEOMETRY_NYQUIST,
        "W2 geometry Nyquist convention mismatch",
    )
    _require(
        isinstance(record["differential"], Mapping)
        and dict(record["differential"]) == _W2_GEOMETRY_DIFFERENTIAL,
        "W2 geometry differential operator identity mismatch",
    )
    _require(
        isinstance(record["workspace_byte_cap"], int)
        and not isinstance(record["workspace_byte_cap"], bool)
        and record["workspace_byte_cap"] == W2_WORKSPACE_BYTE_CAP,
        "W2 geometry workspace cap mismatch",
    )
    _w2_within_budget(
        record,
        schema=W2_GEOMETRY_CONTRACT_SCHEMA,
        budgets=budgets,
        context="W2 geometry contract",
    )
    return canonical_hash(record, W2_GEOMETRY_CONTRACT_SCHEMA)


def _validate_w2_operator_semantic(
    operator: Mapping[str, Any],
    *,
    geometry: Mapping[str, Any],
    geometry_sha256: str,
    budgets: Mapping[str, int],
) -> str:
    expected = {
        "schema": W2_OPERATOR_SEMANTIC_SCHEMA,
        "geometry_contract_sha256": geometry_sha256,
        "dtype": "float64",
        "device": "cpu",
        "inner_product": "sum(conj(a)*b)*dz*dy*dx",
        "gradient": "centered-periodic-roll",
        "divergence": "sum_axis_first_derivatives",
        "curl": "right-handed-[z,y,x]",
        "laplacian": "Dzz+Dyy+Dxx",
        "delta_perp_identity": "Delta_perp=Dyy+Dxx",
        "delta_s_identity": "Delta_s=Dzz",
        "nyquist": dict(geometry["nyquist"]),
    }
    record = _w2_exact_mapping(operator, set(expected), "W2 operator semantic")
    _require(
        canonical_json_bytes(record) == canonical_json_bytes(expected),
        "W2 operator semantic contract mismatch",
    )
    _w2_within_budget(
        record,
        schema=W2_OPERATOR_SEMANTIC_SCHEMA,
        budgets=budgets,
        context="W2 operator semantic",
    )
    return canonical_hash(record, W2_OPERATOR_SEMANTIC_SCHEMA)


def _validate_w2_contract_root(
    root: Mapping[str, Any],
    *,
    registry: Mapping[str, Any],
    geometry_sha256: str,
    operator_sha256: str,
    budgets: Mapping[str, int],
) -> str:
    record = _w2_exact_mapping(
        root,
        {
            "schema",
            "contract_root_id",
            "parent_w1",
            "base_profile_sha256",
            "base_contract_root_sha256",
            "schema_registry",
            "geometry_contract",
            "operator_semantic",
            "self_sha256",
        },
        "W2 contract root",
    )
    _require(record["schema"] == W2_CONTRACT_ROOT_SCHEMA, "W2 contract root schema mismatch")
    _require(
        record["contract_root_id"] == "qi-flow-geometry-w2-development-v1",
        "W2 contract root identifier mismatch",
    )
    _w2_parent_w1(record["parent_w1"], "W2 contract root parent_w1")
    _require(
        record["base_profile_sha256"] == _W2_PARENT_W1["profile_sha256"]
        and record["base_contract_root_sha256"] == _W2_PARENT_W1["contract_root_sha256"],
        "W2 contract root base W1 linkage mismatch",
    )
    registry_sha256 = canonical_hash(registry, W2_SCHEMA_REGISTRY_SCHEMA)
    _w2_component(
        record["schema_registry"],
        schema=W2_SCHEMA_REGISTRY_SCHEMA,
        sha256=registry_sha256,
        context="W2 contract root schema registry",
    )
    _w2_component(
        record["geometry_contract"],
        schema=W2_GEOMETRY_CONTRACT_SCHEMA,
        sha256=geometry_sha256,
        context="W2 contract root geometry contract",
    )
    _w2_component(
        record["operator_semantic"],
        schema=W2_OPERATOR_SEMANTIC_SCHEMA,
        sha256=operator_sha256,
        context="W2 contract root operator semantic",
    )
    self_sha256 = _require_sha256(record["self_sha256"], "W2 contract root self_sha256")
    without_self = dict(record)
    without_self.pop("self_sha256")
    _require(
        canonical_hash(without_self, W2_CONTRACT_ROOT_SCHEMA) == self_sha256,
        "W2 contract root self hash mismatch",
    )
    _w2_within_budget(
        record,
        schema=W2_CONTRACT_ROOT_SCHEMA,
        budgets=budgets,
        context="W2 contract root",
    )
    return self_sha256


def _validate_w2_profile(
    profile: Mapping[str, Any],
    *,
    root_sha256: str,
    registry: Mapping[str, Any],
    geometry: Mapping[str, Any],
    geometry_sha256: str,
    operator: Mapping[str, Any],
    operator_sha256: str,
    budgets: Mapping[str, int],
) -> str:
    record = _w2_exact_mapping(
        profile,
        {
            "schema",
            "parent_w1",
            "base_profile_sha256",
            "base_contract_root_sha256",
            "schema_registry_sha256",
            "geometry_contract",
            "geometry_contract_sha256",
            "operator_semantic",
            "operator_semantic_sha256",
            "contract_root_sha256",
            "profile_sha256",
        },
        "W2 geometry profile",
    )
    _require(record["schema"] == W2_PROFILE_SCHEMA, "W2 geometry profile schema mismatch")
    _w2_parent_w1(record["parent_w1"], "W2 geometry profile parent_w1")
    _require(
        record["base_profile_sha256"] == _W2_PARENT_W1["profile_sha256"]
        and record["base_contract_root_sha256"] == _W2_PARENT_W1["contract_root_sha256"],
        "W2 geometry profile base W1 linkage mismatch",
    )
    _require(
        record["schema_registry_sha256"] == canonical_hash(registry, W2_SCHEMA_REGISTRY_SCHEMA),
        "W2 geometry profile schema registry linkage mismatch",
    )
    _require(
        isinstance(record["geometry_contract"], Mapping)
        and canonical_json_bytes(record["geometry_contract"]) == canonical_json_bytes(geometry),
        "W2 geometry profile embeds a different geometry contract",
    )
    _require(
        record["geometry_contract_sha256"] == geometry_sha256,
        "W2 geometry profile geometry hash mismatch",
    )
    _require(
        isinstance(record["operator_semantic"], Mapping)
        and canonical_json_bytes(record["operator_semantic"]) == canonical_json_bytes(operator),
        "W2 geometry profile embeds a different operator semantic",
    )
    _require(
        record["operator_semantic_sha256"] == operator_sha256,
        "W2 geometry profile operator hash mismatch",
    )
    _require(
        record["contract_root_sha256"] == root_sha256,
        "W2 geometry profile root linkage mismatch",
    )
    profile_sha256 = _require_sha256(record["profile_sha256"], "W2 geometry profile profile_sha256")
    without_profile_sha256 = dict(record)
    without_profile_sha256.pop("profile_sha256")
    _require(
        canonical_hash(without_profile_sha256, W2_PROFILE_SCHEMA) == profile_sha256,
        "W2 geometry profile self hash mismatch",
    )
    _w2_within_budget(
        record,
        schema=W2_PROFILE_SCHEMA,
        budgets=budgets,
        context="W2 geometry profile",
    )
    return profile_sha256


def _w2_relative_path(value: Any, context: str) -> Path:
    _require(isinstance(value, str) and value, f"{context} must be a nonempty relative path")
    candidate = Path(value)
    _require(
        "\\"
        not in value
        and ":" not in value
        and not candidate.is_absolute()
        and not candidate.drive
        and all(part not in {"", ".", ".."} for part in value.split("/")),
        f"{context} is unsafe",
    )
    return candidate


def _validate_w2_parent_link(parent_link: Mapping[str, Any]) -> list[dict[str, Any]]:
    record = _w2_exact_mapping(parent_link, {"schema", "parents"}, "W2 parent link")
    _require(record["schema"] == W2_PARENT_LINK_SCHEMA, "W2 parent link schema mismatch")
    _require(isinstance(record["parents"], list) and len(record["parents"]) == 1, "W2 parent link parent count mismatch")
    return [_w2_parent_w1(record["parents"][0], "W2 parent link parent")]


def _validate_w2_source_identity(
    root_path: Path,
    source_identity: Mapping[str, Any],
    *,
    budgets: Mapping[str, int],
) -> list[dict[str, str]]:
    record = _w2_exact_mapping(
        source_identity,
        {"schema", "sources"},
        "W2 source identity",
    )
    _require(record["schema"] == W2_SOURCE_IDENTITY_SCHEMA, "W2 source identity schema mismatch")
    sources = record["sources"]
    _require(isinstance(sources, list) and sources, "W2 source identity sources are missing")
    required_sources = {
        "cassi_qi_geometry.py",
        "cassi_qi_field.py",
        "cassi_qi_profile.py",
        "run_cassi_qi_geometry.py",
        "verify_cassi_qi_flow.py",
        "cassi-qi-flow-development.json",
    }
    result: list[dict[str, str]] = []
    source_paths: list[str] = []
    for item in sources:
        source = _w2_exact_mapping(item, {"path", "sha256"}, "W2 source record")
        relative = source["path"]
        candidate = _w2_relative_path(relative, "W2 source path")
        digest = _require_sha256(source["sha256"], f"W2 source {relative}")
        target = root_path / "run-spec" / "sources" / candidate
        _require(
            target.is_file() and not target.is_symlink(),
            f"W2 copied source is missing or symlinked: {relative}",
        )
        try:
            raw = target.read_bytes()
        except OSError as error:
            raise VerificationError(f"cannot read W2 copied source {relative}: {error}") from error
        _require(
            hashlib.sha256(raw).hexdigest() == digest,
            f"W2 copied source digest mismatch: {relative}",
        )
        source_paths.append(relative)
        result.append({"path": relative, "sha256": digest})
    _require(
        source_paths == sorted(source_paths) and len(source_paths) == len(set(source_paths)),
        "W2 source records are duplicated or not deterministically sorted",
    )
    _require(
        required_sources.issubset(source_paths),
        "W2 source identity lacks required primary sources",
    )
    _w2_within_budget(
        record,
        schema=W2_SOURCE_IDENTITY_SCHEMA,
        budgets=budgets,
        context="W2 source identity",
    )
    return result


def _validate_w2_measurement(
    value: Any,
    *,
    errors: tuple[str, ...],
    context: str,
    extras: tuple[str, ...] = (),
) -> dict[str, Any]:
    record = _w2_exact_mapping(value, set(errors) | {"tolerance"} | set(extras), context)
    tolerance = _w2_f64(record["tolerance"], f"{context}.tolerance")
    _require(
        record["tolerance"] == W2_ERROR_TOLERANCE,
        f"{context} tolerance mismatch",
    )
    for name in errors:
        error = _w2_f64(record[name], f"{context}.{name}")
        _require(
            0.0 <= error <= tolerance,
            f"{context}.{name} exceeds its tolerance",
        )
    return record


def _validate_g2_candidate(
    candidate: Mapping[str, Any],
    *,
    root_sha256: str,
    profile_sha256: str,
    geometry: Mapping[str, Any],
    geometry_sha256: str,
    operator_sha256: str,
    budgets: Mapping[str, int],
) -> dict[str, Any]:
    required = {
        "schema",
        "parent_w1",
        "geometry_profile_sha256",
        "geometry_contract_root_sha256",
        "geometry_contract_sha256",
        "operator_semantic_sha256",
        "grid_shape",
        "dtype",
        "device",
        "operator_metadata",
        "manufactured",
        "adjoint",
        "skew_adjoint",
        "delta_identity",
        "flatten_direct_index_error",
        "flatten_batched_reference_error",
        "coordinate_lane_order",
        "workspace",
        "mutation_controls",
        "self_sha256",
    }
    record = _w2_exact_mapping(candidate, required, "G2 geometry candidate")
    _require(record["schema"] == G2_GEOMETRY_CANDIDATE_SCHEMA, "G2 geometry candidate schema mismatch")
    _w2_parent_w1(record["parent_w1"], "G2 geometry candidate parent_w1")
    _require(
        record["geometry_profile_sha256"] == profile_sha256
        and record["geometry_contract_root_sha256"] == root_sha256
        and record["geometry_contract_sha256"] == geometry_sha256
        and record["operator_semantic_sha256"] == operator_sha256,
        "G2 geometry candidate semantic linkage mismatch",
    )
    _require(record["grid_shape"] == list(W2_GRID_SHAPE), "G2 geometry candidate grid shape mismatch")
    _require(
        record["dtype"] == "float64" and record["device"] == "cpu",
        "G2 geometry candidate execution contract mismatch",
    )
    expected_metadata = {
        "geometry_profile_sha256": profile_sha256,
        "geometry_contract_root_sha256": root_sha256,
        "geometry_contract_sha256": geometry_sha256,
        "operator_semantic_sha256": operator_sha256,
        "grid_shape": list(W2_GRID_SHAPE),
        "mode_count": W2_MODE_COUNT,
        "axis_order": list(W2_AXIS_ORDER),
        "domain_lengths_m": list(W2_DOMAIN_LENGTHS_M),
        "spacings_m": list(W2_SPACINGS_M),
        "units": {
            "coordinate": "m",
            "gradient": "m^-1",
            "laplacian": "m^-2",
        },
        "nyquist": dict(geometry["nyquist"]),
        "differential": dict(geometry["differential"]),
        "workspace_byte_cap": W2_WORKSPACE_BYTE_CAP,
    }
    metadata = _w2_exact_mapping(
        record["operator_metadata"],
        set(expected_metadata),
        "G2 geometry candidate operator metadata",
    )
    _require(
        canonical_json_bytes(metadata) == canonical_json_bytes(expected_metadata),
        "G2 geometry candidate operator metadata mismatch",
    )
    manufactured = _w2_exact_mapping(
        record["manufactured"],
        {
            "constant",
            "linear",
            "quadratic",
            "sinusoid",
            "mixed_frequency",
            "nyquist",
        },
        "G2 manufactured measurement set",
    )
    for name in (
        "constant",
        "linear",
        "quadratic",
        "sinusoid",
        "mixed_frequency",
        "nyquist",
    ):
        _validate_w2_measurement(
            manufactured[name],
            errors=("gradient_max_abs_error", "laplacian_max_abs_error"),
            context=f"G2 manufactured {name}",
        )
    _validate_w2_measurement(
        record["adjoint"],
        errors=("derivative_inner_product_residual", "laplacian_inner_product_residual"),
        context="G2 adjoint measurement",
    )
    _validate_w2_measurement(
        record["skew_adjoint"],
        errors=("z_residual", "y_residual", "x_residual"),
        context="G2 skew-adjoint measurement",
    )
    delta_identity = _w2_exact_mapping(
        record["delta_identity"],
        {"max_abs_error", "tolerance", "delta_perp", "delta_s"},
        "G2 delta identity measurement",
    )
    _require(
        delta_identity["delta_perp"] == _W2_GEOMETRY_DIFFERENTIAL["delta_perp"]
        and delta_identity["delta_s"] == _W2_GEOMETRY_DIFFERENTIAL["delta_s"],
        "G2 delta identity operator definitions mismatch",
    )
    _validate_w2_measurement(
        delta_identity,
        errors=("max_abs_error",),
        extras=("delta_perp", "delta_s"),
        context="G2 delta identity measurement",
    )
    _validate_w2_measurement(
        record["flatten_direct_index_error"],
        errors=("max_abs_error",),
        context="G2 direct flatten measurement",
    )
    _validate_w2_measurement(
        record["flatten_batched_reference_error"],
        errors=("max_abs_error",),
        context="G2 batched flatten measurement",
    )
    coordinate_lane_order = _w2_exact_mapping(
        record["coordinate_lane_order"],
        {"coordinate_origin_m", "lane_order", "max_abs_error", "tolerance"},
        "G2 coordinate/lane-order measurement",
    )
    _require(
        coordinate_lane_order["coordinate_origin_m"] == list(W2_COORDINATE_ORIGIN_M)
        and coordinate_lane_order["lane_order"] == "[M,B]",
        "G2 coordinate/lane-order contract mismatch",
    )
    _validate_w2_measurement(
        coordinate_lane_order,
        errors=("max_abs_error",),
        extras=("coordinate_origin_m", "lane_order"),
        context="G2 coordinate/lane-order measurement",
    )
    workspace = _w2_exact_mapping(
        record["workspace"],
        {
            "workspace_byte_cap",
            "scalar_batch4_estimate_bytes",
            "vector_batch4_estimate_bytes",
        },
        "G2 workspace measurement",
    )
    _require(
        workspace["workspace_byte_cap"] == W2_WORKSPACE_BYTE_CAP,
        "G2 workspace cap mismatch",
    )
    for name in ("scalar_batch4_estimate_bytes", "vector_batch4_estimate_bytes"):
        _require(
            isinstance(workspace[name], int)
            and not isinstance(workspace[name], bool)
            and 0 <= workspace[name] <= W2_WORKSPACE_BYTE_CAP,
            f"G2 workspace measurement is invalid: {name}",
        )
    controls = _w2_exact_mapping(
        record["mutation_controls"],
        set(_G2_MUTATION_CONTROLS),
        "G2 mutation controls",
    )
    _require(
        all(value is True for value in controls.values()),
        "G2 mutation controls are incomplete or failed",
    )
    self_sha256 = _require_sha256(record["self_sha256"], "G2 geometry candidate self_sha256")
    without_self = dict(record)
    without_self.pop("self_sha256")
    _require(
        canonical_hash(without_self, G2_GEOMETRY_CANDIDATE_SCHEMA) == self_sha256,
        "G2 geometry candidate self hash mismatch",
    )
    _w2_within_budget(
        record,
        schema=G2_GEOMETRY_CANDIDATE_SCHEMA,
        budgets=budgets,
        context="G2 geometry candidate",
    )
    return record


def _w2_tree_paths(root_path: Path, expected_files: Sequence[str]) -> None:
    expected = set(expected_files)
    allowed_directories = {"run-spec", "run-spec/sources", "gates", "gates/g02-geometry"}
    for relative in expected:
        candidate = Path(relative)
        for parent in candidate.parents:
            if parent != Path("."):
                allowed_directories.add(parent.as_posix())
    observed_files: set[str] = set()
    try:
        paths = list(root_path.rglob("*"))
    except OSError as error:
        raise VerificationError(f"cannot enumerate W2 artifact tree: {error}") from error
    for path in paths:
        relative = path.relative_to(root_path).as_posix()
        _require(not path.is_symlink(), f"W2 artifact contains a symlink: {relative}")
        if path.is_file():
            observed_files.add(relative)
        elif path.is_dir():
            _require(relative in allowed_directories, f"W2 artifact contains an unexpected directory: {relative}")
        else:
            raise VerificationError(f"W2 artifact contains a nonregular path: {relative}")
    _require(observed_files == expected, "W2 artifact layout has missing or extra immutable objects")


def _validate_w2_index(
    root_path: Path,
    *,
    parent_w1: Sequence[Mapping[str, Any]],
    root_sha256: str,
    profile_sha256: str,
    source_records: Sequence[Mapping[str, str]],
    budgets: Mapping[str, int],
) -> dict[str, Any]:
    index = _read_object(root_path / "index.json")
    required = {
        "schema",
        "run_id",
        "status",
        "parents",
        "contract_root_sha256",
        "profile_sha256",
        "object_count",
        "objects",
        "self_sha256",
    }
    record = _w2_exact_mapping(index, required, "W2 index")
    _require(record["schema"] == W2_INDEX_SCHEMA, "W2 index schema mismatch")
    _require(record["status"] == "PASS_W2_G2", "W2 index status mismatch")
    _require(
        record["contract_root_sha256"] == root_sha256
        and record["profile_sha256"] == profile_sha256,
        "W2 index profile/root linkage mismatch",
    )
    _require(
        canonical_json_bytes(record["parents"]) == canonical_json_bytes(list(parent_w1)),
        "W2 index parent linkage mismatch",
    )
    objects = record["objects"]
    _require(
        isinstance(objects, list)
        and isinstance(record["object_count"], int)
        and not isinstance(record["object_count"], bool)
        and record["object_count"] == len(objects),
        "W2 index object count mismatch",
    )
    declared_paths: list[str] = []
    for item in objects:
        object_record = _w2_exact_mapping(
            item,
            {"path", "byte_count", "sha256"},
            "W2 index object record",
        )
        relative = object_record["path"]
        candidate = _w2_relative_path(relative, "W2 index object path")
        _require(
            isinstance(object_record["byte_count"], int)
            and not isinstance(object_record["byte_count"], bool)
            and object_record["byte_count"] >= 0,
            "W2 index object byte count is malformed",
        )
        digest = _require_sha256(object_record["sha256"], f"W2 index object {relative}")
        target = root_path / candidate
        _require(
            target.is_file() and not target.is_symlink(),
            f"W2 index object is missing or symlinked: {relative}",
        )
        try:
            raw = target.read_bytes()
        except OSError as error:
            raise VerificationError(f"cannot read W2 index object {relative}: {error}") from error
        _require(
            len(raw) == object_record["byte_count"]
            and hashlib.sha256(raw).hexdigest() == digest,
            f"W2 index object digest mismatch: {relative}",
        )
        declared_paths.append(relative)
    _require(
        declared_paths == sorted(declared_paths) and len(declared_paths) == len(set(declared_paths)),
        "W2 index objects are duplicated or not deterministically sorted",
    )
    static_paths = {
        "run-spec/w2-contract-root.json",
        "run-spec/w2-profile.json",
        "run-spec/w2-geometry-contract.json",
        "run-spec/w2-operator-contract.json",
        "run-spec/w2-schema-registry.json",
        "run-spec/parent-link.json",
        "run-spec/source-identity.json",
        "gates/g02-geometry/geometry.json",
        "gates/g02-geometry/status.json",
    }
    source_paths = {f"run-spec/sources/{item['path']}" for item in source_records}
    expected_paths = sorted(static_paths | source_paths)
    _require(
        declared_paths == expected_paths,
        "W2 index does not cover exactly the sealed G2 layout",
    )
    _w2_tree_paths(root_path, [*expected_paths, "index.json"])
    self_sha256 = _require_sha256(record["self_sha256"], "W2 index self_sha256")
    without_self = dict(record)
    without_self.pop("self_sha256")
    _require(
        canonical_hash(without_self, W2_INDEX_SCHEMA) == self_sha256,
        "W2 index self hash mismatch",
    )
    material = {
        "schema": W2_ARTIFACT_SCHEMA,
        "parents": record["parents"],
        "objects": objects,
        "contract_root_sha256": root_sha256,
        "profile_sha256": profile_sha256,
    }
    _require(
        record["run_id"] == canonical_hash(material, W2_ARTIFACT_SCHEMA),
        "W2 index content-addressed run identity mismatch",
    )
    _w2_within_budget(
        record,
        schema=W2_INDEX_SCHEMA,
        budgets=budgets,
        context="W2 index",
    )
    return record


def verify_g2_geometry(run_root: str | Path) -> dict[str, Any]:
    """Read and independently verify one immutable W2/G2 geometry artifact."""

    root_path = Path(run_root).resolve()
    spec = root_path / "run-spec"
    gate_dir = root_path / "gates" / "g02-geometry"
    registry = _read_object(spec / "w2-schema-registry.json")
    budgets = _validate_w2_schema_registry(registry)
    geometry = _read_object(spec / "w2-geometry-contract.json")
    geometry_sha256 = _validate_w2_geometry_contract(geometry, budgets=budgets)
    operator = _read_object(spec / "w2-operator-contract.json")
    operator_sha256 = _validate_w2_operator_semantic(
        operator,
        geometry=geometry,
        geometry_sha256=geometry_sha256,
        budgets=budgets,
    )
    root = _read_object(spec / "w2-contract-root.json")
    root_sha256 = _validate_w2_contract_root(
        root,
        registry=registry,
        geometry_sha256=geometry_sha256,
        operator_sha256=operator_sha256,
        budgets=budgets,
    )
    profile = _read_object(spec / "w2-profile.json")
    profile_sha256 = _validate_w2_profile(
        profile,
        root_sha256=root_sha256,
        registry=registry,
        geometry=geometry,
        geometry_sha256=geometry_sha256,
        operator=operator,
        operator_sha256=operator_sha256,
        budgets=budgets,
    )
    parent_link = _read_object(spec / "parent-link.json")
    parents = _validate_w2_parent_link(parent_link)
    source_identity = _read_object(spec / "source-identity.json")
    source_records = _validate_w2_source_identity(
        root_path,
        source_identity,
        budgets=budgets,
    )
    candidate = _validate_g2_candidate(
        _read_object(gate_dir / "geometry.json"),
        root_sha256=root_sha256,
        profile_sha256=profile_sha256,
        geometry=geometry,
        geometry_sha256=geometry_sha256,
        operator_sha256=operator_sha256,
        budgets=budgets,
    )
    status = _w2_exact_mapping(
        _read_object(gate_dir / "status.json"),
        {
            "schema",
            "gate",
            "status",
            "geometry_profile_sha256",
            "geometry_contract_root_sha256",
            "geometry_contract_sha256",
            "operator_semantic_sha256",
            "candidate_sha256",
            "registered_schema_count",
            "workspace_peak_bytes",
        },
        "G2 status",
    )
    _require(status["schema"] == GATE_STATUS_SCHEMA, "G2 status schema mismatch")
    _require(status["gate"] == "G2" and status["status"] == "PASS", "G2 status is not PASS")
    _require(
        status["geometry_profile_sha256"] == profile_sha256
        and status["geometry_contract_root_sha256"] == root_sha256
        and status["geometry_contract_sha256"] == geometry_sha256
        and status["operator_semantic_sha256"] == operator_sha256
        and status["candidate_sha256"] == candidate["self_sha256"],
        "G2 status semantic linkage mismatch",
    )
    _require(
        status["registered_schema_count"] == len(budgets),
        "G2 status registry count mismatch",
    )
    workspace = candidate["workspace"]
    _require(
        isinstance(status["workspace_peak_bytes"], int)
        and not isinstance(status["workspace_peak_bytes"], bool)
        and status["workspace_peak_bytes"]
        == max(
            workspace["scalar_batch4_estimate_bytes"],
            workspace["vector_batch4_estimate_bytes"],
        )
        and status["workspace_peak_bytes"] <= W2_WORKSPACE_BYTE_CAP,
        "G2 status workspace peak mismatch",
    )
    _w2_within_budget(
        status,
        schema=GATE_STATUS_SCHEMA,
        budgets=budgets,
        context="G2 status",
    )
    index = _validate_w2_index(
        root_path,
        parent_w1=parents,
        root_sha256=root_sha256,
        profile_sha256=profile_sha256,
        source_records=source_records,
        budgets=budgets,
    )
    return {
        "gate": "G2",
        "status": "PASS",
        "geometry_profile_sha256": profile_sha256,
        "geometry_contract_root_sha256": root_sha256,
        "geometry_contract_sha256": geometry_sha256,
        "operator_semantic_sha256": operator_sha256,
        "candidate_sha256": candidate["self_sha256"],
        "run_id": index["run_id"],
        "status_path": (gate_dir / "status.json").as_posix(),
    }


def _w3_exact_mapping(
    value: Any,
    keys: set[str] | frozenset[str],
    context: str,
) -> dict[str, Any]:
    _require(isinstance(value, Mapping), f"{context} must be an object")
    record = dict(value)
    _require(set(record) == set(keys), f"{context} keyset is not sealed")
    return record


def _w3_f64(value: Any, context: str) -> float:
    return _w2_f64(value, context)


def _w3_parent_w2(value: Any, context: str) -> dict[str, Any]:
    record = _w3_exact_mapping(value, set(_W3_PARENT_W2), context)
    _require(
        canonical_json_bytes(record) == canonical_json_bytes(_W3_PARENT_W2),
        f"{context} does not bind the approved sealed W2/G2 parent",
    )
    return record


def _w3_component(
    value: Any,
    *,
    schema: str,
    sha256: str,
    context: str,
) -> dict[str, Any]:
    record = _w3_exact_mapping(value, {"schema", "sha256"}, context)
    _require(record["schema"] == schema, f"{context} schema mismatch")
    _require(record["sha256"] == sha256, f"{context} digest linkage mismatch")
    return record


def _w3_registry_spec() -> dict[str, tuple[int, tuple[str, ...]]]:
    semantic_parents = (
        "transport_profile_sha256",
        "transport_contract_root_sha256",
        "transport_semantic_sha256",
        "geometry_contract_sha256",
        "operator_semantic_sha256",
    )
    return {
        W3_CONTRACT_ROOT_SCHEMA: (65536, ()),
        W3_G3_CANDIDATE_SCHEMA: (1048576, semantic_parents),
        GATE_STATUS_SCHEMA: (65536, semantic_parents),
        W3_RUN_INDEX_SCHEMA: (1048576, ()),
        W3_PARENT_LINK_SCHEMA: (65536, ()),
        W3_PROFILE_SCHEMA: (
            65536,
            (
                "geometry_contract_sha256",
                "operator_semantic_sha256",
                "transport_semantic_sha256",
            ),
        ),
        W3_SCHEMA_REGISTRY_SCHEMA: (65536, ()),
        W3_SOURCE_IDENTITY_SCHEMA: (65536, ()),
        W3_TRANSPORT_SEMANTIC_SCHEMA: (
            65536,
            ("geometry_contract_sha256", "operator_semantic_sha256"),
        ),
    }


def _validate_w3_schema_registry(registry: Mapping[str, Any]) -> dict[str, int]:
    record = _w3_exact_mapping(registry, {"schema", "entries"}, "W3 schema registry")
    _require(record["schema"] == W3_SCHEMA_REGISTRY_SCHEMA, "W3 schema registry schema mismatch")
    entries = record["entries"]
    _require(isinstance(entries, list), "W3 schema registry entries must be an array")
    specification = _w3_registry_spec()
    expected_schemas = sorted(specification)
    _require(len(entries) == len(expected_schemas), "W3 schema registry entry count mismatch")
    budgets: dict[str, int] = {}
    for entry, expected_schema in zip(entries, expected_schemas, strict=True):
        item = _w3_exact_mapping(
            entry,
            {"schema", "max_bytes", "semantic_parents"},
            "W3 schema registry entry",
        )
        maximum, semantic_parents = specification[expected_schema]
        _require(
            item["schema"] == expected_schema,
            "W3 schema registry entries are missing, duplicated, or reordered",
        )
        _require(
            isinstance(item["max_bytes"], int)
            and not isinstance(item["max_bytes"], bool)
            and item["max_bytes"] == maximum,
            f"W3 schema registry budget mismatch: {expected_schema}",
        )
        _require(
            isinstance(item["semantic_parents"], list)
            and item["semantic_parents"] == list(semantic_parents),
            f"W3 schema registry semantic-parent mismatch: {expected_schema}",
        )
        budgets[expected_schema] = maximum
    _require(
        len(canonical_json_bytes(record)) <= 65536,
        "W3 schema registry exceeds its byte budget",
    )
    return budgets


def _w3_within_budget(
    value: Mapping[str, Any],
    *,
    schema: str,
    budgets: Mapping[str, int],
    context: str,
) -> None:
    _require(schema in budgets, f"{context} has an unregistered schema")
    _require(
        len(canonical_json_bytes(value)) <= budgets[schema],
        f"{context} exceeds its schema byte budget",
    )


def _expected_w3_transport_semantic_map() -> dict[str, Any]:
    """Independently reconstruct the normative W3 semantic map for verification."""

    return {
        "schema": W3_TRANSPORT_SEMANTIC_SCHEMA,
        "geometry_contract_sha256": _W3_PARENT_W2["geometry_contract_sha256"],
        "operator_semantic_sha256": _W3_PARENT_W2["operator_semantic_sha256"],
        "dtype": W3_DTYPE,
        "device": W3_DEVICE,
        "state_layout": {
            "layout_id": W3_LAYOUT_ID,
            "scale_count": W3_SCALE_COUNT,
            "component_count": W3_COMPONENT_COUNT,
            "mode_count": W3_MODE_COUNT,
            "component_lanes": [
                "EY.re",
                "EY.im",
                "EI.re",
                "EI.im",
                "VY.re",
                "VY.im",
                "VI.re",
                "VI.im",
                "epsilon",
            ],
            "endianness": "little",
        },
        "d_vd_transform": {
            "phi": W3_PHI,
            "w_D": "1/(1+phi^2)",
            "D": "EY-phi*EI",
            "C": "(phi*EY+EI)/(1+phi^2)",
            "V_D": "VY-phi*VI",
            "V_C": "(phi*VY+VI)/(1+phi^2)",
            "inverse": (
                "EY=w_D*D+phi*C;EI=C-phi*w_D*D;"
                "VY=w_D*V_D+phi*V_C;VI=V_C-phi*w_D*V_D"
            ),
            "epsilon": "byte-identical",
        },
        "physics": {
            "law": (
                "Ddot=V_D;V_Ddot=c_D,s^2*Delta(D_s)-omega_D,s^2*D_s"
                "-gamma_D,s*V_D-kappa_D,s*abs(D_s)^2*D_s"
            ),
            "c_D_m_per_s": list(W3_C_D_M_PER_S),
            "omega_rad_per_s": list(W3_OMEGA_RAD_PER_S),
            "gamma_per_s": list(W3_GAMMA_PER_S),
            "kappa": list(W3_KAPPA),
            "rho_floor": W3_RHO_FLOOR,
            "amplitude_cap": W3_AMPLITUDE_CAP,
            "finite_only": True,
            "max_source_bytes": W3_MAX_SOURCE_BYTES,
            "candidate_numerical_tolerance": W3_CANDIDATE_TOLERANCE,
        },
        "operator": {
            "geometry_api": "PeriodicSheetGeometry",
            "laplacian": "W2-periodic-second-difference",
            "laplacian_symbol": "-W2-periodic-second-difference",
            "dft": "unitary-3d",
            "damping": "analytic-oscillator-matrix-exactly-once",
            "branches": [
                "underdamped",
                "critical",
                "overdamped",
                "small-argument-series",
            ],
            "advection": "unavailable",
            "undocumented_filter": "forbidden",
        },
        "dealias": {
            "helper": "metric-adjoint-projected-pseudospectral-cubic",
            "oversampling_factors": [2, 2, 2],
            "dft": "unitary",
            "alpha": "sqrt(Nplus/N)",
            "injection": "signed-frequency-J",
            "restriction": "(1/alpha)*F^-1*J^H*Fplus",
            "live_candidate": "inactive-kappa-zero",
            "roundtrip": "required",
        },
        "inactive_terms": {
            "local_curvature": "inactive-kappa-zero",
            "density_conversion": "inactive-w5-unavailable",
            "w4": "unavailable",
            "w5": "unavailable",
            "advection": "unavailable",
            "source": "source-free",
        },
        "execution_contract": {
            "candidate_out_of_place": True,
            "fail_before_commit": True,
            "clip": "forbidden",
            "tanh": "forbidden",
            "threshold": "forbidden",
            "adaptive_dt": "forbidden",
            "fallback": "forbidden",
            "stage_schedule_sha256": canonical_hash(
                W3_G3_STAGE_SCHEDULE,
                W3_STAGE_SCHEDULE_SCHEMA,
            ),
        },
    }


def _validate_w3_transport_semantic(
    semantic: Mapping[str, Any],
    *,
    budgets: Mapping[str, int],
) -> str:
    expected = _expected_w3_transport_semantic_map()
    record = _w3_exact_mapping(semantic, set(expected), "W3 transport semantic")
    _require(
        canonical_json_bytes(record) == canonical_json_bytes(expected),
        "W3 transport semantic contract mismatch",
    )
    _w3_within_budget(
        record,
        schema=W3_TRANSPORT_SEMANTIC_SCHEMA,
        budgets=budgets,
        context="W3 transport semantic",
    )
    return canonical_hash(record, W3_TRANSPORT_SEMANTIC_SCHEMA)


def _validate_w3_contract_root(
    root: Mapping[str, Any],
    *,
    registry: Mapping[str, Any],
    semantic_sha256: str,
    budgets: Mapping[str, int],
) -> str:
    record = _w3_exact_mapping(
        root,
        {
            "schema",
            "contract_root_id",
            "parent_w2",
            "base_geometry_profile_sha256",
            "base_geometry_contract_root_sha256",
            "base_geometry_contract_sha256",
            "base_operator_semantic_sha256",
            "schema_registry",
            "transport_semantic",
            "self_sha256",
        },
        "W3 contract root",
    )
    _require(record["schema"] == W3_CONTRACT_ROOT_SCHEMA, "W3 contract root schema mismatch")
    _require(record["contract_root_id"] == W3_ROOT_ID, "W3 contract root identifier mismatch")
    _w3_parent_w2(record["parent_w2"], "W3 contract root parent_w2")
    _require(
        record["base_geometry_profile_sha256"] == _W3_PARENT_W2["profile_sha256"]
        and record["base_geometry_contract_root_sha256"]
        == _W3_PARENT_W2["contract_root_sha256"]
        and record["base_geometry_contract_sha256"]
        == _W3_PARENT_W2["geometry_contract_sha256"]
        and record["base_operator_semantic_sha256"]
        == _W3_PARENT_W2["operator_semantic_sha256"],
        "W3 contract root frozen W2 geometry linkage mismatch",
    )
    _w3_component(
        record["schema_registry"],
        schema=W3_SCHEMA_REGISTRY_SCHEMA,
        sha256=canonical_hash(registry, W3_SCHEMA_REGISTRY_SCHEMA),
        context="W3 contract root schema registry",
    )
    _w3_component(
        record["transport_semantic"],
        schema=W3_TRANSPORT_SEMANTIC_SCHEMA,
        sha256=semantic_sha256,
        context="W3 contract root transport semantic",
    )
    self_sha256 = _require_sha256(record["self_sha256"], "W3 contract root self_sha256")
    without_self = dict(record)
    without_self.pop("self_sha256")
    _require(
        canonical_hash(without_self, W3_CONTRACT_ROOT_SCHEMA) == self_sha256,
        "W3 contract root self hash mismatch",
    )
    _w3_within_budget(
        record,
        schema=W3_CONTRACT_ROOT_SCHEMA,
        budgets=budgets,
        context="W3 contract root",
    )
    return self_sha256


def _validate_w3_profile(
    profile: Mapping[str, Any],
    *,
    root_sha256: str,
    registry: Mapping[str, Any],
    semantic: Mapping[str, Any],
    semantic_sha256: str,
    budgets: Mapping[str, int],
) -> str:
    record = _w3_exact_mapping(
        profile,
        {
            "schema",
            "parent_w2",
            "base_geometry_profile_sha256",
            "base_geometry_contract_root_sha256",
            "base_geometry_contract_sha256",
            "base_operator_semantic_sha256",
            "schema_registry_sha256",
            "transport_semantic",
            "transport_semantic_sha256",
            "contract_root_sha256",
            "profile_sha256",
        },
        "W3 transport profile",
    )
    _require(record["schema"] == W3_PROFILE_SCHEMA, "W3 transport profile schema mismatch")
    _w3_parent_w2(record["parent_w2"], "W3 transport profile parent_w2")
    _require(
        record["base_geometry_profile_sha256"] == _W3_PARENT_W2["profile_sha256"]
        and record["base_geometry_contract_root_sha256"]
        == _W3_PARENT_W2["contract_root_sha256"]
        and record["base_geometry_contract_sha256"]
        == _W3_PARENT_W2["geometry_contract_sha256"]
        and record["base_operator_semantic_sha256"]
        == _W3_PARENT_W2["operator_semantic_sha256"],
        "W3 transport profile frozen W2 geometry linkage mismatch",
    )
    _require(
        record["schema_registry_sha256"] == canonical_hash(registry, W3_SCHEMA_REGISTRY_SCHEMA),
        "W3 transport profile schema-registry linkage mismatch",
    )
    _require(
        isinstance(record["transport_semantic"], Mapping)
        and canonical_json_bytes(record["transport_semantic"])
        == canonical_json_bytes(semantic),
        "W3 transport profile embeds a different transport semantic",
    )
    _require(
        record["transport_semantic_sha256"] == semantic_sha256,
        "W3 transport profile transport-semantic hash mismatch",
    )
    _require(
        record["contract_root_sha256"] == root_sha256,
        "W3 transport profile root linkage mismatch",
    )
    profile_sha256 = _require_sha256(record["profile_sha256"], "W3 transport profile profile_sha256")
    without_profile_sha256 = dict(record)
    without_profile_sha256.pop("profile_sha256")
    _require(
        canonical_hash(without_profile_sha256, W3_PROFILE_SCHEMA) == profile_sha256,
        "W3 transport profile self hash mismatch",
    )
    _w3_within_budget(
        record,
        schema=W3_PROFILE_SCHEMA,
        budgets=budgets,
        context="W3 transport profile",
    )
    return profile_sha256


def _validate_w3_parent_link(
    parent_link: Mapping[str, Any],
    *,
    budgets: Mapping[str, int],
) -> list[dict[str, Any]]:
    record = _w3_exact_mapping(parent_link, {"schema", "parents"}, "W3 parent link")
    _require(record["schema"] == W3_PARENT_LINK_SCHEMA, "W3 parent link schema mismatch")
    _require(
        isinstance(record["parents"], list) and len(record["parents"]) == 1,
        "W3 parent link parent count mismatch",
    )
    result = [_w3_parent_w2(record["parents"][0], "W3 parent link parent")]
    _w3_within_budget(
        record,
        schema=W3_PARENT_LINK_SCHEMA,
        budgets=budgets,
        context="W3 parent link",
    )
    return result


def _validate_w3_source_identity(
    root_path: Path,
    source_identity: Mapping[str, Any],
    *,
    budgets: Mapping[str, int],
) -> list[dict[str, str]]:
    record = _w3_exact_mapping(
        source_identity,
        {"schema", "parent_w2", "sources"},
        "W3 source identity",
    )
    _require(record["schema"] == W3_SOURCE_IDENTITY_SCHEMA, "W3 source identity schema mismatch")
    _w3_parent_w2(record["parent_w2"], "W3 source identity parent_w2")
    sources = record["sources"]
    _require(isinstance(sources, list), "W3 source identity sources must be an array")
    _require(
        len(sources) == len(W3_REQUIRED_SOURCE_PATHS),
        "W3 source identity source count mismatch",
    )
    result: list[dict[str, str]] = []
    observed_paths: list[str] = []
    verifier_root = Path(__file__).resolve().parent
    for item, expected_path in zip(sources, W3_REQUIRED_SOURCE_PATHS, strict=True):
        source = _w3_exact_mapping(item, {"path", "sha256"}, "W3 source record")
        relative = source["path"]
        _require(relative == expected_path, "W3 source records are missing, duplicated, or reordered")
        candidate = _w2_relative_path(relative, "W3 source path")
        digest = _require_sha256(source["sha256"], f"W3 source {relative}")
        copied = root_path / "run-spec" / "sources" / candidate
        _require(
            copied.is_file() and not copied.is_symlink(),
            f"W3 copied source is missing or symlinked: {relative}",
        )
        live = verifier_root / candidate
        _require(
            live.is_file() and not live.is_symlink(),
            f"W3 verifier source pin is unavailable: {relative}",
        )
        try:
            copied_raw = copied.read_bytes()
            live_raw = live.read_bytes()
        except OSError as error:
            raise VerificationError(f"cannot read W3 source {relative}: {error}") from error
        _require(
            hashlib.sha256(copied_raw).hexdigest() == digest,
            f"W3 copied source digest mismatch: {relative}",
        )
        _require(
            copied_raw == live_raw,
            f"W3 copied source differs from verifier-pinned source: {relative}",
        )
        observed_paths.append(relative)
        result.append({"path": relative, "sha256": digest})
    _require(
        observed_paths == list(W3_REQUIRED_SOURCE_PATHS),
        "W3 source identity source order mismatch",
    )
    _w3_within_budget(
        record,
        schema=W3_SOURCE_IDENTITY_SCHEMA,
        budgets=budgets,
        context="W3 source identity",
    )
    return result


def _validate_w3_state_layout(value: Any) -> tuple[dict[str, Any], int]:
    record = _w3_exact_mapping(
        value,
        {
            "layout_id",
            "dtype",
            "endianness",
            "scale_count",
            "component_count",
            "mode_count",
            "batch_count",
            "shape",
        },
        "G3 state layout",
    )
    batch_count = record["batch_count"]
    _require(
        record["layout_id"] == W3_LAYOUT_ID
        and record["dtype"] == W3_DTYPE
        and record["endianness"] == "little"
        and record["scale_count"] == W3_SCALE_COUNT
        and record["component_count"] == W3_COMPONENT_COUNT
        and record["mode_count"] == W3_MODE_COUNT
        and isinstance(batch_count, int)
        and not isinstance(batch_count, bool)
        and batch_count > 0,
        "G3 state layout mismatch",
    )
    expected_shape = [W3_SCALE_COUNT, W3_COMPONENT_COUNT * W3_MODE_COUNT, batch_count]
    _require(record["shape"] == expected_shape, "G3 state shape mismatch")
    raw_byte_count = (
        W3_SCALE_COUNT
        * W3_COMPONENT_COUNT
        * W3_MODE_COUNT
        * batch_count
        * struct.calcsize("<d")
    )
    _require(
        raw_byte_count <= W3_MAX_RAW_STATE_BYTES,
        "G3 state layout exceeds the fixed raw-state byte cap",
    )
    return record, raw_byte_count


def _w3_raw_state_hash(raw: bytes, *, layout: Mapping[str, Any]) -> str:
    shape = layout["shape"]
    _require(isinstance(shape, list), "G3 raw-state shape is invalid")
    digest = hashlib.sha256()
    digest.update(frame(W3_RAW_STATE_DOMAIN.encode("utf-8")))
    digest.update(frame(W3_DTYPE.encode("ascii")))
    digest.update(struct.pack(">I", len(shape)))
    for dimension in shape:
        _require(
            isinstance(dimension, int) and not isinstance(dimension, bool) and dimension > 0,
            "G3 raw-state shape dimension is invalid",
        )
        digest.update(struct.pack(">Q", dimension))
    digest.update(frame(raw))
    return digest.hexdigest()


def _read_w3_raw_state(
    root_path: Path,
    state: Any,
    *,
    expected_path: str,
    layout: Mapping[str, Any],
    expected_byte_count: int,
    context: str,
) -> tuple[dict[str, Any], bytes]:
    record = _w3_exact_mapping(
        state,
        {"path", "byte_count", "raw_sha256", "state_sha256"},
        context,
    )
    _require(record["path"] == expected_path, f"{context} path mismatch")
    _require(
        isinstance(record["byte_count"], int)
        and not isinstance(record["byte_count"], bool)
        and record["byte_count"] == expected_byte_count,
        f"{context} byte count mismatch",
    )
    raw_sha256 = _require_sha256(record["raw_sha256"], f"{context} raw_sha256")
    state_sha256 = _require_sha256(record["state_sha256"], f"{context} state_sha256")
    target = root_path / _w2_relative_path(record["path"], f"{context} path")
    _require(target.is_file() and not target.is_symlink(), f"{context} is missing or symlinked")
    try:
        raw = target.read_bytes()
    except OSError as error:
        raise VerificationError(f"cannot read {context}: {error}") from error
    _require(len(raw) == expected_byte_count, f"{context} raw byte count mismatch")
    _validate_v3_raw_finite(raw, W3_DTYPE)
    _require(hashlib.sha256(raw).hexdigest() == raw_sha256, f"{context} raw digest mismatch")
    _require(
        _w3_raw_state_hash(raw, layout=layout) == state_sha256,
        f"{context} state identity mismatch",
    )
    return record, raw


def _w3_state_scalar(
    raw: bytes,
    *,
    scale: int,
    component: int,
    mode: int,
    batch: int,
    batch_count: int,
) -> float:
    scalar_index = (
        ((scale * W3_COMPONENT_COUNT + component) * W3_MODE_COUNT + mode) * batch_count
        + batch
    )
    return struct.unpack_from("<d", raw, scalar_index * struct.calcsize("<d"))[0]


def _w3_epsilon_bytes(raw: bytes, *, layout: Mapping[str, Any]) -> bytes:
    batch_count = layout["batch_count"]
    _require(isinstance(batch_count, int), "G3 epsilon layout batch count is invalid")
    pieces = bytearray()
    for scale in range(W3_SCALE_COUNT):
        for mode in range(W3_MODE_COUNT):
            for batch in range(batch_count):
                scalar_index = (
                    ((scale * W3_COMPONENT_COUNT + 8) * W3_MODE_COUNT + mode) * batch_count
                    + batch
                )
                offset = scalar_index * struct.calcsize("<d")
                pieces.extend(raw[offset:offset + struct.calcsize("<d")])
    return bytes(pieces)


def _w3_scale_diagnostics(
    raw: bytes,
    *,
    layout: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Recompute W3 D/V_D diagnostics directly from packed raw float64 bytes."""

    batch_count = layout["batch_count"]
    _require(
        isinstance(batch_count, int) and batch_count > 0,
        "G3 diagnostics batch count is invalid",
    )
    phi = _w3_f64(W3_PHI, "W3 phi")
    weight = 1.0 / (1.0 + phi * phi)
    rho_floor = _w3_f64(W3_RHO_FLOOR, "W3 rho_floor")
    spacings = tuple(
        _w2_f64(value, f"W3 spacing[{axis}]")
        for axis, value in enumerate(W2_SPACINGS_M)
    )
    origins = tuple(
        _w2_f64(value, f"W3 origin[{axis}]")
        for axis, value in enumerate(W2_COORDINATE_ORIGIN_M)
    )
    c_values = tuple(
        _w3_f64(value, f"W3 c_D[{scale}]")
        for scale, value in enumerate(W3_C_D_M_PER_S)
    )
    z_count, y_count, x_count = W3_GRID_SHAPE
    cell_volume = spacings[0] * spacings[1] * spacings[2]

    def mode_index(z: int, y: int, x: int) -> int:
        return ((z * y_count) + y) * x_count + x

    result: list[dict[str, Any]] = []
    for scale in range(W3_SCALE_COUNT):
        c_squared = c_values[scale] * c_values[scale]
        d_l2_terms: list[float] = []
        vd_l2_terms: list[float] = []
        energy_terms: list[float] = []
        charge_terms: list[float] = []
        centroid_weight_terms: list[float] = []
        centroid_terms: list[list[float]] = [[], [], []]
        amplitude_max = 0.0
        amplitude_rate_max = 0.0
        phase_rate_max = 0.0
        current_max = 0.0
        momentum_max = 0.0
        divergence_max = 0.0
        for batch in range(batch_count):
            d_values: list[complex] = []
            vd_values: list[complex] = []
            for mode in range(W3_MODE_COUNT):
                ey = complex(
                    _w3_state_scalar(
                        raw,
                        scale=scale,
                        component=0,
                        mode=mode,
                        batch=batch,
                        batch_count=batch_count,
                    ),
                    _w3_state_scalar(
                        raw,
                        scale=scale,
                        component=1,
                        mode=mode,
                        batch=batch,
                        batch_count=batch_count,
                    ),
                )
                ei = complex(
                    _w3_state_scalar(
                        raw,
                        scale=scale,
                        component=2,
                        mode=mode,
                        batch=batch,
                        batch_count=batch_count,
                    ),
                    _w3_state_scalar(
                        raw,
                        scale=scale,
                        component=3,
                        mode=mode,
                        batch=batch,
                        batch_count=batch_count,
                    ),
                )
                vy = complex(
                    _w3_state_scalar(
                        raw,
                        scale=scale,
                        component=4,
                        mode=mode,
                        batch=batch,
                        batch_count=batch_count,
                    ),
                    _w3_state_scalar(
                        raw,
                        scale=scale,
                        component=5,
                        mode=mode,
                        batch=batch,
                        batch_count=batch_count,
                    ),
                )
                vi = complex(
                    _w3_state_scalar(
                        raw,
                        scale=scale,
                        component=6,
                        mode=mode,
                        batch=batch,
                        batch_count=batch_count,
                    ),
                    _w3_state_scalar(
                        raw,
                        scale=scale,
                        component=7,
                        mode=mode,
                        batch=batch,
                        batch_count=batch_count,
                    ),
                )
                d_values.append(ey - phi * ei)
                vd_values.append(vy - phi * vi)
            currents: list[tuple[float, float, float]] = [
                (0.0, 0.0, 0.0) for _ in range(W3_MODE_COUNT)
            ]
            for z in range(z_count):
                for y in range(y_count):
                    for x in range(x_count):
                        mode = mode_index(z, y, x)
                        d_value = d_values[mode]
                        vd_value = vd_values[mode]
                        gradients = (
                            (
                                d_values[mode_index((z + 1) % z_count, y, x)]
                                - d_values[mode_index((z - 1) % z_count, y, x)]
                            )
                            / (2.0 * spacings[0]),
                            (
                                d_values[mode_index(z, (y + 1) % y_count, x)]
                                - d_values[mode_index(z, (y - 1) % y_count, x)]
                            )
                            / (2.0 * spacings[1]),
                            (
                                d_values[mode_index(z, y, (x + 1) % x_count)]
                                - d_values[mode_index(z, y, (x - 1) % x_count)]
                            )
                            / (2.0 * spacings[2]),
                        )
                        density = d_value.real * d_value.real + d_value.imag * d_value.imag
                        velocity_density = (
                            vd_value.real * vd_value.real + vd_value.imag * vd_value.imag
                        )
                        d_l2_terms.append(density)
                        vd_l2_terms.append(velocity_density)
                        product = d_value.conjugate() * vd_value
                        charge = weight * product.imag
                        charge_terms.append(charge * cell_volume)
                        amplitude_max = max(amplitude_max, math.sqrt(density))
                        amplitude_rate_max = max(
                            amplitude_rate_max,
                            abs(product.real / (density + rho_floor)),
                        )
                        phase_rate_max = max(
                            phase_rate_max,
                            abs(charge / (weight * (density + rho_floor))),
                        )
                        gradient_norm_squared = sum(
                            gradient.real * gradient.real + gradient.imag * gradient.imag
                            for gradient in gradients
                        )
                        energy_terms.append(
                            weight
                            * (0.5 * velocity_density + 0.5 * c_squared * gradient_norm_squared)
                            * cell_volume
                        )
                        currents[mode] = tuple(
                            -weight * c_squared * (d_value.conjugate() * gradient).imag
                            for gradient in gradients
                        )
                        momenta = tuple(
                            -weight * c_squared * (vd_value.conjugate() * gradient).real
                            for gradient in gradients
                        )
                        current_max = max(current_max, *(abs(item) for item in currents[mode]))
                        momentum_max = max(momentum_max, *(abs(item) for item in momenta))
                        centroid_weight = density * cell_volume
                        centroid_weight_terms.append(centroid_weight)
                        centroid_terms[0].append(
                            (origins[0] + z * spacings[0]) * centroid_weight
                        )
                        centroid_terms[1].append(
                            (origins[1] + y * spacings[1]) * centroid_weight
                        )
                        centroid_terms[2].append(
                            (origins[2] + x * spacings[2]) * centroid_weight
                        )
            for z in range(z_count):
                for y in range(y_count):
                    for x in range(x_count):
                        mode = mode_index(z, y, x)
                        divergence = (
                            (
                                currents[mode_index((z + 1) % z_count, y, x)][0]
                                - currents[mode_index((z - 1) % z_count, y, x)][0]
                            )
                            / (2.0 * spacings[0])
                            + (
                                currents[mode_index(z, (y + 1) % y_count, x)][1]
                                - currents[mode_index(z, (y - 1) % y_count, x)][1]
                            )
                            / (2.0 * spacings[1])
                            + (
                                currents[mode_index(z, y, (x + 1) % x_count)][2]
                                - currents[mode_index(z, y, (x - 1) % x_count)][2]
                            )
                            / (2.0 * spacings[2])
                        )
                        divergence_max = max(divergence_max, abs(divergence))
        centroid_weight = math.fsum(centroid_weight_terms)
        centroid = (
            [math.fsum(values) / centroid_weight for values in centroid_terms]
            if centroid_weight > 0.0
            else [0.0, 0.0, 0.0]
        )
        result.append(
            {
                "d_l2": math.fsum(d_l2_terms),
                "vd_l2": math.fsum(vd_l2_terms),
                "metrics": {
                    "amplitude_max": amplitude_max,
                    "amplitude_rate_max_abs": amplitude_rate_max,
                    "charge": math.fsum(charge_terms),
                    "current_max_abs": current_max,
                    "divergence_max_abs": divergence_max,
                    "energy": math.fsum(energy_terms),
                    "momentum_max_abs": momentum_max,
                    "phase_rate_max_abs": phase_rate_max,
                    "centroid_m": centroid,
                },
            }
        )
    return result


def _w3_validate_recorded_float(
    value: Any,
    *,
    expected: float,
    tolerance: float,
    context: str,
) -> float:
    recorded = _w3_f64(value, context)
    _require(
        abs(recorded - expected) <= tolerance,
        f"{context} does not match independent raw-state recomputation",
    )
    return recorded


def _validate_w3_diagnostics(
    value: Any,
    *,
    initial_raw: bytes,
    final_raw: bytes,
    layout: Mapping[str, Any],
) -> dict[str, Any]:
    record = _w3_exact_mapping(value, {"schema", "simple", "scales"}, "G3 diagnostics")
    _require(record["schema"] == W3_DIAGNOSTICS_SCHEMA, "G3 diagnostics schema mismatch")
    tolerance = _w3_f64(W3_CANDIDATE_TOLERANCE, "W3 candidate tolerance")
    initial_scales = _w3_scale_diagnostics(initial_raw, layout=layout)
    final_scales = _w3_scale_diagnostics(final_raw, layout=layout)
    initial_epsilon = _w3_epsilon_bytes(initial_raw, layout=layout)
    final_epsilon = _w3_epsilon_bytes(final_raw, layout=layout)
    simple = _w3_exact_mapping(
        record["simple"],
        {
            "schema",
            "initial_d_l2",
            "initial_vd_l2",
            "final_d_l2",
            "final_vd_l2",
            "initial_epsilon_sha256",
            "final_epsilon_sha256",
            "epsilon_byte_identical",
        },
        "G3 simple diagnostics",
    )
    _require(
        simple["schema"] == W3_SIMPLE_DIAGNOSTICS_SCHEMA,
        "G3 simple diagnostics schema mismatch",
    )
    _w3_validate_recorded_float(
        simple["initial_d_l2"],
        expected=math.fsum(scale["d_l2"] for scale in initial_scales),
        tolerance=tolerance,
        context="G3 simple diagnostics.initial_d_l2",
    )
    _w3_validate_recorded_float(
        simple["initial_vd_l2"],
        expected=math.fsum(scale["vd_l2"] for scale in initial_scales),
        tolerance=tolerance,
        context="G3 simple diagnostics.initial_vd_l2",
    )
    _w3_validate_recorded_float(
        simple["final_d_l2"],
        expected=math.fsum(scale["d_l2"] for scale in final_scales),
        tolerance=tolerance,
        context="G3 simple diagnostics.final_d_l2",
    )
    _w3_validate_recorded_float(
        simple["final_vd_l2"],
        expected=math.fsum(scale["vd_l2"] for scale in final_scales),
        tolerance=tolerance,
        context="G3 simple diagnostics.final_vd_l2",
    )
    _require(
        simple["initial_epsilon_sha256"] == hashlib.sha256(initial_epsilon).hexdigest()
        and simple["final_epsilon_sha256"] == hashlib.sha256(final_epsilon).hexdigest()
        and simple["epsilon_byte_identical"] is True
        and initial_epsilon == final_epsilon,
        "G3 epsilon is not byte-identical across the candidate",
    )
    scales = record["scales"]
    _require(
        isinstance(scales, list) and len(scales) == W3_SCALE_COUNT,
        "G3 diagnostic scale count mismatch",
    )
    for scale_index, (scale_record, before, after) in enumerate(
        zip(scales, initial_scales, final_scales, strict=True)
    ):
        item = _w3_exact_mapping(
            scale_record,
            {
                "scale_index",
                "pre",
                "post",
                "damping_work",
                "damping_charge_quadrature",
                "source_work",
                "transport_closure",
                "first_half_state_sha256",
                "second_half_state_sha256",
            },
            "G3 diagnostic scale",
        )
        _require(item["scale_index"] == scale_index, "G3 diagnostic scale ordering mismatch")
        for label, expected in (("pre", before["metrics"]), ("post", after["metrics"])):
            measurement = _w3_exact_mapping(
                item[label],
                set(W3_G3_DIAGNOSTIC_METRICS) | {"centroid_m"},
                f"G3 diagnostic {label}",
            )
            for metric in W3_G3_DIAGNOSTIC_METRICS:
                _w3_validate_recorded_float(
                    measurement[metric],
                    expected=expected[metric],
                    tolerance=tolerance,
                    context=f"G3 diagnostic scale {scale_index}.{label}.{metric}",
                )
            centroid = measurement["centroid_m"]
            _require(
                isinstance(centroid, list) and len(centroid) == 3,
                f"G3 diagnostic scale {scale_index}.{label}.centroid_m shape mismatch",
            )
            for axis, coordinate in enumerate(centroid):
                _w3_validate_recorded_float(
                    coordinate,
                    expected=expected["centroid_m"][axis],
                    tolerance=tolerance,
                    context=f"G3 diagnostic scale {scale_index}.{label}.centroid_m[{axis}]",
                )
        damping_work = _w3_f64(
            item["damping_work"],
            f"G3 diagnostic scale {scale_index}.damping_work",
        )
        _require(
            damping_work <= tolerance,
            f"G3 diagnostic scale {scale_index} records positive damping work",
        )
        _w3_f64(
            item["damping_charge_quadrature"],
            f"G3 diagnostic scale {scale_index}.damping_charge_quadrature",
        )
        _require(
            item["source_work"] == W3_ZERO,
            f"G3 diagnostic scale {scale_index} source work is not zero",
        )
        closure = _w3_f64(
            item["transport_closure"],
            f"G3 diagnostic scale {scale_index}.transport_closure",
        )
        _require(
            abs(closure) <= tolerance,
            f"G3 diagnostic scale {scale_index} transport closure exceeds tolerance",
        )
        _require_sha256(
            item["first_half_state_sha256"],
            f"G3 diagnostic scale {scale_index}.first_half_state_sha256",
        )
        _require_sha256(
            item["second_half_state_sha256"],
            f"G3 diagnostic scale {scale_index}.second_half_state_sha256",
        )
    return record


def _w3_operator_evidence() -> dict[str, Any]:
    return {
        "dtype": W3_DTYPE,
        "device": W3_DEVICE,
        "geometry_api": "PeriodicSheetGeometry",
        "laplacian": "W2-periodic-second-difference",
        "dft": "unitary-3d",
        "damping_application_count": 1,
        "density_conversion": "inactive-w5-unavailable",
        "local_curvature": "inactive-kappa-zero",
        "advection": "unavailable",
        "dealias_live_candidate": "inactive-kappa-zero",
        "clipping": "forbidden",
        "tanh": "forbidden",
        "threshold": "forbidden",
        "adaptive_dt": "forbidden",
        "fallback": "forbidden",
    }


def _validate_w3_stage_schedule(value: Any) -> str:
    record = _w3_exact_mapping(
        value,
        {"schema", "h_s", "substeps", "stages", "schedule_sha256"},
        "G3 stage schedule",
    )
    core = dict(record)
    schedule_sha256 = _require_sha256(core.pop("schedule_sha256"), "G3 stage schedule sha256")
    _require(
        canonical_json_bytes(core) == canonical_json_bytes(W3_G3_STAGE_SCHEDULE),
        "G3 stage schedule/order/read/write/duration/dependency contract mismatch",
    )
    expected_sha256 = canonical_hash(core, W3_STAGE_SCHEDULE_SCHEMA)
    _require(schedule_sha256 == expected_sha256, "G3 stage schedule hash mismatch")
    return schedule_sha256


def _validate_w3_identity_receipts(
    value: Any,
    *,
    identities: Mapping[str, str],
) -> list[dict[str, str]]:
    _require(isinstance(value, list), "G3 identity receipts must be an array")
    expected_subjects = sorted(identities)
    _require(len(value) == len(expected_subjects), "G3 identity receipt count mismatch")
    result: list[dict[str, str]] = []
    for receipt, subject in zip(value, expected_subjects, strict=True):
        record = _w3_exact_mapping(
            receipt,
            {"schema", "subject", "sha256"},
            "G3 direct identity receipt",
        )
        _require(
            record["schema"] == W3_DIRECT_IDENTITY_RECEIPT_SCHEMA
            and record["subject"] == subject
            and record["sha256"] == identities[subject],
            "G3 direct identity receipt linkage mismatch",
        )
        result.append(record)
    return result


def _validate_w3_controls(value: Any) -> dict[str, Any]:
    record = _w3_exact_mapping(value, _W3_MUTATION_CONTROLS, "G3 mutation controls")
    _require(all(item is True for item in record.values()), "G3 mutation controls are incomplete or failed")
    return record


def _validate_w3_source_request(value: Any) -> dict[str, Any]:
    record = _w3_exact_mapping(
        value,
        {"schema", "source_count", "byte_count", "max_source_bytes", "finite", "accepted"},
        "G3 source request",
    )
    _require(
        record
        == {
            "schema": W3_SOURCE_REQUEST_SCHEMA,
            "source_count": 0,
            "byte_count": 0,
            "max_source_bytes": W3_MAX_SOURCE_BYTES,
            "finite": True,
            "accepted": True,
        },
        "G3 source-free request contract mismatch",
    )
    return record


def _validate_w3_replay(
    value: Any,
    *,
    initial_state_sha256: str,
    final_state_sha256: str,
    tolerance: float,
) -> dict[str, Any]:
    record = _w3_exact_mapping(
        value,
        {
            "schema",
            "initial_state_sha256",
            "final_state_sha256",
            "replay_final_state_sha256",
            "max_abs_error",
            "tolerance",
        },
        "G3 replay",
    )
    _require(
        record["schema"] == W3_REPLAY_SCHEMA
        and record["initial_state_sha256"] == initial_state_sha256
        and record["final_state_sha256"] == final_state_sha256
        and record["replay_final_state_sha256"] == final_state_sha256,
        "G3 replay state identity mismatch",
    )
    _require(record["tolerance"] == W3_CANDIDATE_TOLERANCE, "G3 replay tolerance mismatch")
    error = _w3_f64(record["max_abs_error"], "G3 replay max_abs_error")
    _require(0.0 <= error <= tolerance, "G3 replay error exceeds tolerance")
    return record


def _validate_w3_refinement(
    value: Any,
    *,
    final_state_sha256: str,
    tolerance: float,
) -> dict[str, Any]:
    record = _w3_exact_mapping(
        value,
        {
            "schema",
            "coarse_substeps",
            "fine_substeps",
            "fine_h_s",
            "coarse_final_state_sha256",
            "fine_final_state_sha256",
            "max_abs_error",
            "tolerance",
            "finite",
        },
        "G3 refinement",
    )
    _require(
        record["schema"] == W3_REFINEMENT_SCHEMA
        and record["coarse_substeps"] == 1
        and record["fine_substeps"] == 2
        and record["fine_h_s"] == W3_HALF_H_S
        and record["coarse_final_state_sha256"] == final_state_sha256
        and _is_sha256(record["fine_final_state_sha256"])
        and record["finite"] is True,
        "G3 refinement contract mismatch",
    )
    _require(record["tolerance"] == W3_CANDIDATE_TOLERANCE, "G3 refinement tolerance mismatch")
    error = _w3_f64(record["max_abs_error"], "G3 refinement max_abs_error")
    _require(0.0 <= error <= tolerance, "G3 refinement error exceeds tolerance")
    return record


def _validate_w3_long_horizon(
    value: Any,
    *,
    initial_state_sha256: str,
    tolerance: float,
) -> dict[str, Any]:
    record = _w3_exact_mapping(
        value,
        {
            "schema",
            "initial_state_sha256",
            "long_horizon_final_state_sha256",
            "step_count",
            "finite",
            "amplitude_cap_not_crossed",
            "max_d_abs",
            "static_constant_max_abs_error",
            "tolerance",
        },
        "G3 long-horizon",
    )
    _require(
        record["schema"] == W3_LONG_HORIZON_SCHEMA
        and record["initial_state_sha256"] == initial_state_sha256
        and _is_sha256(record["long_horizon_final_state_sha256"])
        and isinstance(record["step_count"], int)
        and not isinstance(record["step_count"], bool)
        and record["step_count"] > 0
        and record["finite"] is True
        and record["amplitude_cap_not_crossed"] is True,
        "G3 long-horizon contract mismatch",
    )
    _require(record["tolerance"] == W3_CANDIDATE_TOLERANCE, "G3 long-horizon tolerance mismatch")
    max_d_abs = _w3_f64(record["max_d_abs"], "G3 long-horizon max_d_abs")
    static_error = _w3_f64(
        record["static_constant_max_abs_error"],
        "G3 long-horizon static_constant_max_abs_error",
    )
    _require(
        0.0 <= max_d_abs <= _w3_f64(W3_AMPLITUDE_CAP, "W3 amplitude cap"),
        "G3 long-horizon amplitude cap crossed",
    )
    _require(
        0.0 <= static_error <= tolerance,
        "G3 long-horizon constant-state invariance failure",
    )
    return record


def _validate_w3_failure_receipts(
    value: Any,
    *,
    predecessor_state_sha256: str,
) -> list[dict[str, Any]]:
    _require(isinstance(value, list), "G3 failure receipts must be an array")
    _require(
        len(value) == len(W3_REQUIRED_FAILURE_CASES),
        "G3 failure receipt count mismatch",
    )
    result: list[dict[str, Any]] = []
    for receipt, expected_case in zip(value, W3_REQUIRED_FAILURE_CASES, strict=True):
        record = _w3_exact_mapping(
            receipt,
            {
                "schema",
                "case",
                "rejected",
                "predecessor_state_sha256",
                "candidate_committed",
                "predecessor_unchanged",
            },
            "G3 failure receipt",
        )
        _require(
            record["schema"] == W3_FAILURE_RECEIPT_SCHEMA
            and record["case"] == expected_case
            and record["rejected"] is True
            and record["predecessor_state_sha256"] == predecessor_state_sha256
            and record["candidate_committed"] is False
            and record["predecessor_unchanged"] is True,
            "G3 fail-before-commit receipt mismatch",
        )
        result.append(record)
    return result


def _validate_w3_workspace_bounds(
    value: Any,
    *,
    raw_byte_count: int,
) -> dict[str, Any]:
    record = _w3_exact_mapping(
        value,
        {
            "schema",
            "workspace_byte_cap",
            "predecessor_bytes",
            "candidate_bytes",
            "peak_bytes",
            "out_of_place",
        },
        "G3 workspace bounds",
    )
    _require(
        record["schema"] == W3_WORKSPACE_BOUNDS_SCHEMA
        and record["workspace_byte_cap"] == W3_WORKSPACE_BYTE_CAP
        and record["predecessor_bytes"] == raw_byte_count
        and record["candidate_bytes"] == raw_byte_count
        and isinstance(record["peak_bytes"], int)
        and not isinstance(record["peak_bytes"], bool)
        and 2 * raw_byte_count <= record["peak_bytes"] <= W3_WORKSPACE_BYTE_CAP
        and record["out_of_place"] is True,
        "G3 out-of-place workspace bounds mismatch",
    )
    return record


def _validate_w3_stability_bounds(
    value: Any,
    *,
    initial_scales: Sequence[Mapping[str, Any]],
    final_scales: Sequence[Mapping[str, Any]],
    tolerance: float,
) -> dict[str, Any]:
    record = _w3_exact_mapping(
        value,
        {
            "schema",
            "finite_only",
            "amplitude_cap",
            "rho_floor",
            "candidate_tolerance",
            "max_source_bytes",
            "initial_d_max_abs",
            "final_d_max_abs",
            "candidate_finite",
            "amplitude_cap_not_crossed",
        },
        "G3 stability bounds",
    )
    _require(
        record["schema"] == W3_STABILITY_BOUNDS_SCHEMA
        and record["finite_only"] is True
        and record["amplitude_cap"] == W3_AMPLITUDE_CAP
        and record["rho_floor"] == W3_RHO_FLOOR
        and record["candidate_tolerance"] == W3_CANDIDATE_TOLERANCE
        and record["max_source_bytes"] == W3_MAX_SOURCE_BYTES
        and record["candidate_finite"] is True
        and record["amplitude_cap_not_crossed"] is True,
        "G3 stability bounds contract mismatch",
    )
    initial_max = max(scale["metrics"]["amplitude_max"] for scale in initial_scales)
    final_max = max(scale["metrics"]["amplitude_max"] for scale in final_scales)
    _w3_validate_recorded_float(
        record["initial_d_max_abs"],
        expected=initial_max,
        tolerance=tolerance,
        context="G3 stability bounds.initial_d_max_abs",
    )
    _w3_validate_recorded_float(
        record["final_d_max_abs"],
        expected=final_max,
        tolerance=tolerance,
        context="G3 stability bounds.final_d_max_abs",
    )
    cap = _w3_f64(W3_AMPLITUDE_CAP, "W3 amplitude cap")
    _require(
        initial_max <= cap and final_max <= cap,
        "G3 raw-state amplitude cap crossed",
    )
    return record


def _validate_g3_candidate(
    root_path: Path,
    candidate: Mapping[str, Any],
    *,
    registry_sha256: str,
    root_sha256: str,
    profile_sha256: str,
    semantic_sha256: str,
    parent_link_sha256: str,
    source_identity_sha256: str,
    budgets: Mapping[str, int],
) -> dict[str, Any]:
    record = _w3_exact_mapping(candidate, W3_G3_CANDIDATE_KEYSET, "G3 transport candidate")
    _require(
        record["schema"] == W3_G3_CANDIDATE_SCHEMA,
        "G3 transport candidate schema mismatch",
    )
    _w3_parent_w2(record["parent_w2"], "G3 transport candidate parent_w2")
    _require(
        record["schema_registry_sha256"] == registry_sha256
        and record["transport_contract_root_sha256"] == root_sha256
        and record["transport_profile_sha256"] == profile_sha256
        and record["transport_semantic_sha256"] == semantic_sha256
        and record["geometry_contract_root_sha256"] == _W3_PARENT_W2["contract_root_sha256"]
        and record["geometry_profile_sha256"] == _W3_PARENT_W2["profile_sha256"]
        and record["geometry_contract_sha256"] == _W3_PARENT_W2["geometry_contract_sha256"]
        and record["operator_semantic_sha256"] == _W3_PARENT_W2["operator_semantic_sha256"]
        and record["parent_link_sha256"] == parent_link_sha256
        and record["source_identity_sha256"] == source_identity_sha256,
        "G3 transport candidate direct identity linkage mismatch",
    )
    layout, raw_byte_count = _validate_w3_state_layout(record["state_layout"])
    initial_state, initial_raw = _read_w3_raw_state(
        root_path,
        record["initial_state"],
        expected_path="fixtures/initial-state.bin",
        layout=layout,
        expected_byte_count=raw_byte_count,
        context="G3 initial raw state",
    )
    final_state, final_raw = _read_w3_raw_state(
        root_path,
        record["final_state"],
        expected_path="fixtures/final-state.bin",
        layout=layout,
        expected_byte_count=raw_byte_count,
        context="G3 final raw state",
    )
    schedule_sha256 = _validate_w3_stage_schedule(record["stage_schedule"])
    _require(
        record["stage_schedule_sha256"] == schedule_sha256,
        "G3 candidate stage schedule linkage mismatch",
    )
    operator_evidence = _w3_exact_mapping(
        record["operator_evidence"],
        set(_w3_operator_evidence()),
        "G3 operator evidence",
    )
    _require(
        canonical_json_bytes(operator_evidence) == canonical_json_bytes(_w3_operator_evidence()),
        "G3 operator evidence mismatch",
    )
    _validate_w3_source_request(record["source_request"])
    diagnostics = _validate_w3_diagnostics(
        record["diagnostics"],
        initial_raw=initial_raw,
        final_raw=final_raw,
        layout=layout,
    )
    _validate_w3_controls(record["mutation_controls"])
    initial_scales = _w3_scale_diagnostics(initial_raw, layout=layout)
    final_scales = _w3_scale_diagnostics(final_raw, layout=layout)
    tolerance = _w3_f64(W3_CANDIDATE_TOLERANCE, "W3 candidate tolerance")
    _validate_w3_replay(
        record["replay"],
        initial_state_sha256=initial_state["state_sha256"],
        final_state_sha256=final_state["state_sha256"],
        tolerance=tolerance,
    )
    _validate_w3_refinement(
        record["refinement"],
        final_state_sha256=final_state["state_sha256"],
        tolerance=tolerance,
    )
    _validate_w3_long_horizon(
        record["long_horizon"],
        initial_state_sha256=initial_state["state_sha256"],
        tolerance=tolerance,
    )
    _validate_w3_failure_receipts(
        record["failure_receipts"],
        predecessor_state_sha256=initial_state["state_sha256"],
    )
    workspace = _validate_w3_workspace_bounds(
        record["workspace_bounds"],
        raw_byte_count=raw_byte_count,
    )
    _validate_w3_stability_bounds(
        record["stability_bounds"],
        initial_scales=initial_scales,
        final_scales=final_scales,
        tolerance=tolerance,
    )
    identities = {
        "parent_w2": canonical_hash(_W3_PARENT_W2, W3_PARENT_IDENTITY_DOMAIN),
        "schema_registry": registry_sha256,
        "transport_contract_root": root_sha256,
        "transport_profile": profile_sha256,
        "transport_semantic": semantic_sha256,
        "geometry_contract_root": _W3_PARENT_W2["contract_root_sha256"],
        "geometry_profile": _W3_PARENT_W2["profile_sha256"],
        "geometry_contract": _W3_PARENT_W2["geometry_contract_sha256"],
        "operator_semantic": _W3_PARENT_W2["operator_semantic_sha256"],
        "parent_link": parent_link_sha256,
        "source_identity": source_identity_sha256,
        "initial_state": initial_state["state_sha256"],
        "final_state": final_state["state_sha256"],
    }
    _validate_w3_identity_receipts(record["identity_receipts"], identities=identities)
    self_sha256 = _require_sha256(record["self_sha256"], "G3 transport candidate self_sha256")
    without_self = dict(record)
    without_self.pop("self_sha256")
    _require(
        canonical_hash(without_self, W3_G3_CANDIDATE_SCHEMA) == self_sha256,
        "G3 transport candidate self hash mismatch",
    )
    _w3_within_budget(
        record,
        schema=W3_G3_CANDIDATE_SCHEMA,
        budgets=budgets,
        context="G3 transport candidate",
    )
    result = dict(record)
    result["workspace_bounds"] = workspace
    result["diagnostics"] = diagnostics
    return result


def _w3_tree_paths(root_path: Path, expected_files: Sequence[str]) -> None:
    expected = set(expected_files)
    allowed_directories = {Path(".")}
    for relative in expected:
        candidate = Path(relative)
        for parent in candidate.parents:
            allowed_directories.add(parent)
    observed_files: set[str] = set()
    try:
        paths = list(root_path.glob("**/*"))
    except OSError as error:
        raise VerificationError(f"cannot enumerate W3 artifact tree: {error}") from error
    for path in paths:
        relative = path.relative_to(root_path).as_posix()
        _require(not path.is_symlink(), f"W3 artifact contains a symlink: {relative}")
        if path.is_file():
            observed_files.add(relative)
        elif path.is_dir():
            _require(
                Path(relative) in allowed_directories,
                f"W3 artifact contains an unexpected directory: {relative}",
            )
        else:
            raise VerificationError(f"W3 artifact contains a nonregular path: {relative}")
    _require(
        observed_files == expected,
        "W3 artifact layout has missing or extraneous immutable objects",
    )


def _w3_index_expected_paths(source_records: Sequence[Mapping[str, str]]) -> list[str]:
    paths = [
        "fixtures/final-state.bin",
        "fixtures/initial-state.bin",
        "gates/g03-transport/status.json",
        "gates/g03-transport/transport.json",
        "run-spec/parent-link.json",
        "run-spec/source-identity.json",
        "run-spec/w3-contract-root.json",
        "run-spec/w3-profile.json",
        "run-spec/w3-schema-registry.json",
        "run-spec/w3-transport-semantic.json",
    ]
    paths.extend(f"run-spec/sources/{record['path']}" for record in source_records)
    return sorted(paths)


def _validate_w3_index(
    root_path: Path,
    *,
    parent_w2: Sequence[Mapping[str, Any]],
    root_sha256: str,
    profile_sha256: str,
    source_records: Sequence[Mapping[str, str]],
    budgets: Mapping[str, int],
) -> dict[str, Any]:
    record = _w3_exact_mapping(
        _read_object(root_path / "index.json"),
        {
            "schema",
            "run_id",
            "status",
            "parents",
            "contract_root_sha256",
            "profile_sha256",
            "object_count",
            "objects",
            "self_sha256",
        },
        "W3 index",
    )
    _require(record["schema"] == W3_RUN_INDEX_SCHEMA, "W3 index schema mismatch")
    _require(record["status"] == "PASS_W3_G3", "W3 index status mismatch")
    _require(
        record["contract_root_sha256"] == root_sha256
        and record["profile_sha256"] == profile_sha256,
        "W3 index profile/root linkage mismatch",
    )
    parents = record["parents"]
    _require(isinstance(parents, list) and len(parents) == 1, "W3 index parent count mismatch")
    _w3_parent_w2(parents[0], "W3 index parent")
    _require(
        canonical_json_bytes(parents) == canonical_json_bytes(list(parent_w2)),
        "W3 index parent linkage mismatch",
    )
    objects = record["objects"]
    _require(
        isinstance(objects, list)
        and isinstance(record["object_count"], int)
        and not isinstance(record["object_count"], bool)
        and record["object_count"] == len(objects),
        "W3 index object count mismatch",
    )
    declared_paths: list[str] = []
    for item in objects:
        object_record = _w3_exact_mapping(
            item,
            {"path", "byte_count", "sha256"},
            "W3 index object record",
        )
        relative = _w2_relative_path(object_record["path"], "W3 index object path")
        _require(
            isinstance(object_record["byte_count"], int)
            and not isinstance(object_record["byte_count"], bool)
            and object_record["byte_count"] >= 0,
            "W3 index object byte count is invalid",
        )
        digest = _require_sha256(object_record["sha256"], f"W3 index object {relative}")
        target = root_path / relative
        _require(
            target.is_file() and not target.is_symlink(),
            f"W3 index object is missing or symlinked: {relative}",
        )
        try:
            raw = target.read_bytes()
        except OSError as error:
            raise VerificationError(f"cannot read W3 index object {relative}: {error}") from error
        _require(
            len(raw) == object_record["byte_count"]
            and hashlib.sha256(raw).hexdigest() == digest,
            f"W3 index object digest mismatch: {relative}",
        )
        declared_paths.append(relative.as_posix())
    expected_paths = _w3_index_expected_paths(source_records)
    _require(
        declared_paths == sorted(declared_paths) and len(declared_paths) == len(set(declared_paths)),
        "W3 index objects are duplicated or not deterministically sorted",
    )
    _require(
        declared_paths == expected_paths,
        "W3 index does not cover exactly the sealed G3 layout",
    )
    _w3_tree_paths(root_path, [*expected_paths, "index.json"])
    self_sha256 = _require_sha256(record["self_sha256"], "W3 index self_sha256")
    without_self = dict(record)
    without_self.pop("self_sha256")
    _require(
        canonical_hash(without_self, W3_RUN_INDEX_SCHEMA) == self_sha256,
        "W3 index self hash mismatch",
    )
    material = {
        "schema": W3_ARTIFACT_DOMAIN,
        "parents": parents,
        "objects": objects,
        "contract_root_sha256": root_sha256,
        "profile_sha256": profile_sha256,
    }
    _require(
        record["run_id"] == canonical_hash(material, W3_ARTIFACT_DOMAIN),
        "W3 index content-addressed run identity mismatch",
    )
    _w3_within_budget(
        record,
        schema=W3_RUN_INDEX_SCHEMA,
        budgets=budgets,
        context="W3 index",
    )
    return record


def verify_g3_transport(run_root: str | Path) -> dict[str, Any]:
    """Verify the current source-exact periodic-FFT2 W3 artifact."""

    from verify_cassi_qi_transport import verify_artifact

    return verify_artifact(run_root)


def _validate_g1_candidate_status(
    status: Mapping[str, Any],
    *,
    root: Mapping[str, Any],
    profile: Mapping[str, Any],
    candidate: Mapping[str, Any],
    checkpoint_sha256: str,
    receipt_count: int,
) -> dict[str, Any]:
    """Validate the immutable, non-PASS candidate status covered by the W1 index."""

    required = {
        "schema",
        "gate",
        "status",
        "contract_root_sha256",
        "profile_sha256",
        "identity_sha256",
        "checkpoint_sha256",
        "receipt_count",
        "self_sha256",
    }
    _require(set(status) == required, "G1 candidate status keyset is not sealed")
    _require(
        status["schema"] == G1_CANDIDATE_STATUS_SCHEMA,
        "G1 candidate status has wrong schema",
    )
    _require(status["gate"] == "G1", "G1 candidate status has wrong gate")
    _require(
        status["status"] == "CANDIDATE",
        "G1 candidate status must remain non-PASS before independent verification",
    )
    _require(
        status["contract_root_sha256"] == root["self_sha256"],
        "G1 candidate status root mismatch",
    )
    _require(
        status["profile_sha256"] == profile["profile_sha256"],
        "G1 candidate status profile mismatch",
    )
    _require(
        status["identity_sha256"] == candidate["self_sha256"],
        "G1 candidate status identity mismatch",
    )
    _require(
        status["checkpoint_sha256"] == checkpoint_sha256,
        "G1 candidate status checkpoint mismatch",
    )
    _require(
        status["receipt_count"] == receipt_count,
        "G1 candidate status receipt count mismatch",
    )
    self_sha256 = _require_sha256(
        status["self_sha256"],
        "G1 candidate status self_sha256",
    )
    without_self = dict(status)
    without_self.pop("self_sha256")
    _require(
        canonical_hash(without_self, G1_CANDIDATE_STATUS_SCHEMA) == self_sha256,
        "G1 candidate status self hash mismatch",
    )
    return dict(status)


def _g1_recomputed_controls(
    *,
    candidate: Mapping[str, Any],
    checkpoint_bytes: bytes,
    checkpoint: Mapping[str, Any],
    index: Mapping[str, Any],
    index_sha256: str,
) -> list[dict[str, str]]:
    """Describe the independent verifier checks bound into its post-index receipt."""

    mutation_controls = candidate["mutation_controls"]
    return [
        {
            "control_id": "immutable-index",
            "expected": "MATCH",
            "observed": "MATCH",
            "input_sha256": index_sha256,
            "receipt_sha256": index["self_sha256"],
        },
        {
            "control_id": "checkpoint-state",
            "expected": "EXACT",
            "observed": "EXACT",
            "input_sha256": hashlib.sha256(checkpoint_bytes).hexdigest(),
            "receipt_sha256": checkpoint["state_sha256"],
        },
        {
            "control_id": "candidate-mutation-controls",
            "expected": "REJECT",
            "observed": "REJECT",
            "input_sha256": candidate["self_sha256"],
            "receipt_sha256": hashlib.sha256(
                canonical_json_bytes(mutation_controls)
            ).hexdigest(),
        },
    ]


def _g1_frozen_verifier_source_sha256(
    source_identity: Mapping[str, Any],
) -> str:
    """Require this independent verifier to be byte-identical to the frozen source."""

    frozen_sha256: str | None = None
    for record in source_identity["sources"]:
        if record["path"] == Path(__file__).name:
            frozen_sha256 = record["sha256"]
            break
    _require(
        frozen_sha256 is not None,
        "W1 source identity does not record the independent verifier",
    )
    local_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    _require(
        local_sha256 == frozen_sha256,
        "independent verifier source differs from the frozen W1 source record",
    )
    return local_sha256


def _g1_verification_receipt(base: Mapping[str, Any]) -> dict[str, Any]:
    """Build the exact PASS receipt only an independently invoked verifier emits."""

    receipt = {
        "schema": G1_INDEPENDENT_VERIFICATION_SCHEMA,
        "gate": "G1",
        "status": "PASS",
        "run_id": base["run_id"],
        "index_sha256": base["index_sha256"],
        "contract_root_sha256": base["contract_root_sha256"],
        "profile_sha256": base["profile_sha256"],
        "identity_sha256": base["identity_sha256"],
        "checkpoint_state_sha256": base["checkpoint_state_sha256"],
        "trusted_bootstrap_source_sha256": base[
            "trusted_bootstrap_source_sha256"
        ],
        "verifier_source_sha256": base["verifier_source_sha256"],
        "recomputed_controls": [
            dict(control) for control in base["recomputed_controls"]
        ],
    }
    receipt["self_sha256"] = canonical_hash(
        receipt,
        G1_INDEPENDENT_VERIFICATION_SCHEMA,
    )
    return receipt


def _validate_g1_verification_receipt(
    receipt_path: Path,
    expected: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate the exact immutable-index-excluded independent verifier receipt."""

    actual = _read_object(receipt_path)
    _require(
        set(actual) == set(expected)
        and actual.get("schema") == G1_INDEPENDENT_VERIFICATION_SCHEMA
        and actual.get("gate") == "G1"
        and actual.get("status") == "PASS",
        "G1 independent verification receipt has an invalid schema or status",
    )
    self_sha256 = _require_sha256(
        actual["self_sha256"],
        "G1 independent verification receipt self_sha256",
    )
    without_self = dict(actual)
    without_self.pop("self_sha256")
    _require(
        canonical_hash(without_self, G1_INDEPENDENT_VERIFICATION_SCHEMA)
        == self_sha256,
        "G1 independent verification receipt self hash mismatch",
    )
    _require(
        canonical_json_bytes(actual) == canonical_json_bytes(expected),
        "G1 independent verification receipt does not bind the current candidate",
    )
    return actual


def _write_new_canonical_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Write one post-index receipt without ever replacing an existing attestation."""

    _require(
        path.parent.is_dir() and not path.parent.is_symlink(),
        "G1 independent verification directory is unavailable",
    )
    raw = canonical_json_bytes(payload)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except OSError as error:
        raise VerificationError(
            f"cannot create new G1 independent verification receipt: {path}"
        ) from error
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            path.unlink()
        except OSError:
            pass
        raise


def verify_g1_identity(
    run_root: str | Path,
    *,
    bootstrap_identity: Mapping[str, Any] | bytes | str | None = None,
    require_attestation: bool = True,
) -> dict[str, Any]:
    """Verify a provisional G1 candidate and, by default, its independent PASS receipt."""

    root_path = Path(run_root).resolve()
    spec = root_path / "run-spec"
    bootstrap = (
        bootstrap_identity
        if bootstrap_identity is not None
        else _read_object(spec / "bootstrap-identity.json")
    )
    root = _read_object(spec / "contract-root.json")
    canonical_codec = _read_object(spec / "canonical-codec.json")
    canonical_fixture_corpus = _read_object(spec / "canonical-fixture-corpus.json")
    registry_path = spec / "schema-registry" / "manifest.json"
    registry = _read_object(registry_path)
    projections = _read_object(spec / "profile-projections.json")
    profile_defaults = _read_object(spec / "profile-defaults.json")
    profile = _read_object(spec / "profile.json")
    verified_root, entries = validate_root_components(
        contract_root=root,
        canonical_codec=canonical_codec,
        canonical_fixture_corpus=canonical_fixture_corpus,
        schema_registry=registry_path,
        projection_registry=projections,
        profile_defaults=profile_defaults,
        bootstrap_identity=bootstrap,
    )
    verified_profile = validate_profile(
        profile,
        contract_root=verified_root,
        profile_defaults=profile_defaults,
        projection_registry=projections,
    )
    gate_dir = root_path / "gates" / "g01-identity"
    checkpoint_path = gate_dir / "checkpoint.qiflow"
    try:
        checkpoint_bytes = checkpoint_path.read_bytes()
    except OSError as error:
        raise VerificationError(f"cannot read {checkpoint_path}: {error}") from error
    checkpoint = validate_v3_checkpoint(
        checkpoint_bytes,
        contract_root=verified_root,
        profile=verified_profile,
        projection_registry=projections,
    )
    candidate = _validate_g1_candidate(
        _read_object(gate_dir / "identity.json"),
        root=verified_root,
        profile=verified_profile,
        checkpoint=checkpoint,
    )
    receipts_dir = gate_dir / "receipts"
    try:
        receipt_paths = sorted(
            path for path in receipts_dir.iterdir()
            if path.is_file() and path.suffix == ".json"
        )
    except OSError as error:
        raise VerificationError(f"cannot read receipt directory {receipts_dir}: {error}") from error
    receipt_envelope = {
        "schema",
        "receipt_id",
        "contract_root_sha256",
        "profile_sha256",
        "consumed_semantic_subhashes",
        "self_sha256",
    }
    required_receipt_schemas = {
        schema
        for schema, entry in entries.items()
        if entry["object_class"] == "indexed-receipt"
        and receipt_envelope
        <= set(entry["schema_document"]["required_keys"])
    }
    seen_receipt_schemas: set[str] = set()
    for receipt_path in receipt_paths:
        receipt = validate_artifact(
            _read_object(receipt_path),
            contract_root=verified_root,
            canonical_codec=canonical_codec,
            canonical_fixture_corpus=canonical_fixture_corpus,
            schema_registry=registry_path,
            projection_registry=projections,
            profile_defaults=profile_defaults,
            bootstrap_identity=bootstrap,
            profile=verified_profile,
        )
        schema = receipt["schema"]
        _require(schema in required_receipt_schemas, f"G1 receipt schema is not required: {schema}")
        _require(schema not in seen_receipt_schemas, f"G1 receipt schema is duplicated: {schema}")
        seen_receipt_schemas.add(schema)
    _require(
        seen_receipt_schemas == required_receipt_schemas,
        "G1 receipt-domain coverage is incomplete",
    )
    parent_link = _read_object(spec / "parent-link.json")
    linked_parents = parent_link.get("parents")
    candidate_parents = candidate.get("parents")
    _require(
        isinstance(linked_parents, Sequence)
        and isinstance(candidate_parents, Sequence)
        and len(linked_parents) == len(candidate_parents) == 1
        and isinstance(linked_parents[0], Mapping)
        and isinstance(candidate_parents[0], Mapping)
        and linked_parents[0].get("run_id") == candidate_parents[0].get("artifact_sha256")
        and linked_parents[0].get("historical_manifest_sha256")
        == candidate_parents[0].get("historical_manifest_sha256"),
        "G1 sealed W0 parent linkage mismatch",
    )
    index = _validate_w1_index(
        root_path,
        contract_root=verified_root,
        profile=verified_profile,
        bootstrap_identity=bootstrap,
        canonical_fixture_corpus=canonical_fixture_corpus,
        canonical_codec=canonical_codec,
        schema_registry=registry,
        projection_registry=projections,
        trusted_bootstrap_source=Path(__file__).resolve().with_name("cassi_qi_bootstrap.py"),
    )
    status_path = gate_dir / "status.json"
    _validate_g1_candidate_status(
        _read_object(status_path),
        root=verified_root,
        profile=verified_profile,
        candidate=candidate,
        checkpoint_sha256=hashlib.sha256(checkpoint_bytes).hexdigest(),
        receipt_count=len(seen_receipt_schemas),
    )
    index_path = root_path / "index.json"
    try:
        index_sha256 = hashlib.sha256(index_path.read_bytes()).hexdigest()
    except OSError as error:
        raise VerificationError(f"cannot read {index_path}: {error}") from error
    source_identity = _read_object(spec / "source-identity.json")
    base = {
        "gate": "G1",
        "status": "CANDIDATE",
        "contract_root_sha256": verified_root["self_sha256"],
        "profile_sha256": verified_profile["profile_sha256"],
        "registered_schema_count": len(entries),
        "receipt_count": len(seen_receipt_schemas),
        "run_id": index["run_id"],
        "index_sha256": index_sha256,
        "checkpoint_state_sha256": checkpoint["state_sha256"],
        "identity_sha256": candidate["self_sha256"],
        "trusted_bootstrap_source_sha256": source_identity[
            "bootstrap_source_sha256"
        ],
        "verifier_source_sha256": _g1_frozen_verifier_source_sha256(
            source_identity
        ),
        "recomputed_controls": _g1_recomputed_controls(
            candidate=candidate,
            checkpoint_bytes=checkpoint_bytes,
            checkpoint=checkpoint,
            index=index,
            index_sha256=index_sha256,
        ),
        "status_path": status_path.as_posix(),
    }
    verification_path = gate_dir / "verification.json"
    if not verification_path.exists() and not verification_path.is_symlink():
        _require(
            not require_attestation,
            "G1 independent post-index verification receipt is missing",
        )
        return base
    _require(
        verification_path.is_file() and not verification_path.is_symlink(),
        "G1 independent post-index verification receipt is not a regular file",
    )
    expected_receipt = _g1_verification_receipt(base)
    _validate_g1_verification_receipt(verification_path, expected_receipt)
    verification_sha256 = hashlib.sha256(verification_path.read_bytes()).hexdigest()
    return {
        **base,
        "status": "PASS",
        "verification_sha256": verification_sha256,
        "verification_path": verification_path.as_posix(),
    }


def write_g1_verification(
    run_root: str | Path,
    *,
    bootstrap_identity: Mapping[str, Any] | bytes | str | None = None,
) -> dict[str, Any]:
    """Independently attest one sealed provisional W1 candidate without mutating its index."""

    root_path = Path(run_root).resolve()
    verification_path = root_path / "gates" / "g01-identity" / "verification.json"
    _require(
        not verification_path.exists() and not verification_path.is_symlink(),
        "G1 independent post-index verification receipt already exists",
    )
    base = verify_g1_identity(
        root_path,
        bootstrap_identity=bootstrap_identity,
        require_attestation=False,
    )
    _require(
        base["status"] == "CANDIDATE",
        "G1 candidate unexpectedly already has a verification status",
    )
    _write_new_canonical_json(
        verification_path,
        _g1_verification_receipt(base),
    )
    return verify_g1_identity(
        root_path,
        bootstrap_identity=bootstrap_identity,
    )


def _command_line() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Cassi Qi Flow artifact verifier")
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--run-root", type=Path, help="run tree containing G1, G2, or G3 artifacts")
    selection.add_argument("--artifact", type=Path, help="one receipt JSON artifact")
    parser.add_argument("--contract-root", type=Path, help="canonical contract-root JSON for --artifact")
    parser.add_argument("--schema-registry", type=Path, help="canonical schema-registry JSON for --artifact")
    parser.add_argument("--canonical-codec", type=Path, help="canonical codec JSON for --artifact")
    parser.add_argument("--canonical-fixture-corpus", type=Path, help="canonical fixture corpus JSON for --artifact")
    parser.add_argument("--projection-registry", type=Path, help="profile projection registry JSON for --artifact")
    parser.add_argument("--profile-defaults", type=Path, help="profile defaults JSON for --artifact")
    parser.add_argument("--profile", type=Path, help="canonical profile JSON for --artifact")
    parser.add_argument("--bootstrap-identity", type=Path, help="canonical bootstrap source/toolchain/fixture pin")
    parser.add_argument("--expected-schema", help="require this artifact schema")
    parser.add_argument(
        "--write-receipt",
        action="store_true",
        help="independently create the post-index G1 verification receipt",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point; G1 receipt mode writes only a post-index independent attestation."""

    args = _command_line().parse_args(argv)
    try:
        if args.run_root is not None:
            if (args.run_root / "gates" / "g03-transport").is_dir():
                _require(
                    not args.write_receipt,
                    "--write-receipt is available only for a G1 run root",
                )
                result = verify_g3_transport(args.run_root)
            elif (args.run_root / "gates" / "g02-geometry").is_dir():
                _require(
                    not args.write_receipt,
                    "--write-receipt is available only for a G1 run root",
                )
                result = verify_g2_geometry(args.run_root)
            else:
                bootstrap = _read_object(args.bootstrap_identity) if args.bootstrap_identity else None
                result = (
                    write_g1_verification(
                        args.run_root,
                        bootstrap_identity=bootstrap,
                    )
                    if args.write_receipt
                    else verify_g1_identity(
                        args.run_root,
                        bootstrap_identity=bootstrap,
                    )
                )
        else:
            bootstrap = _read_object(args.bootstrap_identity) if args.bootstrap_identity else None
            _require(
                not args.write_receipt,
                "--write-receipt requires --run-root for a G1 candidate",
            )
            _require(
                args.contract_root is not None
                and args.schema_registry is not None
                and args.canonical_codec is not None
                and args.canonical_fixture_corpus is not None
                and args.projection_registry is not None
                and args.profile_defaults is not None
                and bootstrap is not None,
                "--artifact requires every root component and --bootstrap-identity",
            )
            artifact = _read_object(args.artifact)
            root = _read_object(args.contract_root)
            canonical_codec = _read_object(args.canonical_codec)
            canonical_fixture_corpus = _read_object(args.canonical_fixture_corpus)
            projections = _read_object(args.projection_registry)
            profile_defaults = _read_object(args.profile_defaults)
            profile = _read_object(args.profile) if args.profile is not None else None
            result = validate_artifact(
                artifact,
                contract_root=root,
                canonical_codec=canonical_codec,
                canonical_fixture_corpus=canonical_fixture_corpus,
                schema_registry=args.schema_registry,
                projection_registry=projections,
                profile_defaults=profile_defaults,
                bootstrap_identity=bootstrap,
                profile=profile,
                expected_schema=args.expected_schema,
            )
        sys.stdout.buffer.write(canonical_json_bytes(result) + b"\n")
        return 0
    except VerificationError as error:
        sys.stderr.write(f"verification failed: {error}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
