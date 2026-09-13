#!/usr/bin/env python3
"""Audit the anchored block-local Feshbach receipt without assembling matrices."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(__file__).resolve()
PROTOCOL = ROOT / "computations/yang-mills-volume-block-local-feshbach-prereg.md"
PRIMARY_SOURCE = ROOT / "computations/verify_yang_mills_volume_block_local_feshbach.py"
ADAPTED_SOURCE = ROOT / "computations/verify_yang_mills_volume_adapted_feshbach.py"
ADAPTED_PROTOCOL = ROOT / "computations/yang-mills-volume-adapted-feshbach-prereg.md"
ADAPTED_PRIMARY_RECEIPT = ROOT / "runs/yang_mills_volume_adapted_feshbach/verification.json"
ADAPTED_INDEPENDENT_RECEIPT = ROOT / "runs/yang_mills_volume_adapted_feshbach/verification-independent.json"
VOLUME_BRIDGE_SOURCE = ROOT / "computations/verify_yang_mills_volume_feshbach_bridge.py"
EXACT_SOURCE = ROOT / "computations/verify_yang_mills_exact_block_spectrum.py"
LARGE_SOURCE = ROOT / "computations/verify_yang_mills_su2_larger_volume_hamiltonian.py"
SCIENTIFIC_PROTOCOL = ROOT / "computations/yang-mills-su2-larger-volume-hamiltonian-prereg.md"
RECOVERY_PROTOCOL = ROOT / "computations/yang-mills-su2-larger-volume-hamiltonian-recovery-prereg.md"
LARGE_RECEIPT = ROOT / "runs/yang_mills_su2_larger_volume_hamiltonian_recovery/verification.json"
PRIMARY = ROOT / "runs/yang_mills_volume_block_local_feshbach/verification.json"
DEFAULT_OUTPUT = ROOT / "runs/yang_mills_volume_block_local_feshbach/verification-independent.json"

COUPLINGS = ("1/64", "1/16", "1/4", "1")
EXPECTED_DIMENSIONS = {"small": 4, "large": 868}
RANK_TOLERANCE = 1.0e-10
TOLERANCE = 1.0e-10


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def close(actual: float, expected: float) -> bool:
    return abs(float(actual) - float(expected)) <= TOLERANCE * max(
        1.0, abs(float(actual)), abs(float(expected))
    )


def record_check(result: dict[str, Any], name: str, passed: bool, detail: Any) -> None:
    result["checks"].append({"name": name, "passed": bool(passed), "detail": detail})
    if not passed:
        result["failures"].append(name)


def rank_from_singular_values(values: list[float]) -> int:
    if not values or values[0] <= 0.0:
        return 0
    return sum(value > RANK_TOLERANCE * values[0] for value in values)


def expected_volume_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for coupling in COUPLINGS:
        small = next(row for row in rows if row["graph"] == "small" and row["coupling"] == coupling)
        large = next(row for row in rows if row["graph"] == "large" and row["coupling"] == coupling)
        output[coupling] = {
            "alpha_large_to_small": large["alpha_retained"] / small["alpha_retained"],
            "delta_large_to_small": large["delta_discarded"] / small["delta_discarded"],
            "beta_large_to_small": large["beta_coupling"] / small["beta_coupling"],
        }
    return output


def audit() -> dict[str, Any]:
    primary = json.loads(PRIMARY.read_text(encoding="utf-8"))
    result: dict[str, Any] = {
        "schema": "cassi.yang-mills.volume-block-local-feshbach.independent.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "protocol": {"path": PROTOCOL.relative_to(ROOT).as_posix(), "sha256": digest(PROTOCOL)},
            "source": {"path": SOURCE.relative_to(ROOT).as_posix(), "sha256": digest(SOURCE)},
            "primary_source": {"path": PRIMARY_SOURCE.relative_to(ROOT).as_posix(), "sha256": digest(PRIMARY_SOURCE)},
            "adapted_source": {"path": ADAPTED_SOURCE.relative_to(ROOT).as_posix(), "sha256": digest(ADAPTED_SOURCE)},
            "adapted_protocol": {"path": ADAPTED_PROTOCOL.relative_to(ROOT).as_posix(), "sha256": digest(ADAPTED_PROTOCOL)},
            "adapted_primary_receipt": {"path": ADAPTED_PRIMARY_RECEIPT.relative_to(ROOT).as_posix(), "sha256": digest(ADAPTED_PRIMARY_RECEIPT)},
            "adapted_independent_receipt": {"path": ADAPTED_INDEPENDENT_RECEIPT.relative_to(ROOT).as_posix(), "sha256": digest(ADAPTED_INDEPENDENT_RECEIPT)},
            "volume_bridge_source": {"path": VOLUME_BRIDGE_SOURCE.relative_to(ROOT).as_posix(), "sha256": digest(VOLUME_BRIDGE_SOURCE)},
            "exact_source": {"path": EXACT_SOURCE.relative_to(ROOT).as_posix(), "sha256": digest(EXACT_SOURCE)},
            "large_source": {"path": LARGE_SOURCE.relative_to(ROOT).as_posix(), "sha256": digest(LARGE_SOURCE)},
            "scientific_protocol": {"path": SCIENTIFIC_PROTOCOL.relative_to(ROOT).as_posix(), "sha256": digest(SCIENTIFIC_PROTOCOL)},
            "recovery_protocol": {"path": RECOVERY_PROTOCOL.relative_to(ROOT).as_posix(), "sha256": digest(RECOVERY_PROTOCOL)},
            "large_receipt": {"path": LARGE_RECEIPT.relative_to(ROOT).as_posix(), "sha256": digest(LARGE_RECEIPT)},
            "primary_receipt": {"path": PRIMARY.relative_to(ROOT).as_posix(), "sha256": digest(PRIMARY)},
        },
        "checks": [],
        "failures": [],
    }
    source_record = primary.get("sources", {})
    record_check(result, "primary status and complete checks",
                 primary.get("status") == "PASS"
                 and primary.get("failures") == []
                 and primary.get("classification") == "SUPPORTS_FINITE_VOLUME_ANCHORED_BLOCK_FAMILY"
                 and primary.get("summary", {}).get("rows") == 8
                 and primary.get("summary", {}).get("checks") == primary.get("summary", {}).get("passing_checks")
                 and primary.get("summary", {}).get("positive_certified_rows") == 8,
                 {"status": primary.get("status"), "classification": primary.get("classification"), "summary": primary.get("summary")})
    expected_bindings = {
        "protocol": PROTOCOL,
        "source": PRIMARY_SOURCE,
        "independent_source": SOURCE,
        "adapted_source": ADAPTED_SOURCE,
        "adapted_protocol": ADAPTED_PROTOCOL,
        "adapted_primary_receipt": ADAPTED_PRIMARY_RECEIPT,
        "adapted_independent_receipt": ADAPTED_INDEPENDENT_RECEIPT,
        "volume_bridge_source": VOLUME_BRIDGE_SOURCE,
        "exact_source": EXACT_SOURCE,
        "large_source": LARGE_SOURCE,
        "scientific_protocol": SCIENTIFIC_PROTOCOL,
        "recovery_protocol": RECOVERY_PROTOCOL,
        "large_receipt": LARGE_RECEIPT,
    }
    for key, path in expected_bindings.items():
        record_check(result, f"primary {key} binding",
                     source_record.get(key, {}).get("sha256") == digest(path),
                     {"recorded": source_record.get(key, {}).get("sha256"), "computed": digest(path)})
    record_check(result, "fixed anchored block schedule",
                 primary.get("schedule") == {
                     "graphs": EXPECTED_DIMENSIONS,
                     "retained_family": "vacuum plus first source-order plaquette",
                     "plaquette_ordinal": 0,
                     "weight_rule": "equal unit weight before orthonormalization",
                     "couplings": list(COUPLINGS),
                     "rows": 8,
                 }, primary.get("schedule"))
    basis = primary.get("source_basis", {})
    for graph in EXPECTED_DIMENSIONS:
        local = basis.get(graph, {}).get("local", {})
        singular = [float(value) for value in local.get("singular_values", [])]
        record_check(result, f"{graph} anchored block source rank and singular values",
                     local.get("column_count") == 2
                     and local.get("plaquette_ordinal") == 0
                     and local.get("rank") == rank_from_singular_values(singular)
                     and local.get("rank") == 2
                     and all(singular[index] + TOLERANCE >= singular[index + 1]
                             for index in range(len(singular) - 1)),
                     {"local": local})
    rows = primary.get("rows", [])
    expected_pairs = {(graph, coupling) for graph in EXPECTED_DIMENSIONS for coupling in COUPLINGS}
    observed_pairs = {(str(row.get("graph")), str(row.get("coupling"))) for row in rows}
    record_check(result, "row schedule and dimensions",
                 len(rows) == 8 and observed_pairs == expected_pairs
                 and all(row.get("full_dimension") == EXPECTED_DIMENSIONS[row["graph"]] for row in rows),
                 {"rows": len(rows), "observed": sorted(observed_pairs)})
    positive_rows = []
    for row in rows:
        graph = str(row["graph"])
        coupling = str(row["coupling"])
        label = f"graph={graph},x={coupling}"
        source_rank = int(basis[graph]["local"]["rank"])
        alpha = float(row["alpha_retained"])
        delta = float(row["delta_discarded"])
        beta = float(row["beta_coupling"])
        lam = float(row["lambda_test"])
        gap = float(row["finite_gap"])
        resolvent_bound = 1.0 / (delta - lam)
        self_energy_bound = beta * beta / (delta - lam)
        phi_test = alpha - lam - self_energy_bound
        phi_zero = alpha - beta * beta / delta
        root = None
        if phi_zero > 0.0:
            root = 0.5 * (alpha + delta - math.sqrt((alpha - delta) ** 2 + 4.0 * beta * beta))
            positive_rows.append(row)
        source_singular = [float(value) for value in row.get("source_singular_values", [])]
        projected_singular = [float(value) for value in row.get("projected_source_singular_values", [])]
        record_check(result, f"{label}:rank and frame arithmetic",
                     int(row["retained_source_rank"]) == source_rank
                     and int(row["retained_dimension"]) > 0
                     and int(row["retained_dimension"]) <= source_rank
                     and int(row["discarded_dimension"]) == int(row["full_dimension"]) - int(row["retained_dimension"]) - 1
                     and rank_from_singular_values(source_singular) == source_rank
                     and rank_from_singular_values(projected_singular) == int(row["retained_dimension"]),
                     {"source_rank": row["retained_source_rank"], "retained_rank": row["retained_dimension"], "discarded_rank": row["discarded_dimension"]})
        record_check(result, f"{label}:resolvent arithmetic",
                     float(row["resolvent_norm"]) <= resolvent_bound * (1.0 + TOLERANCE),
                     {"actual": row["resolvent_norm"], "recomputed_bound": resolvent_bound})
        record_check(result, f"{label}:self-energy arithmetic",
                     float(row["self_energy_norm"]) <= self_energy_bound * (1.0 + TOLERANCE),
                     {"actual": row["self_energy_norm"], "recomputed_bound": self_energy_bound})
        record_check(result, f"{label}:Schur scalar reconstruction",
                     close(row["phi_test"], phi_test) and close(row["phi_zero"], phi_zero),
                     {"recorded_phi_test": row["phi_test"], "recomputed_phi_test": phi_test, "recorded_phi_zero": row["phi_zero"], "recomputed_phi_zero": phi_zero})
        record_check(result, f"{label}:root reconstruction",
                     row["certified_gap_lower_bound"] is not None and root is not None
                     and close(row["certified_gap_lower_bound"], root),
                     {"recorded": row["certified_gap_lower_bound"], "recomputed": root})
        expected_ratio = root / gap if root is not None else None
        record_check(result, f"{label}:root-to-gap reconstruction",
                     row["root_to_gap_ratio"] is not None and expected_ratio is not None
                     and close(row["root_to_gap_ratio"], expected_ratio),
                     {"recorded": row["root_to_gap_ratio"], "recomputed": expected_ratio})
        record_check(result, f"{label}:gap ordering",
                     root is not None and gap + TOLERANCE >= root,
                     {"gap": gap, "root": root})
        record_check(result, f"{label}:tail-floor guard",
                     row["tail_floor_resolvent_defined"] is False and float(row["tail_floor_distance"]) == 0.0,
                     {"distance": row["tail_floor_distance"], "resolvent_defined": row["tail_floor_resolvent_defined"]})
    record_check(result, "scientific classification arithmetic",
                 primary.get("classification") == "SUPPORTS_FINITE_VOLUME_ANCHORED_BLOCK_FAMILY"
                 and len(positive_rows) == len(rows),
                 {"recorded": primary.get("classification"), "positive_rows": len(positive_rows), "rows": len(rows)})
    record_check(result, "row schedule and grouped counts",
                 len(rows) == 8 and all(sum(1 for row in rows if row["graph"] == graph) == 4 for graph in EXPECTED_DIMENSIONS),
                 {"rows": len(rows)})
    expected_volume = expected_volume_summary(rows)
    recorded_volume = primary.get("volume_summary", {})
    volume_matches = all(
        close(recorded_volume.get(coupling, {}).get(key), expected_volume[coupling][key])
        for coupling in COUPLINGS
        for key in ("alpha_large_to_small", "delta_large_to_small", "beta_large_to_small")
    )
    record_check(result, "volume ratio summary arithmetic", volume_matches,
                 {"recorded": recorded_volume, "recomputed": expected_volume})
    result["status"] = "PASS" if not result["failures"] else "FAIL"
    result["classification"] = "ARITHMETIC_AND_BINDING_AUDIT_ONLY"
    result["scope"] = {
        "matrix_reassembly": "NOT_PERFORMED",
        "finite_resolvent_arithmetic": "RECONSTRUCTED",
        "translation_uniformity": "UNRESOLVED",
        "volume_uniform_bound": "UNRESOLVED",
        "continuum_recovery": "UNRESOLVED",
        "continuum_mass_gap": "UNRESOLVED",
    }
    result["summary"] = {
        "checks": len(result["checks"]),
        "passing_checks": sum(1 for row in result["checks"] if row["passed"]),
        "rows_reconstructed": len(rows),
    }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing receipt: {output}")
    required = (PROTOCOL, SOURCE, PRIMARY_SOURCE, ADAPTED_SOURCE, ADAPTED_PROTOCOL,
                ADAPTED_PRIMARY_RECEIPT, ADAPTED_INDEPENDENT_RECEIPT, VOLUME_BRIDGE_SOURCE,
                EXACT_SOURCE, LARGE_SOURCE, SCIENTIFIC_PROTOCOL, RECOVERY_PROTOCOL,
                LARGE_RECEIPT, PRIMARY)
    if not all(path.exists() for path in required):
        raise FileNotFoundError("protocol, sources, adapted receipts, volume protocols, primary or receipt is missing")
    result = audit()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(f"Receipt: {output}")
    print(json.dumps({key: result[key] for key in ("status", "classification", "summary", "failures")}, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
