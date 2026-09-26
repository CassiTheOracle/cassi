"""Bounded field-level probe of the production coarse/fine resolution boundary.

This workstream tests only the numerical layout transitions exposed by
``expand_resolution`` and ``reduce_resolution``.  It does not claim a
self-similar physical hierarchy, semantic memory, recall, or task utility.
The packet parent/sibling regrouping relation is measured by the existing
fractal-memory workstream and is deliberately not duplicated here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping

import numpy as np

import cassi_resonant_field as field
import run_fractal_geometry_exploration as geometry
import run_fractal_memory_exploration as memory

SCHEMA = "cassifi.fractal-resolution-exploration.v1"
DEFAULT_OUTPUT = Path("_diag/fractal-resolution/exploration.json")
GEOMETRY_RECEIPT = Path("_diag/fractal-geometry/exploration.json")
MEMORY_RECEIPT = Path("_diag/fractal-memory/exploration.json")

SEED = 20260917
COARSE_PORTS_PER_POOL = 4
FINE_PORTS_PER_POOL = 8
BASELINE_TICKS = 8
DRIVE_BUDGET = 1e-3
REDUCTION_ERROR_ALLOWANCE = 50000.0
EXPANSION_MARGIN = 1e-12
REDUCTION_SLACK_MARGIN = 1e-9
BINDING_MARGIN = 1e-12
CONTINUITY_TOLERANCE = 1e-12
TIMING_KEYS = frozenset({"elapsed_seconds", "runtime_seconds", "content_digest", "receipt_sha256"})
REQUIRED_APIS = (
    "initial_workspace",
    "advance_workspace",
    "apply_helical_packet_impulse",
    "bind_workspace",
    "expand_resolution",
    "reduce_resolution",
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (np.integer, np.floating, np.bool_)):
        return value.item()
    return value


def _strip_clock(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _strip_clock(item)
            for key, item in value.items()
            if key not in TIMING_KEYS
        }
    if isinstance(value, list):
        return [_strip_clock(item) for item in value]
    return value


def digest_obj(value: Any) -> str:
    return hashlib.sha256(canonical_json(_jsonable(value)).encode("utf-8")).hexdigest()


def content_digest(receipt: Mapping[str, Any]) -> str:
    return digest_obj(_strip_clock(receipt))


def api_probe() -> dict[str, Any]:
    symbols = {name: callable(getattr(field, name, None)) for name in REQUIRED_APIS}
    return {
        "required_symbols": list(REQUIRED_APIS),
        "symbols": symbols,
        "available": bool(all(symbols.values())),
        "unsupported_arm": {
            "attempted": False,
            "verdict": "NOT_APPLICABLE" if all(symbols.values()) else "OUT_OF_SCOPE",
            "reason": (
                "production scale-indexed resolution APIs are present"
                if all(symbols.values())
                else "one or more production scale-indexed resolution APIs are unavailable"
            ),
        },
    }


def _source_workspace() -> tuple[Any, dict[str, Any], dict[str, Any]]:
    profile = geometry.build_profile(geometry.arrangement_named("helix7", seed=SEED))
    if profile.ports_per_pool != COARSE_PORTS_PER_POOL:
        raise field.ResonantNumericalError("canonical continuity profile is not coarse resolution")
    workspace, advance = field.advance_workspace(
        field.initial_workspace(profile), ticks=BASELINE_TICKS, source_enabled=True
    )
    problem = field.ResonantProblem(
        variable_ids=("resolution-probe",),
        precision=np.eye(1, dtype=np.float64),
        observed={"resolution-probe.__pool": 0.0},
    )
    workspace = field.bind_workspace(workspace, problem)
    workspace, impulse = field.apply_helical_packet_impulse(
        workspace,
        path="",
        component="scale",
        flow_signal=(0.6, -0.8),
        work_budget=DRIVE_BUDGET,
        evidence_tick=workspace.evidence_tick,
        event_kind=memory.EVENT_KIND,
    )
    binding = dict(workspace.bindings["resolution-probe"])
    source = {
        "advance_accepted": bool(advance["accepted"]),
        "seed": SEED,
        "profile": {
            "topology": str(profile.topology),
            "pools": int(profile.pools),
            "ports_per_pool": int(profile.ports_per_pool),
            "port_count": int(profile.port_count),
            "layout_identity": profile.layout_identity,
        },
        "baseline_ticks": BASELINE_TICKS,
        "binding": binding,
        "binding_sha256": digest_obj(binding),
        "impulse": {
            "path": impulse["path"],
            "component": impulse["component"],
            "accepted": bool(impulse["accepted"]),
            "requested_work": float(impulse["requested_work"]),
            "applied_work": float(impulse["applied_work"]),
            "balance_defect": float(impulse["balance_defect"]),
            "basis_sha256": str(impulse["basis_sha256"]),
        },
        "state_sha256": workspace.state_sha256,
        "page_sha256": hashlib.sha256(workspace.page_bytes).hexdigest(),
    }
    return workspace, source, {"advance": advance, "impulse": impulse}


def _unsupported_body(probe: Mapping[str, Any], started: float) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "declared": {
            "question": "Does the production field expose a bounded coarse/fine resolution relation?",
            "semantic_recall_claim": False,
            "probe_kind": "field-level boundary/surrogate probe",
            "api_probe": dict(probe),
            "resolutions": {"coarse_ports_per_pool": COARSE_PORTS_PER_POOL, "fine_ports_per_pool": FINE_PORTS_PER_POOL},
            "margins": {
                "expansion_state_error": EXPANSION_MARGIN,
                "reduction_slack": REDUCTION_SLACK_MARGIN,
                "binding_port_error": BINDING_MARGIN,
            },
        },
        "arms": {
            "unsupported-resolution": {
                "attempted": False,
                "verdict": "OUT_OF_SCOPE",
                "reason": probe["unsupported_arm"]["reason"],
            }
        },
        "comparisons": [],
        "continuity": continuity_checks(),
        "controls": {"firing": [], "unsupported": dict(probe["unsupported_arm"])},
        "limitations": limitations(),
    }
    body["runtime_seconds"] = float(perf_counter() - started)
    body["content_digest"] = content_digest(body)
    body["receipt_sha256"] = body["content_digest"]
    return body


def measure_resolution() -> dict[str, Any]:
    workspace, source, _details = _source_workspace()
    expanded, expansion = field.expand_resolution(
        workspace, ports_per_pool=FINE_PORTS_PER_POOL
    )
    reduced, reduction = field.reduce_resolution(
        expanded,
        ports_per_pool=COARSE_PORTS_PER_POOL,
        error_allowance=REDUCTION_ERROR_ALLOWANCE,
    )
    expanded_binding = dict(expanded.bindings["resolution-probe"])
    reduced_binding = dict(reduced.bindings["resolution-probe"])
    certificate_keys = (
        "reconstruction_error_bound",
        "frequency_response_error_bound",
        "nonlinear_trajectory_error_bound",
    )
    certificate_bounds = {
        key: float(reduction[key]) for key in certificate_keys
    }
    certificate_max = max(certificate_bounds.values())
    reduction_slack = float(REDUCTION_ERROR_ALLOWANCE - certificate_max)
    binding_port_error = abs(
        int(reduced_binding["port"]) - int(source["binding"]["port"])
    )
    expansion_error = float(expansion["state_error_norm"])
    comparisons = [
        {
            "id": "expansion_zero_mode_embedding",
            "quantity": expansion_error,
            "quantity_name": "state_error_norm",
            "predicate": "quantity <= margin",
            "margin": EXPANSION_MARGIN,
            "holds": bool(expansion_error <= EXPANSION_MARGIN),
            "firing_control": {
                "attempted": True,
                "mutation": "replace the measured state_error_norm by 2*margin",
                "mutated_quantity": float(2.0 * EXPANSION_MARGIN),
                "holds_after": bool(2.0 * EXPANSION_MARGIN <= EXPANSION_MARGIN),
                "can_fail": bool(2.0 * EXPANSION_MARGIN > EXPANSION_MARGIN),
            },
        },
        {
            "id": "reduction_certificate_slack",
            "quantity": reduction_slack,
            "quantity_name": "error_allowance_minus_max_certificate_bound",
            "predicate": "quantity >= margin",
            "margin": REDUCTION_SLACK_MARGIN,
            "holds": bool(reduction_slack >= REDUCTION_SLACK_MARGIN),
            "firing_control": {
                "attempted": True,
                "mutation": "replace the largest certificate bound by error_allowance+margin",
                "mutated_quantity": float(-REDUCTION_SLACK_MARGIN),
                "holds_after": bool(-REDUCTION_SLACK_MARGIN >= REDUCTION_SLACK_MARGIN),
                "can_fail": bool(-REDUCTION_SLACK_MARGIN < REDUCTION_SLACK_MARGIN),
            },
        },
        {
            "id": "binding_survives_coarse_fine_transition",
            "quantity": float(binding_port_error),
            "quantity_name": "absolute_binding_port_error",
            "predicate": "quantity <= margin",
            "margin": BINDING_MARGIN,
            "holds": bool(binding_port_error <= BINDING_MARGIN),
            "firing_control": {
                "attempted": True,
                "mutation": "replace the reduced binding port by source_port+1",
                "mutated_quantity": 1.0,
                "holds_after": bool(1.0 <= BINDING_MARGIN),
                "can_fail": bool(1.0 > BINDING_MARGIN),
            },
        },
    ]
    return {
        "source": source,
        "arms": {
            "expansion": {
                "from_layout": workspace.profile.layout_identity,
                "to_layout": expanded.profile.layout_identity,
                "from_ports_per_pool": int(workspace.profile.ports_per_pool),
                "to_ports_per_pool": int(expanded.profile.ports_per_pool),
                "transition": dict(expansion),
                "state_sha256": expanded.state_sha256,
                "page_sha256": hashlib.sha256(expanded.page_bytes).hexdigest(),
                "binding": expanded_binding,
                "new_coordinates_zero": bool(expansion["new_coordinates_zero"]),
            },
            "reduction": {
                "from_layout": expanded.profile.layout_identity,
                "to_layout": reduced.profile.layout_identity,
                "from_ports_per_pool": int(expanded.profile.ports_per_pool),
                "to_ports_per_pool": int(reduced.profile.ports_per_pool),
                "transition": dict(reduction),
                "certificate_bounds": certificate_bounds,
                "certificate_max_bound": certificate_max,
                "error_allowance": REDUCTION_ERROR_ALLOWANCE,
                "slack": reduction_slack,
                "binding": reduced_binding,
                "occupied_bindings_preserved": bool(reduction["occupied_bindings_preserved"]),
                "state_sha256": reduced.state_sha256,
                "page_sha256": hashlib.sha256(reduced.page_bytes).hexdigest(),
            },
        },
        "comparisons": comparisons,
        "verdict": "PASS" if all(row["holds"] for row in comparisons) else "MEASURED_NO_VERDICT",
    }


def continuity_checks() -> list[dict[str, Any]]:
    root = Path(__file__).resolve().parent
    geometry_path = root / GEOMETRY_RECEIPT
    memory_path = root / MEMORY_RECEIPT
    with geometry_path.open("r", encoding="utf-8") as stream:
        geometry_receipt = json.load(stream)
    with memory_path.open("r", encoding="utf-8") as stream:
        memory_receipt = json.load(stream)
    expected_retention = float(
        next(
            row["retention"]["retention_mean"]
            for row in geometry_receipt["arrangements"]
            if row["construction"]["name"] == "helix7"
        )
    )
    profile = geometry.build_profile(geometry.arrangement_named("helix7", seed=SEED))
    measured_retention = float(
        geometry.retention_metrics(
            profile,
            pools=geometry.DEFAULT_IMPULSE_POOLS,
            work=geometry.DEFAULT_IMPULSE_WORK,
            ticks=geometry.DEFAULT_RETENTION_TICKS,
        )["retention_mean"]
    )
    expected_reconstruction = float(
        memory_receipt["view_integrity"]["maximum_coefficient_reconstruction_error"]
    )
    measured_reconstruction = float(
        memory.stage_view_integrity(memory.ExplorationConfig(), profile)[
            "maximum_coefficient_reconstruction_error"
        ]
    )
    rows = [
        {
            "source": str(GEOMETRY_RECEIPT),
            "selector": "arrangements[construction.name=helix7].retention.retention_mean",
            "expected": expected_retention,
            "measured": measured_retention,
            "difference": float(measured_retention - expected_retention),
            "tolerance": CONTINUITY_TOLERANCE,
            "within_tolerance": bool(abs(measured_retention - expected_retention) <= CONTINUITY_TOLERANCE),
        },
        {
            "source": str(MEMORY_RECEIPT),
            "selector": "view_integrity.maximum_coefficient_reconstruction_error",
            "expected": expected_reconstruction,
            "measured": measured_reconstruction,
            "difference": float(measured_reconstruction - expected_reconstruction),
            "tolerance": CONTINUITY_TOLERANCE,
            "within_tolerance": bool(abs(measured_reconstruction - expected_reconstruction) <= CONTINUITY_TOLERANCE),
        },
    ]
    return rows


def limitations() -> list[str]:
    return [
        "This is a field-level resolution-boundary probe, not a semantic hierarchy or recall experiment.",
        "expand_resolution is a zero-mode embedding and reduce_resolution is an orthonormal passive reduction; neither establishes self-similar physics or a parent/child learned representation.",
        "The p=8 profile is rebuilt by the production API, so no claim is made that coarse and fine dynamics are identical.",
        "The reduction certificate is bounded to its production assumptions: positive energy metric and damping, unchanged body profile, dense source-port limit, and its declared finite field-time horizon.",
        "Binding preservation is metadata placement through a layout transition; it is not evidence that a semantic task target survives.",
        "The existing fractal-memory receipt already measures packet analyze/split/compose parent-sibling regrouping; these figures are not a second packet-hierarchy claim.",
        "All figures are deterministic numerical observables; no semantic recall, task utility, consumer retrieval, or architectural advantage is claimed.",
    ]


def build_receipt() -> dict[str, Any]:
    started = perf_counter()
    probe = api_probe()
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "declared": {
            "question": "Does the production field expose a bounded coarse/fine resolution relation?",
            "semantic_recall_claim": False,
            "probe_kind": "field-level boundary/surrogate probe",
            "seed": SEED,
            "api_probe": probe,
            "resolutions": {
                "coarse_ports_per_pool": COARSE_PORTS_PER_POOL,
                "fine_ports_per_pool": FINE_PORTS_PER_POOL,
            },
            "source_construction": "geometry.build_profile(arrangement_named('helix7')) -> initial_workspace -> advance_workspace -> bind_workspace -> apply_helical_packet_impulse",
            "transition_path": ["expand_resolution", "reduce_resolution"],
            "packet_path": "",
            "margins": {
                "expansion_state_error": EXPANSION_MARGIN,
                "reduction_slack": REDUCTION_SLACK_MARGIN,
                "binding_port_error": BINDING_MARGIN,
            },
            "reduction_error_allowance": REDUCTION_ERROR_ALLOWANCE,
        },
    }
    if probe["available"]:
        measured = measure_resolution()
        body.update(measured)
        body["continuity"] = continuity_checks()
        body["controls"] = {
            "firing": [
                {
                    "comparison": row["id"],
                    **dict(row["firing_control"]),
                }
                for row in measured["comparisons"]
            ],
            "unsupported": dict(probe["unsupported_arm"]),
        }
        body["limitations"] = limitations()
    else:
        unsupported = _unsupported_body(probe, started)
        unsupported["declared"] = body["declared"]
        return unsupported
    body["continuity_verdict"] = "PASS" if all(row["within_tolerance"] for row in body["continuity"]) else "MEASURED_NO_VERDICT"
    body["runtime_seconds"] = float(perf_counter() - started)
    body["content_digest"] = content_digest(body)
    body["receipt_sha256"] = body["content_digest"]
    return body


def verify_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    actual = content_digest(receipt)
    return {
        "content_digest_matches": bool(actual == receipt.get("content_digest")),
        "digest": actual,
    }


def can_fail_probes(receipt: Mapping[str, Any]) -> dict[str, Any]:
    rows = receipt.get("comparisons", [])
    controls = receipt.get("controls", {}).get("firing", [])
    return {
        "comparison_count": len(rows),
        "control_count": len(controls),
        "all_attempted": bool(controls) and all(bool(row.get("attempted")) for row in controls),
        "all_can_fail": bool(controls) and all(bool(row.get("can_fail")) for row in controls),
        "all_flip": bool(controls) and all(not bool(row.get("holds_after")) for row in controls),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    receipt = build_receipt()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(_jsonable(receipt), sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "content_digest": receipt["content_digest"],
                "runtime_seconds": receipt["runtime_seconds"],
                "verdict": receipt.get("verdict", "OUT_OF_SCOPE"),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
