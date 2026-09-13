#!/usr/bin/env python3
"""Audit the volume-adapted Feshbach receipt without assembling either matrix."""
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
PROTOCOL = ROOT / "computations/yang-mills-volume-adapted-feshbach-prereg.md"
PRIMARY_SOURCE = ROOT / "computations/verify_yang_mills_volume_adapted_feshbach.py"
VOLUME_BRIDGE_SOURCE = ROOT / "computations/verify_yang_mills_volume_feshbach_bridge.py"
EXACT_SOURCE = ROOT / "computations/verify_yang_mills_exact_block_spectrum.py"
LARGE_SOURCE = ROOT / "computations/verify_yang_mills_su2_larger_volume_hamiltonian.py"
SCIENTIFIC_PROTOCOL = ROOT / "computations/yang-mills-su2-larger-volume-hamiltonian-prereg.md"
RECOVERY_PROTOCOL = ROOT / "computations/yang-mills-su2-larger-volume-hamiltonian-recovery-prereg.md"
LARGE_RECEIPT = ROOT / "runs/yang_mills_su2_larger_volume_hamiltonian_recovery/verification.json"
PRIMARY = ROOT / "runs/yang_mills_volume_adapted_feshbach/verification.json"
DEFAULT_OUTPUT = ROOT / "runs/yang_mills_volume_adapted_feshbach/verification-independent.json"

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
        values = {
            "alpha_large_to_small": (large.get("alpha_retained"), small.get("alpha_retained")),
            "delta_large_to_small": (large.get("delta_discarded"), small.get("delta_discarded")),
            "beta_large_to_small": (large.get("beta_coupling"), small.get("beta_coupling")),
        }
        output[coupling] = {
            key: None if numerator is None or denominator is None else numerator / denominator
            for key, (numerator, denominator) in values.items()
        }
    return output


def audit() -> dict[str, Any]:
    primary = json.loads(PRIMARY.read_text(encoding="utf-8"))
    result: dict[str, Any] = {
        "schema": "cassi.yang-mills.volume-adapted-feshbach.independent.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "protocol": {"path": PROTOCOL.relative_to(ROOT).as_posix(), "sha256": digest(PROTOCOL)},
            "source": {"path": SOURCE.relative_to(ROOT).as_posix(), "sha256": digest(SOURCE)},
            "primary_source": {"path": PRIMARY_SOURCE.relative_to(ROOT).as_posix(), "sha256": digest(PRIMARY_SOURCE)},
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
    record_check(
        result,
        "primary status and complete checks",
        primary.get("status") in {"PASS", "FAIL"}
        and primary.get("summary", {}).get("rows") == 8
        and primary.get("summary", {}).get("checks", 0) >= primary.get("summary", {}).get("passing_checks", -1)
        and (
            (primary.get("status") == "PASS"
             and primary.get("failures") == []
             and primary.get("summary", {}).get("positive_certified_rows") == 8)
            or (primary.get("status") == "FAIL"
                and primary.get("classification") == "INCONCLUSIVE"
                and bool(primary.get("failures"))
                and primary.get("summary", {}).get("positive_certified_rows", 0) < 8)
        ),
        {"status": primary.get("status"), "summary": primary.get("summary")},
    )
    expected_bindings = {
        "protocol": PROTOCOL,
        "source": PRIMARY_SOURCE,
        "independent_source": SOURCE,
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
    record_check(
        result,
        "fixed volume-adapted schedule",
        primary.get("schedule") == {
            "graphs": EXPECTED_DIMENSIONS,
            "retained_family": "vacuum plus every fundamental plaquette action",
            "couplings": list(COUPLINGS),
            "rows": 8,
        },
        primary.get("schedule"),
    )
    basis = primary.get("source_basis", {})
    for graph, plaquettes in (("small", 2), ("large", 11)):
        local = basis.get(graph, {}).get("local", {})
        singular = local.get("singular_values", [])
        record_check(
            result,
            f"{graph} retained source rank and singular values",
            local.get("plaquettes") == plaquettes
            and local.get("column_count") == plaquettes + 1
            and local.get("rank") == rank_from_singular_values(singular)
            and local.get("rank", 0) > 0
            and all(float(singular[index]) + TOLERANCE >= float(singular[index + 1])
                    for index in range(len(singular) - 1)),
            {"local": local},
        )
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
        if row.get("failure") == "empty_discarded_sector":
            undefined_fields = (
                "alpha_retained", "delta_discarded", "beta_coupling",
                "lambda_test", "resolvent_norm", "self_energy_norm",
                "phi_test", "phi_zero", "certified_gap_lower_bound",
            )
            record_check(
                result,
                f"{label}:expected empty discarded sector",
                int(row.get("discarded_dimension", -1)) == 0
                and int(row.get("retained_dimension", -1)) == int(row.get("full_dimension", 0)) - 1
                and all(row.get(field) is None for field in undefined_fields),
                {"failure": row.get("failure"), "discarded_dimension": row.get("discarded_dimension"),
                 "undefined_fields": {field: row.get(field) for field in undefined_fields}},
            )
            continue
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
                     {"source_rank": row["retained_source_rank"], "retained_rank": row["retained_dimension"],
                      "discarded_rank": row["discarded_dimension"]})
        record_check(result, f"{label}:resolvent arithmetic",
                     float(row["resolvent_norm"]) <= resolvent_bound * (1.0 + TOLERANCE),
                     {"actual": row["resolvent_norm"], "recomputed_bound": resolvent_bound})
        record_check(result, f"{label}:self-energy arithmetic",
                     float(row["self_energy_norm"]) <= self_energy_bound * (1.0 + TOLERANCE),
                     {"actual": row["self_energy_norm"], "recomputed_bound": self_energy_bound})
        record_check(result, f"{label}:Schur scalar reconstruction",
                     close(row["phi_test"], phi_test) and close(row["phi_zero"], phi_zero),
                     {"recorded_phi_test": row["phi_test"], "recomputed_phi_test": phi_test,
                      "recorded_phi_zero": row["phi_zero"], "recomputed_phi_zero": phi_zero})
        record_check(result, f"{label}:root reconstruction",
                     (root is None and row["certified_gap_lower_bound"] is None)
                     or (root is not None and row["certified_gap_lower_bound"] is not None
                         and close(row["certified_gap_lower_bound"], root)),
                     {"recorded": row["certified_gap_lower_bound"], "recomputed": root})
        expected_ratio = None if root is None else root / gap
        record_check(result, f"{label}:root-to-gap reconstruction",
                     (expected_ratio is None and row["root_to_gap_ratio"] is None)
                     or (expected_ratio is not None and close(row["root_to_gap_ratio"], expected_ratio)),
                     {"recorded": row["root_to_gap_ratio"], "recomputed": expected_ratio})
        record_check(result, f"{label}:gap ordering",
                     root is None or gap + TOLERANCE >= root,
                     {"gap": gap, "root": root})
        record_check(result, f"{label}:tail-floor guard",
                     row["tail_floor_resolvent_defined"] is False
                     and float(row["tail_floor_distance"]) == 0.0,
                     {"distance": row["tail_floor_distance"], "resolvent_defined": row["tail_floor_resolvent_defined"]})
    if primary.get("status") != "PASS":
        expected_classification = "INCONCLUSIVE"
    elif len(positive_rows) == len(rows):
        expected_classification = "SUPPORTS_FINITE_VOLUME_VOLUME_ADAPTED_FAMILY"
    else:
        expected_classification = "NO_POSITIVE_VOLUME_ADAPTED_FAMILY"
    record_check(result, "scientific classification arithmetic",
                 primary.get("classification") == expected_classification,
                 {"recorded": primary.get("classification"), "recomputed": expected_classification})
    record_check(result, "row schedule and grouped counts",
                 len(rows) == 8 and all(sum(1 for row in rows if row["graph"] == graph) == 4 for graph in EXPECTED_DIMENSIONS),
                 {"rows": len(rows)})
    expected_volume = expected_volume_summary(rows)
    recorded_volume = primary.get("volume_summary", {})
    volume_matches = all(
        (
            expected_volume[coupling][key] is None
            and recorded_volume.get(coupling, {}).get(key) is None
        )
        or (
            expected_volume[coupling][key] is not None
            and recorded_volume.get(coupling, {}).get(key) is not None
            and close(recorded_volume[coupling][key], expected_volume[coupling][key])
        )
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
    required = (PROTOCOL, SOURCE, PRIMARY_SOURCE, VOLUME_BRIDGE_SOURCE, EXACT_SOURCE, LARGE_SOURCE, SCIENTIFIC_PROTOCOL, RECOVERY_PROTOCOL, LARGE_RECEIPT, PRIMARY)
    if not all(path.exists() for path in required):
        raise FileNotFoundError("protocol, sources, volume protocols, primary or receipt is missing")
    result = audit()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Receipt: {output}")
    print(json.dumps({key: result[key] for key in ("status", "classification", "summary", "failures")}, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
