#!/usr/bin/env python3
"""Qualify the strict rational inputs to the specified scalar-vacuum witness.

Run from the repository root:
python computations/matter_formation_scalar_vacuum_sign_check.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
NOTE = ROOT / "computations/matter-formation-continuum-report.md"
HEADING = "### 16.5 Rational inequality supplement: pre-execution criteria\n"
ACCEPTED = ROOT / "runs/20260906_matter_formation_scalar_vacuum/results.json"
ACCEPTED_SHA = "b2932913890ee3c97f1d8e05f6d94e08eebbdd34d48b438a9fc647fe2c990dc5"


def digest(path: Path, canonical: bool = False) -> str:
    data = path.read_bytes()
    return hashlib.sha256(data.replace(b"\r\n", b"\n") if canonical else data).hexdigest()


def run(output: Path) -> int:
    output.mkdir(parents=True, exist_ok=False)
    receipt = {"schema": "matter-formation-scalar-vacuum-sign-v1", "checks": [],
               "numerical_pass": False, "verdict": "INCONCLUSIVE", "failures": []}
    try:
        text = NOTE.read_text(encoding="utf-8").replace("\r\n", "\n")
        start = text.index(HEADING)
        end = text.index("\n##", start + len(HEADING))
        section = text[start:end] + "\n"
        with (output / "protocol.txt").open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(section)
        if digest(ACCEPTED) != ACCEPTED_SHA:
            raise ValueError("accepted scalar-vacuum receipt hash mismatch")
        accepted = json.loads(ACCEPTED.read_text(encoding="utf-8"))
        if accepted["numerical_pass"] is not True or accepted["failures"]:
            raise ValueError("accepted scalar-vacuum evidence is unqualified")
        for identity in accepted["identities"].values():
            if digest(ROOT / identity["path"], canonical=True) != identity["sha256"]:
                raise ValueError("sealed scalar-vacuum identity mismatch")
        receipt["identities"] = {
            "program": {"path": Path(__file__).resolve().relative_to(ROOT).as_posix(), "sha256": digest(Path(__file__), True)},
            "protocol": {"path": NOTE.relative_to(ROOT).as_posix(), "heading": HEADING.strip(), "sha256": hashlib.sha256(section.encode()).hexdigest()},
            "accepted_receipt": {"path": ACCEPTED.relative_to(ROOT).as_posix(), "sha256": ACCEPTED_SHA},
        }
        with (output / "inputs.json").open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(receipt["identities"], stream, indent=2, allow_nan=False)
            stream.write("\n")
        x = sp.symbols("x", real=True)
        log_integrand = 1 / x - sp.Rational(2, 3) + sp.Rational(4, 9) * (x - sp.Rational(3, 2))
        log_lower = (2 * x - 3) ** 2 / 18
        pi_integrand = x ** 4 * (1 - x) ** 4 / (1 + x ** 2)
        pi_lower = x ** 4 * (1 - x) ** 4 / 2

        def check(name: str, condition, evidence) -> None:
            passed = bool(condition)
            receipt["checks"].append({"name": name, "pass": passed, "exact_evidence": str(evidence)})
            if not passed:
                receipt["failures"].append(name)

        log_counterexample = sp.reduce_inequalities([x >= 1, x <= 2, log_integrand < log_lower], x)
        check("log_rational_identity_and_lower_bound",
              sp.simplify(log_integrand - (2 * x - 3) ** 2 / (9 * x)) == 0 and log_counterexample.as_set() == sp.EmptySet,
              sp.factor(log_integrand - log_lower))
        pi_counterexample = sp.reduce_inequalities([x >= 0, x <= 1, pi_integrand < pi_lower], x)
        check("pi_rational_identity_and_lower_bound",
              sp.simplify(pi_integrand - pi_lower - x ** 4 * (1 - x) ** 4 * (1 - x ** 2) / (2 * (1 + x ** 2))) == 0
              and pi_counterexample.as_set() == sp.EmptySet, sp.factor(pi_integrand - pi_lower))
        log_margin = sp.integrate(log_lower, (x, 1, 2))
        pi_margin = sp.integrate(pi_lower, (x, 0, 1))
        check("strict_positive_log_margin", log_margin == sp.Rational(1, 54) and log_margin > 0, log_margin)
        check("strict_positive_pi_margin", pi_margin == sp.Rational(1, 1260) and pi_margin > 0, pi_margin)
        check("log_integral_identity", sp.simplify(sp.integrate(log_integrand, (x, 1, 2)) - sp.log(2) + sp.Rational(2, 3)) == 0,
              "log(2) - 2/3 >= 1/54 > 0")
        check("pi_integral_identity", sp.simplify(sp.integrate(pi_integrand, (x, 0, 1)) - sp.Rational(22, 7) + sp.pi) == 0,
              "22/7 - pi >= 1/1260 > 0")
        d = sp.Integer(63)
        polynomial = 2 * d + 7 * d ** 2 + sp.Rational(26, 3) * d ** 3 + sp.Rational(25, 6) * d ** 4
        bracket = 8 * sp.Integer(64) ** 4 - polynomial
        upper = 72 * d ** 2 - bracket / 160
        check("negative_rational_bulk_witness", bracket > 0 and sp.Rational(22, 7) ** 2 < 10
              and upper == -sp.Rational(8265011, 64) and upper < 0, upper)
        receipt["numerical_pass"] = len(receipt["checks"]) == 7 and not receipt["failures"]
        if receipt["numerical_pass"]:
            receipt["verdict"] = "SUPPORTS—strict rational inputs to the specified local one-loop energy witness"
    except Exception as error:
        receipt["failures"].append(f"{type(error).__name__}: {error}")
    finally:
        with (output / "results.json").open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(receipt, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
    print(json.dumps(receipt, ensure_ascii=False, allow_nan=False))
    return 0 if receipt["numerical_pass"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "runs/20260906_matter_formation_scalar_vacuum_sign")
    return run(parser.parse_args().output_dir.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
