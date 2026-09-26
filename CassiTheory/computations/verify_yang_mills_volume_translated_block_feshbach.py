#!/usr/bin/env python3
"""Measure the pre-registered translated block-local Feshbach sweep."""
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
PROTOCOL = ROOT / "computations/yang-mills-volume-translated-block-feshbach-prereg.md"
INDEPENDENT_SOURCE = ROOT / "computations/verify_yang_mills_volume_translated_block_feshbach_independent.py"
BLOCK_SOURCE = ROOT / "computations/verify_yang_mills_volume_block_local_feshbach.py"
BLOCK_PROTOCOL = ROOT / "computations/yang-mills-volume-block-local-feshbach-prereg.md"
BLOCK_PRIMARY_RECEIPT = ROOT / "runs/yang_mills_volume_block_local_feshbach/verification.json"
BLOCK_INDEPENDENT_RECEIPT = ROOT / "runs/yang_mills_volume_block_local_feshbach/verification-independent.json"
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
DEFAULT_OUTPUT = ROOT / "runs/yang_mills_volume_translated_block_feshbach/verification.json"

COUPLINGS = (Fraction(1, 64), Fraction(1, 16), Fraction(1, 4), Fraction(1))
EXPECTED_DIMENSION = 868
EXPECTED_PLAQUETTES = (
    "xy_z0_0", "xy_z0_1", "xy_z1_0", "xy_z1_1",
    "xz_y0_0", "xz_y0_1", "xz_y1_0", "xz_y1_1",
    "yz_x0", "yz_x1", "yz_x2",
)


def load_adapted() -> Any:
    spec = importlib.util.spec_from_file_location("volume_adapted_translated", ADAPTED_SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load source: {ADAPTED_SOURCE}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["volume_adapted_translated"] = module
    spec.loader.exec_module(module)
    return module


def translated_columns(columns: np.ndarray, ordinal: int) -> np.ndarray:
    if columns.shape[1] <= ordinal + 1:
        raise ArithmeticError(f"missing plaquette column {ordinal}")
    return np.asarray(columns[:, [0, ordinal + 1]], dtype=float)


def translated_meta(v1: Any, meta: dict[str, Any], columns: np.ndarray, ordinal: int, name: str, word: Any) -> dict[str, Any]:
    frame, singular, rank = v1.orthonormal_range(columns)
    selected = dict(meta)
    selected["local"] = {
        "plaquettes": 1,
        "column_count": int(columns.shape[1]),
        "rank": int(rank),
        "singular_values": [float(value) for value in singular],
        "vector_sha256": v1.array_sha256(columns),
        "frame_sha256": v1.array_sha256(frame),
        "plaquette_ordinal": ordinal,
        "plaquette_name": name,
        "plaquette_word": [[int(edge), int(sign)] for edge, sign in word],
        "weight_rule": "vacuum plus one source-order plaquette with unit weight",
    }
    return selected


def append_row_checks(result: dict[str, Any], local_result: dict[str, Any], ordinal: int, name: str) -> None:
    prefix = f"plaquette={ordinal}:{name}"
    for check in local_result["checks"]:
        check["name"] = f"{prefix}:{check['name']}"
        result["checks"].append(check)
    result["failures"].extend(f"{prefix}:{failure}" for failure in local_result["failures"])


def build_record(v1: Any, bridge: Any, exact: Any, large: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema": "cassi.yang-mills.volume-translated-block-feshbach.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "protocol": {"path": PROTOCOL.relative_to(ROOT).as_posix(), "sha256": v1.sha256(PROTOCOL)},
            "source": {"path": SOURCE.relative_to(ROOT).as_posix(), "sha256": v1.sha256(SOURCE)},
            "independent_source": {"path": INDEPENDENT_SOURCE.relative_to(ROOT).as_posix(), "sha256": v1.sha256(INDEPENDENT_SOURCE)},
            "block_source": {"path": BLOCK_SOURCE.relative_to(ROOT).as_posix(), "sha256": v1.sha256(BLOCK_SOURCE)},
            "block_protocol": {"path": BLOCK_PROTOCOL.relative_to(ROOT).as_posix(), "sha256": v1.sha256(BLOCK_PROTOCOL)},
            "block_primary_receipt": {"path": BLOCK_PRIMARY_RECEIPT.relative_to(ROOT).as_posix(), "sha256": v1.sha256(BLOCK_PRIMARY_RECEIPT)},
            "block_independent_receipt": {"path": BLOCK_INDEPENDENT_RECEIPT.relative_to(ROOT).as_posix(), "sha256": v1.sha256(BLOCK_INDEPENDENT_RECEIPT)},
            "adapted_source": {"path": ADAPTED_SOURCE.relative_to(ROOT).as_posix(), "sha256": v1.sha256(ADAPTED_SOURCE)},
            "adapted_protocol": {"path": ADAPTED_PROTOCOL.relative_to(ROOT).as_posix(), "sha256": v1.sha256(ADAPTED_PROTOCOL)},
            "adapted_primary_receipt": {"path": ADAPTED_PRIMARY_RECEIPT.relative_to(ROOT).as_posix(), "sha256": v1.sha256(ADAPTED_PRIMARY_RECEIPT)},
            "adapted_independent_receipt": {"path": ADAPTED_INDEPENDENT_RECEIPT.relative_to(ROOT).as_posix(), "sha256": v1.sha256(ADAPTED_INDEPENDENT_RECEIPT)},
            "volume_bridge_source": {"path": VOLUME_BRIDGE_SOURCE.relative_to(ROOT).as_posix(), "sha256": v1.sha256(VOLUME_BRIDGE_SOURCE)},
            "exact_source": {"path": EXACT_SOURCE.relative_to(ROOT).as_posix(), "sha256": v1.sha256(EXACT_SOURCE)},
            "large_source": {"path": LARGE_SOURCE.relative_to(ROOT).as_posix(), "sha256": v1.sha256(LARGE_SOURCE)},
            "scientific_protocol": {"path": SCIENTIFIC_PROTOCOL.relative_to(ROOT).as_posix(), "sha256": v1.sha256(SCIENTIFIC_PROTOCOL)},
            "recovery_protocol": {"path": RECOVERY_PROTOCOL.relative_to(ROOT).as_posix(), "sha256": v1.sha256(RECOVERY_PROTOCOL)},
            "large_receipt": {"path": LARGE_RECEIPT.relative_to(ROOT).as_posix(), "sha256": v1.sha256(LARGE_RECEIPT)},
        },
        "schedule": {
            "graph": "large",
            "dimension": EXPECTED_DIMENSION,
            "plaquettes": list(EXPECTED_PLAQUETTES),
            "retained_family": "vacuum plus one source-order plaquette",
            "weight_rule": "equal unit weight before orthonormalization",
            "couplings": [str(value) for value in COUPLINGS],
            "rows": 44,
        },
        "checks": [],
        "failures": [],
        "rows": [],
    }
    small_meta_unused, large_meta_all, data = v1.local_source_data(exact, large)
    del small_meta_unused
    large_columns = data["large_columns"]
    names = tuple(large.PLAQUETTE_NAMES)
    words = tuple(large.PLAQUETTES)
    v1.check(result, "large dimension", large_columns.shape[0] == EXPECTED_DIMENSION,
             {"dimension": int(large_columns.shape[0])})
    v1.check(result, "plaquette names", names == EXPECTED_PLAQUETTES,
             {"recorded": names, "expected": EXPECTED_PLAQUETTES})
    v1.check(result, "plaquette count", len(words) == len(EXPECTED_PLAQUETTES),
             {"count": len(words)})
    basis: dict[str, Any] = {}
    large_states = data["large_states"]
    large_operator = data["large_operator"]
    large_matrices: dict[int, np.ndarray] = {}
    for ordinal, name in enumerate(EXPECTED_PLAQUETTES):
        columns = translated_columns(large_columns, ordinal)
        meta = translated_meta(v1, large_meta_all, columns, ordinal, name, words[ordinal])
        basis[name] = meta
        v1.check(result, f"plaquette {ordinal} source family",
                 meta["local"]["rank"] == 2 and meta["local"]["column_count"] == 2,
                 {"ordinal": ordinal, "name": name, "local": meta["local"]})
    result["source_basis"] = basis
    for coupling in COUPLINGS:
        large_matrices[coupling.numerator * 1000000 // coupling.denominator] = bridge.large_outer(
            large, large_states, large_operator, coupling)
    for ordinal, name in enumerate(EXPECTED_PLAQUETTES):
        columns = translated_columns(large_columns, ordinal)
        meta = basis[name]
        for coupling in COUPLINGS:
            matrix = large_matrices[coupling.numerator * 1000000 // coupling.denominator]
            local_result: dict[str, Any] = {"checks": [], "failures": []}
            row = v1.feshbach_row("large", coupling, matrix, columns, meta["local"], local_result)
            row["plaquette_ordinal"] = ordinal
            row["plaquette_name"] = name
            result["rows"].append(row)
            append_row_checks(result, local_result, ordinal, name)
    expected_pairs = {(ordinal, str(coupling)) for ordinal in range(len(EXPECTED_PLAQUETTES)) for coupling in COUPLINGS}
    observed_pairs = {(row.get("plaquette_ordinal"), row.get("coupling")) for row in result["rows"]}
    v1.check(result, "translated row schedule",
             len(result["rows"]) == 44 and observed_pairs == expected_pairs,
             {"rows": len(result["rows"]), "observed_count": len(observed_pairs)})
    per_plaquette: dict[str, Any] = {}
    for name in EXPECTED_PLAQUETTES:
        rows = [row for row in result["rows"] if row["plaquette_name"] == name]
        positive = [row for row in rows if row.get("certified_gap_lower_bound") is not None and row["certified_gap_lower_bound"] > 0.0]
        per_plaquette[name] = {
            "rows": len(rows),
            "positive_roots": len(positive),
            "min_certified_gap_lower_bound": min(row["certified_gap_lower_bound"] for row in positive) if positive else None,
            "max_beta": max(row["beta_coupling"] for row in rows),
            "max_self_energy_ratio": max(row["self_energy_ratio_at_zero"] for row in rows),
            "max_root_to_gap_ratio": max(row["root_to_gap_ratio"] for row in rows),
        }
    result["per_plaquette"] = per_plaquette
    positive_rows = [row for row in result["rows"] if row.get("certified_gap_lower_bound") is not None and row["certified_gap_lower_bound"] > 0.0]
    result["status"] = "PASS" if not result["failures"] else "FAIL"
    if result["status"] != "PASS":
        result["classification"] = "INCONCLUSIVE"
    elif len(positive_rows) == len(result["rows"]):
        result["classification"] = "SUPPORTS_FINITE_TRANSLATED_BLOCK_SWEEP"
    else:
        result["classification"] = "NO_POSITIVE_TRANSLATED_BLOCK_SWEEP"
    result["summary"] = {
        "checks": len(result["checks"]),
        "passing_checks": sum(1 for row in result["checks"] if row["passed"]),
        "rows": len(result["rows"]),
        "positive_certified_rows": len(positive_rows),
        "plaquettes": len(EXPECTED_PLAQUETTES),
        "couplings": len(COUPLINGS),
    }
    result["scope"] = {
        "retained_family": "vacuum plus one translated source-order plaquette",
        "outer_family": "finite gauge-invariant C=1 source space",
        "translation_coverage": "ALL 11 RECOVERED PLAQUETTES",
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
    required = (PROTOCOL, SOURCE, INDEPENDENT_SOURCE, BLOCK_SOURCE, BLOCK_PROTOCOL,
                BLOCK_PRIMARY_RECEIPT, BLOCK_INDEPENDENT_RECEIPT, ADAPTED_SOURCE,
                ADAPTED_PROTOCOL, ADAPTED_PRIMARY_RECEIPT, ADAPTED_INDEPENDENT_RECEIPT,
                VOLUME_BRIDGE_SOURCE, EXACT_SOURCE, LARGE_SOURCE, SCIENTIFIC_PROTOCOL,
                RECOVERY_PROTOCOL, LARGE_RECEIPT)
    if not all(path.exists() for path in required):
        raise FileNotFoundError("protocol, sources, block/adapted receipts, volume protocols or receipt is missing")
    input_bytes = {path: path.read_bytes() for path in required}
    v1 = load_adapted()
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
    for name, summary in record["per_plaquette"].items():
        print(f"plaquette {name}: {json.dumps(summary, sort_keys=True)}")
    return 0 if record["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
