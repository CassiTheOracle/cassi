#!/usr/bin/env python3
"""Exercise the spatial receipt failure path and check numerical continuity.

Run after matter_formation_spatial_domain_v2.py from the repository root:
python computations/verify_matter_formation_spatial_domain_receipts.py
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

import matter_formation_spatial_domain_v2 as calculation

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "runs/20260906_matter_formation_spatial_domain/results.json"
BASELINE_SHA = "aa743746d1a3155640914e8856f41f73fab5468ae7330689e764bb1817e4663d"


def strict_read(path: Path) -> dict:
    def reject(value: str):
        raise ValueError(f"nonfinite JSON token: {value}")
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=reject)


def run(output: Path) -> int:
    output.mkdir(parents=True, exist_ok=False)
    receipt = {"schema": "matter-formation-spatial-receipt-verification-v1", "checks": [],
               "numerical_pass": False, "failures": []}

    def check(name: str, condition, evidence=None) -> None:
        passed = bool(condition)
        receipt["checks"].append({"name": name, "pass": passed, "evidence": evidence})
        if not passed:
            receipt["failures"].append(name)

    try:
        accepted_path = calculation.DEFAULT_OUTPUT / "results.json"
        accepted_hash = calculation.sha(accepted_path)
        current = strict_read(accepted_path)
        if calculation.sha(BASELINE) != BASELINE_SHA:
            raise ValueError("sealed baseline receipt mismatch")
        baseline = strict_read(BASELINE)
        receipt["identities"] = {
            "program": {"path": Path(__file__).resolve().relative_to(ROOT).as_posix(), "sha256": calculation.sha(Path(__file__), True)},
            "qualified_receipt": {"path": accepted_path.relative_to(ROOT).as_posix(), "sha256": accepted_hash},
            "baseline_receipt": {"path": BASELINE.relative_to(ROOT).as_posix(), "sha256": BASELINE_SHA},
        }
        check("qualified_success", current["numerical_pass"] is True and not current["failures"]
              and len(current["comparisons"]) == 14 and all(row["pass"] is True for row in current["comparisons"]))
        check("unrelaxed_spectral_tie", current["retained_spectrum_check"]["pass"] is True
              and len(current["retained_spectrum_check"]["comparisons"]) == 24)
        for path, expected in current["inputs"]["programs"].items():
            check("identity:" + path, calculation.sha(ROOT / path, True) == expected)
        prior_rows = {row["id"]: row for row in baseline["rows"]}
        continuity = []
        for row in current["rows"]:
            check("artifact:" + row["id"], calculation.sha(calculation.DEFAULT_OUTPUT / row["artifact"]["path"]) == row["artifact"]["sha256"])
            previous = prior_rows[row["id"]]
            for name, value in {**row["metrics"], "energy": row["source"]["energy"], "omega": row["source"]["omega"]}.items():
                before = previous["metrics"].get(name, previous["source"].get(name))
                delta = abs(value - before)
                tolerance = 1e-10 * max(1.0, abs(value), abs(before))
                continuity.append({"id": row["id"], "quantity": name, "difference": delta, "tolerance": tolerance})
        check("numerical_continuity", len(continuity) == 36 and all(row["difference"] <= row["tolerance"] for row in continuity), continuity)

        control_dir = output / "nonfinite_newton"
        original = calculation.continue_stationary
        def injected_failure(state: dict, grid) -> None:
            state["f"][0] = np.nan
            state["c"][0] = np.inf
            state["c"][1] = -np.inf
            state["trace"].append({"iteration": 0, "residual": float("inf"),
                                   "population": float("nan"), "signed_diagnostic": -float("inf")})
            raise FloatingPointError("declared nonfinite Newton failure control")
        calculation.continue_stationary = injected_failure
        try:
            control_exit = calculation.run(control_dir)
        finally:
            calculation.continue_stationary = original
        control = strict_read(control_dir / "results.json")
        check("control_failure_is_visible", control_exit == 1 and control["numerical_pass"] is False
              and control["verdict"] == "INCONCLUSIVE" and bool(control["failures"]))
        check("control_retains_every_attempt", len(control["rows"]) == 4
              and all(row["numerical_pass"] is False for row in control["rows"]))
        check("control_nonfinite_diagnostics_are_null", all(
            row["newton_trace"][0][key] is None for row in control["rows"]
            for key in ("residual", "population", "signed_diagnostic")))
        for row in control["rows"]:
            with np.load(control_dir / row["artifact"]["path"], allow_pickle=False) as arrays:
                check("control_raw_values:" + row["id"], np.isnan(arrays["f"][0])
                      and np.isposinf(arrays["c"][0]) and np.isneginf(arrays["c"][1]))
        receipt["control_receipt"] = {"path": (control_dir / "results.json").relative_to(ROOT).as_posix(),
                                      "sha256": calculation.sha(control_dir / "results.json")}
        refused = False
        try:
            calculation.run(calculation.DEFAULT_OUTPUT)
        except FileExistsError:
            refused = True
        check("existing_evidence_is_immutable", refused and calculation.sha(accepted_path) == accepted_hash)
        receipt["numerical_pass"] = not receipt["failures"]
    except Exception as error:
        receipt["failures"].append(f"{type(error).__name__}: {error}")
    finally:
        calculation.write_json(output / "results.json", receipt)
    print(json.dumps({"checks": len(receipt["checks"]), "numerical_pass": receipt["numerical_pass"],
                      "failures": receipt["failures"]}, allow_nan=False))
    return 0 if receipt["numerical_pass"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "runs/20260906_matter_formation_spatial_receipt_checks")
    return run(parser.parse_args().output_dir.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
