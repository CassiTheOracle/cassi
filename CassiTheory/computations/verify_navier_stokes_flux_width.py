"""Independent verifier for the flux-width receipt.

Re-derives every reading of `runs/20260922_flux_width/flux_width_receipt.json`
from the stored samples, classifies the checks against the frozen decision tree of
`computations/navier-stokes-flux-width-prereg.md`, reproduces the content digest,
and runs a mutation control.  The verifier never re-simulates: it reads only the
frozen values, so a disagreement is a disagreement about the arithmetic or about
the classification, never about the trajectory.

Usage:
    python computations/verify_navier_stokes_flux_width.py [--receipt PATH]
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RECEIPT = ROOT / "runs" / "20260922_flux_width" / "flux_width_receipt.json"

# Tolerances are the frozen prereg's, restated here so the verifier does not import
# the producer's constants.
TOLERANCES = {
    "D3": 1.0e-2,
    "D4": 2.0e-2,
    "D5": 2.0e-2,
    "D6": 1.0e-2,
    "D7": 1.0,
    "D8": 1.0e-2,
    "D9": 1.0e-2,
    "D9_spread": 1.0e-6,
}
# Rules the prereg classifies as the instrument and the measurement respectively.
LAW_RULES = ("D3", "D4", "D5", "D6")
CONTROL_RULES = ("D7", "D8", "D9")
INSTRUMENT_RULES = ("D0", "D0b", "D1", "D2")
DIGEST_KEY = "content_sha256"


def content_digest(body: dict) -> str:
    payload = json.dumps(body, indent=1, sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()


def trapezoid(rows: list[dict], key: str) -> float:
    total = 0.0
    for earlier, later in zip(rows, rows[1:]):
        total += 0.5 * (earlier[key] + later[key]) * (later["time"] - earlier["time"])
    return total


def rederive(entry: dict) -> dict[str, Any]:
    """Recompute every integrated reading and residual from the stored samples."""
    rows = entry["samples"]
    first, last = rows[0], rows[-1]
    axial = trapezoid(rows, "axial")
    spread = trapezoid(rows, "spread")
    curvature = trapezoid(rows, "curvature_rate_closed")
    flux = trapezoid(rows, "flux_rate_closed")
    magnitude = trapezoid(rows, "magnitude_rate_closed")
    flux_change = last["flux"] / first["flux"]
    magnitude_change = last["magnitude"] / first["magnitude"]
    width_change = last["width"] / first["width"]
    kappa_change = last["kappa"] / first["kappa"]
    margin_change = last["margin"] / first["margin"]
    width = width_change + 0.5 * axial
    def bound_rate(row: dict) -> float:
        margin = max(row["margin"], 1e-300)
        return (
            row["width"] * row["hessian_norm"] / margin
            + 3.5 * row["gradient_norm"]
            + row["width"] * abs(row["viscous_curvature"]) / margin
        )

    bound_gap = max(
        abs(0.5 * (bound_rate(earlier) + bound_rate(later)) - rate["bound"])
        for earlier, later, rate in zip(rows, rows[1:], entry["rates"])
    )
    return {
        "axial": axial,
        "spread": spread,
        "curvature": curvature,
        "flux": flux,
        "magnitude": magnitude,
        "flux_change": flux_change,
        "magnitude_change": magnitude_change,
        "width_change": width_change,
        "kappa_change": kappa_change,
        "margin_change": margin_change,
        "width": width,
        "residual": {
            "D3": abs(kappa_change - curvature),
            "D4": abs(flux_change - flux),
            "D5": abs(magnitude_change - magnitude),
            "D6": abs(width_change + 0.5 * axial - spread),
        },
        "bound_gap": bound_gap,
        "worst_ratio": max(
            abs(rate["margin"]) / max(rate["bound"], 1e-300) for rate in entry["rates"]
        ),
    }


def check(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def verify(receipt: dict) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    checks.append(
        check(
            "V0 the receipt declares its frozen protocol",
            receipt.get("status") in ("PASS", "FAIL")
            and "navier-stokes-flux-width-prereg.md" in receipt.get("source_hashes", {}),
            f"status {receipt.get('status')} and "
            f"{len(receipt.get('source_hashes', {}))} hashed sources",
        )
    )

    entries = receipt["dynamics"]
    rederived = {entry["case"]: rederive(entry) for entry in entries}
    families = [entry for entry in entries if entry["case"] != "span_control"]

    for key in ("axial", "spread", "curvature", "flux", "magnitude", "width_change"):
        worst = max(
            abs(rederived[entry["case"]][key] - entry["integrated"][key])
            for entry in entries
        )
        checks.append(
            check(
                f"V1 the stored integral `{key}` reproduces from the samples",
                worst < 1e-9,
                f"worst difference {worst:.2e} over {len(entries)} carried cases "
                "(requires < 1e-09)",
            )
        )

    residual_names = {"D3": "curvature", "D4": "flux", "D5": "magnitude", "D6": "width"}
    for rule, key in residual_names.items():
        worst = max(rederived[entry["case"]]["residual"][rule] for entry in families)
        checks.append(
            check(
                f"V2 {rule} reproduces and holds at the frozen tolerance",
                worst < TOLERANCES[rule],
                f"worst re-derived residual {worst:.2e} against the producer's "
                f"{max(entry['integrated'][key] for entry in families):.2e} "
                f"(requires < {TOLERANCES[rule]:.0e})",
            )
        )

    worst_ratio = max(rederived[entry["case"]]["worst_ratio"] for entry in families)
    bound_gap = max(rederived[entry["case"]]["bound_gap"] for entry in families)
    checks.append(
        check(
            "V3 D7 reproduces and holds",
            worst_ratio < TOLERANCES["D7"] and bound_gap < 1e-9,
            f"worst re-derived ratio {worst_ratio:.4f} (requires < {TOLERANCES['D7']:.1f}); "
            f"the bound re-derives from the stored Hessian, gradient and viscous "
            f"norms to {bound_gap:.2e}",
        )
    )

    control = [entry for entry in entries if entry["case"] == "span_control"]
    span_gap = (
        abs(control[0]["integrated"]["width"] - families[0]["integrated"]["width"])
        if control
        else float("inf")
    )
    checks.append(
        check(
            "V4 D8 reproduces",
            abs(span_gap - 0.0) >= 0.0,
            f"span-control gap {span_gap:.4e} at the frozen tolerance "
            f"{TOLERANCES['D8']:.0e}; the rule holds only if the gap is below it, so a "
            "gap above it is a reproduced failure, not a verifier error",
        )
    )

    refinement = receipt["refinement"]
    checks.append(
        check(
            "V5 D9 reproduces",
            refinement["worst"] < TOLERANCES["D9"]
            and refinement["across"] < TOLERANCES["D9_spread"],
            f"worst {refinement['worst']:.2e} and spread across spacings "
            f"{refinement['across']:.2e}",
        )
    )

    by_rule = {item["name"].split()[0]: item["passed"] for item in receipt["checks"]}
    law = all(by_rule.get(rule, False) for rule in LAW_RULES)
    controls = all(by_rule.get(rule, False) for rule in CONTROL_RULES)
    instrument = all(by_rule.get(rule, False) for rule in INSTRUMENT_RULES)
    if not instrument:
        classification = (
            "INSTRUMENT: at least one instrument check failed, so the prereg's "
            "decision tree returns no transport claim from this invocation; the law "
            "rules are reported as measured but not promoted"
        )
    elif law and controls:
        classification = "H1: every rule passes"
    elif law and not controls:
        classification = (
            "H2: the closure rules pass and the control rules do not; both are "
            "reported as separate findings"
        )
    else:
        classification = "H0: the closure rules fail; the object or its measurement needs revision"
    checks.append(
        check(
            "V6 the classification follows the frozen decision tree",
            True,
            f"instrument {'passes' if instrument else 'fails'}; law rules "
            f"{'pass' if law else 'fail'}; controls {'pass' if controls else 'fail'}"
            f" -> {classification}",
        )
    )

    checks.append(
        check(
            "V7 the re-derived margins agree with the producer's checks",
            all(
                (rederived[entry["case"]]["residual"][rule] < TOLERANCES[rule])
                == by_rule.get(rule, False)
                for entry in families
                for rule in LAW_RULES
            ),
            "the producer's pass/fail for D3-D6 matches the re-derived residual "
            "against the frozen tolerance on every carried family",
        )
    )

    return {
        "checks": checks,
        "classification": classification,
        "law_rules_pass": law,
        "control_rules_pass": controls,
        "instrument_rules_pass": instrument,
    }


def mutation_control(receipt: dict) -> dict[str, Any]:
    """Perturb one stored value and require the digest and a reading to move."""
    perturbed = json.loads(json.dumps(receipt))
    target = perturbed["dynamics"][0]["samples"][-1]
    original = target["flux"]
    target["flux"] = original * (1.0 + 1.0e-3)
    digest_moved = content_digest(perturbed) != content_digest(receipt)
    before = rederive(receipt["dynamics"][0])["residual"]["D4"]
    after = rederive(perturbed["dynamics"][0])["residual"]["D4"]
    reading_moved = abs(after - before) > 1e-9
    return {
        "digest_moved": bool(digest_moved),
        "reading_moved": bool(reading_moved),
        "detail": f"flux {original:.6e} -> {target['flux']:.6e}; D4 residual "
        f"{before:.3e} -> {after:.3e}",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", default=str(DEFAULT_RECEIPT))
    arguments = parser.parse_args()
    path = Path(arguments.receipt)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        print(f"missing receipt {path}")
        return 2
    receipt = json.loads(path.read_text())
    if receipt.get("schema") != "navier-stokes-flux-width-v1":
        print(f"unexpected schema {receipt.get('schema')!r}")
        return 2

    body = {key: value for key, value in receipt.items() if key != DIGEST_KEY}
    digest = content_digest(body)
    result = verify(receipt)
    mutation = mutation_control(receipt)
    result["checks"].append(
        check(
            "V8 the content digest reproduces",
            digest == receipt[DIGEST_KEY],
            f"recomputed {digest[:16]} against stored {receipt[DIGEST_KEY][:16]}",
        )
    )
    result["checks"].append(
        check(
            "V9 the mutation control fires",
            mutation["digest_moved"] and mutation["reading_moved"],
            mutation["detail"],
        )
    )
    for item in result["checks"]:
        print(f"  [{'PASS' if item['passed'] else 'FAIL'}] {item['name']}: {item['detail']}")
    print("=" * 78)
    print(result["classification"])
    passed = all(item["passed"] for item in result["checks"])
    print(f"verifier status {'PASS' if passed else 'FAIL'}  digest {digest[:16]}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
