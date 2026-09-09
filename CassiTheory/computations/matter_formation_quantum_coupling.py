#!/usr/bin/env python3
"""Scalar quantum coupling qualification for working notebook section 66.

python computations/matter_formation_quantum_coupling.py --manifest PATH --output FRESH_DIR
The supplied scalar action and MS-bar convention do not select physical matter.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path

import numpy as np
import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
REPORT = "computations/matter-formation-continuum-report.md"
HEADINGS = {
    "## 66. Working notes: quantum coupling normalization and radiative closure",
    "## 64. Working notes: matching quantum conversion to the scalar action",
}
SOURCES = {
    "computations/matter_formation_quantum_coupling.py",
    "computations/verify_matter_formation_scalar_scattering.py",
    "computations/verify_matter_formation_scalar_radiative.py",
    "foundations/particle-stationary-action-closure.md",
}
SCHEMA = "matter-formation-quantum-coupling-v1"
MANIFEST_SCHEMA = "matter-formation-quantum-coupling-manifest-v1"
VERDICT = "SUPPORTS-conditional scalar quantum coupling constraints"
H_KEYS = ("0", "2", "2.9598260763447164", "6")
NORMS = (1, 4, 16, 64)
CHANNELS = ((0, 0), (1, 1), (2, 2), (0, 1), (0, 2), (1, 2))
BOUND = 1e-9


def canonical(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def digest(path: Path) -> str:
    return hashlib.sha256(canonical(path)).hexdigest()


def validate_manifest(path: Path) -> None:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValueError("unexpected manifest schema")
    sections = manifest["sections"]
    if len(sections) != 2 or {item["heading"] for item in sections} != HEADINGS:
        raise ValueError("incomplete or duplicate section bindings")
    lines = canonical(ROOT / REPORT).decode("utf-8").splitlines(keepends=True)
    for item in sections:
        if item["path"] != REPORT:
            raise ValueError("unexpected section path")
        starts = [i for i, line in enumerate(lines) if line.rstrip() == item["heading"]]
        if len(starts) != 1:
            raise ValueError("section must occur exactly once")
        start = starts[0]
        stop = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
        live = ("".join(lines[start:stop]).rstrip() + "\n").encode("utf-8")
        if hashlib.sha256(live).hexdigest() != item["sha256"] or canonical(ROOT / item["snapshot"]) != live:
            raise ValueError("frozen or live section mismatch")
    sources = manifest["sources"]
    if len(sources) != len(SOURCES) or {item["path"] for item in sources} != SOURCES:
        raise ValueError("incomplete or duplicate source bindings")
    for item in sources:
        if digest(ROOT / item["path"]) != item["sha256"] or digest(ROOT / item["snapshot"]) != item["sha256"]:
            raise ValueError("source mismatch: " + item["path"])
    reviews = manifest["mathematical_reviews"]
    if len(reviews) != 2 or {item["role"] for item in reviews} != {"scattering", "radiative"}:
        raise ValueError("incomplete or duplicate reviews")
    for item in reviews:
        path = ROOT / item["snapshot"]
        flags = [line.strip() for line in canonical(path).decode("utf-8").splitlines()
                 if line.strip().startswith("accepted:")]
        if item.get("accepted") is not True or flags != ["accepted: true"] or digest(path) != item["sha256"]:
            raise ValueError("unaccepted mathematical review: " + item["role"])


def tensor(indices: tuple[int, ...], L, P, U):
    ordered = tuple(sorted(indices))
    if ordered == (0, 0, 0, 0):
        return L
    if ordered in ((1, 1, 1, 1), (2, 2, 2, 2)):
        return 3 * U
    if ordered in ((0, 0, 1, 1), (0, 0, 2, 2)):
        return P
    if ordered == (1, 1, 2, 2):
        return U
    return sp.S.Zero


def zero(value) -> bool:
    return sp.simplify(value) == 0


def compare(actual, expected) -> bool:
    actual = np.asarray(actual, dtype=np.float64)
    expected = np.asarray(expected, dtype=np.float64)
    if actual.shape != expected.shape or not np.isfinite(actual).all() or not np.isfinite(expected).all():
        return False
    return bool(np.linalg.norm(actual - expected) / max(1.0, float(np.linalg.norm(expected))) <= BOUND)


def exact_calculation() -> dict:
    L, P, U = sp.symbols("L P U", real=True)
    S, X, Y = sp.symbols("S X Y", real=True)
    ms, mc = sp.symbols("muS2 muC2", real=True)
    fields = (S, X, Y)
    n, a, cp, ur, uc, h, e = sp.symbols("N a cPsi ur uc h e", positive=True)
    speed = 1 / sp.sqrt(cp)
    vh = sp.sqrt(n * cp) * speed ** sp.Rational(3, 2)
    f = S / vh
    density = (X * X + Y * Y) / (2 * n * a * speed**3)
    B = e + 1 / (4 * a)
    source = n * speed**3 * (ur * (f * f - 1)**2 / 4 + (B - h + h * f * f) * density + uc * density**2 / 2)
    couplings = (6 * ur / (n * cp**2 * speed**3), 2 * h / (n * a * cp * speed**3), uc / (n * a*a * speed**3))
    masses = (-ur / cp, (B - h) / a)
    constant = n * speed**3 * ur / 4
    quartic = L * S**4 / 24 + P * S*S * (X*X + Y*Y) / 4 + U * (X*X + Y*Y)**2 / 8
    reconstructed = constant + masses[0] * S*S / 2 + masses[1] * (X*X + Y*Y) / 2 + quartic.subs(dict(zip((L, P, U), couplings)))
    checks = {
        "canonical_full_potential": zero(source - reconstructed),
        "canonical_mediator_kinetic": zero(n * speed**3 * cp / vh**2 - 1),
        "unit_cone_mediator_gradient": zero(n * speed / vh**2 - 1),
        "canonical_carrier_kinetic": zero(n * speed**3 * a / (n * a * speed**3) - 1),
        "unit_cone_carrier_gradient": zero((2*a/cp) / (2*a*speed**2) - 1),
    }
    tensor_potential = sum(tensor(ids, L, P, U) * sp.prod(fields[i] for i in ids)
                           for ids in itertools.product(range(3), repeat=4)) / 24
    checks["tensor_potential"] = zero(tensor_potential - quartic)
    factors = [sp.sqrt(1 + (i == j)) for i, j in CHANNELS]
    C = sp.Matrix(6, 6, lambda i, j: tensor(CHANNELS[i] + CHANNELS[j], L, P, U) / (factors[i] * factors[j]))
    eigen_parameter = sp.symbols("z", real=True)
    polynomial = (eigen_parameter-U)**2 * (eigen_parameter-P)**2 * ((eigen_parameter-L/2)*(eigen_parameter-2*U)-P**2/2)
    characteristic = C.charpoly(eigen_parameter)
    checks["full_characteristic_polynomial"] = zero(characteristic.as_expr().subs(characteristic.gen, eigen_parameter) - polynomial)
    cut = sp.Matrix(6, 6, lambda i, j: sum(tensor(CHANNELS[i] + (m, q), L, P, U) * tensor((m, q) + CHANNELS[j], L, P, U)
                                                     for m in range(3) for q in range(3)) / (2*factors[i]*factors[j]))
    checks["identical_pair_optical_cut"] = all(zero(v) for v in cut - C*C)
    beta_tensor = {}
    for i, j, k, ell in itertools.product(range(3), repeat=4):
        beta_tensor[i, j, k, ell] = sp.expand(sum(
            tensor((i, j, m, q), L, P, U) * tensor((m, q, k, ell), L, P, U)
            + tensor((i, k, m, q), L, P, U) * tensor((m, q, j, ell), L, P, U)
            + tensor((i, ell, m, q), L, P, U) * tensor((m, q, j, k), L, P, U)
            for m in range(3) for q in range(3)))
    betas = (beta_tensor[0, 0, 0, 0], beta_tensor[0, 0, 1, 1], beta_tensor[1, 1, 2, 2])
    expected = (3*L*L + 6*P*P, P*(L+4*U+4*P), 10*U*U+P*P)
    checks["three_quartic_beta_functions"] = all(zero(x-y) for x, y in zip(betas, expected))
    checks["all_tensor_components_close"] = all(zero(value-tensor(indices, *betas)) for indices, value in beta_tensor.items())
    mass_beta = sp.Matrix(3, 3, lambda i, j: sum(tensor((i, j, k, k), L, P, U)*mass for k, mass in enumerate((ms, mc, mc))))
    mass_expected = sp.diag(L*ms+2*P*mc, P*ms+4*U*mc, P*ms+4*U*mc)
    checks["full_mass_counterterm_matrix"] = all(zero(v) for v in mass_beta-mass_expected)
    const_beta = (ms**2 + 2*mc**2) / 2
    ratio_beta = sp.factor(3*(L*betas[1]-P*betas[0])/L**2)
    ray = sp.expand(betas[0] - 6*betas[2])
    checks["retained_ray_drift"] = zero(ray.subs({L: 6*U, P: h*U}) - 48*U*U)
    checks["first_tree_zero_drift"] = zero(ratio_beta.subs({P: L/3, U: L/6}) + 2*L/3)
    checks["second_tree_zero_drift"] = zero(ratio_beta.subs({P: L, U: L/6}) + 10*L)
    checks["real_scalar_limit"] = zero(betas[0].subs({P: 0, U: 0}) - 3*L*L)
    checks["O2_limit"] = zero(betas[2].subs({L: 0, P: 0}) - 10*U*U)
    o3 = [sp.expand(value.subs({L: 3*U, P: U})) for value in betas]
    checks["O3_quartic_flow"] = all(zero(x-y) for x, y in zip(o3, (33*U*U, 11*U*U, 11*U*U)))
    checks["Gaussian_limit"] = all(zero(value.subs({L: 0, P: 0, U: 0})) for value in betas)
    checks["fixed_point_square_identity"] = zero(betas[0]-3*L*L-6*P*P) and zero(betas[2]-10*U*U-P*P)
    ly = sp.symbols("lambdaY", real=True)
    checks["single_real_scalar_partial_wave"] = zero((C[0, 0].subs(L, 6*ly))/(16*sp.pi) - 3*ly/(16*sp.pi))
    checks["single_real_scalar_bound_saturation"] = zero((3*ly/(16*sp.pi)).subs(ly, 8*sp.pi/3) - sp.Rational(1, 2))
    base = {a: sp.Rational(1, 16), cp: sp.Rational(1, 8), ur: 4, uc: 1, e: sp.Rational(3, 4)}
    checks["retained_normalization_family"] = all(zero(value.subs(base)-8*sp.sqrt(2)*target/n)
                                                   for value, target in zip(couplings, (6, h, 1)))
    return dict(checks=checks, C=C, variables=(L, P, U, ms, mc), betas=betas,
                mass_beta=(mass_beta[0, 0], mass_beta[1, 1]), const_beta=const_beta,
                ratio_beta=ratio_beta, ray=ray,
                symbolic={"quartic_beta_numerators": [str(v) for v in betas],
                          "mass_beta_numerators": [str(mass_beta[i, i]) for i in (0, 1)],
                          "constant_beta_numerator": str(const_beta), "ratio_beta_numerator": str(ratio_beta),
                          "ray_drift_numerator": str(ray), "characteristic_polynomial": str(polynomial),
                          "fixed_point_proof": "For real couplings beta_L=0 forces L=P=0; beta_U=0 then forces U=0. This is only a one-loop statement."})


def calculate() -> dict:
    exact = exact_calculation()
    checks = exact["checks"]
    rows = []
    Ls, Ps, Us, ms, mc = exact["variables"]
    c = math.sqrt(8.0)
    for norm in NORMS:
        for h_key in H_KEYS:
            h = float(h_key)
            U = 8*math.sqrt(2.0)/norm
            L, P = 6*U, h*U
            mass2 = (-32.0, 16*(4.75-h))
            values = dict(zip((Ls, Ps, Us, ms, mc), (L, P, U, *mass2)))
            matrix = np.asarray(exact["C"].subs(values), dtype=np.float64)
            eig = np.linalg.eigvalsh(matrix)
            split = math.sqrt((L-4*U)**2 + 8*P*P)/4
            expected = sorted((U, U, P, P, L/4+U-split, L/4+U+split))
            radius = float(np.max(np.abs(eig)))/(16*math.pi)
            key = f"N{norm}-h{h_key}"
            checks[key+"_spectrum"] = compare(eig, expected)
            checks[key+"_bound_formula"] = compare(2*norm*radius, math.sqrt(2)/(2*math.pi)*(5+math.sqrt(1+2*h*h)))
            checks[key+"_spectral_invariants"] = compare([sum(eig), sum(eig*eig)], [np.trace(matrix), np.trace(matrix@matrix)])
            rows.append(dict(key=key, N=norm, h=h, c=c, couplings=[L, P, U], C=matrix.tolist(),
                             eigenvalues=eig.tolist(), a0_radius=radius, N_min_tree=2*norm*radius,
                             tree_bound_pass=bool(radius <= 0.5),
                             beta_quartic_numerator=[float(v.subs(values)) for v in exact["betas"]],
                             mass2=list(mass2), beta_mass_numerator=[float(v.subs(values)) for v in exact["mass_beta"]],
                             beta_constant_numerator=float(exact["const_beta"].subs(values)),
                             beta_x_numerator=float(exact["ratio_beta"].subs(values)),
                             ray_drift_numerator=float(exact["ray"].subs(values))))
    passed = all(checks.values())
    return dict(schema=SCHEMA, role="primary", verdict=VERDICT if passed else "INCONCLUSIVE",
                numeric_pass=passed, error=None, checks=checks, symbolic=exact["symbolic"], rows=rows,
                complete_physical_matter_formation=False,
                scope="Supplied scalar action, high-energy tree criterion and one-loop MS-bar potential counterterms; no production rate or microscopic selection.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    try:
        validate_manifest(args.manifest)
        result = calculate()
        text = json.dumps(result, indent=2, allow_nan=False) + "\n"
    except Exception as exc:
        result = dict(schema=SCHEMA, role="primary", verdict="INCONCLUSIVE", numeric_pass=False,
                      error=f"{type(exc).__name__}: {exc}", checks={}, rows=[],
                      complete_physical_matter_formation=False)
        text = json.dumps(result, indent=2, allow_nan=False) + "\n"
    (args.output / "result.json").write_text(text, encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("role", "verdict", "numeric_pass", "error", "complete_physical_matter_formation")}, allow_nan=False))
    return 0 if result["numeric_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
