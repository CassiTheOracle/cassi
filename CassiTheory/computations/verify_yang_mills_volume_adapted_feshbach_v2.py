#!/usr/bin/env python3
"""Measure the pre-registered reserved-plaquette volume-adapted family."""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(__file__).resolve()
PROTOCOL = ROOT / "computations/yang-mills-volume-adapted-feshbach-v2-prereg.md"
INDEPENDENT_SOURCE = ROOT / "computations/verify_yang_mills_volume_adapted_feshbach_v2_independent.py"
V1_SOURCE = ROOT / "computations/verify_yang_mills_volume_adapted_feshbach.py"
V1_PROTOCOL = ROOT / "computations/yang-mills-volume-adapted-feshbach-prereg.md"
V1_PRIMARY_RECEIPT = ROOT / "runs/yang_mills_volume_adapted_feshbach/verification.json"
V1_INDEPENDENT_RECEIPT = ROOT / "runs/yang_mills_volume_adapted_feshbach/verification-independent.json"
VOLUME_BRIDGE_SOURCE = ROOT / "computations/verify_yang_mills_volume_feshbach_bridge.py"
EXACT_SOURCE = ROOT / "computations/verify_yang_mills_exact_block_spectrum.py"
LARGE_SOURCE = ROOT / "computations/verify_yang_mills_su2_larger_volume_hamiltonian.py"
SCIENTIFIC_PROTOCOL = ROOT / "computations/yang-mills-su2-larger-volume-hamiltonian-prereg.md"
RECOVERY_PROTOCOL = ROOT / "computations/yang-mills-su2-larger-volume-hamiltonian-recovery-prereg.md"
LARGE_RECEIPT = ROOT / "runs/yang_mills_su2_larger_volume_hamiltonian_recovery/verification.json"
DEFAULT_OUTPUT = ROOT / "runs/yang_mills_volume_adapted_feshbach_v2/verification.json"

COUPLINGS = (Fraction(1, 64), Fraction(1, 16), Fraction(1, 4), Fraction(1))
EXPECTED_DIMENSIONS = {"small": 4, "large": 868}


def select_meta(v1: Any, meta: dict[str, Any], columns: np.ndarray, reserved_index: int) -> dict[str, Any]:
    frame, singular, rank = v1.orthonormal_range(columns)
    local = {
        "plaquettes": int(meta["local"]["plaquettes"]) - 1,
        "column_count": int(columns.shape[1]),
        "rank": int(rank),
        "singular_values": [float(value) for value in singular],
        "vector_sha256": v1.array_sha256(columns),
        "frame_sha256": v1.array_sha256(frame),
        "reserved_plaquette_index": int(reserved_index),
    }
    selected = dict(meta)
    selected["local"] = local
    return selected


def build_record(v1: Any, bridge: Any, exact: Any, large: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema": "cassi.yang-mills.volume-adapted-feshbach-v2.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "protocol": {"path": PROTOCOL.relative_to(ROOT).as_posix(), "sha256": v1.sha256(PROTOCOL)},
            "source": {"path": SOURCE.relative_to(ROOT).as_posix(), "sha256": v1.sha256(SOURCE)},
            "independent_source": {"path": INDEPENDENT_SOURCE.relative_to(ROOT).as_posix(), "sha256": v1.sha256(INDEPENDENT_SOURCE)},
            "v1_source": {"path": V1_SOURCE.relative_to(ROOT).as_posix(), "sha256": v1.sha256(V1_SOURCE)},
            "v1_protocol": {"path": V1_PROTOCOL.relative_to(ROOT).as_posix(), "sha256": v1.sha256(V1_PROTOCOL)},
            "v1_primary_receipt": {"path": V1_PRIMARY_RECEIPT.relative_to(ROOT).as_posix(), "sha256": v1.sha256(V1_PRIMARY_RECEIPT)},
            "v1_independent_receipt": {"path": V1_INDEPENDENT_RECEIPT.relative_to(ROOT).as_posix(), "sha256": v1.sha256(V1_INDEPENDENT_RECEIPT)},
            "volume_bridge_source": {"path": VOLUME_BRIDGE_SOURCE.relative_to(ROOT).as_posix(), "sha256": v1.sha256(VOLUME_BRIDGE_SOURCE)},
            "exact_source": {"path": EXACT_SOURCE.relative_to(ROOT).as_posix(), "sha256": v1.sha256(EXACT_SOURCE)},
            "large_source": {"path": LARGE_SOURCE.relative_to(ROOT).as_posix(), "sha256": v1.sha256(LARGE_SOURCE)},
            "scientific_protocol": {"path": SCIENTIFIC_PROTOCOL.relative_to(ROOT).as_posix(), "sha256": v1.sha256(SCIENTIFIC_PROTOCOL)},
            "recovery_protocol": {"path": RECOVERY_PROTOCOL.relative_to(ROOT).as_posix(), "sha256": v1.sha256(RECOVERY_PROTOCOL)},
            "large_receipt": {"path": LARGE_RECEIPT.relative_to(ROOT).as_posix(), "sha256": v1.sha256(LARGE_RECEIPT)},
        },
        "schedule": {
            "graphs": EXPECTED_DIMENSIONS,
            "retained_family": "vacuum plus every fundamental plaquette action except final source-order plaquette",
            "reserved_plaquette_rule": "exclude final source-order plaquette",
            "retained_source_column_counts": {"small": 2, "large": 11},
            "couplings": [str(value) for value in COUPLINGS],
            "rows": 8,
        },
        "checks": [],
        "failures": [],
        "rows": [],
    }
    small_meta_all, large_meta_all, data = v1.local_source_data(exact, large)
    small_columns = data["small_columns"][:, :-1]
    large_columns = data["large_columns"][:, :-1]
    small_meta = select_meta(v1, small_meta_all, small_columns, small_meta_all["local"]["plaquettes"] - 1)
    large_meta = select_meta(v1, large_meta_all, large_columns, large_meta_all["local"]["plaquettes"] - 1)
    v1.check(result, "small reserved-plaquette source family",
             small_columns.shape[1] == 2 and small_meta["local"]["rank"] > 0,
             {"columns": int(small_columns.shape[1]), "local": small_meta["local"]})
    v1.check(result, "large reserved-plaquette source family",
             large_columns.shape[1] == 11 and large_meta["local"]["rank"] > 0,
             {"columns": int(large_columns.shape[1]), "local": large_meta["local"]})
    v1.check(result, "reserved plaquette is final source-order column",
             small_meta["local"]["reserved_plaquette_index"] == 1
             and large_meta["local"]["reserved_plaquette_index"] == 10,
             {"small": small_meta["local"]["reserved_plaquette_index"],
              "large": large_meta["local"]["reserved_plaquette_index"]})
    result["source_basis"] = {"small": small_meta, "large": large_meta}
    large_states = data["large_states"]
    large_operator = data["large_operator"]
    small_cache = {coupling: bridge.small_outer(exact, coupling)[0] for coupling in COUPLINGS}
    coupling_values = COUPLINGS
    for coupling in coupling_values:
        result["rows"].append(v1.feshbach_row(
            "small", coupling, small_cache[coupling], small_columns, small_meta["local"], result))
        large_matrix = bridge.large_outer(large, large_states, large_operator, coupling)
        result["rows"].append(v1.feshbach_row(
            "large", coupling, large_matrix, large_columns, large_meta["local"], result))
    expected_pairs = {(graph, str(coupling)) for graph in EXPECTED_DIMENSIONS for coupling in coupling_values}
    observed_pairs = {(row["graph"], row["coupling"]) for row in result["rows"]}
    v1.check(result, "reserved-plaquette row schedule",
             len(result["rows"]) == 8 and observed_pairs == expected_pairs,
             {"rows": len(result["rows"]), "observed": sorted(observed_pairs)})
    volume_summary: dict[str, Any] = {}
    for coupling in (str(value) for value in coupling_values):
        small_row = next(row for row in result["rows"] if row["graph"] == "small" and row["coupling"] == coupling)
        large_row = next(row for row in result["rows"] if row["graph"] == "large" and row["coupling"] == coupling)
        volume_summary[coupling] = {
            "alpha_large_to_small": large_row.get("alpha_retained") / small_row.get("alpha_retained"),
            "delta_large_to_small": large_row.get("delta_discarded") / small_row.get("delta_discarded"),
            "beta_large_to_small": large_row.get("beta_coupling") / small_row.get("beta_coupling"),
        }
    result["volume_summary"] = volume_summary
    positive_rows = [row for row in result["rows"] if row.get("certified_gap_lower_bound") is not None and row["certified_gap_lower_bound"] > 0.0]
    result["status"] = "PASS" if not result["failures"] else "FAIL"
    if result["status"] != "PASS":
        result["classification"] = "INCONCLUSIVE"
    elif len(positive_rows) == len(result["rows"]):
        result["classification"] = "SUPPORTS_FINITE_VOLUME_RESERVED_PLAQUETTE_FAMILY"
    else:
        result["classification"] = "NO_POSITIVE_RESERVED_PLAQUETTE_FAMILY"
    result["summary"] = {
        "checks": len(result["checks"]),
        "passing_checks": sum(1 for row in result["checks"] if row["passed"]),
        "rows": len(result["rows"]),
        "positive_certified_rows": len(positive_rows),
        "graphs": 2,
        "couplings": 4,
    }
    result["scope"] = {
        "retained_family": "vacuum plus every fundamental plaquette action except final source-order plaquette",
        "outer_family": "finite gauge-invariant C=1 source space",
        "volume_uniform_bound": "UNRESOLVED",
        "lattice_spacing_uniform_bound": "UNRESOLVED",
        "continuum_recovery": "UNRESOLVED",
        "continuum_mass_gap": "UNRESOLVED",
    }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing receipt: {output}")
    required = (
        PROTOCOL, SOURCE, INDEPENDENT_SOURCE, V1_SOURCE, V1_PROTOCOL,
        V1_PRIMARY_RECEIPT, V1_INDEPENDENT_RECEIPT, VOLUME_BRIDGE_SOURCE,
        EXACT_SOURCE, LARGE_SOURCE, SCIENTIFIC_PROTOCOL, RECOVERY_PROTOCOL,
        LARGE_RECEIPT,
    )
    if not all(path.exists() for path in required):
        raise FileNotFoundError("protocol, sources, v1 receipts, large-volume protocols or receipt is missing")
    input_bytes = {path: path.read_bytes() for path in required}
    spec = importlib.util.spec_from_file_location("volume_adapted_v1", V1_SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load source: {V1_SOURCE}")
    v1 = importlib.util.module_from_spec(spec)
    sys.modules["volume_adapted_v1"] = v1
    spec.loader.exec_module(v1)
    bridge = v1.load_module("verify_yang_mills_volume_feshbach_bridge", VOLUME_BRIDGE_SOURCE)
    exact, large = bridge.load_sources()
    record = build_record(v1, bridge, exact, large)
    if any(path.read_bytes() != content for path, content in input_bytes.items()):
        raise RuntimeError("input bytes changed during the run; refusing to seal a mixed-source receipt")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(record, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(f"Receipt: {output}")
    print(json.dumps({key: record[key] for key in ("status", "classification", "summary", "failures")}, indent=2))
    for row in record["rows"]:
        print(
            "row "
            f"graph={row['graph']} x={row['coupling']} "
            f"source_rank={row['retained_source_rank']} P={row['retained_dimension']} Q={row['discarded_dimension']} "
            f"alpha={row.get('alpha_retained')!r} delta={row.get('delta_discarded')!r} "
            f"beta={row.get('beta_coupling')!r} rho={row.get('self_energy_ratio_at_zero')!r} "
            f"phi_zero={row.get('phi_zero')!r} root={row.get('certified_gap_lower_bound')!r}"
        )
    return 0 if record["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
