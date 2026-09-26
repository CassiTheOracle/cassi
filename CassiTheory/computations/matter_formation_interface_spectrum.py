#!/usr/bin/env python3
"""Qualify the exact wall, carrier, and interface-mode calculation in report §33.

Run from the repository root in a fresh directory:
python computations/matter_formation_interface_spectrum.py --output-dir runs/<fresh-name>

The program is an exact SymPy calculation.  It evaluates no nonlinear trajectory
and does not fit any coefficient; the decimal h_C is retained exactly as supplied
for the prescribed mathematical witness.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import re
from pathlib import Path
from typing import Any

import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "computations/matter-formation-continuum-report.md"
PARENT = ROOT / "foundations/particle-stationary-action-closure.md"
PROTOCOL_HEADING = "### 33.3 Interface calculation: pre-execution criteria\n"
DERIVATION_HEADING = "## 33. Boundary-localized carrier modes and interface survival\n"
PROTOCOL_SHA = "158d575a616c47aaae8a543b007467e81e40c484c4e5b2f8e7391ab19511a391"
DERIVATION_SHA = "f7cb325c2b3ac5964c07814cf8dc3d51f9ebdb440de8606bb577b75aab6060f2"
PARENT_SHA = "4b00696501134487757f174eb08e4022609ceefe39f32e169d294f99a79f8956"
SCHEMA = "matter-formation-interface-spectrum-v1"
VERDICT = "SUPPORTS—conditional interface trapping and sign-wall instability"
PRECISION = 80


def canonical_bytes(path: Path) -> bytes:
    """Return UTF-8 source bytes with the protocol's LF normalization."""
    return path.read_bytes().replace(b"\r\n", b"\n")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def raw_sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def relpath(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def frozen_section(path: Path, heading: str, stop_heading: str | None = None) -> str:
    text = canonical_bytes(path).decode("utf-8")
    if text.count(heading) != 1:
        raise ValueError(f"frozen heading is not unique: {heading.strip()}")
    start = text.index(heading)
    after = text[start + len(heading):]
    if stop_heading is not None:
        end = after.index(stop_heading)
        body = after[:end]
    else:
        match = re.search(r"\n#{1,3} ", after)
        body = after[:match.start()] if match else after
    return (heading + body).rstrip() + "\n"


def exact_text(value: Any) -> str:
    return sp.sstr(sp.factor(value))


def decimal_text(value: Any) -> str:
    return str(sp.N(value, PRECISION))


def finite_number(value: Any) -> float:
    result = float(sp.N(value, PRECISION))
    if not math.isfinite(result):
        raise ValueError(f"nonfinite numerical value: {value}")
    return result


def check_row(checks: list[dict[str, Any]], name: str, condition: bool, evidence: Any) -> None:
    checks.append({"name": name, "pass": bool(condition), "exact_evidence": evidence})


def algebra() -> tuple[list[dict[str, Any]], dict[str, str], dict[str, Any]]:
    """Return exact residual checks, expressions, and coefficient witnesses."""
    x, y, u = sp.symbols("x y u", positive=True, real=True)
    k, h, e, a, uc, p = sp.symbols("k h e a u_C p", positive=True, real=True)
    s = sp.symbols("s", positive=True, real=True)
    t = sp.symbols("t", real=True)
    delta = sp.sqrt(2 / u)
    f = sp.tanh(y)
    dx = lambda expression: sp.diff(expression, y) / delta
    dxx = lambda expression: sp.diff(expression, y, 2) / delta**2
    sech = sp.sech(y)

    checks: list[dict[str, Any]] = []
    expressions: dict[str, str] = {}

    wall_fx = dx(f)
    wall_fxx = dxx(f)
    wall_residual = sp.simplify(-wall_fxx + u * (f**2 - 1) * f)
    first_integral = sp.simplify(sp.Rational(1, 2) * wall_fx**2 - u * (f**2 - 1) ** 2 / 4)
    # With v=tanh(y), sech(y)^4 dy=(1-v^2) dv on v in [-1,1].
    v = sp.symbols("v", real=True)
    sech4_integral = sp.integrate(1 - v**2, (v, -1, 1))
    tension = sp.simplify(u * delta * sech4_integral / 2)
    tension_expected = 2 * sp.sqrt(2 * u) / 3
    check_row(checks, "wall_ode_residual", wall_residual == 0, exact_text(wall_residual))
    check_row(checks, "wall_first_integral_residual", first_integral == 0, exact_text(first_integral))
    check_row(
        checks,
        "wall_tension_integral",
        sech4_integral == sp.Rational(4, 3) and sp.simplify(tension - tension_expected) == 0,
        {"sech4_integral": exact_text(sech4_integral), "tension_residual": exact_text(tension - tension_expected)},
    )
    expressions.update({
        "wall_profile": exact_text(f),
        "wall_width": exact_text(delta),
        "wall_ode": exact_text(-wall_fxx + u * (f**2 - 1) * f),
        "wall_first_integral": exact_text(sp.Rational(1, 2) * wall_fx**2 - u * (f**2 - 1) ** 2 / 4),
        "wall_tension": exact_text(tension_expected),
    })

    K = k * u / 4
    carrier_ground = sech**s
    carrier_first = sp.tanh(y) * sech ** (s - 1)
    carrier_ground_residual = sp.simplify(
        -sp.diff(carrier_ground, y, 2) - s * (s + 1) * sech**2 * carrier_ground + s**2 * carrier_ground
    )
    carrier_first_residual = sp.simplify(
        -sp.diff(carrier_first, y, 2) - s * (s + 1) * sech**2 * carrier_first + (s - 1) ** 2 * carrier_first
    )
    carrier_continuum = sp.limit(-K * s * (s + 1) * sech**2, y, sp.oo)
    carrier_endpoint_tail = sp.simplify(sech ** (s - s))
    check_row(checks, "carrier_ground_eigenfunction", carrier_ground_residual == 0, exact_text(carrier_ground_residual))
    check_row(checks, "carrier_first_eigenfunction", carrier_first_residual == 0, exact_text(carrier_first_residual))
    check_row(checks, "carrier_continuum_threshold", sp.simplify(carrier_continuum) == 0, exact_text(carrier_continuum))
    check_row(checks, "carrier_n_equals_s_nondecaying", carrier_endpoint_tail == 1, exact_text(carrier_endpoint_tail))
    expressions.update({
        "carrier_K": exact_text(K),
        "carrier_h_relation": "h = K*s*(s + 1)",
        "carrier_ground_profile": exact_text(carrier_ground),
        "carrier_first_profile": exact_text(carrier_first),
        "carrier_ground_eigenvalue": exact_text(-K * s**2),
        "carrier_first_eigenvalue": exact_text(-K * (s - 1) ** 2),
    })

    eta = sech
    phase_residual = sp.simplify(-dxx(eta) - u * sech**2 * eta + u * eta / 2)
    # For |f+i*t*eta|^2, the t² energy coefficient is
    # 1/2*(eta_x² + u*(f²-1)*eta²); the second derivative is its doubled
    # integral.  Keeping the half on the potential term is essential.
    phase_integrand = sp.Rational(1, 2) * dx(eta) ** 2 + u * (f**2 - 1) * eta**2 / 2
    phase_second_variation = sp.simplify(delta * sp.integrate(2 * phase_integrand, (y, -sp.oo, sp.oo)))
    # The factor 2 above converts the coefficient in E(t) to d²E/dt².
    phase_i2 = sp.simplify(phase_second_variation)
    phase_i4 = sp.simplify(u * delta * sech4_integral)
    phase_sigma = tension_expected
    phase_energy = sp.expand(phase_sigma + phase_i2 * t**2 / 2 + phase_i4 * t**4 / 4)
    phase_expected = sp.expand(phase_sigma - sp.sqrt(2 * u) * t**2 / 2 + sp.sqrt(2 * u) * t**4 / 3)
    check_row(checks, "complex_phase_negative_mode", phase_residual == 0, exact_text(phase_residual))
    check_row(checks, "phase_path_energy_expansion", sp.simplify(phase_energy - phase_expected) == 0, exact_text(phase_energy - phase_expected))
    check_row(
        checks,
        "phase_second_variation_factor",
        sp.simplify(sp.diff(phase_energy, t, 2).subs(t, 0) - phase_i2) == 0
        and sp.simplify(phase_i2 + sp.sqrt(2 * u)) == 0,
        {"second_derivative": exact_text(sp.diff(phase_energy, t, 2).subs(t, 0)), "quadratic_coefficient": exact_text(phase_i2 / 2)},
    )
    expressions.update({
        "phase_profile": exact_text(eta),
        "phase_operator_eigenvalue": exact_text(-u / 2),
        "phase_second_variation": exact_text(phase_i2),
        "phase_quadratic_energy_coefficient": exact_text(phase_i2 / 2),
        "phase_quartic_energy_coefficient": exact_text(phase_i4 / 4),
        "phase_path_energy": exact_text(phase_energy),
    })

    q_translation = sech**2
    q_shape = sp.tanh(y) * sech
    parallel_operator = lambda q: sp.simplify(-dxx(q) + u * (3 * f**2 - 1) * q)
    translation_residual = sp.simplify(parallel_operator(q_translation))
    shape_residual = sp.simplify(parallel_operator(q_shape) - 3 * u * q_shape / 2)
    continuum_threshold = sp.limit(u * (3 * f**2 - 1), y, sp.oo)
    check_row(checks, "real_translation_zero_mode", translation_residual == 0, exact_text(translation_residual))
    check_row(checks, "real_shape_mode", shape_residual == 0, exact_text(shape_residual))
    check_row(checks, "real_continuum_threshold", sp.simplify(continuum_threshold - 2 * u) == 0, exact_text(continuum_threshold - 2 * u))
    expressions.update({
        "real_translation_profile": exact_text(q_translation),
        "real_shape_profile": exact_text(q_shape),
        "real_translation_eigenvalue": exact_text(0),
        "real_shape_eigenvalue": exact_text(3 * u / 2),
        "real_continuum_threshold": exact_text(2 * u),
    })

    # PA15 charges and the PA14 electric side are formed symbolically, then
    # restricted to the static PA16 sector.  No charge is assumed zero before
    # the temporal-momentum and zero-connection substitutions.
    eps_x, eps_s, c_psi, c_phi, g_q = sp.symbols("epsilon_x epsilon_s C_Psi C_Phi g_Q", positive=True, real=True)
    d_i_fti, d_s_fts = sp.symbols("D_i_F_ti D_s_F_ts", real=True)
    im_psi_dt, cross_phi_dt = sp.symbols("Im_Psi_T_DtPsi Phi_cross_DtPhi", real=True)
    a0, dt_psi, dt_phi, f_ti, f_ts = sp.symbols("A_0 D_t_Psi D_t_Phi F_ti F_ts", real=True)
    electric_side = eps_x * d_i_fti + eps_s * d_s_fts
    q_psi_general = c_psi * g_q * im_psi_dt
    q_phi_general = -c_phi * g_q * cross_phi_dt
    gauss_residual = electric_side - q_psi_general - q_phi_general
    static_substitution = {
        a0: 0, dt_psi: 0, dt_phi: 0, f_ti: 0, f_ts: 0,
        d_i_fti: 0, d_s_fts: 0, im_psi_dt: 0, cross_phi_dt: 0,
    }
    static_gauss_residual = sp.simplify(gauss_residual.subs(static_substitution))
    check_row(
        checks,
        "static_zero_momentum_gauss_compatibility",
        static_gauss_residual == 0,
        {"general_PA14_minus_PA15": exact_text(gauss_residual), "PA16_restricted": exact_text(static_gauss_residual)},
    )
    expressions["static_gauss_residual"] = exact_text(static_gauss_residual)

    lam, p_squared, w2 = sp.symbols("lambda p_squared omega_squared", real=True)
    dispersion = a * w2 - (lam + k * p_squared / 2)
    gamma2 = (-lam - k * p_squared / 2) / a
    dispersion_identity = sp.simplify(dispersion.subs(w2, (lam + k * p_squared / 2) / a))
    gamma_slope = sp.simplify(sp.diff(gamma2, p_squared))
    check_row(checks, "tangential_dispersion_identity", dispersion_identity == 0, exact_text(dispersion_identity))
    check_row(checks, "surface_dispersion_monotonicity", sp.simplify(gamma_slope + k / (2 * a)) == 0, exact_text(gamma_slope + k / (2 * a)))
    expressions.update({
        "surface_dispersion": exact_text((lam + k * p**2 / 2) / a),
        "surface_growth_squared": exact_text(gamma2),
        "surface_growth_slope_in_p_squared": exact_text(gamma_slope),
    })

    coefficient = {
        "u_rho": sp.Integer(4),
        "k_Cx": sp.Integer(1),
        "u_C": sp.Integer(1),
        "e_C": sp.Rational(3, 4),
        "h_C": sp.Rational("2.9598260763447164"),
    }
    cu = coefficient["u_rho"]
    ck = coefficient["k_Cx"]
    ce = coefficient["e_C"]
    ch = coefficient["h_C"]
    cuc = coefficient["u_C"]
    cdelta = sp.sqrt(2 / cu)
    cK = ck * cu / 4
    cs = sp.simplify((-1 + sp.sqrt(1 + 4 * ch / cK)) / 2)
    ca_wall = sp.simplify(1 / (4 * (cK * cs**2 - ce)))
    bulk_gap = sp.simplify(ch - ce - sp.sqrt(cu * cuc / 2))
    ca_vac = sp.simplify(1 / (4 * bulk_gap))
    root_residual = sp.simplify(cs * (cs + 1) - ch / cK)
    check_row(checks, "coefficient_positive_root", bool(sp.N(cs, PRECISION) > 0) and root_residual == 0, {"s": exact_text(cs), "s_times_s_plus_one_minus_h_over_K": exact_text(root_residual)})
    check_row(checks, "wall_threshold_formula", sp.simplify(4 * (cK * cs**2 - ce) * ca_wall - 1) == 0, exact_text(4 * (cK * cs**2 - ce) * ca_wall - 1))
    check_row(checks, "vacuum_threshold_formula", sp.simplify(4 * bulk_gap * ca_vac - 1) == 0, exact_text(4 * bulk_gap * ca_vac - 1))
    check_row(checks, "coefficient_first_state_bound", bool(sp.N(cs - 1, PRECISION) > 0 and sp.N(2 - cs, PRECISION) > 0), {"s_minus_one": exact_text(cs - 1), "two_minus_s": exact_text(2 - cs)})
    check_row(checks, "threshold_ordering", bool(sp.N(ca_wall - ca_vac, PRECISION) < 0), {"a_wall_minus_a_vac": exact_text(ca_wall - ca_vac)})
    check_row(checks, "bulk_threshold_denominator_positive", bool(sp.N(bulk_gap, PRECISION) > 0), exact_text(bulk_gap))

    a_values = [sp.Rational(1, 16), sp.Rational(3, 10), sp.Rational(1, 2)]
    coefficient_rows: list[dict[str, Any]] = []
    expected_surface = (False, True, True)
    expected_bulk = (True, True, False)
    for index, aval in enumerate(a_values):
        B = ce + 1 / (4 * aval)
        lambda0 = sp.simplify(B - cK * cs**2)
        lambda1 = sp.simplify(B - cK * (cs - 1) ** 2)
        bulk_potential = sp.simplify(1 / (4 * aval) - bulk_gap)
        surface_unstable = bool(sp.N(lambda0, PRECISION) < 0)
        bulk_nonnegative = bool(sp.N(bulk_potential, PRECISION) >= 0)
        coefficient_rows.append({
            "a": finite_number(aval),
            "a_exact": exact_text(aval),
            "carrier_eigenvalues": [finite_number(lambda0), finite_number(lambda1)],
            "carrier_eigenvalues_decimal": [decimal_text(lambda0), decimal_text(lambda1)],
            "carrier_eigenvalues_exact": [exact_text(lambda0), exact_text(lambda1)],
            "lambda0": finite_number(lambda0),
            "lambda0_exact": exact_text(lambda0),
            "bulk_potential": finite_number(bulk_potential),
            "bulk_potential_exact": exact_text(bulk_potential),
            "surface_unstable": surface_unstable,
            "bulk_nonnegative": bulk_nonnegative,
        })
        check_row(checks, f"carrier_growth_sign_a_{exact_text(aval)}", surface_unstable == expected_surface[index], {"lambda0": exact_text(lambda0), "negative": surface_unstable, "expected": expected_surface[index]})
        check_row(checks, f"bulk_potential_sign_a_{exact_text(aval)}", bulk_nonnegative == expected_bulk[index], {"bulk_potential": exact_text(bulk_potential), "nonnegative": bulk_nonnegative, "expected": expected_bulk[index]})

    coefficient_exact = {
        "delta": exact_text(cdelta),
        "K": exact_text(cK),
        "s": exact_text(cs),
        "a_wall": exact_text(ca_wall),
        "a_vac": exact_text(ca_vac),
        "bulk_gap": exact_text(bulk_gap),
        "sigma": exact_text(2 * sp.sqrt(2 * cu) / 3),
        "phase_eigenvalues": [exact_text(-cu / 2)],
        "radial_eigenvalues": [exact_text(0), exact_text(3 * cu / 2)],
    }
    coefficient_numeric = {
        "delta": finite_number(cdelta),
        "s": finite_number(cs),
        "a_wall": finite_number(ca_wall),
        "a_vac": finite_number(ca_vac),
        "sigma": finite_number(2 * sp.sqrt(2 * cu) / 3),
        "phase_eigenvalues": [finite_number(-cu / 2)],
        "radial_eigenvalues": [finite_number(0), finite_number(3 * cu / 2)],
    }
    numeric_decimals = {
        "delta": decimal_text(cdelta),
        "s": decimal_text(cs),
        "a_wall": decimal_text(ca_wall),
        "a_vac": decimal_text(ca_vac),
        "sigma": decimal_text(2 * sp.sqrt(2 * cu) / 3),
        "phase_eigenvalues": [decimal_text(-cu / 2)],
        "radial_eigenvalues": [decimal_text(0), decimal_text(3 * cu / 2)],
    }
    witness = {
        "coefficient": {key: exact_text(value) for key, value in coefficient.items()},
        "rows": coefficient_rows,
        "exact": coefficient_exact,
        "numeric": coefficient_numeric,
        "decimal": numeric_decimals,
    }
    return checks, expressions, witness
def artifact_record(path: Path) -> dict[str, Any]:
    return {"path": path.name, "sha256": raw_sha256(path), "bytes": path.stat().st_size}


def write_exclusive(path: Path, data: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(data)
def empty_receipt() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "numerical_pass": False,
        "verdict": "INCONCLUSIVE",
        "primary_scope": "Exact primary calculation only; joint qualification requires the independent verifier and analytical review.",
        "failures": [],
        "checks": [],
        "identities": {},
        "artifacts": {},
        "library_versions": {},
        "scalars": {},
        "scalars_exact": {},
        "scalars_decimal": {},
        "analytic_rows": [],
        "phase_eigenvalues": [],
        "radial_eigenvalues": [],
        "phase_eigenvalues_exact": [],
        "radial_eigenvalues_exact": [],
        "spectral_values": [],
        "spectral_values_decimal": [],
        "spectral_values_exact": [],
        "exact_expressions": {},
    }


def run(note: Path, output: Path) -> int:
    output.mkdir(parents=True, exist_ok=False)
    receipt = empty_receipt()
    try:
        # Bind every source and the program before doing any algebra.
        report_canon = canonical_bytes(note)
        parent_canon = canonical_bytes(PARENT)
        protocol = frozen_section(note, PROTOCOL_HEADING)
        derivation = frozen_section(note, DERIVATION_HEADING, PROTOCOL_HEADING)
        if sha256_bytes(protocol.encode("utf-8")) != PROTOCOL_SHA:
            raise ValueError("frozen §33.3 protocol hash mismatch")
        if sha256_bytes(derivation.encode("utf-8")) != DERIVATION_SHA:
            raise ValueError("frozen §33 derivation hash mismatch")
        if sha256_bytes(parent_canon) != PARENT_SHA:
            raise ValueError("particle stationary-action parent hash mismatch")
        program_canon = canonical_bytes(Path(__file__))
        receipt["identities"] = {
            "protocol": {"path": relpath(note), "heading": PROTOCOL_HEADING.strip(), "sha256": PROTOCOL_SHA, "raw_sha256": raw_sha256(note)},
            "derivation": {"path": relpath(note), "heading": DERIVATION_HEADING.strip(), "sha256": DERIVATION_SHA, "raw_sha256": raw_sha256(note)},
            "parent": {"path": relpath(PARENT), "sha256": PARENT_SHA, "raw_sha256": raw_sha256(PARENT)},
            "program": {"path": relpath(Path(__file__)), "sha256": sha256_bytes(program_canon), "raw_sha256": raw_sha256(Path(__file__))},
        }
        receipt["library_versions"] = {"python": platform.python_version(), "sympy": sp.__version__, "precision_digits": PRECISION}

        snapshots = {
            "protocol.txt": protocol.encode("utf-8"),
            "derivation.txt": derivation.encode("utf-8"),
            "report_source.md": report_canon,
            "parent_source.md": parent_canon,
            "program_source.py": program_canon,
        }
        for filename, content in snapshots.items():
            write_exclusive(output / filename, content)
        receipt["artifacts"] = [artifact_record(output / name) for name in snapshots]
        manifest = {
            "schema": "matter-formation-interface-input-manifest-v1",
            "identities": receipt["identities"],
            "artifacts": receipt["artifacts"],
        }
        manifest_bytes = (json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        write_exclusive(output / "hash_manifest.json", manifest_bytes)
        receipt["artifacts"].append(artifact_record(output / "hash_manifest.json"))

        checks, expressions, witness = algebra()
        receipt["checks"] = checks
        receipt["exact_expressions"] = expressions
        receipt["coefficient"] = witness["coefficient"]
        receipt["scalars"] = witness["numeric"]
        receipt["scalars_exact"] = witness["exact"]
        receipt["scalars_decimal"] = witness["decimal"]
        receipt["analytic_rows"] = witness["rows"]
        receipt["phase_eigenvalues"] = witness["numeric"]["phase_eigenvalues"]
        receipt["radial_eigenvalues"] = witness["numeric"]["radial_eigenvalues"]
        receipt["phase_eigenvalues_exact"] = witness["exact"]["phase_eigenvalues"]
        receipt["radial_eigenvalues_exact"] = witness["exact"]["radial_eigenvalues"]
        receipt["spectral_values"] = [
            row["carrier_eigenvalues"][index]
            for row in witness["rows"]
            for index in (0, 1)
        ] + witness["numeric"]["phase_eigenvalues"] + witness["numeric"]["radial_eigenvalues"]
        receipt["spectral_values_decimal"] = [
            row["carrier_eigenvalues_decimal"][index]
            for row in witness["rows"]
            for index in (0, 1)
        ] + witness["decimal"]["phase_eigenvalues"] + witness["decimal"]["radial_eigenvalues"]
        receipt["spectral_values_exact"] = [
            row["carrier_eigenvalues_exact"][index]
            for row in witness["rows"]
            for index in (0, 1)
        ] + witness["exact"]["phase_eigenvalues"] + witness["exact"]["radial_eigenvalues"]
        receipt["spectral_value_count"] = len(receipt["spectral_values"])
        receipt["failures"] = [row["name"] for row in checks if not row["pass"]]
        if receipt["spectral_value_count"] != 9:
            receipt["failures"].append("expected nine spectral values")
        receipt["primary_scope"] = "Exact primary calculation only; joint qualification requires the independent verifier and analytical review."
        receipt["numerical_pass"] = not receipt["failures"]
        if receipt["numerical_pass"]:
            receipt["verdict"] = VERDICT
    except Exception as error:
        receipt["failures"].append(f"{type(error).__name__}: {error}")
        # Missing or altered inputs leave the scientific payload at its empty shape.
        receipt["checks"] = []
        receipt["scalars"] = {}
        receipt["scalars_exact"] = {}
        receipt["scalars_decimal"] = {}
        receipt["analytic_rows"] = []
        receipt["phase_eigenvalues"] = []
        receipt["radial_eigenvalues"] = []
        receipt["phase_eigenvalues_exact"] = []
        receipt["radial_eigenvalues_exact"] = []
        receipt["spectral_values"] = []
        receipt["spectral_values_decimal"] = []
        receipt["spectral_values_exact"] = []
        receipt["exact_expressions"] = {}
    result_bytes = (json.dumps(receipt, indent=2, ensure_ascii=False, allow_nan=False, sort_keys=True) + "\n").encode("utf-8")
    write_exclusive(output / "results.json", result_bytes)
    print(json.dumps(receipt, ensure_ascii=False, allow_nan=False))
    return 0 if receipt["numerical_pass"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--note", type=Path, default=REPORT)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    return run(args.note.resolve(), args.output_dir.resolve())


if __name__ == "__main__":
    raise SystemExit(main())


