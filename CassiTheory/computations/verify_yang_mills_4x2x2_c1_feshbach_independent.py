#!/usr/bin/env python3
"""Independent arithmetic and source-binding audit for the 4x2x2 C=1 screen."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(__file__).resolve()
PRIMARY_SOURCE = ROOT / "computations/verify_yang_mills_4x2x2_c1_feshbach.py"
PROTOCOL = ROOT / "computations/yang-mills-4x2x2-c1-feshbach-prereg.md"
EXACT_SOURCE = ROOT / "computations/verify_yang_mills_exact_block_spectrum.py"
REFERENCE_SOURCE = ROOT / "computations/verify_yang_mills_su2_larger_volume_hamiltonian.py"
REFERENCE_PROTOCOL = ROOT / "computations/yang-mills-su2-larger-volume-hamiltonian-recovery-prereg.md"
DEFAULT_PRIMARY = ROOT / "runs/yang_mills_4x2x2_c1_feshbach/verification.json"
DEFAULT_OUTPUT = ROOT / "runs/yang_mills_4x2x2_c1_feshbach/verification-independent.json"

CUTOFF = 1
EXPECTED_DIMENSION = 25676
COUPLINGS = ("1/64", "1/16", "1/4", "1")
PLAQUETTE_NAMES = (
    "xy_z0_0", "xy_z0_1", "xy_z0_2", "xy_z1_0", "xy_z1_1", "xy_z1_2",
    "xz_y0_0", "xz_y0_1", "xz_y0_2", "xz_y1_0", "xz_y1_1", "xz_y1_2",
    "yz_x0", "yz_x1", "yz_x2", "yz_x3",
)
ROOT_TOLERANCE = 1.0e-8
FLOAT_TOLERANCE = 1.0e-10


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def close(left: Any, right: Any, tolerance: float = FLOAT_TOLERANCE) -> bool:
    if left is None or right is None:
        return left is None and right is None
    return math.isclose(float(left), float(right), rel_tol=tolerance, abs_tol=tolerance)


def check(name: str, passed: bool, **detail: Any) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), **detail}


def valid(a: int, b: int, c: int) -> bool:
    return (a + b + c) % 2 == 0 and abs(a - b) <= c <= a + b


def state_inventory() -> tuple[int, str, list[list[int]], list[int], list[int], list[int], list[int]]:
    coords = [(x, y, z) for x in range(4) for y in range(2) for z in range(2)]
    vertex = {coord: index for index, coord in enumerate(coords)}
    tails: list[int] = []
    heads: list[int] = []
    axes: list[int] = []
    edge_key: dict[tuple[str, int, int, int], int] = {}
    for x in range(3):
        for y in range(2):
            for z in range(2):
                edge_key[("x", x, y, z)] = len(tails)
                tails.append(vertex[(x, y, z)])
                heads.append(vertex[(x + 1, y, z)])
                axes.append(0)
    for x in range(4):
        for y in range(1):
            for z in range(2):
                edge_key[("y", x, y, z)] = len(tails)
                tails.append(vertex[(x, y, z)])
                heads.append(vertex[(x, y + 1, z)])
                axes.append(1)
    for x in range(4):
        for y in range(2):
            for z in range(1):
                edge_key[("z", x, y, z)] = len(tails)
                tails.append(vertex[(x, y, z)])
                heads.append(vertex[(x, y, z + 1)])
                axes.append(2)
    incident: list[list[tuple[int, int, int]]] = [[] for _ in coords]
    for edge, (tail, head, axis) in enumerate(zip(tails, heads, axes)):
        incident[tail].append((axis, 0, edge))
        incident[head].append((axis, 1, edge))
    legs = [tuple((edge, +1 if outgoing == 0 else -1, axis) for axis, outgoing, edge in sorted(items)) for items in incident]
    four = [index for index, items in enumerate(legs) if len(items) == 4]
    left = [
        edge for edge, (tail, head) in enumerate(zip(tails, heads))
        if min(coords[tail][0], coords[head][0]) == 0 and max(coords[tail][0], coords[head][0]) <= 1
    ]
    right = [
        edge for edge, (tail, head) in enumerate(zip(tails, heads))
        if min(coords[tail][0], coords[head][0]) >= 2 and max(coords[tail][0], coords[head][0]) == 3
    ]
    middle = [edge for edge in range(len(tails)) if edge not in left + right]

    def boundary(ids: list[int], vertices: list[int]) -> list[tuple[int, ...]]:
        output: list[tuple[int, ...]] = []
        for values in itertools.product(range(CUTOFF + 1), repeat=len(ids)):
            mapping = dict(zip(ids, values))
            if all(valid(*(mapping[edge] for edge, _, _ in legs[v])) for v in vertices):
                output.append(tuple(values))
        return output

    left_values = boundary(left, [v for v, coord in enumerate(coords) if coord[0] == 0])
    right_values = boundary(right, [v for v, coord in enumerate(coords) if coord[0] == 3])
    states: list[tuple[int, ...]] = []
    for middle_values in itertools.product(range(CUTOFF + 1), repeat=len(middle)):
        middle_map = dict(zip(middle, middle_values))
        for left_values_row in left_values:
            left_map = dict(zip(left, left_values_row))
            for right_values_row in right_values:
                edge_map = left_map | dict(zip(right, right_values_row)) | middle_map
                edges = tuple(edge_map[index] for index in range(len(tails)))
                channels: list[tuple[int, ...]] = []
                valid_state = True
                for v in four:
                    a, b, c, d = (edges[edge] for edge, _, _ in legs[v])
                    choices = tuple(channel for channel in range(abs(a - b), a + b + 1, 2) if valid(channel, c, d))
                    if not choices:
                        valid_state = False
                        break
                    channels.append(choices)
                if valid_state:
                    states.extend(edges + tuple(values) for values in itertools.product(*channels))
    states.sort()
    encoded = json.dumps(states, separators=(",", ":")).encode("utf-8")
    return len(states), hashlib.sha256(encoded).hexdigest(), [list(item) for item in states[:3]], tails, heads, axes, four


def expected_row_root(row: dict[str, Any]) -> float | None:
    alpha = float(row["alpha_retained"])
    delta = float(row["delta_oracle"])
    beta = float(row["beta_coupling"])
    phi_zero = alpha - beta * beta / delta
    if phi_zero <= 0.0:
        return None
    return 0.5 * (alpha + delta - math.sqrt((alpha - delta) ** 2 + 4.0 * beta * beta))


def run(primary_path: Path, output: Path) -> dict[str, Any]:
    primary = json.loads(primary_path.read_text(encoding="utf-8"))
    checks: list[dict[str, Any]] = []
    required_paths = {
        "protocol": PROTOCOL,
        "source": PRIMARY_SOURCE,
        "independent_source": SOURCE,
        "exact_source": EXACT_SOURCE,
        "reference_source": REFERENCE_SOURCE,
        "reference_protocol": REFERENCE_PROTOCOL,
    }
    recorded_hashes = primary.get("source_hashes", {})
    for key, path in required_paths.items():
        checks.append(check(f"source_hash_{key}", recorded_hashes.get(key) == sha256(path), recorded=recorded_hashes.get(key), recomputed=sha256(path)))
    dimension, state_digest, _, tails, heads, axes, four = state_inventory()
    graph = primary.get("graph", {})
    checks.extend([
        check("graph_shape", graph.get("shape") == [4, 2, 2], observed=graph.get("shape")),
        check("graph_vertices", len(graph.get("vertices", [])) == 16),
        check("graph_links", len(graph.get("tails", [])) == 28 and len(graph.get("heads", [])) == 28),
        check("graph_edge_binding", graph.get("tails") == tails and graph.get("heads") == heads and graph.get("axes") == axes),
        check("four_valence_binding", graph.get("four_valence_vertices") == four),
        check("cutoff_binding", graph.get("cutoff") == CUTOFF),
        check("basis_dimension", dimension == EXPECTED_DIMENSION and primary.get("basis", {}).get("dimension") == dimension, observed=dimension),
        check("basis_hash", primary.get("basis", {}).get("state_sha256") == state_digest, observed=primary.get("basis", {}).get("state_sha256"), recomputed=state_digest),
    ])
    plaquettes = primary.get("plaquettes", [])
    checks.append(check("plaquette_schedule", [item.get("name") for item in plaquettes] == list(PLAQUETTE_NAMES)))
    rows = primary.get("rows", [])
    expected_pairs = {(name, coupling) for name in PLAQUETTE_NAMES for coupling in COUPLINGS}
    observed_pairs = {(row.get("plaquette_name"), row.get("coupling")) for row in rows}
    checks.append(check("row_schedule", len(rows) == 64 and observed_pairs == expected_pairs, observed_count=len(observed_pairs)))
    for row in rows:
        prefix = f"{row.get('plaquette_name')}:x={row.get('coupling')}"
        checks.extend([
            check(
                f"{prefix}:dimension",
                row.get("full_dimension") == EXPECTED_DIMENSION,
            ),
            check(
                f"{prefix}:rank",
                row.get("retained_source_rank") == 2 and row.get("retained_dimension") == 2,
            ),
            check(
                f"{prefix}:oracle_delta",
                close(row.get("delta_oracle"), row.get("finite_gap")),
            ),
            check(
                f"{prefix}:phi_zero",
                close(
                    row.get("phi_zero"),
                    float(row["alpha_retained"]) - float(row["beta_coupling"]) ** 2 / float(row["delta_oracle"]),
                ),
            ),
            check(
                f"{prefix}:phi_test",
                close(
                    row.get("phi_test"),
                    float(row["alpha_retained"])
                    - float(row["lambda_test"])
                    - float(row["beta_coupling"]) ** 2
                    / (float(row["delta_oracle"]) - float(row["lambda_test"])),
                ),
            ),
            check(
                f"{prefix}:root_formula",
                close(row.get("conditional_gap_lower_bound"), expected_row_root(row)),
            ),
            check(
                f"{prefix}:root_ratio",
                row.get("conditional_gap_lower_bound") is None
                or close(
                    row.get("root_to_gap_ratio"),
                    float(row["conditional_gap_lower_bound"]) / float(row["finite_gap"]),
                ),
            ),
            check(
                f"{prefix}:root_bound",
                row.get("conditional_gap_lower_bound") is None
                or float(row["conditional_gap_lower_bound"]) <= float(row["finite_gap"]) + ROOT_TOLERANCE,
            ),
        ])
    expected_summary: dict[str, Any] = {}
    for name in PLAQUETTE_NAMES:
        family = [row for row in rows if row.get("plaquette_name") == name]
        positive = [row for row in family if row.get("conditional_gap_lower_bound") is not None and float(row["conditional_gap_lower_bound"]) > 0.0]
        expected_summary[name] = {
            "rows": len(family),
            "positive_roots": len(positive),
            "min_conditional_gap_lower_bound": min((float(row["conditional_gap_lower_bound"]) for row in positive), default=None),
            "max_beta": max((float(row["beta_coupling"]) for row in family), default=None),
            "max_root_to_gap_ratio": max((float(row["root_to_gap_ratio"]) for row in positive), default=None),
        }
    recorded_summary = primary.get("per_plaquette", {})
    summary_ok = True
    for name, expected in expected_summary.items():
        actual = recorded_summary.get(name, {})
        summary_ok = summary_ok and actual.get("rows") == expected["rows"] and actual.get("positive_roots") == expected["positive_roots"]
        for key in ("min_conditional_gap_lower_bound", "max_beta", "max_root_to_gap_ratio"):
            summary_ok = summary_ok and close(actual.get(key), expected[key])
    checks.append(check("per_plaquette_summary", summary_ok))
    primary_checks = primary.get("checks", [])
    checks.append(check(
        "primary_check_accounting",
        primary.get("checks_passed") == sum(bool(item.get("passed")) for item in primary_checks)
        and primary.get("checks_total") == len(primary_checks)
        and primary.get("checks_total", 0) > 0,
    ))
    positive_count = sum(1 for row in rows if row.get("conditional_gap_lower_bound") is not None and float(row["conditional_gap_lower_bound"]) > 0.0)
    expected_classification = (
        "SUPPORTS_FINITE_4X2X2_C1_TRANSLATED_FAMILY"
        if primary.get("status") == "PASS" and primary.get("checks_passed") == primary.get("checks_total") and positive_count == len(rows)
        else "NO_POSITIVE_4X2X2_C1_TRANSLATED_FAMILY"
        if primary.get("status") == "PASS" and primary.get("checks_passed") == primary.get("checks_total")
        else "INCONCLUSIVE"
    )
    checks.append(check("classification_recomputed", primary.get("classification") == expected_classification, recorded=primary.get("classification"), recomputed=expected_classification))
    passed = sum(item["passed"] for item in checks)
    record = {
        "schema": "cassi.yang-mills.4x2x2-c1-feshbach-independent.v1",
        "status": "PASS" if passed == len(checks) else "FAIL",
        "classification": "ARITHMETIC_AND_BINDING_AUDIT_ONLY",
        "primary_receipt": primary_path.relative_to(ROOT).as_posix(),
        "source": SOURCE.relative_to(ROOT).as_posix(),
        "checks": checks,
        "checks_passed": passed,
        "checks_total": len(checks),
        "observed_primary_classification": primary.get("classification"),
        "positive_conditional_rows": positive_count,
        "scope": "independent arithmetic, graph-inventory and source-binding audit; no sparse Hamiltonian assembly",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing receipt: {output}")
    output.write_text(json.dumps(record, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary", type=Path, default=DEFAULT_PRIMARY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    record = run(args.primary.resolve(), args.output.resolve())
    print(json.dumps({key: record[key] for key in ("status", "classification", "checks_passed", "checks_total", "positive_conditional_rows")}, indent=2))
    return 0 if record["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
