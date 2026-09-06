#!/usr/bin/env python3
"""Qualify exact scaling certificates for the source-free positive-root energy.

Run from the repository root:
python computations/matter_formation_kappa4_selection.py --output-dir runs/<fresh-name>

This is an algebra calculation. The continuum variational proof and excluded
models are specified in the working record; no field evolution is simulated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
NOTE = ROOT / "computations/matter-formation-continuum-report.md"
HEADING = "### 12.11 Fourth-gradient selection: pre-execution criteria\n"
PROTOCOL_SHA = "7bdc796f77e395f0d242a34f63936a0e4b54872cfa0a6df4b58dddba02fb5333"
VERDICT = "SUPPORTS—absence of static localization in the declared source-free positive-root energy"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def frozen_section(note: Path) -> str:
    text = note.read_text(encoding="utf-8").replace("\r\n", "\n")
    start = text.index(HEADING)
    after = text[start + len(HEADING):]
    end = re.search(r"\n#{1,3} ", after)
    return (HEADING + (after[:end.start()] if end else after)).rstrip() + "\n"


def exact_checks() -> list[dict]:
    length, amplitude = sp.symbols("L a", positive=True)
    t2, t4, v4 = sp.symbols("T2 T4 V4", nonnegative=True)
    energies = (t2, t4, v4)
    # Each entry specifies derivative order per field and field power.
    terms = ((1, 2), (2, 2), (0, 4))
    weights = [amplitude**power * length**(3 - order * power)
               for order, power in terms]
    energy = sum(weight * term for weight, term in zip(weights, energies))
    checks = []

    def check(name: str, condition, evidence) -> None:
        checks.append({"name": name, "pass": bool(condition),
                       "exact_evidence": str(evidence)})

    spatial_weights = [weight.subs(amplitude, 1) for weight in weights]
    spatial_energy = energy.subs(amplitude, 1)
    spatial_derivative = sp.diff(spatial_energy, length).subs(length, 1)
    check("fixed_amplitude_spatial_weights",
          spatial_weights == [length, 1 / length, length**3]
          and sp.expand(spatial_derivative - (t2 - t4 + 3 * v4)) == 0,
          {"weights": spatial_weights, "derivative_at_one": spatial_derivative})

    amplitude_energy = energy.subs(length, 1)
    amplitude_derivative = sp.diff(amplitude_energy, amplitude).subs(amplitude, 1)
    amplitude_coefficients = [amplitude_derivative.coeff(term) for term in energies]
    check("amplitude_descent_certificate",
          amplitude_coefficients == [2, 2, 4]
          and sp.expand(amplitude_derivative - sum(c * e for c, e in zip(amplitude_coefficients, energies))) == 0,
          {"energy": amplitude_energy, "derivative_at_one": amplitude_derivative,
           "strictness_assumption": "T2 > 0 for a nonzero finite-L2 field on R3"})

    norm_amplitude = length**(-sp.Rational(3, 2))
    norm_weight = (amplitude**2 * length**3).subs(amplitude, norm_amplitude)
    norm_weights = [sp.simplify(weight.subs(amplitude, norm_amplitude)) for weight in weights]
    norm_energy = sp.simplify(energy.subs(amplitude, norm_amplitude))
    norm_derivative = sp.diff(norm_energy, length).subs(length, 1).expand()
    norm_limit = sp.limit(norm_energy, length, sp.oo)
    check("fixed_population_dilution_certificate",
          norm_weight == 1 and norm_weights == [length**-2, length**-4, length**-3]
          and sp.expand(norm_derivative + 2 * t2 + 4 * t4 + 3 * v4) == 0
          and norm_limit == 0,
          {"population_weight": norm_weight, "energy_weights": norm_weights,
           "derivative_at_one": norm_derivative, "infinite_length_limit": norm_limit})

    control = {t2: 1, t4: 4, v4: 1}
    control_spatial_slope = spatial_derivative.subs(control)
    control_spatial_curvature = sp.diff(spatial_energy, length, 2).subs(length, 1).subs(control)
    control_amplitude_slope = amplitude_derivative.subs(control)
    check("scaling_minimum_scope_control",
          control_spatial_slope == 0 and control_spatial_curvature > 0
          and control_amplitude_slope > 0,
          {"energy_triple": (1, 4, 1), "spatial_slope": control_spatial_slope,
           "spatial_curvature": control_spatial_curvature,
           "amplitude_slope": control_amplitude_slope})
    return checks


def run(note: Path, output: Path) -> int:
    output.mkdir(parents=True, exist_ok=False)
    receipt = {"schema": "matter-formation-kappa4-selection-v1", "checks": [],
               "numerical_pass": False, "verdict": "INCONCLUSIVE", "failures": [],
               "identities": {}}
    try:
        section = frozen_section(note)
        section_sha = digest(section.encode("utf-8"))
        if section_sha != PROTOCOL_SHA:
            raise ValueError("frozen fourth-gradient section hash mismatch")
        receipt["identities"] = {
            "program": {"path": Path(__file__).resolve().relative_to(ROOT).as_posix(),
                        "sha256": digest(Path(__file__).read_bytes().replace(b"\r\n", b"\n"))},
            "protocol": {"path": note.relative_to(ROOT).as_posix(),
                         "heading": HEADING.strip(), "sha256": section_sha},
        }
        with (output / "protocol.txt").open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(section)
        receipt["checks"] = exact_checks()
        receipt["failures"] = [row["name"] for row in receipt["checks"] if not row["pass"]]
        if len(receipt["checks"]) != 4:
            receipt["failures"].append("frozen exact-check count mismatch")
        receipt["numerical_pass"] = not receipt["failures"]
        if receipt["numerical_pass"]:
            receipt["verdict"] = VERDICT
    except Exception as error:
        receipt["failures"].append(f"{type(error).__name__}: {error}")
    with (output / "results.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(receipt, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    print(json.dumps(receipt, ensure_ascii=False, allow_nan=False))
    return 0 if receipt["numerical_pass"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--note", type=Path, default=NOTE)
    parser.add_argument("--output-dir", type=Path,
                        default=ROOT / "runs/20260906_matter_formation_kappa4_selection")
    args = parser.parse_args()
    return run(args.note.resolve(), args.output_dir.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
