from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

SCHEMA = "cassifi.general-intelligence-program.v1"
VERIFY_SCHEMA = "cassifi.general-intelligence-program-verification.v1"
DOMAINS = ("measurement", "temporal", "inventory", "software")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def equal(expected: Any, actual: Any) -> bool:
    if isinstance(expected, float):
        return (
            isinstance(actual, (int, float))
            and not isinstance(actual, bool)
            and math.isclose(float(actual), expected, rel_tol=1e-12, abs_tol=1e-12)
        )
    return expected == actual


def expected_for(row: Mapping[str, Any]) -> Any:
    inputs = row["inputs"]
    domain = row["domain"]
    if domain == "measurement":
        delta = float(inputs["x"]) - float(inputs["y"])
        return (delta > 0.0) - (delta < 0.0)
    if domain == "temporal":
        return "fired" if int(inputs["elapsed"]) >= int(inputs["delay"]) else "waiting"
    if domain == "inventory":
        return {
            "object": inputs["place"],
            "relation": "located-in",
            "subject": inputs["item"],
        }
    if domain == "software":
        return float(inputs["errors"]) / float(inputs["records"])
    raise ValueError(f"unknown evaluation domain {domain!r}")


def iter_evaluations(report: Mapping[str, Any]):
    for lifetime in report["lifetimes"]:
        yield from lifetime["evaluations"]
    controls = report["controls"]
    for group in ("structural_controls", "irrelevant_controls"):
        for control in controls[group]:
            yield from control["evaluations"]
    for intervention in controls["interventions"]:
        yield intervention["before"]
        yield intervention["after"]


def verify(path: Path, repo_root: Path) -> dict[str, Any]:
    failures: list[str] = []
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, detail: Any = None) -> None:
        checks.append({"check": name, "passed": bool(passed), "detail": detail})
        if not passed:
            failures.append(name)

    raw = path.read_bytes()
    report = json.loads(raw)
    check("schema", report.get("schema") == SCHEMA, report.get("schema"))
    claimed_receipt = report.get("receipt_sha256")
    unhashed = dict(report)
    unhashed.pop("receipt_sha256", None)
    computed_receipt = sha256_bytes(canonical_bytes(unhashed))
    check("receipt-sha256", claimed_receipt == computed_receipt, computed_receipt)

    manifest = report.get("manifest", {}).get("implementation_sha256", {})
    manifest_results: dict[str, str] = {}
    for relative, expected_hash in sorted(manifest.items()):
        source = repo_root / relative
        actual_hash = sha256_bytes(source.read_bytes()) if source.is_file() else "missing"
        manifest_results[relative] = actual_hash
        check(f"manifest:{relative}", actual_hash == expected_hash, actual_hash)

    program = report["program"]
    blocks = int(program["blocks"])
    seeds = list(program["seeds"])
    roots = int(program["roots_per_domain_checkpoint"])
    decisions = int(program["decisions_per_root"])
    events_per_lifetime = blocks * len(DOMAINS) * 4
    check("domains", tuple(program["domains"]) == DOMAINS, program["domains"])
    check(
        "feedback-event-formula",
        program["feedback_events_per_lifetime"] == events_per_lifetime,
        program["feedback_events_per_lifetime"],
    )
    check("lifetime-count", len(report["lifetimes"]) == len(seeds), len(report["lifetimes"]))
    check("training-executed", program.get("training_executed") is True)
    allocation = program["allocation"]
    default_profile = allocation["default_regional_profile"]
    expanded_profile = allocation["expanded_regional_profile"]
    expected_multiplier = (
        expanded_profile["default_value_words"]
        / default_profile["default_value_words"]
    )
    check(
        "allocation-multiplier",
        allocation["value_capacity_multiplier"] == expected_multiplier,
        expected_multiplier,
    )
    sizing = report["sizing"]
    sizing_consistent = (
        (
            sizing["status"] == "capacity-bound"
            and sizing["failure"] is not None
            and (
                sizing["completed_feedback_events"] < events_per_lifetime
                or sizing["acquisitions_completed"] < blocks * len(DOMAINS)
            )
        )
        or (
            sizing["status"] == "completed"
            and sizing["failure"] is None
            and sizing["completed_feedback_events"] == events_per_lifetime
        )
    )
    check("default-sizing-consistency", sizing_consistent, sizing["status"])
    check("default-sizing-profile", sizing["profile"] == default_profile)

    evaluation_rows: list[Mapping[str, Any]] = []
    all_knowledge_frozen = True
    for evaluation in iter_evaluations(report):
        rows = evaluation["rows"]
        evaluation_rows.extend(rows)
        recomputed_correct = 0
        for row in rows:
            try:
                expected = expected_for(row)
            except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
                check(f"row-formula:{row.get('case_id')}", False, str(exc))
                continue
            formula_ok = equal(expected, row["expected"])
            answer_ok = equal(row["expected"], row["actual"])
            check(f"row-formula:{row['control']}:{row['case_id']}", formula_ok, expected)
            check(
                f"row-score:{row['control']}:{row['case_id']}",
                row["correct"] is answer_ok,
                {"actual": row["actual"], "expected": row["expected"]},
            )
            recomputed_correct += int(answer_ok)
        check(
            f"evaluation-total:{evaluation['control']}:{evaluation['checkpoint']}",
            evaluation["total"] == len(rows) == roots * decisions * len({row["domain"] for row in rows}),
            evaluation["total"],
        )
        check(
            f"evaluation-correct:{evaluation['control']}:{evaluation['checkpoint']}",
            evaluation["correct"] == recomputed_correct,
            recomputed_correct,
        )
        frozen = (
            evaluation["knowledge_frozen"] is True
            and evaluation["knowledge_before_sha256"] == evaluation["knowledge_after_sha256"]
        )
        all_knowledge_frozen = all_knowledge_frozen and frozen
        check(
            f"knowledge-frozen:{evaluation['control']}:{evaluation['checkpoint']}",
            frozen,
        )

    training_roots: set[str] = set()
    evaluation_roots = {str(row["root_id"]) for row in evaluation_rows}
    for lifetime in report["lifetimes"]:
        rows = lifetime["training_rows"]
        check(
            f"training-count:{lifetime['seed']}",
            len(rows) == events_per_lifetime,
            len(rows),
        )
        check(
            f"acquisition-count:{lifetime['seed']}",
            len(lifetime["acquisitions"]) == blocks * len(DOMAINS),
            len(lifetime["acquisitions"]),
        )
        roles = [row["event_role"] for row in rows]
        check(
            f"construction-count:{lifetime['seed']}",
            roles.count("construction") == blocks * len(DOMAINS) * 3,
            roles.count("construction"),
        )
        check(
            f"selection-count:{lifetime['seed']}",
            roles.count("selection") == blocks * len(DOMAINS),
            roles.count("selection"),
        )
        check(
            f"regional-profile:{lifetime['seed']}",
            lifetime["regional_profile"] == expanded_profile,
        )
        checkpoints = [int(row["checkpoint"]) for row in lifetime["resource_curve"]]
        check(
            f"resource-curve-checkpoints:{lifetime['seed']}",
            checkpoints == [0, *(16 * block for block in range(1, blocks + 1))],
            checkpoints,
        )
        for acquisition in lifetime["acquisitions"]:
            check(
                f"acquisition-work:{lifetime['seed']}:{acquisition['block']}:{acquisition['domain']}",
                acquisition["work"]
                == acquisition["work_after"] - acquisition["work_before"],
                acquisition["work"],
            )
        for row in rows:
            training_roots.add(str(row["split_root"]))
            check(
                f"training-content:{row['source_id']}",
                sha256_bytes(canonical_bytes(row["payload"])) == row["content_sha256"],
            )
            check(
                f"training-source-codec:{row['source_id']}",
                row.get("source_codec") == "opaque-exact-json-bytes",
                row.get("source_codec"),
            )
    check("evaluation-root-separation", training_roots.isdisjoint(evaluation_roots))
    summary = report["summary"]
    expected_learning_points = len(seeds) * (blocks + 1) * len(DOMAINS)
    check(
        "learning-curve-size",
        len(summary["learning_curves"]) == expected_learning_points,
        len(summary["learning_curves"]),
    )
    check(
        "retention-matrix-size",
        len(summary["retention_matrix"]) == expected_learning_points,
        len(summary["retention_matrix"]),
    )
    check(
        "cost-curve-size",
        len(summary["cost_curves"]) == len(seeds) * (blocks + 1),
        len(summary["cost_curves"]),
    )
    for curve in summary["learning_curves"]:
        key = (
            int(curve["seed"]),
            int(curve["checkpoint"]),
            str(curve["domain"]),
        )
        matching = [
            row
            for lifetime in report["lifetimes"]
            if int(lifetime["seed"]) == key[0]
            for evaluation in lifetime["evaluations"]
            if int(evaluation["checkpoint"]) == key[1]
            for row in evaluation["rows"]
            if row["domain"] == key[2]
        ]
        check(
            f"learning-curve-score:{key[0]}:{key[1]}:{key[2]}",
            curve["attempted"] == len(matching)
            and curve["correct"] == sum(int(row["correct"]) for row in matching),
        )

    for intervention in report["controls"]["interventions"]:
        effect = intervention["before"]["correct"] - intervention["after"]["correct"]
        check(f"intervention-effect:{intervention['seed']}", effect == intervention["causal_effect"], effect)
        check(
            f"intervention-revoked:{intervention['seed']}",
            intervention["revocation_result"].get("status") == "supported",
            intervention["revocation_result"].get("status"),
        )

    for section_name in ("shared_belief", "reduced_sensory", "real_sources"):
        for item in report[section_name]:
            if section_name == "shared_belief":
                passed = sum(int(row["passed"]) for row in item["checks"])
                total = len(item["checks"])
            else:
                passed = sum(int(row["correct"]) for row in item["rows"])
                total = len(item["rows"])
                for row in item["rows"]:
                    check(
                        f"{section_name}-row:{item['seed']}:{row.get('modality', row.get('path'))}",
                        row["correct"] is equal(row["expected"], row["actual"]),
                    )
            check(f"{section_name}-score:{item['seed']}", item["passed"] == passed and item["total"] == total)

    separation = report["separation"]
    check("single-adaptive-state", separation.get("adaptive_state") == "one resident cognition.field per lifetime")
    check("no-evaluation-feedback", separation.get("evaluation_feedback_returned") is False)
    check("no-teacher-or-qwen", separation.get("qwen_or_teacher_calls") == 0)
    check("learner-boundary", separation.get("external_environment_is_learner") is False)
    check(
        "summary-knowledge-freeze",
        report["summary"].get("all_snapshot_knowledge_frozen") is all_knowledge_frozen,
        all_knowledge_frozen,
    )

    return {
        "schema": VERIFY_SCHEMA,
        "receipt": str(path),
        "receipt_sha256": computed_receipt,
        "checks": checks,
        "failures": failures,
        "passed": not failures,
        "manifest_sha256": manifest_results,
        "totals": {
            "checks": len(checks),
            "evaluation_rows": len(evaluation_rows),
            "failures": len(failures),
            "training_roots": len(training_roots),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Independently verify a retained general-intelligence program receipt.")
    parser.add_argument("receipt", nargs="?", type=Path, default=Path("_diag/general_intelligence_program.json"))
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    result = verify(args.receipt, args.repo_root.resolve())
    print(json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
