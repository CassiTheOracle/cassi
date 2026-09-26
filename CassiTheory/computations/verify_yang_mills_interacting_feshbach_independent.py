#!/usr/bin/env python3
"""Audit the finite Feshbach receipt without importing its primary verifier.

This checker reconstructs the scalar resolvent, self-energy, Schur-root and
source-binding decisions from the primary receipt. It is an arithmetic and
provenance audit, not a second assembly of the SU(2) Hamiltonian.
"""
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
PROTOCOL = ROOT / "computations/yang-mills-interacting-feshbach-prereg.md"
PRIMARY_SOURCE = ROOT / "computations/verify_yang_mills_interacting_feshbach.py"
REFERENCE = ROOT / "computations/verify_yang_mills_exact_block_spectrum.py"
PRIMARY = ROOT / "runs/yang_mills_interacting_feshbach/verification.json"
DEFAULT_OUTPUT = ROOT / "runs/yang_mills_interacting_feshbach/verification-independent.json"
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


def audit() -> dict[str, Any]:
    primary = json.loads(PRIMARY.read_text(encoding="utf-8"))
    result: dict[str, Any] = {
        "schema": "cassi.yang-mills.interacting-feshbach.independent.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "protocol": {"path": PROTOCOL.relative_to(ROOT).as_posix(), "sha256": digest(PROTOCOL)},
            "primary_source": {"path": PRIMARY_SOURCE.relative_to(ROOT).as_posix(), "sha256": digest(PRIMARY_SOURCE)},
            "reference": {"path": REFERENCE.relative_to(ROOT).as_posix(), "sha256": digest(REFERENCE)},
            "primary_receipt": {"path": PRIMARY.relative_to(ROOT).as_posix(), "sha256": digest(PRIMARY)},
        },
        "checks": [],
        "failures": [],
    }
    source_record = primary["sources"]
    record_check(result, "primary status and complete checks",
                 primary.get("status") == "PASS" and primary.get("failures") == []
                 and primary.get("summary", {}).get("checks") == 38
                 and primary.get("summary", {}).get("passing_checks") == 38,
                 {"status": primary.get("status"), "summary": primary.get("summary")})
    record_check(result, "primary protocol binding",
                 source_record["protocol"]["sha256"] == digest(PROTOCOL),
                 {"recorded": source_record["protocol"]["sha256"], "computed": digest(PROTOCOL)})
    record_check(result, "primary source binding",
                 source_record["source"]["sha256"] == digest(PRIMARY_SOURCE),
                 {"recorded": source_record["source"]["sha256"], "computed": digest(PRIMARY_SOURCE)})
    record_check(result, "primary reference binding",
                 source_record["reference"]["sha256"] == digest(REFERENCE),
                 {"recorded": source_record["reference"]["sha256"], "computed": digest(REFERENCE)})
    record_check(result, "fixed source dimensions and schedule",
                 primary.get("schedule") == {
                     "retained_cutoff": 1,
                     "full_cutoff": 3,
                     "couplings": ["1/4", "1", "4", "16"],
                 }, primary.get("schedule"))

    rows = primary.get("rows", [])
    for row in rows:
        label = row["coupling"]
        alpha = float(row["alpha_retained"])
        delta = float(row["delta_discarded"])
        beta = float(row["beta_coupling"])
        lam = float(row["lambda_test"])
        resolvent_bound = 1.0 / (delta - lam)
        self_energy_bound = beta * beta / (delta - lam)
        phi_test = alpha - lam - self_energy_bound
        phi_zero = alpha - beta * beta / delta
        discriminant = (alpha - delta) ** 2 + 4.0 * beta * beta
        root = 0.5 * (alpha + delta - math.sqrt(discriminant)) if phi_zero > 0.0 else None
        prefix = f"x={label}"
        record_check(result, f"{prefix}:dimensions and ranks",
                     row["full_dimension"] == 23 and row["retained_dimension"] == 4
                     and row["discarded_dimension"] == 18,
                     {key: row[key] for key in ("full_dimension", "retained_dimension", "discarded_dimension")})
        record_check(result, f"{prefix}:resolvent inequality",
                     float(row["resolvent_norm"]) <= resolvent_bound * (1.0 + TOLERANCE),
                     {"actual": row["resolvent_norm"], "recomputed_bound": resolvent_bound})
        record_check(result, f"{prefix}:self-energy inequality",
                     float(row["self_energy_norm"]) <= self_energy_bound * (1.0 + TOLERANCE),
                     {"actual": row["self_energy_norm"], "recomputed_bound": self_energy_bound})
        record_check(result, f"{prefix}:Schur scalar reconstruction",
                     close(row["phi_test"], phi_test) and close(row["phi_zero"], phi_zero),
                     {"recorded_phi_test": row["phi_test"], "recomputed_phi_test": phi_test,
                      "recorded_phi_zero": row["phi_zero"], "recomputed_phi_zero": phi_zero})
        record_check(result, f"{prefix}:certified root reconstruction",
                     (root is None and row["certified_gap_lower_bound"] is None)
                     or (root is not None and row["certified_gap_lower_bound"] is not None
                         and close(row["certified_gap_lower_bound"], root)),
                     {"recorded": row["certified_gap_lower_bound"], "recomputed": root})
        record_check(result, f"{prefix}:tail-floor guard",
                     row["tail_floor_resolvent_defined"] is False
                     and float(row["tail_floor_distance"]) == 0.0,
                     {"distance": row["tail_floor_distance"],
                      "resolvent_defined": row["tail_floor_resolvent_defined"]})

    result["status"] = "PASS" if not result["failures"] else "FAIL"
    result["classification"] = "ARITHMETIC_AND_BINDING_AUDIT_ONLY"
    result["scope"] = {
        "matrix_reassembly": "NOT_PERFORMED",
        "finite_resolvent_arithmetic": "RECONSTRUCTED",
        "uniform_spacing_bound": "UNRESOLVED",
        "uniform_volume_bound": "UNRESOLVED",
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
    if not PRIMARY.exists():
        raise FileNotFoundError(f"primary receipt is missing: {PRIMARY}")
    result = audit()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Receipt: {output}")
    print(json.dumps({key: result[key] for key in ("status", "classification", "summary", "failures")}, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
