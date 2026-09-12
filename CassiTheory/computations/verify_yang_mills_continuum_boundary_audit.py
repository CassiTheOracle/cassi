"""Audit recovered finite SU(2) evidence against the continuum mass-gap target.

This verifier does not reconstruct the 955835-state Hamiltonian.  It binds the
already reconstructed primary and independent receipts to the current source
files, checks the finite claims used by the theory documents, and records the
continuum obligations that those receipts do not discharge.

Run from the CassiTheory root:

    python computations/verify_yang_mills_continuum_boundary_audit.py --replace
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(__file__).resolve()
OUTPUT = ROOT / "runs" / "yang_mills_continuum_boundary_audit" / "verification.json"
PRIMARY_RECEIPT = (
    ROOT
    / "runs"
    / "yang_mills_su2_larger_volume_hamiltonian_recovery"
    / "verification.json"
)
INDEPENDENT_RECEIPT = (
    ROOT
    / "runs"
    / "yang_mills_su2_larger_volume_hamiltonian_recovery"
    / "verification-independent.json"
)
RECEIPT_BOUND_RECOVERY_PROTOCOL = (
    ROOT
    / "runs"
    / "yang_mills_su2_larger_volume_hamiltonian_recovery"
    / "recovery-protocol-receipt-bound.md"
)
RECOVERY_PROTOCOL = (
    ROOT
    / "computations"
    / "yang-mills-su2-larger-volume-hamiltonian-recovery-prereg.md"
)
SCIENTIFIC_PROTOCOL = (
    ROOT / "computations" / "yang-mills-su2-larger-volume-hamiltonian-prereg.md"
)
THEORY_SOURCE = ROOT / "foundations" / "loop-to-bubble-projection-theorem.md"
PRIMARY_SOURCE = (
    ROOT / "computations" / "verify_yang_mills_su2_larger_volume_hamiltonian.py"
)
INDEPENDENT_SOURCE = (
    ROOT
    / "computations"
    / "verify_yang_mills_su2_larger_volume_hamiltonian_independent.py"
)
HELPER_SOURCE = ROOT / "computations" / "verify_yang_mills_exact_block_spectrum.py"
CUTOFF_FORM_PROTOCOL = (
    ROOT / "computations" / "yang-mills-finite-graph-cutoff-form-prereg.md"
)
CUTOFF_FORM_PRIMARY_SOURCE = (
    ROOT / "computations" / "verify_yang_mills_finite_graph_cutoff_form.py"
)
CUTOFF_FORM_INDEPENDENT_SOURCE = (
    ROOT
    / "computations"
    / "verify_yang_mills_finite_graph_cutoff_form_independent.py"
)
CUTOFF_FORM_PRIMARY_RECEIPT = (
    ROOT / "runs" / "yang_mills_finite_graph_cutoff_form" / "verification.json"
)
CUTOFF_FORM_INDEPENDENT_RECEIPT = (
    ROOT
    / "runs"
    / "yang_mills_finite_graph_cutoff_form"
    / "verification-independent.json"
)


EXCLUDED_PRIMARY_RECEIPT = Path("D:/Cassi-ym-larger-volume/verification-final2.json")
EXCLUDED_INDEPENDENT_RECEIPT = Path(
    "D:/Cassi-ym-larger-volume/verification-independent-final2.json"
)
EXCLUDED_PRIMARY_SHA256 = (
    "e3f331ad8e0f7a667882651fef4c88278f1d27e7e332d6fe13722176fbcc5e82"
)
EXCLUDED_INDEPENDENT_SHA256 = (
    "a0991c86276e93222ceda2413573aa46a2521e5023a701d9ea392945d99f6d62"
)

CURRENT_REFERENCE = (
    b"- `computations/verify_yang_mills_su2_larger_volume_hamiltonian.py`"
    b"\xe2\x80\x94recovered primary implementation."
)
RECEIPT_BOUND_REFERENCE = (
    b"- `computations/verify_yang_mills_su2-larger-volume-hamiltonian.py`"
    b"\xe2\x80\x94recovered primary implementation."
)
EXPECTED_PRIMARY_FAILURES = {
    "tail_separation_C1_x0.25",
    "tail_separation_C2_x0.25",
    "tail_separation_C1_x1.0",
    "tail_separation_C2_x1.0",
}
EXPECTED_BASIS = {
    "1": {
        "dimension": 868,
        "state_sha256": "78a1d9dbfe14fc97f439120b74df17189be9d332b5fffd40ad26522fb92b9411",
    },
    "2": {
        "dimension": 955835,
        "state_sha256": "b67c27f88e48148208382bebcc52fd06374885da0b6de102ddb185f3ae4bc67c",
    },
}
COUPLINGS = [0.015625, 0.0625, 0.25, 1.0]
MISSING_CLAY_OBLIGATIONS = [
    "nontrivial four-dimensional quantum Yang-Mills construction on R^4",
    "reflection-positive Euclidean Schwinger functions and OS/Wightman reconstruction",
    "renormalized local gauge-invariant field content with the required short-distance behavior",
    "uniform weak-coupling estimates along a->0",
    "spatial-volume- and lattice-spacing-uniform character-cutoff estimates",
    "thermodynamic limit L^3->infinity",
    "regulator-independent positive gauge-invariant mass gap",
    "extension from SU(2) to every compact simple gauge group",
]


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(4 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise TypeError(f"expected a JSON object in {path}")
    return value


def read_primary_top_level(path: Path, keys: Iterable[str]) -> dict[str, Any]:
    """Read selected top-level values without materializing the huge basis."""

    wanted = set(keys)
    values: dict[str, Any] = {}
    with path.open("r", encoding="utf-8") as handle:
        iterator = iter(handle)
        for line in iterator:
            if not line.startswith('  "'):
                continue
            split = line.find('": ')
            if split < 0:
                continue
            key = line[3:split]
            if key not in wanted:
                continue
            raw = line[split + 3 :]
            stripped = raw.lstrip()
            if stripped.startswith("[") or stripped.startswith("{"):
                closer = "]" if stripped.startswith("[") else "}"
                pieces = [raw]
                for continuation in iterator:
                    pieces.append(continuation)
                    if continuation.startswith(f"  {closer}") and continuation.strip().rstrip(",") == closer:
                        break
                text = "".join(pieces).strip()
            else:
                text = raw.strip()
            if text.endswith(","):
                text = text[:-1]
            values[key] = json.loads(text)
            if wanted == values.keys():
                break
    missing = wanted - values.keys()
    if missing:
        raise KeyError(f"missing top-level keys in {path}: {sorted(missing)}")
    return values


def validate_protocol_snapshot_relation() -> bytes:
    current = RECOVERY_PROTOCOL.read_bytes()
    snapshot = RECEIPT_BOUND_RECOVERY_PROTOCOL.read_bytes()
    if (
        current.count(CURRENT_REFERENCE) != 1
        or current.count(RECEIPT_BOUND_REFERENCE) != 0
        or snapshot.count(CURRENT_REFERENCE) != 0
        or snapshot.count(RECEIPT_BOUND_REFERENCE) != 1
        or snapshot.replace(RECEIPT_BOUND_REFERENCE, CURRENT_REFERENCE, 1) != current
    ):
        raise ValueError(
            "materialized receipt-bound protocol snapshot must differ from the "
            "current protocol only in the corrected primary-source reference"
        )
    return current


def matrix_summary(record: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    keys = (
        "name",
        "candidate_entries",
        "nonzero_entries",
        "matrix_hash",
        "spectator_channels_preserved",
        "candidate_targets_unique",
    )
    return {
        cutoff: [{key: row[key] for key in keys} for row in rows]
        for cutoff, rows in record["matrices"].items()
    }


def energy_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "coupling": row["coupling"],
            "ground_energies": {
                cutoff: data["ground_energy"]
                for cutoff, data in row["cutoffs"].items()
            },
        }
        for row in rows
    ]


def close(a: float, b: float, tolerance: float = 1.0e-10) -> bool:
    return math.isclose(float(a), float(b), rel_tol=tolerance, abs_tol=tolerance)


def run(output: Path, replace: bool) -> dict[str, Any]:
    required_paths = [
        PRIMARY_RECEIPT,
        INDEPENDENT_RECEIPT,
        RECEIPT_BOUND_RECOVERY_PROTOCOL,
        RECOVERY_PROTOCOL,
        SCIENTIFIC_PROTOCOL,
        THEORY_SOURCE,
        PRIMARY_SOURCE,
        INDEPENDENT_SOURCE,
        HELPER_SOURCE,
        CUTOFF_FORM_PROTOCOL,
        CUTOFF_FORM_PRIMARY_SOURCE,
        CUTOFF_FORM_INDEPENDENT_SOURCE,
        CUTOFF_FORM_PRIMARY_RECEIPT,
        CUTOFF_FORM_INDEPENDENT_RECEIPT,
        EXCLUDED_PRIMARY_RECEIPT,
        EXCLUDED_INDEPENDENT_RECEIPT,
    ]
    missing_paths = [display_path(path) for path in required_paths if not path.is_file()]
    if missing_paths:
        raise FileNotFoundError(f"missing audit inputs: {missing_paths}")

    primary_keys = {
        "schema",
        "status",
        "classification",
        "protocol",
        "scientific_protocol",
        "source",
        "helper",
        "protocol_sha256",
        "scientific_protocol_sha256",
        "source_sha256",
        "helper_sha256",
        "matrices",
        "wilson_operator_spectra",
        "spectator_channel_firing_control",
        "rows",
        "checks",
        "checks_passed",
        "checks_total",
        "finite_checks_passed",
        "finite_checks_total",
        "cutoff_checks_passed",
        "cutoff_checks_total",
        "cutoff_qualifications",
        "useful_tail_rows",
        "continuum_claim",
    }
    primary = read_primary_top_level(PRIMARY_RECEIPT, primary_keys)
    independent = load_json(INDEPENDENT_RECEIPT)
    cutoff_form_primary = load_json(CUTOFF_FORM_PRIMARY_RECEIPT)
    cutoff_form_independent = load_json(CUTOFF_FORM_INDEPENDENT_RECEIPT)

    current_protocol = validate_protocol_snapshot_relation()
    hashes = {
        "audit_source": sha256(SOURCE),
        "primary_receipt": sha256(PRIMARY_RECEIPT),
        "independent_receipt": sha256(INDEPENDENT_RECEIPT),
        "current_recovery_protocol": sha256_bytes(current_protocol),
        "receipt_bound_recovery_protocol": sha256(
            RECEIPT_BOUND_RECOVERY_PROTOCOL
        ),
        "scientific_protocol": sha256(SCIENTIFIC_PROTOCOL),
        "theory_source": sha256(THEORY_SOURCE),
        "primary_source": sha256(PRIMARY_SOURCE),
        "independent_source": sha256(INDEPENDENT_SOURCE),
        "helper_source": sha256(HELPER_SOURCE),
        "cutoff_form_protocol": sha256(CUTOFF_FORM_PROTOCOL),
        "cutoff_form_primary_source": sha256(CUTOFF_FORM_PRIMARY_SOURCE),
        "cutoff_form_independent_source": sha256(CUTOFF_FORM_INDEPENDENT_SOURCE),
        "cutoff_form_primary_receipt": sha256(CUTOFF_FORM_PRIMARY_RECEIPT),
        "cutoff_form_independent_receipt": sha256(
            CUTOFF_FORM_INDEPENDENT_RECEIPT
        ),
        "excluded_primary_receipt": sha256(EXCLUDED_PRIMARY_RECEIPT),
        "excluded_independent_receipt": sha256(EXCLUDED_INDEPENDENT_RECEIPT),
    }

    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, **details: Any) -> None:
        checks.append({"name": name, "passed": bool(passed), **details})

    check(
        "primary receipt schema and finite classification",
        primary["schema"] == "yang_mills_su2_larger_volume_hamiltonian_recovery_v2"
        and primary["status"] == "PASS"
        and primary["classification"] == "PASS_RECOVERED_FINITE_CONSTRUCTION",
        schema=primary["schema"],
        status=primary["status"],
        classification=primary["classification"],
    )
    check(
        "primary finite checks all pass",
        primary["finite_checks_passed"] == primary["finite_checks_total"] == 226,
        passed_count=primary["finite_checks_passed"],
        total=primary["finite_checks_total"],
    )
    failed_primary = {
        row["name"] for row in primary["checks"] if not bool(row.get("passed"))
    }
    check(
        "primary aggregate failures are exactly non-gating tail separations",
        primary["checks_passed"] == 234
        and primary["checks_total"] == 238
        and failed_primary == EXPECTED_PRIMARY_FAILURES,
        passed_count=primary["checks_passed"],
        total=primary["checks_total"],
        failed=sorted(failed_primary),
    )
    check(
        "nested cutoff energies pass",
        primary["cutoff_checks_passed"] == primary["cutoff_checks_total"] == 4,
        passed_count=primary["cutoff_checks_passed"],
        total=primary["cutoff_checks_total"],
    )
    check(
        "all aggregate tail qualifications are inconclusive",
        set(primary["cutoff_qualifications"].keys())
        == {str(value) for value in COUPLINGS}
        and set(primary["cutoff_qualifications"].values()) == {"INCONCLUSIVE"}
        and primary["useful_tail_rows"] == 1,
        qualifications=primary["cutoff_qualifications"],
        useful_tail_rows=primary["useful_tail_rows"],
    )
    check(
        "independent reconstruction passes 256 checks",
        independent.get("schema")
        == "yang_mills_su2_larger_volume_hamiltonian_recovery_independent_v2"
        and independent.get("status") == "PASS"
        and independent.get("checks_passed") == independent.get("checks_total") == 256,
        schema=independent.get("schema"),
        status=independent.get("status"),
        passed_count=independent.get("checks_passed"),
        total=independent.get("checks_total"),
    )
    check(
        "both receipts withhold a continuum claim",
        primary["continuum_claim"] is False
        and independent.get("continuum_claim") is False,
        primary=primary["continuum_claim"],
        independent=independent.get("continuum_claim"),
    )
    check(
        "fixed-graph cutoff-form primary passes and withholds a Clay claim",
        cutoff_form_primary.get("schema")
        == "cassi.yang_mills_finite_graph_cutoff_form.v1"
        and cutoff_form_primary.get("finite_graph_status") == "PASS"
        and cutoff_form_primary.get("checks_passed")
        == cutoff_form_primary.get("checks_total")
        == 22
        and cutoff_form_primary.get("continuum_hypotheses_present") is False
        and cutoff_form_primary.get("clay_verdict") == "NULL",
        status=cutoff_form_primary.get("finite_graph_status"),
        passed_count=cutoff_form_primary.get("checks_passed"),
        total=cutoff_form_primary.get("checks_total"),
        clay_verdict=cutoff_form_primary.get("clay_verdict"),
    )
    check(
        "fixed-graph cutoff-form independent reconstruction passes",
        cutoff_form_independent.get("schema")
        == "cassi.yang_mills_finite_graph_cutoff_form.independent.v1"
        and cutoff_form_independent.get("finite_graph_status") == "PASS"
        and cutoff_form_independent.get("checks_passed")
        == cutoff_form_independent.get("checks_total")
        == 18
        and cutoff_form_independent.get("continuum_hypotheses_present") is False
        and cutoff_form_independent.get("clay_verdict") == "NULL",
        status=cutoff_form_independent.get("finite_graph_status"),
        passed_count=cutoff_form_independent.get("checks_passed"),
        total=cutoff_form_independent.get("checks_total"),
        clay_verdict=cutoff_form_independent.get("clay_verdict"),
    )
    cutoff_primary_inputs = cutoff_form_primary.get("inputs", {})
    cutoff_independent_inputs = cutoff_form_independent.get("inputs", {})
    check(
        "fixed-graph cutoff-form protocol sources and primary receipt are bound",
        cutoff_primary_inputs.get("protocol", {}).get("sha256")
        == cutoff_independent_inputs.get("protocol", {}).get("sha256")
        == hashes["cutoff_form_protocol"]
        and cutoff_primary_inputs.get("primary_source", {}).get("sha256")
        == cutoff_independent_inputs.get("primary_source", {}).get("sha256")
        == hashes["cutoff_form_primary_source"]
        and cutoff_independent_inputs.get("independent_source", {}).get("sha256")
        == hashes["cutoff_form_independent_source"]
        and cutoff_independent_inputs.get("primary_receipt", {}).get("sha256")
        == hashes["cutoff_form_primary_receipt"],
        protocol_sha256=hashes["cutoff_form_protocol"],
        primary_source_sha256=hashes["cutoff_form_primary_source"],
        independent_source_sha256=hashes["cutoff_form_independent_source"],
        primary_receipt_sha256=hashes["cutoff_form_primary_receipt"],
    )
    cutoff_primary_spectrum = cutoff_form_primary.get("square_spectrum", {})
    cutoff_independent_spectrum = cutoff_form_independent.get(
        "square_spectrum", {}
    )
    cutoff_firing = cutoff_form_primary.get("noncommuting_firing_control", {})
    check(
        "fixed-graph tail Ritz and noncommuting firing controls pass",
        cutoff_primary_spectrum.get("tail_attempted") == 84
        and cutoff_primary_spectrum.get("tail_passed") == 84
        and cutoff_primary_spectrum.get("square_tail_passed") == 84
        and cutoff_primary_spectrum.get("ritz_applicable") == 67
        and cutoff_primary_spectrum.get("ritz_passed") == 67
        and cutoff_independent_spectrum.get("row_count") == 84
        and cutoff_independent_spectrum.get("tail_passed") == 84
        and cutoff_independent_spectrum.get("square_tail_passed") == 84
        and cutoff_independent_spectrum.get("ritz_applicable") == 67
        and cutoff_independent_spectrum.get("ritz_passed") == 67
        and cutoff_firing.get("incomplete_bound_violation_margin", 0.0)
        > 1.0e-3,
        primary_tail_passed=cutoff_primary_spectrum.get("tail_passed"),
        primary_tail_attempted=cutoff_primary_spectrum.get("tail_attempted"),
        primary_ritz_passed=cutoff_primary_spectrum.get("ritz_passed"),
        primary_ritz_applicable=cutoff_primary_spectrum.get("ritz_applicable"),
        independent_rows=cutoff_independent_spectrum.get("row_count"),
        firing_margin=cutoff_firing.get("incomplete_bound_violation_margin"),
    )


    receipt_protocol_hashes = {
        primary["protocol_sha256"], independent.get("protocol_sha256")
    }
    check(
        "materialized receipt-bound recovery protocol snapshot is exact",
        receipt_protocol_hashes == {hashes["receipt_bound_recovery_protocol"]},
        recorded=sorted(receipt_protocol_hashes),
        materialized=hashes["receipt_bound_recovery_protocol"],
        current=hashes["current_recovery_protocol"],
    )
    check(
        "scientific protocol hash matches both receipts",
        primary["scientific_protocol_sha256"]
        == independent.get("scientific_protocol_sha256")
        == hashes["scientific_protocol"],
        computed=hashes["scientific_protocol"],
    )
    check(
        "primary source hash matches both receipts",
        primary["source_sha256"]
        == independent.get("primary_source_sha256")
        == hashes["primary_source"],
        computed=hashes["primary_source"],
    )
    check(
        "independent source hash matches its receipt",
        independent.get("source_sha256") == hashes["independent_source"],
        computed=hashes["independent_source"],
    )
    check(
        "shared representation helper hash matches both receipts",
        primary["helper_sha256"]
        == independent.get("helper_sha256")
        == hashes["helper_source"],
        computed=hashes["helper_source"],
    )
    check(
        "receipt paths name the audited files",
        primary["protocol"] == display_path(RECOVERY_PROTOCOL)
        and independent.get("protocol") == display_path(RECOVERY_PROTOCOL)
        and primary["scientific_protocol"] == display_path(SCIENTIFIC_PROTOCOL)
        and independent.get("scientific_protocol") == display_path(SCIENTIFIC_PROTOCOL)
        and primary["source"] == display_path(PRIMARY_SOURCE)
        and independent.get("primary_source") == display_path(PRIMARY_SOURCE)
        and independent.get("source") == display_path(INDEPENDENT_SOURCE)
        and primary["helper"] == display_path(HELPER_SOURCE)
        and independent.get("helper") == display_path(HELPER_SOURCE),
    )

    check(
        "independent basis reconstruction matches the declared sectors",
        independent.get("basis") == EXPECTED_BASIS,
        basis=independent.get("basis"),
    )
    primary_matrices = matrix_summary(primary)
    independent_matrices = matrix_summary(independent)
    matrix_rows = [row for rows in independent_matrices.values() for row in rows]
    check(
        "primary and independent plaquette hashes and supports match",
        primary_matrices == independent_matrices
        and len(matrix_rows) == 22
        and all(row["spectator_channels_preserved"] for row in matrix_rows)
        and all(row["candidate_targets_unique"] for row in matrix_rows),
        plaquette_matrices=len(matrix_rows),
    )

    primary_firing = primary["spectator_channel_firing_control"]
    independent_firing = independent.get("spectator_channel_firing_control", {})
    exact_firing_keys = (
        "plaquette",
        "right_state_index",
        "legacy_candidate_count",
        "recovered_candidate_count",
        "mismatched_remote_channel_state_index",
        "mismatched_remote_channel_position",
        "mismatched_remote_channel_vertex",
        "corrected_mismatched_value",
        "local_channel_overlap",
        "mismatched_state_excluded_from_recovered_support",
    )
    firing_indices_match = all(
        primary_firing.get(key) == independent_firing.get(key)
        for key in exact_firing_keys
    )
    legacy_values_match = all(
        close(primary_firing["legacy_mismatched_value"][part], independent_firing["legacy_mismatched_value"][part])
        for part in (0, 1)
    )
    check(
        "spectator-channel defect witness fires and is removed",
        firing_indices_match
        and legacy_values_match
        and primary_firing.get("plaquette") == "yz_x0"
        and primary_firing.get("legacy_candidate_count") == 80
        and primary_firing.get("recovered_candidate_count") == 5
        and close(primary_firing.get("legacy_normalized_column_norm_squared"), 16.0)
        and close(independent_firing.get("legacy_normalized_column_norm_squared"), 16.0)
        and close(primary_firing.get("recovered_normalized_column_norm_squared"), 1.0)
        and close(independent_firing.get("recovered_normalized_column_norm_squared"), 1.0)
        and primary_firing.get("mismatched_remote_channel_vertex") == 6
        and primary_firing.get("corrected_mismatched_value") == [0.0, 0.0]
        and primary_firing.get("local_channel_overlap") == [0.0, 0.0]
        and primary_firing.get("mismatched_state_excluded_from_recovered_support")
        is True,
        plaquette=primary_firing.get("plaquette"),
        legacy_candidates=primary_firing.get("legacy_candidate_count"),
        recovered_candidates=primary_firing.get("recovered_candidate_count"),
    )

    primary_wilson = primary["wilson_operator_spectra"]
    independent_wilson = independent.get("wilson_operator_spectra", {})
    wilson_match = all(
        close(primary_wilson[cutoff][edge], independent_wilson[cutoff][edge])
        for cutoff in ("1", "2")
        for edge in ("minimum", "maximum")
    )
    wilson_bounded = all(
        primary_wilson[cutoff]["minimum"] >= -22.0 - 1.0e-8
        and primary_wilson[cutoff]["maximum"] <= 22.0 + 1.0e-8
        for cutoff in ("1", "2")
    )
    check(
        "Wilson extrema reconstruct independently and obey the plaquette bound",
        wilson_match and wilson_bounded,
        extrema={
            cutoff: {
                "minimum": primary_wilson[cutoff]["minimum"],
                "maximum": primary_wilson[cutoff]["maximum"],
            }
            for cutoff in ("1", "2")
        },
    )

    primary_energies = energy_summary(primary["rows"])
    independent_energies = energy_summary(independent.get("rows", []))
    energies_match = len(primary_energies) == len(independent_energies) == 4 and all(
        p_row["coupling"] == i_row["coupling"]
        and all(
            close(p_row["ground_energies"][cutoff], i_row["ground_energies"][cutoff])
            for cutoff in ("1", "2")
        )
        for p_row, i_row in zip(primary_energies, independent_energies)
    )
    energies_nonnegative = all(
        energy >= -1.0e-8
        for row in primary_energies
        for energy in row["ground_energies"].values()
    )
    check(
        "all scheduled ground energies reconstruct and are nonnegative",
        energies_match and energies_nonnegative,
        rows=primary_energies,
    )

    check(
        "excluded primary receipt hash matches recorded defect provenance",
        hashes["excluded_primary_receipt"] == EXCLUDED_PRIMARY_SHA256,
        computed=hashes["excluded_primary_receipt"],
        expected=EXCLUDED_PRIMARY_SHA256,
    )
    check(
        "excluded independent receipt hash matches recorded defect provenance",
        hashes["excluded_independent_receipt"] == EXCLUDED_INDEPENDENT_SHA256,
        computed=hashes["excluded_independent_receipt"],
        expected=EXCLUDED_INDEPENDENT_SHA256,
    )

    theory = THEORY_SOURCE.read_text(encoding="utf-8")
    check(
        "theory separates fixed-graph cutoff removal from the open Clay target",
        "Fixed-graph character-cutoff form theorem (YM187)\u2013(YM195) | **Derived**"
        in theory
        and "`continuum_hypotheses_present=false` and `clay_verdict=NULL`"
        in theory
        and "Continuum Yang\u2013Mills existence and mass gap | **Open**" in theory,
    )

    all_passed = all(row["passed"] for row in checks)
    record: dict[str, Any] = {
        "schema": "yang_mills_continuum_boundary_audit_v3",
        "status": "PASS" if all_passed else "FAIL",
        "verdict": "UNRESOLVED_CONTINUUM_PROBLEM",
        "clay_verdict": "NULL",
        "scope": "Hash-bound audit of recovered finite SU(2) Hamiltonian evidence and fixed-graph cutoff removal against the Clay Yang-Mills existence and mass-gap obligations",
        "audit_source": {
            "path": display_path(SOURCE),
            "sha256": hashes["audit_source"],
        },
        "inputs": {
            "recovered_primary_receipt": {
                "path": display_path(PRIMARY_RECEIPT),
                "sha256": hashes["primary_receipt"],
                "bytes": PRIMARY_RECEIPT.stat().st_size,
            },
            "recovered_independent_receipt": {
                "path": display_path(INDEPENDENT_RECEIPT),
                "sha256": hashes["independent_receipt"],
                "bytes": INDEPENDENT_RECEIPT.stat().st_size,
            },
            "recovery_protocol": {
                "path": display_path(RECOVERY_PROTOCOL),
                "sha256": hashes["current_recovery_protocol"],
            },
            "receipt_bound_recovery_protocol_snapshot": {
                "path": display_path(RECEIPT_BOUND_RECOVERY_PROTOCOL),
                "sha256": hashes["receipt_bound_recovery_protocol"],
                "bytes": RECEIPT_BOUND_RECOVERY_PROTOCOL.stat().st_size,
            },
            "scientific_protocol": {
                "path": display_path(SCIENTIFIC_PROTOCOL),
                "sha256": hashes["scientific_protocol"],
            },
            "theory_source": {
                "path": display_path(THEORY_SOURCE),
                "sha256": hashes["theory_source"],
            },
            "primary_verifier_source": {
                "path": display_path(PRIMARY_SOURCE),
                "sha256": hashes["primary_source"],
            },
            "independent_verifier_source": {
                "path": display_path(INDEPENDENT_SOURCE),
                "sha256": hashes["independent_source"],
            },
            "helper_source": {
                "path": display_path(HELPER_SOURCE),
                "sha256": hashes["helper_source"],
            },
            "cutoff_form_protocol": {
                "path": display_path(CUTOFF_FORM_PROTOCOL),
                "sha256": hashes["cutoff_form_protocol"],
            },
            "cutoff_form_primary_source": {
                "path": display_path(CUTOFF_FORM_PRIMARY_SOURCE),
                "sha256": hashes["cutoff_form_primary_source"],
            },
            "cutoff_form_independent_source": {
                "path": display_path(CUTOFF_FORM_INDEPENDENT_SOURCE),
                "sha256": hashes["cutoff_form_independent_source"],
            },
            "cutoff_form_primary_receipt": {
                "path": display_path(CUTOFF_FORM_PRIMARY_RECEIPT),
                "sha256": hashes["cutoff_form_primary_receipt"],
                "bytes": CUTOFF_FORM_PRIMARY_RECEIPT.stat().st_size,
            },
            "cutoff_form_independent_receipt": {
                "path": display_path(CUTOFF_FORM_INDEPENDENT_RECEIPT),
                "sha256": hashes["cutoff_form_independent_receipt"],
                "bytes": CUTOFF_FORM_INDEPENDENT_RECEIPT.stat().st_size,
            },
        },
        "protocol_snapshot_audit": {
            "current_reference": CURRENT_REFERENCE.decode("utf-8"),
            "receipt_bound_reference": RECEIPT_BOUND_REFERENCE.decode("utf-8"),
            "materialized_path": display_path(RECEIPT_BOUND_RECOVERY_PROTOCOL),
            "exact_single_reference_difference": True,
            "current_sha256": hashes["current_recovery_protocol"],
            "receipt_bound_materialized_sha256": hashes[
                "receipt_bound_recovery_protocol"
            ],
            "primary_recorded_sha256": primary["protocol_sha256"],
            "independent_recorded_sha256": independent.get("protocol_sha256"),
        },
        "finite_evidence": {
            "primary_status": primary["status"],
            "primary_classification": primary["classification"],
            "primary_checks_passed": primary["checks_passed"],
            "primary_checks_total": primary["checks_total"],
            "finite_checks_passed": primary["finite_checks_passed"],
            "finite_checks_total": primary["finite_checks_total"],
            "independent_status": independent.get("status"),
            "independent_checks_passed": independent.get("checks_passed"),
            "independent_checks_total": independent.get("checks_total"),
            "basis": independent.get("basis"),
            "coupling_schedule_x": COUPLINGS,
            "wilson_extrema": {
                cutoff: {
                    "minimum": primary_wilson[cutoff]["minimum"],
                    "maximum": primary_wilson[cutoff]["maximum"],
                }
                for cutoff in ("1", "2")
            },
            "ground_energies": primary_energies,
            "spectator_channel_firing_control": primary_firing,
            "primary_continuum_claim": primary["continuum_claim"],
            "independent_continuum_claim": independent.get("continuum_claim"),
        },
        "fixed_graph_cutoff_form": {
            "classification": "DERIVED_FIXED_FINITE_GRAPH",
            "primary_status": cutoff_form_primary["finite_graph_status"],
            "primary_checks_passed": cutoff_form_primary["checks_passed"],
            "primary_checks_total": cutoff_form_primary["checks_total"],
            "independent_status": cutoff_form_independent["finite_graph_status"],
            "independent_checks_passed": cutoff_form_independent["checks_passed"],
            "independent_checks_total": cutoff_form_independent["checks_total"],
            "tail_rows_passed": cutoff_primary_spectrum["tail_passed"],
            "tail_rows_attempted": cutoff_primary_spectrum["tail_attempted"],
            "ritz_rows_passed": cutoff_primary_spectrum["ritz_passed"],
            "ritz_rows_applicable": cutoff_primary_spectrum["ritz_applicable"],
            "continuum_hypotheses_present": False,
            "clay_verdict": "NULL",
        },
        "cutoff_tail_evidence": {
            "qualifications": primary["cutoff_qualifications"],
            "useful_tail_rows": primary["useful_tail_rows"],
            "classification": "INCONCLUSIVE",
        },
        "excluded_provenance": {
            "classification": "EXCLUDED_SPECTATOR_CHANNEL_DEFECT",
            "reason": "edge-only plaquette support omits remote spectator-intertwiner Kronecker deltas",
            "primary_receipt": {
                "path": display_path(EXCLUDED_PRIMARY_RECEIPT),
                "sha256": hashes["excluded_primary_receipt"],
                "bytes": EXCLUDED_PRIMARY_RECEIPT.stat().st_size,
            },
            "independent_receipt": {
                "path": display_path(EXCLUDED_INDEPENDENT_RECEIPT),
                "sha256": hashes["excluded_independent_receipt"],
                "bytes": EXCLUDED_INDEPENDENT_RECEIPT.stat().st_size,
            },
        },
        "audit_checks": checks,
        "audit_checks_passed": sum(row["passed"] for row in checks),
        "audit_checks_total": len(checks),
        "conditional_gap_target": {
            "regulated_identity": "Delta_phys(a,L) = (g^2/(2a)) lambda_gi(mu_(a,L))",
            "sufficient_physical_bound": "inf_(a,L) (g_L^2/(2a_L)) (chi_(a,L) C_L^2)^(-1) >= m_* > 0",
            "unproved_inputs": [
                "uniform interacting fibre and coarse Poincare margins",
                "uniform transport-score or mixed-Hessian bounds",
                "graph-size-, weak-coupling-, and lattice-spacing-uniform character-cutoff control",
                "thermodynamic control",
            ],
        },
        "regime_check": {
            "strong_coupling_condition": "64/g^4 <= beta_Y",
            "equivalent_dimensionless_condition": "32 x <= beta_Y for x=2/g^4",
            "continuum_asymptotic_freedom": "g(a)->0, hence x(a)->infinity",
            "conclusion": "the proved strong-coupling region does not cover the continuum trajectory",
        },
        "infrared_countercheck": {
            "observable": "lambda_N = 4 sin(pi/(2(N+1)))",
            "values": {
                f"N={size}": 4.0 * math.sin(math.pi / (2.0 * (size + 1)))
                for size in (16, 64, 256, 1024)
            },
            "conclusion": "positive local conditional rates alone do not imply a volume-uniform global gap",
        },
        "missing_clay_obligations": MISSING_CLAY_OBLIGATIONS,
        "claim_boundary": "The recovered receipts establish a finite 3x2x2 SU(2) regulated Hamiltonian construction, and the form theorem removes the character cutoff after the graph, coupling and low-energy index are fixed. Its constants are not uniform in graph size, weak coupling or lattice spacing, and no continuum Yang-Mills construction or regulator-independent mass-gap theorem is supplied.",
    }

    if not all_passed:
        failed = [row["name"] for row in checks if not row["passed"]]
        raise RuntimeError(f"continuum boundary audit failed: {failed}")
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and not replace:
        raise FileExistsError(f"refusing to overwrite existing receipt: {output}")
    temporary = output.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    record = run(args.output, args.replace)
    print(
        f"status={record['status']} verdict={record['verdict']} "
        f"checks={record['audit_checks_passed']}/{record['audit_checks_total']}"
    )
    print(
        "finite="
        f"{record['finite_evidence']['finite_checks_passed']}/"
        f"{record['finite_evidence']['finite_checks_total']} "
        "independent="
        f"{record['finite_evidence']['independent_checks_passed']}/"
        f"{record['finite_evidence']['independent_checks_total']} "
        f"tails={record['cutoff_tail_evidence']['classification']}"
    )


if __name__ == "__main__":
    main()
