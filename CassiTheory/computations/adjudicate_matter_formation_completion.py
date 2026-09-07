#!/usr/bin/env python3
"""Adjudicate the complete matter-formation claim from frozen receipts.

Run from the repository root:
    python computations/adjudicate_matter_formation_completion.py

This is a deterministic synthesis step. It does not fit a model or run a new
physics calculation; it checks the independently verified conditional baryon
benchmark against the six physical-completion requirements registered in
``foundations/matter-completion-boundary.md`` §12.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import traceback
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PRIMARY = ROOT / "runs" / "20260907_matter_formation_conditional_baryon" / "results.json"
DEFAULT_VERIFICATION = (
    ROOT
    / "runs"
    / "20260907_matter_formation_conditional_baryon_verification"
    / "verification.json"
)
DEFAULT_OUTPUT = ROOT / "runs" / "20260907_matter_formation_completion_adjudication"
SCHEMA = "matter-formation-completion-adjudication-v1"
EXPECTED_BENCHMARK_VERDICT = (
    "ADOPT—Mapped conditional leading colour-neutral chiral baryon benchmark"
)
EXPECTED_LIMITATIONS = [
    "added effective field and action rather than a canonical Cassi derivation",
    "two measured masses fix the two action coefficients",
    "FR character and charge rule are supplied analytic model inputs",
    "no quantum vacuum, density operator, regulator, or renormalization",
    "no canonical Cassi coupling, stress exchange, or general interaction normalization",
    "no infinite-domain, nonradial, or degree-zero creation result",
    "no QCD, colour-confinement, baryogenesis, nuclear-binding, or chemistry derivation",
    "one or more absolute out-of-fit nucleon observables miss the precision threshold",
]


class AdjudicationError(RuntimeError):
    """Typed failure of the receipt or adjudication contract."""


def raw_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relpath(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise AdjudicationError(f"missing input: {relpath(path)}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AdjudicationError(f"JSON root is not an object: {relpath(path)}")
    return value


def prepare_output(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise AdjudicationError(f"output directory is not empty: {path}")
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AdjudicationError(message)


def validate_receipts(
    primary_path: Path,
    verification_path: Path,
    primary: dict[str, Any],
    verification: dict[str, Any],
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, detail: Any) -> None:
        checks.append({"name": name, "pass": bool(passed), "detail": detail})

    check(
        "primary_schema",
        primary.get("schema") == "matter-formation-conditional-baryon-v2",
        primary.get("schema"),
    )
    check("primary_qualified", primary.get("qualified") is True, primary.get("qualified"))
    check(
        "primary_verdict",
        primary.get("scientific_verdict") == EXPECTED_BENCHMARK_VERDICT,
        primary.get("scientific_verdict"),
    )
    check(
        "primary_limitations_exact",
        primary.get("limitations") == EXPECTED_LIMITATIONS,
        primary.get("limitations"),
    )
    check(
        "primary_radial_relaxation",
        primary.get("radial_relaxation", {}).get("pass") is True,
        primary.get("radial_relaxation", {}).get("gates"),
    )
    check(
        "precision_discriminator_contradiction",
        primary.get("verdicts", {}).get("precision_nucleon_observables")
        == "CONTRADICTS—one or more absolute out-of-fit observables miss 10 percent",
        primary.get("verdicts", {}).get("precision_nucleon_observables"),
    )
    check(
        "verification_schema",
        verification.get("schema") == "matter-formation-conditional-baryon-verification-v2",
        verification.get("schema"),
    )
    check(
        "verification_qualified",
        verification.get("qualified") is True,
        verification.get("qualified"),
    )
    check(
        "verification_no_failed_checks",
        verification.get("failed_checks") == [],
        verification.get("failed_checks"),
    )
    check(
        "verification_reproduces_verdict",
        verification.get("reproduced_primary_verdict") == EXPECTED_BENCHMARK_VERDICT,
        verification.get("reproduced_primary_verdict"),
    )
    primary_digest = raw_sha256(primary_path)
    registered_digest = verification.get("identities", {}).get("primary_receipt", {}).get("sha256")
    check(
        "verified_primary_receipt_identity",
        registered_digest == primary_digest,
        {"registered": registered_digest, "actual": primary_digest},
    )
    check_names = [row["name"] for row in checks]
    check(
        "unique_check_names",
        len(check_names) == len(set(check_names)),
        sorted({name for name in check_names if check_names.count(name) > 1}),
    )
    failed = [row["name"] for row in checks if row["pass"] is not True]
    require(not failed, "receipt validation failed: " + ", ".join(failed))
    return checks


def completion_requirements(primary: dict[str, Any]) -> list[dict[str, Any]]:
    calibration = primary["calibration"]
    relaxation = primary["radial_relaxation"]
    particle_map = primary["particle_map"]
    discriminators = primary["empirical_discriminators"]
    contradictory = sorted(
        name
        for name, row in discriminators.items()
        if isinstance(row, dict) and row.get("verdict") == "CONTRADICTS"
    )

    return [
        {
            "requirement": 1,
            "name": "canonical microscopic action and complete conserved stress",
            "status": "UNMET",
            "evidence": (
                "The successful benchmark adds an SU(2) field and Finkelstein–Rubinstein "
                "action instead of deriving them from the canonical Cassi fields; it contains "
                "no canonical coupling, stress exchange, or general interaction normalization."
            ),
        },
        {
            "requirement": 2,
            "name": "regulator-compatible quantum state selection",
            "status": "UNMET",
            "evidence": (
                "The benchmark supplies an odd-degree FR sign but no quantum vacuum, density "
                "operator, regulator, renormalization, or dynamical state-selection rule."
            ),
        },
        {
            "requirement": 3,
            "name": "physical normalization with empirical inputs ledgered",
            "status": "MET_CONDITIONAL",
            "evidence": {
                "method": calibration["label"],
                "fitted_targets_MeV": {
                    "nucleon": calibration["M_N_target_MeV"],
                    "Delta": calibration["M_Delta_target_MeV"],
                },
                "fitted_coefficients": {
                    "e_B": calibration["e_B"],
                    "f_B_MeV": calibration["f_B_MeV"],
                },
                "length_unit_fm": calibration["length_unit_fm"],
                "boundary": (
                    "The two action coefficients are fixed by two measured masses; no canonical "
                    "Cassi normalization, carrier flux, or Q_C identification follows."
                ),
            },
        },
        {
            "requirement": 4,
            "name": "infinite-domain existence and all-sector stability",
            "status": "PARTIAL",
            "evidence": {
                "supported": (
                    "A degree-one stationary hedgehog and conservative radial relaxation pass "
                    "on the finite interval epsilon <= x <= 64."
                ),
                "finite_domain_virial_relative": primary["static"]["finite_domain_virial_relative"],
                "radial_relaxation_pass": relaxation["pass"],
                "open": "No infinite-domain, nonradial, or complete fluctuation result is supplied.",
            },
        },
        {
            "requirement": 5,
            "name": "physically normalized localized production and persistence",
            "status": "PARTIAL",
            "evidence": {
                "supported": (
                    "A prepared, broadened degree-one profile sheds energy and approaches the "
                    "stationary hedgehog while conserving degree."
                ),
                "late_to_initial_inner_excess_ratio": relaxation[
                    "late_to_initial_inner_excess_ratio"
                ],
                "max_total_energy_relative_drift": relaxation[
                    "max_total_energy_relative_drift"
                ],
                "open": (
                    "The run starts in the B=1 sector; it does not create localized matter from "
                    "degree-zero data, measure production rates, or establish a nonradial basin."
                ),
            },
        },
        {
            "requirement": 6,
            "name": "derived particle identity, spin, statistics, and discriminators",
            "status": "PARTIAL",
            "evidence": {
                "conditional_map": particle_map,
                "contradictory_out_of_fit_observables": contradictory,
                "open": (
                    "Spin/statistics and electric charge follow only after supplying the FR and "
                    "charge rules. Several absolute out-of-fit nucleon observables miss 10 percent."
                ),
            },
        },
    ]


def render_record(payload: dict[str, Any]) -> str:
    rows = payload["completion_requirements"]
    lines = [
        "# Matter-formation completion adjudication",
        "",
        f"- Receipt validation: **{'PASS' if payload['receipt_validation_pass'] else 'FAIL'}**",
        f"- Conditional baryon benchmark: **{payload['conditional_benchmark_verdict']}**",
        f"- Complete-mechanism gate: **{payload['complete_mechanism_gate']}**",
        f"- Present matter-formation status: **{payload['matter_formation_status']}**",
        "",
        "| Requirement | Status | Evidence boundary |",
        "|---|---|---|",
    ]
    for row in rows:
        evidence = row["evidence"]
        if isinstance(evidence, dict):
            boundary = str(evidence.get("open") or evidence.get("boundary") or evidence)
        else:
            boundary = evidence
        lines.append(
            f"| {row['requirement']}. {row['name']} | {row['status']} | {boundary} |"
        )
    lines.extend(
        [
            "",
            "The conditional benchmark is a substantive positive endpoint: it supplies a stable "
            "finite-domain radial baryon soliton, mapped nucleon/Delta masses, conditional charge "
            "and spin assignments, out-of-fit discriminators, and real-time relaxation of prepared "
            "degree-one data. It does not select the additional field, action, quantum state, or "
            "particle rules from the canonical Cassi variables.",
            "",
            "Accordingly, the successful conditional benchmark does not satisfy the conjunctive "
            "physical-completion gate. Matter formation remains open at the microscopic selection, "
            "quantum-state, continuum/all-sector stability, degree-zero production, and derived "
            "particle-identification boundaries.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary", type=Path, default=DEFAULT_PRIMARY)
    parser.add_argument("--verification", type=Path, default=DEFAULT_VERIFICATION)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    primary_path = args.primary.resolve()
    verification_path = args.verification.resolve()
    output = args.output_dir.resolve()
    prepare_output(output)

    primary = load_json(primary_path)
    verification = load_json(verification_path)
    receipt_checks = validate_receipts(primary_path, verification_path, primary, verification)
    requirements = completion_requirements(primary)
    complete = all(row["status"] == "MET" for row in requirements)

    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "inputs": {
            "primary": {"path": relpath(primary_path), "sha256": raw_sha256(primary_path)},
            "verification": {
                "path": relpath(verification_path),
                "sha256": raw_sha256(verification_path),
            },
        },
        "receipt_checks": receipt_checks,
        "receipt_validation_pass": True,
        "conditional_benchmark_verdict": EXPECTED_BENCHMARK_VERDICT,
        "completion_requirements": requirements,
        "complete_mechanism_gate": "PASS" if complete else "FAIL",
        "matter_formation_status": "DERIVED" if complete else "HYPOTHESIZED/OPEN",
        "conclusion": (
            "Complete physical matter formation is established."
            if complete
            else (
                "The mapped conditional baryon benchmark is adopted within its declared model; "
                "the complete Cassi matter-formation mechanism remains open."
            )
        ),
    }
    write_json(output / "adjudication.json", payload)
    (output / "completion_record.md").write_text(
        render_record(payload), encoding="utf-8", newline="\n"
    )
    print(
        json.dumps(
            {
                "receipt_validation_pass": payload["receipt_validation_pass"],
                "conditional_benchmark_verdict": payload["conditional_benchmark_verdict"],
                "complete_mechanism_gate": payload["complete_mechanism_gate"],
                "matter_formation_status": payload["matter_formation_status"],
                "requirements": {
                    str(row["requirement"]): row["status"] for row in requirements
                },
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        if not isinstance(exc, AdjudicationError):
            traceback.print_exc()
        raise SystemExit(2)
