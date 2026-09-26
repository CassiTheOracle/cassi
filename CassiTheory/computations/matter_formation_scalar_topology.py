#!/usr/bin/env python3
"""Check the frozen algebra supporting the declared scalar homotopies.

Run from the repository root:
python computations/matter_formation_scalar_topology.py --output-dir runs/<fresh-name>

The continuum topology is proved in the working record. These exact algebra
checks qualify its certificates and scope controls; they do not compute pi_1.
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
HEADING = "### 12.7 Scalar configuration topology: pre-execution criteria\n"
PROTOCOL_SHA = "6282acadafd451a53097bb6bec37635c98418583aac360a661dc0eec9bbe394e"
VERDICT = "SUPPORTS—algebraic certificates for the declared scalar configuration-space contractions"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def frozen_section(note: Path) -> str:
    text = note.read_text(encoding="utf-8").replace("\r\n", "\n")
    start = text.index(HEADING)
    after = text[start + len(HEADING):]
    end = re.search(r"\n#{1,3} ", after)
    return (HEADING + (after[:end.start()] if end else after)).rstrip() + "\n"


def exact_checks() -> list[dict]:
    checks = []

    def check(name: str, condition, evidence) -> None:
        checks.append({"name": name, "pass": bool(condition),
                       "exact_evidence": str(evidence)})

    t, a, b = sp.symbols("t a b", real=True)
    u, v = sp.symbols("u v", nonnegative=True)
    d = (1 - t) * u**2 + t * v**2
    fisher_gap = ((1 - t) * a**2 + t * b**2) * d - ((1 - t) * u * a + t * v * b)**2
    fisher_certificate = t * (1 - t) * (v * a - u * b)**2
    check("fisher_gap", sp.expand(fisher_gap - fisher_certificate) == 0,
          sp.factor(fisher_gap))

    x = sp.symbols("x", real=True)
    root = sp.Function("u", positive=True)(x)
    density = root**2
    gradient_ratio = sp.diff(density, x)**2 / density
    check("root_gradient_factor_four",
          sp.simplify(gradient_ratio - 4 * sp.diff(root, x)**2) == 0,
          sp.simplify(gradient_ratio))

    u1, u2, v1, v2 = sp.symbols("u1 u2 v1 v2", nonnegative=True)
    w1, w2, n = sp.symbols("w1 w2 N", positive=True)
    cross = sp.symbols("c", nonnegative=True)
    norm_u = w1 * u1**2 + w2 * u2**2
    norm_v = w1 * v1**2 + w2 * v2**2
    inner = w1 * u1 * v1 + w2 * u2 * v2
    norm_w = w1 * ((1 - t) * u1 + t * v1)**2 + w2 * ((1 - t) * u2 + t * v2)**2
    expanded = (1 - t)**2 * norm_u + t**2 * norm_v + 2 * t * (1 - t) * inner
    equal_population_norm = n * ((1 - t)**2 + t**2) + 2 * t * (1 - t) * cross
    floor_certificate = 2 * n * (t - sp.Rational(1, 2))**2 + 2 * t * (1 - t) * cross
    check("weighted_amplitude_norm_and_floor",
          sp.expand(norm_w - expanded) == 0
          and sp.expand(equal_population_norm - n / 2 - floor_certificate) == 0,
          {"expansion_residual": sp.expand(norm_w - expanded),
           "floor_certificate": floor_certificate})

    jensen_gap = (1 - t) * a**2 + t * b**2 - ((1 - t) * a + t * b)**2
    check("laplacian_jensen_gap",
          sp.expand(jensen_gap - t * (1 - t) * (a - b)**2) == 0,
          sp.factor(jensen_gap))

    e1, e2 = sp.Matrix([1, 0]), sp.Matrix([0, 1])
    midpoint = (e1 + e2) / 2
    midpoint_norm = midpoint.dot(midpoint)
    check("disjoint_support_sharp_floor",
          e1.dot(e2) == 0 and midpoint_norm == sp.Rational(1, 2)
          and 1 / midpoint_norm == 2,
          {"midpoint_norm_squared": midpoint_norm, "normalization_squared": 1 / midpoint_norm})

    metric = sp.Matrix([[1, -sp.Rational(9, 10)], [-sp.Rational(9, 10), 1]])
    metric_cross = (e1.T * metric * e2)[0]
    metric_midpoint = (midpoint.T * metric * midpoint)[0]
    check("nondiagonal_metric_scope_control",
          metric[0, 0] > 0 and metric.det() > 0
          and (e1.T * metric * e1)[0] == 1 and (e2.T * metric * e2)[0] == 1
          and metric_cross < 0 and metric_midpoint == sp.Rational(1, 20),
          {"leading_minor": metric[0, 0], "determinant": metric.det(),
           "cross_inner_product": metric_cross, "midpoint_norm_squared": metric_midpoint})

    p, q = sp.Matrix([1, 1, 0]), sp.Matrix([1, 0, 1])
    boundary_midpoint = (p + q) / 2
    boundary_scale_squared = p.dot(p) / boundary_midpoint.dot(boundary_midpoint)
    check("nonzero_boundary_scope_control",
          p.dot(p) == q.dot(q) and p[0] == q[0] == 1
          and boundary_scale_squared * boundary_midpoint[0]**2 == sp.Rational(4, 3),
          {"population": p.dot(p), "common_boundary": p[0],
           "normalized_boundary_squared": boundary_scale_squared * boundary_midpoint[0]**2})

    theta = sp.symbols("theta", real=True)
    rotation = sp.Matrix([[sp.cos(theta), -sp.sin(theta), 0],
                          [sp.sin(theta), sp.cos(theta), 0], [0, 0, 1]])
    sigma3 = sp.diag(1, -1)
    spinor_rotation = (-sp.I * theta * sigma3 / 2).exp()
    vector_endpoint = rotation.subs(theta, 2 * sp.pi).applyfunc(sp.simplify)
    spinor_endpoint = spinor_rotation.subs(theta, 2 * sp.pi).applyfunc(sp.simplify)
    check("scalar_vector_spinor_rotation_control",
          vector_endpoint == sp.eye(3) and spinor_endpoint == -sp.eye(2),
          {"spatial_endpoint": vector_endpoint, "spinor_endpoint": spinor_endpoint})
    return checks


def run(note: Path, output: Path) -> int:
    output.mkdir(parents=True, exist_ok=False)
    receipt = {"schema": "matter-formation-scalar-topology-v1", "checks": [],
               "numerical_pass": False, "verdict": "INCONCLUSIVE", "failures": [],
               "identities": {}}
    try:
        section = frozen_section(note)
        section_sha = digest(section.encode("utf-8"))
        if section_sha != PROTOCOL_SHA:
            raise ValueError("frozen scalar-topology section hash mismatch")
        receipt["identities"] = {
            "program": {"path": Path(__file__).resolve().relative_to(ROOT).as_posix(),
                        "sha256": digest(Path(__file__).read_bytes().replace(b"\r\n", b"\n"))},
            "protocol": {"path": note.as_posix(), "heading": HEADING.strip(), "sha256": section_sha},
        }
        with (output / "protocol.txt").open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(section)
        receipt["checks"] = exact_checks()
        receipt["failures"] = [row["name"] for row in receipt["checks"] if not row["pass"]]
        if len(receipt["checks"]) != 8:
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
                        default=ROOT / "runs/20260906_matter_formation_scalar_topology")
    args = parser.parse_args()
    return run(args.note.resolve(), args.output_dir.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
