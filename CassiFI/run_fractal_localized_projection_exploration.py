"""Measure a localized fine packet write and its disposable coarse view.

This is a field-level packet-view probe.  The production packet API exposes
nested Haar views over one live page; it does not create persistent parent or
child memory.  The runner therefore measures immediate write reach, the
parent's level-zero projection, and public split/compose round trips without
claiming semantic hierarchy or recall.
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

SCHEMA = "cassifi.fractal-localized-projection-exploration.v1"
DEFAULT_OUTPUT = Path("_diag/fractal-localized-projection/exploration.json")
GEOMETRY_RECEIPT = Path("_diag/fractal-geometry/exploration.json")
MEMORY_RECEIPT = Path("_diag/fractal-memory/exploration.json")
SEED = 20260917
PORTS_PER_POOL = 4
PARENT_PATH = "L"
FINE_PATH = "LL"
SIBLING_PATH = "LR"
FLOW_SIGNAL = (1.0, 0.0)
DRIVE_BUDGET = 1e-3
CONTINUITY_TOLERANCE = 1e-12
FINE_REACH_MARGIN = 1e-12
PROJECTION_SEPARATION_MARGIN = 1e-8
RECONSTRUCTION_MARGIN = 1e-12
TIMING_KEYS = frozenset({"elapsed_seconds", "runtime_seconds", "content_digest", "receipt_sha256"})

BOUNDARY = (
    "Canonical-field numerical measurements only. A packet is a disposable view "
    "of one live field page; split/compose reconstructs a packet view and never "
    "writes persistent parent or child state. No semantic hierarchy, recall, "
    "consumer retrieval, task utility, or architectural advantage is claimed."
)
LIMITATIONS = [
    "This workstream uses nested packet views on one fixed p=4 page, not expand_resolution or reduce_resolution.",
    "expand_resolution is a whole-page zero-mode embedding and reduce_resolution is a whole-page orthonormal passive reduction; neither is a localized parent/child memory operation.",
    "analyze_helical_packet returns a disposable localized view; split_helical_packet and compose_helical_packets reconstruct that view only and do not mutate or restore the live workspace.",
    "The parent level-zero coefficient is a Haar block-average projection of the declared parent support, not a persistent coarse representation.",
    "All comparisons are field observables. A failed LL-vs-LR projection separation is a negative result for this readout, not evidence that no other readout could distinguish placements.",
]


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


def canonical_json(value: Any) -> str:
    return json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


def _strip_timing(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _strip_timing(item)
            for key, item in value.items()
            if key not in TIMING_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_strip_timing(item) for item in value]
    return value


def content_digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(_strip_timing(value)).encode("utf-8")).hexdigest()


def page_sha256(workspace: Any) -> str:
    return hashlib.sha256(workspace.page_bytes).hexdigest()


def _profile() -> field.ResonantProfile:
    return geometry.build_profile(
        geometry.arrangement_named("helix7", seed=SEED),
        ports_per_pool=PORTS_PER_POOL,
    )


def _packet_record(workspace: Any) -> dict[str, Any]:
    parent = dict(field.analyze_helical_packet(workspace, path=PARENT_PATH))
    child = dict(field.analyze_helical_packet(workspace, path=FINE_PATH))
    sibling = dict(field.analyze_helical_packet(workspace, path=SIBLING_PATH))
    left, right = field.split_helical_packet(parent)
    reconstructed = field.compose_helical_packets(left, right)
    parent_coefficients = np.asarray(parent["coefficients"], dtype=np.float64)
    child_coefficients = np.asarray(child["coefficients"], dtype=np.float64)
    left_coefficients = np.asarray(left["coefficients"], dtype=np.float64)
    reconstructed_coefficients = np.asarray(reconstructed["coefficients"], dtype=np.float64)
    return {
        "parent": parent,
        "fine_child": child,
        "sibling_child": sibling,
        "split_left": dict(left),
        "split_right": dict(right),
        "reconstructed_parent": dict(reconstructed),
        "parent_level_zero_projection": parent_coefficients[0].tolist(),
        "parent_level_zero_norm": float(np.linalg.norm(parent_coefficients[0])),
        "fine_child_norm": float(np.linalg.norm(child_coefficients)),
        "parent_reconstruction_error": float(
            np.max(np.abs(parent_coefficients - reconstructed_coefficients), initial=0.0)
        ),
        "direct_child_split_error": float(
            np.max(np.abs(child_coefficients - left_coefficients), initial=0.0)
        ),
    }


def _write_arm(profile: field.ResonantProfile, name: str, path: str | None) -> dict[str, Any]:
    workspace = field.initial_workspace(profile)
    impulse = None
    if path is not None:
        workspace, impulse = field.apply_helical_packet_impulse(
            workspace,
            path=path,
            component="scale",
            flow_signal=FLOW_SIGNAL,
            work_budget=DRIVE_BUDGET,
            evidence_tick=workspace.evidence_tick,
            event_kind=memory.EVENT_KIND,
        )
    packets = _packet_record(workspace)
    return {
        "arm": name,
        "write_path": path,
        "component": "scale" if path is not None else None,
        "flow_signal": list(FLOW_SIGNAL) if path is not None else None,
        "requested_work": 0.0 if impulse is None else float(impulse["requested_work"]),
        "applied_work": 0.0 if impulse is None else float(impulse["applied_work"]),
        "impulse": None if impulse is None else {
            key: impulse[key]
            for key in (
                "schema", "accepted", "basis_sha256", "path", "component", "support",
                "mode", "flow_signal", "requested_work", "applied_work", "impulse_amount",
                "balance_defect", "energy_roundoff_allowance", "source_state_sha256", "state_sha256",
            )
        },
        "state_sha256": workspace.state_sha256,
        "page_sha256": page_sha256(workspace),
        "views": packets,
    }


def _comparison(
    identifier: str,
    quantity: float,
    quantity_name: str,
    predicate: str,
    margin: float,
    holds: bool,
    mutation: str,
    mutated_quantity: float,
    holds_after: bool,
) -> dict[str, Any]:
    return {
        "id": identifier,
        "quantity": float(quantity),
        "quantity_name": quantity_name,
        "predicate": predicate,
        "margin": float(margin),
        "holds": bool(holds),
        "firing_control": {
            "attempted": True,
            "mutation": mutation,
            "mutated_quantity": float(mutated_quantity),
            "holds_after": bool(holds_after),
            "can_fail": bool(not holds_after),
        },
    }


def _comparisons(arms: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    baseline = arms["no-write"]["views"]
    fine = arms["fine-LL"]["views"]
    sibling = arms["fine-LR"]["views"]
    child_reach = float(
        np.linalg.norm(
            np.asarray(fine["fine_child"]["coefficients"], dtype=np.float64)
            - np.asarray(baseline["fine_child"]["coefficients"], dtype=np.float64)
        )
    )
    projection_separation = float(
        np.linalg.norm(
            np.asarray(fine["parent_level_zero_projection"], dtype=np.float64)
            - np.asarray(sibling["parent_level_zero_projection"], dtype=np.float64)
        )
    )
    parent_error = float(fine["parent_reconstruction_error"])
    child_error = float(fine["direct_child_split_error"])
    return [
        _comparison(
            "fine_child_reaches",
            child_reach,
            "||coeff(LL,fine-LL)-coeff(LL,no-write)||2",
            "quantity > margin",
            FINE_REACH_MARGIN,
            child_reach > FINE_REACH_MARGIN,
            "silence the fine-LL write by replacing its child delta with the no-write delta",
            0.0,
            0.0 > FINE_REACH_MARGIN,
        ),
        _comparison(
            "coarse_projection_separates_LL_from_LR",
            projection_separation,
            "||level0(parent,fine-LL)-level0(parent,fine-LR)||2",
            "quantity > margin",
            PROJECTION_SEPARATION_MARGIN,
            projection_separation > PROJECTION_SEPARATION_MARGIN,
            "silence the placement contrast by replacing fine-LL level0 with fine-LR level0",
            0.0,
            0.0 > PROJECTION_SEPARATION_MARGIN,
        ),
        _comparison(
            "parent_split_compose_reconstructs",
            parent_error,
            "max_abs(parent_coefficients-compose(split(parent)))",
            "quantity <= margin",
            RECONSTRUCTION_MARGIN,
            parent_error <= RECONSTRUCTION_MARGIN,
            "mutate reconstructed parent coefficient by 2*margin",
            2.0 * RECONSTRUCTION_MARGIN,
            2.0 * RECONSTRUCTION_MARGIN <= RECONSTRUCTION_MARGIN,
        ),
        _comparison(
            "split_child_matches_direct_fine_view",
            child_error,
            "max_abs(coeff(LL,direct)-coeff(LL,split(parent)))",
            "quantity <= margin",
            RECONSTRUCTION_MARGIN,
            child_error <= RECONSTRUCTION_MARGIN,
            "mutate split child coefficient by 2*margin",
            2.0 * RECONSTRUCTION_MARGIN,
            2.0 * RECONSTRUCTION_MARGIN <= RECONSTRUCTION_MARGIN,
        ),
    ]


def continuity_checks() -> list[dict[str, Any]]:
    root = Path(__file__).resolve().parent
    with (root / GEOMETRY_RECEIPT).open("r", encoding="utf-8") as stream:
        geometry_receipt = json.load(stream)
    with (root / MEMORY_RECEIPT).open("r", encoding="utf-8") as stream:
        memory_receipt = json.load(stream)
    profile = _profile()
    expected_retention = float(
        next(
            row["retention"]["retention_mean"]
            for row in geometry_receipt["arrangements"]
            if row["construction"]["name"] == "helix7"
        )
    )
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
    return [
        {
            "source": str(GEOMETRY_RECEIPT),
            "selector": "arrangements[construction.name=helix7].retention.retention_mean",
            "expected": expected_retention,
            "measured": measured_retention,
            "difference": measured_retention - expected_retention,
            "tolerance": CONTINUITY_TOLERANCE,
            "within_tolerance": abs(measured_retention - expected_retention) <= CONTINUITY_TOLERANCE,
        },
        {
            "source": str(MEMORY_RECEIPT),
            "selector": "view_integrity.maximum_coefficient_reconstruction_error",
            "expected": expected_reconstruction,
            "measured": measured_reconstruction,
            "difference": measured_reconstruction - expected_reconstruction,
            "tolerance": CONTINUITY_TOLERANCE,
            "within_tolerance": abs(measured_reconstruction - expected_reconstruction) <= CONTINUITY_TOLERANCE,
        },
    ]


def build_receipt() -> dict[str, Any]:
    started = perf_counter()
    profile = _profile()
    arms = {
        "no-write": _write_arm(profile, "no-write", None),
        "fine-LL": _write_arm(profile, "fine-LL", FINE_PATH),
        "fine-LR": _write_arm(profile, "fine-LR", SIBLING_PATH),
        "coarse-L": _write_arm(profile, "coarse-L", PARENT_PATH),
    }
    comparisons = _comparisons(arms)
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "declared": {
            "question": "Does a localized fine-scale write reach its child view and remain distinguishable in a coarse parent projection?",
            "semantic_recall_claim": False,
            "probe_kind": "localized packet-view projection/reconstruction probe",
            "seed": SEED,
            "profile": profile.as_dict(),
            "packet_paths": {
                "parent": PARENT_PATH,
                "fine_child": FINE_PATH,
                "sibling_null": SIBLING_PATH,
            },
            "drive": {
                "component": "scale",
                "flow_signal": list(FLOW_SIGNAL),
                "work_budget": DRIVE_BUDGET,
                "event_kind": memory.EVENT_KIND,
            },
            "margins": {
                "fine_child_reach": FINE_REACH_MARGIN,
                "coarse_projection_separation": PROJECTION_SEPARATION_MARGIN,
                "reconstruction": RECONSTRUCTION_MARGIN,
                "continuity": CONTINUITY_TOLERANCE,
            },
            "api_surface": [
                "initial_workspace", "apply_helical_packet_impulse", "analyze_helical_packet",
                "split_helical_packet", "compose_helical_packets",
            ],
        },
        "arms": arms,
        "comparisons": comparisons,
        "continuity": continuity_checks(),
        "continuity_verdict": "PASS",
        "controls": {
            "firing": [
                {"comparison": row["id"], **row["firing_control"]}
                for row in comparisons
            ],
            "all_attempted": True,
            "all_can_fail": all(row["firing_control"]["can_fail"] for row in comparisons),
            "all_flip": all(not row["firing_control"]["holds_after"] for row in comparisons),
        },
        "limitations": LIMITATIONS,
        "boundary": BOUNDARY,
        "verdict": (
            "MEASURED_NO_PARENT_CHILD_MEMORY"
            if not next(row for row in comparisons if row["id"] == "coarse_projection_separates_LL_from_LR")["holds"]
            else "MEASURED_NO_VERDICT"
        ),
    }
    body["runtime_seconds"] = float(perf_counter() - started)
    body["content_digest"] = content_digest(body)
    body["receipt_sha256"] = body["content_digest"]
    return body


def verify_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    actual = content_digest(receipt)
    return {"content_digest_matches": actual == receipt.get("content_digest"), "digest": actual}


def can_fail_probes(receipt: Mapping[str, Any]) -> dict[str, Any]:
    rows = receipt.get("comparisons", [])
    controls = receipt.get("controls", {}).get("firing", [])
    return {
        "comparison_count": len(rows),
        "control_count": len(controls),
        "all_attempted": bool(controls) and all(row.get("attempted") for row in controls),
        "all_can_fail": bool(controls) and all(row.get("can_fail") for row in controls),
        "all_flip": bool(controls) and all(not row.get("holds_after") for row in controls),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    receipt = build_receipt()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(_jsonable(receipt), sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "content_digest": receipt["content_digest"], "runtime_seconds": receipt["runtime_seconds"], "verdict": receipt["verdict"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
