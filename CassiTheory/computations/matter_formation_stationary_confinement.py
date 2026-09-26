#!/usr/bin/env python3
"""Exact identities for the stationary population confinement theorem.

Run from the repository root:
python computations/matter_formation_stationary_confinement.py --output-dir runs/repro_stationary_confinement

The continuum proof and applicability assumptions are in report section 24.
The independent analytical/source reviews are required local evidence inputs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
from pathlib import Path

import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
NOTE = ROOT / "computations/matter-formation-continuum-report.md"
SOLVER = ROOT / "two-fluid/cassi_two_fluid_3d_gpu.py"
HEADING = "### 24.3 Stationary confinement calculation: pre-execution criteria"
PROTOCOL_SHA = "bb94a563ee713e0b3db70b2a81aa2ca9e0c87fa08c59224fa472ce5ca7b62374"
SOLVER_SHA = "258e8783294250b731d93e7b5869b8172558c8aa0742502330cf3dbb5e3c90cc"
REVIEW_ROOT = ROOT / "runs/20260907_matter_formation_stationary_confinement_review"
REVIEWS = {
    "ConfinementProof.json": "3734725cec62ab0673bfb0b961f83742bf37e470e1568eb92752bd38c2ed07c1",
    "ConfinementSource.json": "5537e64df6aca52ce45a8ca79f7966ec2f191bdd5cbd05213d1eb73fa6a7b347",
}
VERDICT = "SUPPORTS—isolated stationary population exclusion under integrable radial drift"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def frozen_section(note: Path) -> bytes:
    text = note.read_text(encoding="utf-8").replace("\r\n", "\n")
    if text.count(HEADING) != 1:
        raise ValueError("Frozen confinement heading must occur exactly once")
    section = text[text.index(HEADING):]
    end = re.search(r"\n#{1,3} ", section)
    section = section[:end.start()] if end else section
    return (section.rstrip() + "\n").encode("utf-8")


def exact_groups() -> list[dict]:
    groups = []

    def group(name: str, relations: list[tuple]) -> None:
        checks = []
        for label, actual, expected in relations:
            actual, expected = sp.sympify(actual), sp.sympify(expected)
            passed = actual == expected
            if not passed and not isinstance(actual, sp.logic.boolalg.Boolean):
                passed = sp.simplify(actual - expected) == 0
            checks.append({"name": label, "actual": str(actual),
                           "expected": str(expected), "passed": bool(passed)})
        groups.append({"name": name, "checks": checks,
                       "passed": all(row["passed"] for row in checks)})

    r, R, T, D, M, K, f0, phi, lam = sp.symbols(
        "r R T D M K f0 phi lambda", positive=True)
    Y, I, dY, dI, u, p = sp.symbols("Y I dY dI u Phi_r", real=True)
    cy, ci, Q = sp.symbols("chi_Y chi Q", real=True)
    jy = Y * u + cy * Y * p - D * dY
    ji = I * u - ci * I * p - D * dI
    conv_y, conv_i = -lam * (Y - phi * I), lam * (Y - phi * I)
    group("total_current_and_conversion", [
        ("population_current", sp.expand(jy + ji),
         (Y + I) * u + (cy * Y - ci * I) * p - D * (dY + dI)),
        ("population_conversion", conv_y + conv_i, 0),
    ])

    mass = sp.Function("M")(r)
    f = sp.Function("f")(r)
    radial_force = mass / (4 * sp.pi * r**2)
    lap_phi = sp.diff(r**2 * radial_force, r) / r**2
    angular_flux, df = sp.symbols("angular_flux df", real=True)
    solved_df = sp.solve(sp.Eq(Q, 4 * sp.pi * r**2 * (angular_flux - D * df)), df)[0]
    group("spherical_flux_and_newtonian_identities", [
        ("sphere_average_with_origin_flux", solved_df,
         angular_flux / D - Q / (4 * sp.pi * D * r**2)),
        ("radial_poisson", lap_phi.subs(sp.diff(mass, r), 4 * sp.pi * r**2 * f), f),
        ("incompressible_radial_velocity", sp.diff(r**2 * Q / r**2, r) / r**2, 0),
        ("origin_velocity_coefficient", sp.limit(r**2 * Q / r**2, r, 0), Q),
    ])

    a, b = sp.symbols("a b", real=True)
    weight = K * ((2 * a - 1) * Y - (2 * b - 1) * I)
    group("component_mobility_bound", [
        ("upper_factorization", K * (Y + I) - weight, 2 * K * ((1 - a) * Y + b * I)),
        ("lower_factorization", K * (Y + I) + weight, 2 * K * (a * Y + (1 - b) * I)),
        ("negative_a_excluded", sp.reduce_inequalities([a >= 0, a <= 1, a < 0], a), False),
        ("negative_one_minus_a_excluded", sp.reduce_inequalities([a >= 0, a <= 1, 1 - a < 0], a), False),
        ("negative_b_excluded", sp.reduce_inequalities([b >= 0, b <= 1, b < 0], b), False),
        ("negative_one_minus_b_excluded", sp.reduce_inequalities([b >= 0, b <= 1, 1 - b < 0], b), False),
    ])

    G = sp.Function("G")(r)
    factor = sp.exp(G / D)
    group("integrating_factor", [
        ("differentiated_lower_bound", sp.diff(factor * f, r),
         factor * (sp.diff(f, r) + sp.diff(G, r) * f / D)),
    ])

    tail = sp.integrate(K * M / (4 * sp.pi * r**2), (r, R, sp.oo))
    floor = f0 * sp.exp(-tail / D)
    lower_population = sp.integrate(4 * sp.pi * r**2 * floor, (r, R, T))
    group("newtonian_tail_and_population", [
        ("finite_force_tail", tail, K * M / (4 * sp.pi * R)),
        ("positive_tail_floor", floor.is_positive, True),
        ("enclosed_population_lower_bound", lower_population,
         4 * sp.pi * floor * (T**3 - R**3) / 3),
        ("infinite_population_lower_bound", sp.limit(lower_population, T, sp.oo), sp.oo),
    ])

    rho = (1 + r**2)**-2
    ey, ei = phi * rho / (1 + phi), rho / (1 + phi)
    inward_u = -4 * D * r / (1 + r**2)
    envelope_integral = sp.integrate(-inward_u, (r, R, T))
    group("normalizable_scope_controls", [
        ("confining_yang_current", ey * inward_u - D * sp.diff(ey, r), 0),
        ("confining_yin_current", ei * inward_u - D * sp.diff(ei, r), 0),
        ("equilibrium_conversion", -lam * (ey - phi * ei), 0),
        ("finite_control_population", sp.integrate(4 * sp.pi * r**2 * rho, (r, 0, sp.oo)), sp.pi**2),
        ("nonintegrable_control_envelope", sp.limit(envelope_integral, T, sp.oo), sp.oo),
        ("zero_diffusion_yang_current", (-D * sp.diff(ey, r)).subs(D, 0), 0),
        ("zero_diffusion_yin_current", (-D * sp.diff(ei, r)).subs(D, 0), 0),
    ])

    x, y, z, theta = sp.symbols("x y z theta", real=True)
    swirl = sp.Matrix([-y, x, 0])
    coords = sp.Matrix([x, y, z])
    tangent = sp.Matrix([-sp.sin(theta), sp.cos(theta), 0])
    circle_u = swirl.subs({x: sp.cos(theta), y: sp.sin(theta)})
    source_flux = 4 * sp.pi * r**2 * (-D * sp.diff(1 / r, r))
    group("angular_current_and_origin_source", [
        ("solenoidal_circulation", sum(sp.diff(swirl[i], coords[i]) for i in range(3)), 0),
        ("zero_radial_circulation", swirl.dot(coords), 0),
        ("nonzero_closed_loop_circulation", sp.integrate(circle_u.dot(tangent), (theta, 0, 2 * sp.pi)), 2 * sp.pi),
        ("point_source_integrated_flux", source_flux, 4 * sp.pi * D),
        ("origin_flux_correction", D * sp.diff(1 / r, r) + source_flux / (4 * sp.pi * r**2), 0),
    ])
    return groups


def run(output: Path, note: Path) -> int:
    output.mkdir(parents=True, exist_ok=False)
    receipt = {"schema": "matter-formation-stationary-confinement-v1",
               "verdict": "INCONCLUSIVE", "passed": False,
               "groups": [], "files": {}, "error": None,
               "environment": {"python": platform.python_version(), "sympy": sp.__version__}}

    def retain(name: str, data: bytes) -> None:
        (output / name).write_bytes(data)
        receipt["files"][name] = sha(data)

    try:
        retain("source_primary.py", Path(__file__).read_bytes())
        protocol = frozen_section(note)
        retain("frozen_protocol.txt", protocol)
        if sha(protocol) != PROTOCOL_SHA:
            raise ValueError("Frozen confinement section hash mismatch")
        solver = SOLVER.read_bytes()
        retain("source_solver.py", solver)
        if sha(solver.replace(b"\r\n", b"\n")) != SOLVER_SHA:
            raise ValueError("Canonical solver hash mismatch")
        for name, expected in REVIEWS.items():
            data = (REVIEW_ROOT / name).read_bytes()
            if sha(data) != expected:
                raise ValueError(f"Independent review hash mismatch: {name}")
            json.loads(data)
            retain(name, data)
        receipt["groups"] = exact_groups()
        receipt["passed"] = all(row["passed"] for row in receipt["groups"])
        if receipt["passed"]:
            receipt["verdict"] = VERDICT
    except Exception as error:
        receipt["error"] = f"{type(error).__name__}: {error}"
    with (output / "results.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(receipt, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"verdict": receipt["verdict"], "groups": len(receipt["groups"]),
                      "failed_groups": [row["name"] for row in receipt["groups"] if not row["passed"]],
                      "error": receipt["error"]}, ensure_ascii=False, allow_nan=False))
    return 0 if receipt["passed"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--record", type=Path, default=NOTE)
    args = parser.parse_args()
    return run(args.output_dir.resolve(), args.record.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
