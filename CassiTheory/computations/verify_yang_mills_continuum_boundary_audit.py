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
LOCAL_CUTOFF_PROTOCOL = (
    ROOT / "computations" / "yang-mills-local-cutoff-density-prereg.md"
)
LOCAL_CUTOFF_PRIMARY_SOURCE = (
    ROOT / "computations" / "verify_yang_mills_local_cutoff_density.py"
)
LOCAL_CUTOFF_INDEPENDENT_SOURCE = (
    ROOT / "computations" / "verify_yang_mills_local_cutoff_density_independent.mjs"
)
LOCAL_CUTOFF_PRIMARY_RECEIPT = (
    ROOT / "runs" / "yang_mills_local_cutoff_density" / "verification.json"
)
LOCAL_CUTOFF_INDEPENDENT_RECEIPT = (
    ROOT
    / "runs"
    / "yang_mills_local_cutoff_density"
    / "verification-independent.json"
)
THERMODYNAMIC_PROTOCOL = (
    ROOT / "computations" / "yang-mills-thermodynamic-ground-state-prereg.md"
)
THERMODYNAMIC_PRIMARY_SOURCE = (
    ROOT / "computations" / "verify_yang_mills_thermodynamic_ground_state.py"
)
THERMODYNAMIC_INDEPENDENT_SOURCE = (
    ROOT
    / "computations"
    / "verify_yang_mills_thermodynamic_ground_state_independent.mjs"
)
THERMODYNAMIC_PRIMARY_RECEIPT = (
    ROOT / "runs" / "yang_mills_thermodynamic_ground_state" / "verification.json"
)
THERMODYNAMIC_INDEPENDENT_RECEIPT = (
    ROOT
    / "runs"
    / "yang_mills_thermodynamic_ground_state"
    / "verification-independent.json"
)
EUCLIDEAN_PROTOCOL = (
    ROOT / "computations" / "yang-mills-euclidean-reflection-positive-prereg.md"
)
EUCLIDEAN_PRIMARY_SOURCE = (
    ROOT / "computations" / "verify_yang_mills_euclidean_reflection_positive.py"
)
EUCLIDEAN_INDEPENDENT_SOURCE = (
    ROOT
    / "computations"
    / "verify_yang_mills_euclidean_reflection_positive_independent.mjs"
)
EUCLIDEAN_PRIMARY_RECEIPT = (
    ROOT
    / "runs"
    / "yang_mills_euclidean_reflection_positive"
    / "verification.json"
)
EUCLIDEAN_INDEPENDENT_RECEIPT = (
    ROOT
    / "runs"
    / "yang_mills_euclidean_reflection_positive"
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
    "continuum Osterwalder-Schrader axioms, Euclidean covariance restoration, and Wightman reconstruction",
    "renormalized local gauge-invariant field content with the required short-distance behavior",
    "uniform weak-coupling estimates along a->0",
    "full-sequence thermodynamic phase control, uniqueness, and clustering",
    "lattice-spacing-uniform interacting estimates beyond fixed-support character tails",
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
        LOCAL_CUTOFF_PROTOCOL,
        LOCAL_CUTOFF_PRIMARY_SOURCE,
        LOCAL_CUTOFF_INDEPENDENT_SOURCE,
        LOCAL_CUTOFF_PRIMARY_RECEIPT,
        LOCAL_CUTOFF_INDEPENDENT_RECEIPT,
        THERMODYNAMIC_PROTOCOL,
        THERMODYNAMIC_PRIMARY_SOURCE,
        THERMODYNAMIC_INDEPENDENT_SOURCE,
        THERMODYNAMIC_PRIMARY_RECEIPT,
        THERMODYNAMIC_INDEPENDENT_RECEIPT,
        EUCLIDEAN_PROTOCOL,
        EUCLIDEAN_PRIMARY_SOURCE,
        EUCLIDEAN_INDEPENDENT_SOURCE,
        EUCLIDEAN_PRIMARY_RECEIPT,
        EUCLIDEAN_INDEPENDENT_RECEIPT,
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
    local_cutoff_primary = load_json(LOCAL_CUTOFF_PRIMARY_RECEIPT)
    local_cutoff_independent = load_json(LOCAL_CUTOFF_INDEPENDENT_RECEIPT)
    thermodynamic_primary = load_json(THERMODYNAMIC_PRIMARY_RECEIPT)
    thermodynamic_independent = load_json(THERMODYNAMIC_INDEPENDENT_RECEIPT)
    euclidean_primary = load_json(EUCLIDEAN_PRIMARY_RECEIPT)
    euclidean_independent = load_json(EUCLIDEAN_INDEPENDENT_RECEIPT)

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
        "local_cutoff_protocol": sha256(LOCAL_CUTOFF_PROTOCOL),
        "local_cutoff_primary_source": sha256(LOCAL_CUTOFF_PRIMARY_SOURCE),
        "local_cutoff_independent_source": sha256(LOCAL_CUTOFF_INDEPENDENT_SOURCE),
        "local_cutoff_primary_receipt": sha256(LOCAL_CUTOFF_PRIMARY_RECEIPT),
        "local_cutoff_independent_receipt": sha256(
            LOCAL_CUTOFF_INDEPENDENT_RECEIPT
        ),
        "thermodynamic_protocol": sha256(THERMODYNAMIC_PROTOCOL),
        "thermodynamic_primary_source": sha256(THERMODYNAMIC_PRIMARY_SOURCE),
        "thermodynamic_independent_source": sha256(
            THERMODYNAMIC_INDEPENDENT_SOURCE
        ),
        "thermodynamic_primary_receipt": sha256(THERMODYNAMIC_PRIMARY_RECEIPT),
        "thermodynamic_independent_receipt": sha256(
            THERMODYNAMIC_INDEPENDENT_RECEIPT
        ),
        "euclidean_protocol": sha256(EUCLIDEAN_PROTOCOL),
        "euclidean_primary_source": sha256(EUCLIDEAN_PRIMARY_SOURCE),
        "euclidean_independent_source": sha256(EUCLIDEAN_INDEPENDENT_SOURCE),
        "euclidean_primary_receipt": sha256(EUCLIDEAN_PRIMARY_RECEIPT),
        "euclidean_independent_receipt": sha256(EUCLIDEAN_INDEPENDENT_RECEIPT),
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
    local_primary_summary = local_cutoff_primary.get("local_summary", {})
    check(
        "local cutoff-density primary passes and retains the Clay boundary",
        local_cutoff_primary.get("schema")
        == "cassi.yang_mills_local_cutoff_density.v1"
        and local_cutoff_primary.get("status") == "PASS"
        and local_cutoff_primary.get("local_cutoff_status") == "PASS"
        and local_cutoff_primary.get("checks_passed")
        == local_cutoff_primary.get("checks_total")
        == 16
        and local_primary_summary.get("attempted") == 1536
        and local_primary_summary.get("applicable") == 1152
        and close(local_primary_summary.get("maximum_volume_spread"), 0.0)
        and local_cutoff_primary.get("global_norm_uniformity")
        == "EXCLUDED_BY_PRODUCT_FAMILY"
        and local_cutoff_primary.get("thermodynamic_limit_constructed") is False
        and local_cutoff_primary.get("continuum_hypotheses_present") is False
        and local_cutoff_primary.get("clay_verdict") == "NULL",
        status=local_cutoff_primary.get("status"),
        passed_count=local_cutoff_primary.get("checks_passed"),
        total=local_cutoff_primary.get("checks_total"),
        local_summary=local_primary_summary,
        clay_verdict=local_cutoff_primary.get("clay_verdict"),
    )
    local_independent_summary = local_cutoff_independent.get("local_summary", {})
    check(
        "local cutoff-density independent reconstruction passes",
        local_cutoff_independent.get("schema")
        == "cassi.yang_mills_local_cutoff_density.independent.v1"
        and local_cutoff_independent.get("status") == "PASS"
        and local_cutoff_independent.get("local_cutoff_status") == "PASS"
        and local_cutoff_independent.get("checks_passed")
        == local_cutoff_independent.get("checks_total")
        == 17
        and local_independent_summary.get("attempted") == 1536
        and local_independent_summary.get("applicable") == 1152
        and close(local_independent_summary.get("maximum_primary_difference"), 0.0)
        and local_cutoff_independent.get("global_norm_uniformity")
        == "EXCLUDED_BY_PRODUCT_FAMILY"
        and local_cutoff_independent.get("thermodynamic_limit_constructed")
        is False
        and local_cutoff_independent.get("continuum_hypotheses_present") is False
        and local_cutoff_independent.get("clay_verdict") == "NULL",
        status=local_cutoff_independent.get("status"),
        passed_count=local_cutoff_independent.get("checks_passed"),
        total=local_cutoff_independent.get("checks_total"),
        local_summary=local_independent_summary,
        clay_verdict=local_cutoff_independent.get("clay_verdict"),
    )
    local_primary_inputs = local_cutoff_primary.get("inputs", {})
    local_independent_inputs = local_cutoff_independent.get("inputs", {})
    check(
        "local cutoff protocol sources and primary receipt are hash bound",
        local_primary_inputs.get("protocol", {}).get("sha256")
        == local_independent_inputs.get("protocol", {}).get("sha256")
        == hashes["local_cutoff_protocol"]
        and local_primary_inputs.get("primary_source", {}).get("sha256")
        == local_independent_inputs.get("primary_source", {}).get("sha256")
        == hashes["local_cutoff_primary_source"]
        and local_independent_inputs.get("independent_source", {}).get("sha256")
        == hashes["local_cutoff_independent_source"]
        and local_independent_inputs.get("primary_receipt", {}).get("sha256")
        == hashes["local_cutoff_primary_receipt"],
        protocol_sha256=hashes["local_cutoff_protocol"],
        primary_source_sha256=hashes["local_cutoff_primary_source"],
        independent_source_sha256=hashes["local_cutoff_independent_source"],
        primary_receipt_sha256=hashes["local_cutoff_primary_receipt"],
    )
    local_joint = local_cutoff_primary.get("joint_cutoff_rows", [])
    local_joint_tails = [float(row["local_tail_bound"]) for row in local_joint]
    local_obstruction = local_cutoff_primary.get("global_obstruction", {})
    local_firing = local_obstruction.get("firing_control", {})
    check(
        "local auxiliary schedule and global-norm firing control pass",
        len(local_joint) == 7
        and all(
            close(row["cutoff_squared_over_x"], float(row["scale_k"]) ** 2)
            for row in local_joint
        )
        and all(
            right < left
            for left, right in zip(local_joint_tails, local_joint_tails[1:])
        )
        and len(local_obstruction.get("rows", [])) == 180
        and local_firing.get("q") == 0.5
        and local_firing.get("cutoff_C") == 2
        and local_firing.get("loops_N") == 512
        and local_firing.get("discarded_global_norm_sq", 0.0) > 0.999,
        joint_rows=len(local_joint),
        joint_tail_bounds=local_joint_tails,
        obstruction_rows=len(local_obstruction.get("rows", [])),
        firing_control=local_firing,
    )
    check(
        "thermodynamic primary passes with the conditional premise boundary",
        thermodynamic_primary.get("schema")
        == "cassi.yang_mills_thermodynamic_ground_state.v1"
        and thermodynamic_primary.get("status") == "PASS"
        and thermodynamic_primary.get("classification")
        == "FINITE_IDENTITY_SUPPORT_FOR_CONDITIONAL_THERMODYNAMIC_BRIDGE"
        and thermodynamic_primary.get("conditional_thermodynamic_bridge_status")
        == "PASS"
        and thermodynamic_primary.get("checks_passed")
        == thermodynamic_primary.get("checks_total")
        == 18
        and thermodynamic_primary.get("operator_argument_scope")
        == "CONDITIONAL_ON_FINITE_VOLUME_GROUND_DENSITIES_AND_YMT2"
        and thermodynamic_primary.get("finite_volume_setup_proved_by_verifier")
        is False
        and thermodynamic_primary.get("uniform_tail_bound_proved_by_verifier")
        is False
        and thermodynamic_primary.get(
            "thermodynamic_state_constructed_by_verifier"
        )
        is False
        and thermodynamic_primary.get("uniform_mass_gap_established") is False
        and thermodynamic_primary.get("continuum_hypotheses_present") is False
        and thermodynamic_primary.get("clay_verdict") == "NULL",
        status=thermodynamic_primary.get("status"),
        classification=thermodynamic_primary.get("classification"),
        passed_count=thermodynamic_primary.get("checks_passed"),
        total=thermodynamic_primary.get("checks_total"),
        operator_argument_scope=thermodynamic_primary.get(
            "operator_argument_scope"
        ),
    )
    check(
        "thermodynamic independent reconstruction retains the same boundary",
        thermodynamic_independent.get("schema")
        == "cassi.yang_mills_thermodynamic_ground_state.independent.v1"
        and thermodynamic_independent.get("status") == "PASS"
        and thermodynamic_independent.get("classification")
        == "FINITE_IDENTITY_SUPPORT_FOR_CONDITIONAL_THERMODYNAMIC_BRIDGE"
        and thermodynamic_independent.get(
            "conditional_thermodynamic_bridge_status"
        )
        == "PASS"
        and thermodynamic_independent.get("checks_passed")
        == thermodynamic_independent.get("checks_total")
        == 19
        and thermodynamic_independent.get("operator_argument_scope")
        == "CONDITIONAL_ON_FINITE_VOLUME_GROUND_DENSITIES_AND_YMT2"
        and thermodynamic_independent.get(
            "finite_volume_setup_proved_by_verifier"
        )
        is False
        and thermodynamic_independent.get(
            "uniform_tail_bound_proved_by_verifier"
        )
        is False
        and thermodynamic_independent.get(
            "thermodynamic_state_constructed_by_verifier"
        )
        is False
        and thermodynamic_independent.get("uniform_mass_gap_established")
        is False
        and thermodynamic_independent.get("continuum_hypotheses_present")
        is False
        and thermodynamic_independent.get("clay_verdict") == "NULL",
        status=thermodynamic_independent.get("status"),
        classification=thermodynamic_independent.get("classification"),
        passed_count=thermodynamic_independent.get("checks_passed"),
        total=thermodynamic_independent.get("checks_total"),
    )
    thermodynamic_primary_inputs = thermodynamic_primary.get("inputs", {})
    thermodynamic_independent_inputs = thermodynamic_independent.get("inputs", {})
    check(
        "thermodynamic protocol sources and receipts are hash bound",
        thermodynamic_primary_inputs.get("protocol", {}).get("sha256")
        == thermodynamic_independent_inputs.get("protocol", {}).get("sha256")
        == hashes["thermodynamic_protocol"]
        and thermodynamic_primary_inputs.get("primary_source", {}).get("sha256")
        == thermodynamic_independent_inputs.get("primary_source", {}).get(
            "sha256"
        )
        == hashes["thermodynamic_primary_source"]
        and thermodynamic_independent_inputs.get("independent_source", {}).get(
            "sha256"
        )
        == hashes["thermodynamic_independent_source"]
        and thermodynamic_independent_inputs.get("primary_receipt", {}).get(
            "sha256"
        )
        == hashes["thermodynamic_primary_receipt"]
        and thermodynamic_primary_inputs.get("local_primary_receipt", {}).get(
            "sha256"
        )
        == thermodynamic_independent_inputs.get(
            "local_primary_receipt", {}
        ).get("sha256")
        == hashes["local_cutoff_primary_receipt"],
        protocol_sha256=hashes["thermodynamic_protocol"],
        primary_source_sha256=hashes["thermodynamic_primary_source"],
        independent_source_sha256=hashes["thermodynamic_independent_source"],
        primary_receipt_sha256=hashes["thermodynamic_primary_receipt"],
    )
    thermodynamic_comparisons = thermodynamic_independent.get("comparisons", {})
    thermodynamic_rank = thermodynamic_comparisons.get("rank", {})
    thermodynamic_compactness = thermodynamic_comparisons.get("compactness", {})
    thermodynamic_ground = thermodynamic_comparisons.get("ground", {})
    check(
        "thermodynamic rank compactness and ground schedules reconstruct",
        len(thermodynamic_primary.get("rank_rows", [])) == 36
        and len(thermodynamic_independent.get("rank_rows", [])) == 36
        and len(thermodynamic_primary.get("compactness_rows", [])) == 100
        and len(thermodynamic_independent.get("compactness_rows", [])) == 100
        and len(thermodynamic_primary.get("ground_identity_rows", [])) == 12
        and len(thermodynamic_independent.get("ground_identity_rows", [])) == 12
        and max(
            row["cutoff_search"]
            for row in thermodynamic_primary.get("compactness_rows", [])
        )
        == 4095
        and thermodynamic_rank.get("keys_match") is True
        and thermodynamic_rank.get("exact_match") is True
        and close(thermodynamic_rank.get("maximum_difference"), 0.0)
        and thermodynamic_compactness.get("keys_match") is True
        and thermodynamic_compactness.get("exact_match") is True
        and close(thermodynamic_compactness.get("maximum_difference"), 0.0)
        and thermodynamic_ground.get("keys_match") is True
        and thermodynamic_ground.get("exact_match") is True
        and thermodynamic_ground.get("maximum_difference", 1.0) < 1.0e-12,
        primary_rank_rows=len(thermodynamic_primary.get("rank_rows", [])),
        primary_compactness_rows=len(
            thermodynamic_primary.get("compactness_rows", [])
        ),
        primary_ground_rows=len(
            thermodynamic_primary.get("ground_identity_rows", [])
        ),
        comparisons={
            "rank": thermodynamic_rank,
            "compactness": thermodynamic_compactness,
            "ground": thermodynamic_ground,
        },
    )
    thermodynamic_firing = thermodynamic_primary.get("firing_controls", {})
    thermodynamic_alternating = thermodynamic_firing.get(
        "alternating_sequence", {}
    )
    thermodynamic_escape = thermodynamic_firing.get("escaping_sector_rows", [])
    thermodynamic_gaps = thermodynamic_firing.get("ferromagnetic_gap_rows", [])
    thermodynamic_premise = next(
        (
            row
            for row in thermodynamic_primary.get("checks", [])
            if row.get("name") == "analytic_input_boundary"
        ),
        {},
    )
    check(
        "thermodynamic implication controls fire and premises stay explicit",
        thermodynamic_premise.get("passed") is True
        and thermodynamic_premise.get("measured", {}).get(
            "finite_volume_ground_densities"
        )
        == "ANALYTIC_INPUT_NOT_CONSTRUCTED_BY_VERIFIER"
        and thermodynamic_premise.get("measured", {}).get(
            "uniform_tail_bound_YMT2"
        )
        == "ANALYTIC_INPUT_NOT_PROVED_BY_VERIFIER"
        and thermodynamic_alternating.get("even_odd_trace_distance") == 2.0
        and thermodynamic_alternating.get("full_sequence_converges") is False
        and len(thermodynamic_escape) == 35
        and sum(row.get("tail_mass") == 1.0 for row in thermodynamic_escape)
        == 25
        and len(thermodynamic_gaps) == 7
        and all(
            right["one_magnon_gap_upper_bound"]
            < left["one_magnon_gap_upper_bound"]
            for left, right in zip(thermodynamic_gaps, thermodynamic_gaps[1:])
        )
        and thermodynamic_gaps[-1]["one_magnon_gap_upper_bound"] < 1.0e-3,
        premise=thermodynamic_premise.get("measured"),
        alternating=thermodynamic_alternating,
        escaping_rows=len(thermodynamic_escape),
        escaping_tail_rows=sum(
            row.get("tail_mass") == 1.0 for row in thermodynamic_escape
        ),
        terminal_gap_bound=(
            thermodynamic_gaps[-1]["one_magnon_gap_upper_bound"]
            if thermodynamic_gaps
            else None
        ),
    )



    check(
        "Euclidean reflection primary and independent receipts pass",
        euclidean_primary.get("schema")
        == "cassi.yang-mills.euclidean-reflection-positive.v1"
        and euclidean_primary.get("verdict") == "PASS"
        and euclidean_primary.get("fixed_regulator_euclidean_support") == "PASS"
        and euclidean_primary.get("summary", {}).get("rows") == 36
        and euclidean_primary.get("summary", {}).get("checks") == 308
        and euclidean_primary.get("summary", {}).get("passed") == 308
        and euclidean_primary.get("summary", {}).get("failed") == 0
        and euclidean_independent.get("schema")
        == "cassi.yang-mills.euclidean-reflection-positive.independent.v1"
        and euclidean_independent.get("verdict") == "PASS"
        and euclidean_independent.get("summary", {}).get("rows_reconstructed")
        == 36
        and euclidean_independent.get("summary", {}).get("checks") == 22
        and euclidean_independent.get("summary", {}).get("passed") == 22
        and euclidean_independent.get("summary", {}).get("failed") == 0,
        primary_summary=euclidean_primary.get("summary"),
        independent_summary=euclidean_independent.get("summary"),
    )
    check(
        "Euclidean reflection protocol sources and primary receipt are hash bound",
        euclidean_primary.get("protocol_sha256") == hashes["euclidean_protocol"]
        and euclidean_independent.get("protocol_sha256")
        == hashes["euclidean_protocol"]
        and euclidean_primary.get("source_sha256")
        == hashes["euclidean_primary_source"]
        and euclidean_independent.get("primary_source_sha256")
        == hashes["euclidean_primary_source"]
        and euclidean_independent.get("independent_source_sha256")
        == hashes["euclidean_independent_source"]
        and euclidean_independent.get("primary_receipt_sha256")
        == hashes["euclidean_primary_receipt"],
        protocol_sha256=hashes["euclidean_protocol"],
        primary_source_sha256=hashes["euclidean_primary_source"],
        independent_source_sha256=hashes["euclidean_independent_source"],
        primary_receipt_sha256=hashes["euclidean_primary_receipt"],
    )
    euclidean_rows = euclidean_primary.get("rows", [])
    euclidean_independent_rows = euclidean_independent.get("rows", [])
    check(
        "Euclidean reflection schedules and finite rows reconstruct",
        euclidean_primary.get("schedule", {}).get("beta_values")
        == [0.25, 1.0, 4.0, 16.0]
        and euclidean_primary.get("schedule", {}).get("character_cutoffs")
        == [4, 8, 16]
        and euclidean_primary.get("schedule", {}).get("sample_counts")
        == [8, 12, 16]
        and len(euclidean_rows) == 36
        and all(
            len(row.get("checks", [])) == 8
            and all(item.get("passed") is True for item in row.get("checks", []))
            for row in euclidean_rows
        )
        and len(euclidean_independent_rows) == 36
        and all(row.get("checks_passed") == 8 for row in euclidean_independent_rows)
        and euclidean_primary.get("haar_fixture", {}).get(
            "maximum_relative_error", 1.0
        )
        <= 1.0e-9
        and euclidean_independent.get("haar_fixture", {}).get(
            "maximum_relative_error", 1.0
        )
        <= 1.0e-9,
        primary_rows=len(euclidean_rows),
        independent_rows=len(euclidean_independent_rows),
        primary_haar_relative_error=euclidean_primary.get(
            "haar_fixture", {}
        ).get("maximum_relative_error"),
        independent_haar_relative_error=euclidean_independent.get(
            "haar_fixture", {}
        ).get("maximum_relative_error"),
    )
    euclidean_inputs = euclidean_primary.get("analytic_inputs", {})
    euclidean_boundaries = euclidean_primary.get("boundaries", {})
    euclidean_independent_boundaries = euclidean_independent.get("boundaries", {})
    euclidean_negative = euclidean_primary.get("negative_coefficient_fixture", {})
    euclidean_asymmetric = euclidean_primary.get("asymmetric_kernel_fixture", {})
    euclidean_alternating = euclidean_primary.get(
        "alternating_sequence_fixture", {}
    )
    euclidean_gaps = euclidean_primary.get("collapsing_gap_fixture", {})
    check(
        "Euclidean analytic premises and implication controls stay explicit",
        euclidean_inputs.get("finite_torus_wilson_reflection_positivity") is True
        and euclidean_inputs.get("finite_spatial_volume_positive_transfer")
        is True
        and euclidean_inputs.get("compact_group_finite_range_gibbs_compactness")
        is True
        and euclidean_inputs.get(
            "executable_proof_of_geometric_reflection_factorization"
        )
        is False
        and euclidean_inputs.get("infinite_volume_measure_constructed_by_verifier")
        is False
        and euclidean_negative.get("passed") is True
        and euclidean_negative.get("minimum_eigenvalue", 0.0) < -1.0
        and euclidean_asymmetric.get("passed") is True
        and euclidean_alternating.get("passed") is True
        and euclidean_gaps.get("passed") is True
        and euclidean_gaps.get("rows", [])[-1].get("gap", 1.0) < 1.0e-3
        and euclidean_boundaries == euclidean_independent_boundaries
        and euclidean_boundaries.get("full_sequence_convergence_established")
        is False
        and euclidean_boundaries.get("uniqueness_established") is False
        and euclidean_boundaries.get("clustering_established") is False
        and euclidean_boundaries.get(
            "anisotropic_hamiltonian_equivalence_established"
        )
        is False
        and euclidean_boundaries.get("continuum_limit_established") is False
        and euclidean_boundaries.get("wightman_reconstruction_established")
        is False
        and euclidean_boundaries.get("uniform_mass_gap_established") is False
        and euclidean_boundaries.get("clay_verdict") == "NULL",
        analytic_inputs=euclidean_inputs,
        boundaries=euclidean_boundaries,
        negative_minimum_eigenvalue=euclidean_negative.get("minimum_eigenvalue"),
        terminal_gap=(
            euclidean_gaps.get("rows", [])[-1].get("gap")
            if euclidean_gaps.get("rows")
            else None
        ),
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
        "theory separates fixed-regulator Euclidean support from the open Clay target",
        "Fixed-graph character-cutoff form theorem (YM187)–(YM195) | **Derived**"
        in theory
        and "Volume-uniform local cutoff density and global-norm obstruction "
        "(YM196)–(YM205) | **Derived**"
        in theory
        and "Fixed-regulator thermodynamic ground-state subsequence "
        "(YM206)–(YM213) | **Derived conditional**"
        in theory
        and "Fixed-regulator Euclidean reflection-positive Gibbs subsequence "
        "(YM214)–(YM222) | **Derived conditional**"
        in theory
        and "`thermodynamic_state_constructed_by_verifier=false`" in theory
        and "`infinite_volume_measure_constructed_by_verifier=false`" in theory
        and "`clay_verdict=NULL`" in theory
        and "Continuum Yang–Mills existence and mass gap | **Open**" in theory,
    )

    if len(checks) != 38:
        raise RuntimeError(f"expected 38 audit checks, constructed {len(checks)}")
    all_passed = all(row["passed"] for row in checks)
    record: dict[str, Any] = {
        "schema": "yang_mills_continuum_boundary_audit_v6",
        "status": "PASS" if all_passed else "FAIL",
        "verdict": "UNRESOLVED_CONTINUUM_PROBLEM",
        "clay_verdict": "NULL",
        "scope": "Hash-bound audit of recovered finite SU(2) Hamiltonian evidence, fixed-graph and local cutoff control, conditional thermodynamic finite-identity evidence, and fixed-regulator Euclidean reflection support against the Clay Yang-Mills existence and mass-gap obligations",
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
            "local_cutoff_protocol": {
                "path": display_path(LOCAL_CUTOFF_PROTOCOL),
                "sha256": hashes["local_cutoff_protocol"],
            },
            "local_cutoff_primary_source": {
                "path": display_path(LOCAL_CUTOFF_PRIMARY_SOURCE),
                "sha256": hashes["local_cutoff_primary_source"],
            },
            "local_cutoff_independent_source": {
                "path": display_path(LOCAL_CUTOFF_INDEPENDENT_SOURCE),
                "sha256": hashes["local_cutoff_independent_source"],
            },
            "local_cutoff_primary_receipt": {
                "path": display_path(LOCAL_CUTOFF_PRIMARY_RECEIPT),
                "sha256": hashes["local_cutoff_primary_receipt"],
                "bytes": LOCAL_CUTOFF_PRIMARY_RECEIPT.stat().st_size,
            },
            "local_cutoff_independent_receipt": {
                "path": display_path(LOCAL_CUTOFF_INDEPENDENT_RECEIPT),
                "sha256": hashes["local_cutoff_independent_receipt"],
                "bytes": LOCAL_CUTOFF_INDEPENDENT_RECEIPT.stat().st_size,
            },
            "thermodynamic_protocol": {
                "path": display_path(THERMODYNAMIC_PROTOCOL),
                "sha256": hashes["thermodynamic_protocol"],
            },
            "thermodynamic_primary_source": {
                "path": display_path(THERMODYNAMIC_PRIMARY_SOURCE),
                "sha256": hashes["thermodynamic_primary_source"],
            },
            "thermodynamic_independent_source": {
                "path": display_path(THERMODYNAMIC_INDEPENDENT_SOURCE),
                "sha256": hashes["thermodynamic_independent_source"],
            },
            "thermodynamic_primary_receipt": {
                "path": display_path(THERMODYNAMIC_PRIMARY_RECEIPT),
                "sha256": hashes["thermodynamic_primary_receipt"],
                "bytes": THERMODYNAMIC_PRIMARY_RECEIPT.stat().st_size,
            },
            "thermodynamic_independent_receipt": {
                "path": display_path(THERMODYNAMIC_INDEPENDENT_RECEIPT),
                "sha256": hashes["thermodynamic_independent_receipt"],
                "bytes": THERMODYNAMIC_INDEPENDENT_RECEIPT.stat().st_size,
            },
            "euclidean_protocol": {
                "path": display_path(EUCLIDEAN_PROTOCOL),
                "sha256": hashes["euclidean_protocol"],
            },
            "euclidean_primary_source": {
                "path": display_path(EUCLIDEAN_PRIMARY_SOURCE),
                "sha256": hashes["euclidean_primary_source"],
            },
            "euclidean_independent_source": {
                "path": display_path(EUCLIDEAN_INDEPENDENT_SOURCE),
                "sha256": hashes["euclidean_independent_source"],
            },
            "euclidean_primary_receipt": {
                "path": display_path(EUCLIDEAN_PRIMARY_RECEIPT),
                "sha256": hashes["euclidean_primary_receipt"],
                "bytes": EUCLIDEAN_PRIMARY_RECEIPT.stat().st_size,
            },
            "euclidean_independent_receipt": {
                "path": display_path(EUCLIDEAN_INDEPENDENT_RECEIPT),
                "sha256": hashes["euclidean_independent_receipt"],
                "bytes": EUCLIDEAN_INDEPENDENT_RECEIPT.stat().st_size,
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
        "local_cutoff_density": {
            "classification": "DERIVED_VOLUME_UNIFORM_FIXED_SUPPORT",
            "global_norm_uniformity": "EXCLUDED_BY_PRODUCT_FAMILY",
            "primary_status": local_cutoff_primary["local_cutoff_status"],
            "primary_checks_passed": local_cutoff_primary["checks_passed"],
            "primary_checks_total": local_cutoff_primary["checks_total"],
            "independent_status": local_cutoff_independent["local_cutoff_status"],
            "independent_checks_passed": local_cutoff_independent["checks_passed"],
            "independent_checks_total": local_cutoff_independent["checks_total"],
            "local_rows_attempted": local_primary_summary["attempted"],
            "local_rows_applicable": local_primary_summary["applicable"],
            "maximum_volume_spread": local_primary_summary[
                "maximum_volume_spread"
            ],
            "joint_cutoff_rows": len(local_joint),
            "global_obstruction_rows": len(local_obstruction["rows"]),
            "firing_control": local_firing,
            "thermodynamic_limit_constructed": False,
            "continuum_hypotheses_present": False,
            "clay_verdict": "NULL",
        },
        "thermodynamic_ground_state_bridge": {
            "classification": thermodynamic_primary["classification"],
            "operator_argument_scope": thermodynamic_primary[
                "operator_argument_scope"
            ],
            "primary_status": thermodynamic_primary["status"],
            "primary_checks_passed": thermodynamic_primary["checks_passed"],
            "primary_checks_total": thermodynamic_primary["checks_total"],
            "independent_status": thermodynamic_independent["status"],
            "independent_checks_passed": thermodynamic_independent[
                "checks_passed"
            ],
            "independent_checks_total": thermodynamic_independent["checks_total"],
            "rank_rows": len(thermodynamic_primary["rank_rows"]),
            "compactness_rows": len(thermodynamic_primary["compactness_rows"]),
            "synthetic_ground_identity_rows": len(
                thermodynamic_primary["ground_identity_rows"]
            ),
            "maximum_selected_cutoff": max(
                row["cutoff_search"]
                for row in thermodynamic_primary["compactness_rows"]
            ),
            "finite_volume_setup_proved_by_verifier": False,
            "uniform_tail_bound_proved_by_verifier": False,
            "thermodynamic_state_constructed_by_verifier": False,
            "full_sequence_convergence_established": False,
            "uniform_mass_gap_established": False,
            "continuum_hypotheses_present": False,
            "clay_verdict": "NULL",
        },
        "euclidean_reflection_bridge": {
            "classification": "CONDITIONAL_FIXED_REGULATOR_EUCLIDEAN_GIBBS_SUBSEQUENCE",
            "primary_status": euclidean_primary["fixed_regulator_euclidean_support"],
            "primary_checks_passed": euclidean_primary["summary"]["passed"],
            "primary_checks_total": euclidean_primary["summary"]["checks"],
            "independent_status": euclidean_independent["verdict"],
            "independent_checks_passed": euclidean_independent["summary"]["passed"],
            "independent_checks_total": euclidean_independent["summary"]["checks"],
            "rows": len(euclidean_primary["rows"]),
            "primary_maximum_haar_relative_error": euclidean_primary[
                "haar_fixture"
            ]["maximum_relative_error"],
            "independent_maximum_haar_relative_error": euclidean_independent[
                "haar_fixture"
            ]["maximum_relative_error"],
            "finite_volume_reflection_positivity_analytic_input": True,
            "finite_volume_positive_transfer_analytic_input": True,
            "infinite_volume_measure_constructed_by_verifier": False,
            "full_sequence_convergence_established": False,
            "uniqueness_established": False,
            "clustering_established": False,
            "continuum_limit_established": False,
            "wightman_reconstruction_established": False,
            "uniform_mass_gap_established": False,
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
                "weak-coupling- and lattice-spacing-uniform interacting estimates",
                "full-sequence thermodynamic phase control, uniqueness, and clustering",
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
        "claim_boundary": "The recovered receipts establish a finite 3x2x2 SU(2) regulated Hamiltonian construction; the form theorem removes the character cutoff after the graph, coupling and low-energy index are fixed; and the local-density theorem controls every fixed support uniformly over periodic cubic volumes. Conditional on finite-volume ground densities and YMT2, the operator argument extracts a locally normal fixed-regulator ground-state subsequence. Conditional on the established finite-lattice Wilson reflection and transfer theorems, compact local Euclidean marginals extract a reflection-positive DLR subsequence at every fixed beta. The executable evidence checks finite identities, kernels and implication controls; it constructs no infinite-volume Hamiltonian or Euclidean state directly. Full-sequence phase control, clustering, weak-coupling continuum construction, continuum Osterwalder-Schrader reconstruction and a regulator-independent mass-gap theorem remain open.",
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
        f"tails={record['cutoff_tail_evidence']['classification']} "
        "local="
        f"{record['local_cutoff_density']['primary_checks_passed']}/"
        f"{record['local_cutoff_density']['primary_checks_total']} "
        "thermodynamic="
        f"{record['thermodynamic_ground_state_bridge']['primary_checks_passed']}/"
        f"{record['thermodynamic_ground_state_bridge']['primary_checks_total']} "
        "euclidean="
        f"{record['euclidean_reflection_bridge']['primary_checks_passed']}/"
        f"{record['euclidean_reflection_bridge']['primary_checks_total']}"
    )


if __name__ == "__main__":
    main()
