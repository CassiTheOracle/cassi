#!/usr/bin/env python3
"""High-precision exterior inverse-square tail and log-annulus spectrum.

This calculation is deliberately self-contained.  It tests only the exterior
carrier quadratic form and its exact s-wave Bessel tail; it does not solve a
vortex core or infer physical matter formation.
"""
from __future__ import annotations

import json
import sys
from typing import Any

import mpmath as mp


SCHEMA = "matter-formation-vortex-tail-spectrum-v1"
DPS = 70
mp.mp.dps = DPS
TOL = mp.mpf("1e-30")
BISECTION_LIMIT = 640
INTEGRATION_PIECES = 16


def s(value: mp.mpf | mp.mpc | int | float) -> str:
    """Render an mpmath value without converting through binary float."""
    if not finite_mp(value):
        raise ValueError("non-finite numerical result")
    if isinstance(value, mp.mpc):
        if abs(mp.im(value)) > mp.mpf("1e-65"):
            raise ValueError("unexpected non-real value")
        value = mp.re(value)
    return mp.nstr(value, 80)


def finite_mp(value: mp.mpf | mp.mpc) -> bool:
    if isinstance(value, mp.mpc):
        return bool(mp.isfinite(mp.re(value)) and mp.isfinite(mp.im(value)))
    return bool(mp.isfinite(value))


def normalized_error(actual: mp.mpf, expected: mp.mpf, scale: mp.mpf | None = None) -> mp.mpf:
    denominator = max(mp.mpf(1), abs(expected) if scale is None else abs(scale))
    return abs(actual - expected) / denominator


def integrate_radial(function: Any, r0: mp.mpf, r1: mp.mpf, pieces: int = INTEGRATION_PIECES) -> mp.mpf:
    """Integrate in r, using fixed geometric subintervals in the exterior."""
    log_span = mp.log(r1 / r0)
    edges = [r0 * mp.exp(log_span * i / pieces) for i in range(pieces + 1)]
    return mp.fsum(mp.quad(function, [edges[i], edges[i + 1]]) for i in range(pieces))


def trial_form(
    L: mp.mpf,
    *,
    r0: mp.mpf,
    K: mp.mpf,
    gamma: mp.mpf,
    ell: int,
) -> dict[str, mp.mpf]:
    r1 = r0 * mp.exp(L)
    pi = mp.pi

    def chi(r: mp.mpf) -> mp.mpf:
        return mp.sin(pi * mp.log(r / r0) / L)

    def dchi(r: mp.mpf) -> mp.mpf:
        return (pi / L) * mp.cos(pi * mp.log(r / r0) / L) / r

    def kinetic_integrand(r: mp.mpf) -> mp.mpf:
        value = dchi(r) ** 2 + ell * ell * chi(r) ** 2 / (r * r)
        return 2 * pi * (K / 2) * value * r

    def inverse_square_integrand(r: mp.mpf) -> mp.mpf:
        return 2 * pi * (-gamma * chi(r) ** 2 / (r * r)) * r

    def norm_integrand(r: mp.mpf) -> mp.mpf:
        return 2 * pi * chi(r) ** 2 * r

    kinetic = integrate_radial(kinetic_integrand, r0, r1)
    inverse_square = integrate_radial(inverse_square_integrand, r0, r1)
    norm = integrate_radial(norm_integrand, r0, r1)
    radial_form = kinetic + inverse_square
    nu2 = 2 * gamma / K - ell * ell
    log_numerator = pi * K * L / 2 * ((pi / L) ** 2 - nu2)
    omega2 = (pi / L) ** 2
    exact_norm = pi * r0**2 * mp.expm1(2 * L) * omega2 / (2 * (1 + omega2))
    return {
        "L": L,
        "r_outer": r1,
        "kinetic_form": kinetic,
        "inverse_square_form": inverse_square,
        "radial_form": radial_form,
        "direct_norm": norm,
        "exact_norm": exact_norm,
        "norm_normalized_error": normalized_error(norm, exact_norm),
        "rayleigh_energy": radial_form / norm,
        "nu2": nu2,
        "log_numerator": log_numerator,
    }


def bracket_root(nu: mp.mpf, n: int) -> dict[str, Any]:
    """Bisection in t=log(2/x) over the prescribed, non-adaptive bracket."""
    phase = mp.arg(mp.gamma(1 + 1j * nu))
    center = (n * mp.pi - phase) / nu
    half_width = mp.pi / (4 * nu)
    lo = center - half_width
    hi = center + half_width

    def value(t: mp.mpf) -> mp.mpf:
        return mp.re(mp.besselk(1j * nu, 2 * mp.exp(-t)))

    flo = value(lo)
    fhi = value(hi)
    row: dict[str, Any] = {
        "n": n,
        "t_center": s(center),
        "t_lo": s(lo),
        "t_hi": s(hi),
        "bracket_value_lo": s(flo),
        "bracket_value_hi": s(fhi),
        "pass_bracket": False,
    }
    if not (finite_mp(lo) and finite_mp(hi) and finite_mp(flo) and finite_mp(fhi) and lo > 0 and hi > lo):
        row["error"] = "non-finite or non-positive prescribed bracket"
        return row
    if flo == 0:
        root_t = lo
    elif fhi == 0:
        root_t = hi
    elif flo * fhi > 0:
        row["error"] = "prescribed bracket does not change sign"
        return row
    else:
        left, right, fleft, fright = lo, hi, flo, fhi
        root_t = (left + right) / 2
        root_value = value(root_t)
        converged = False
        for _ in range(BISECTION_LIMIT):
            root_t = (left + right) / 2
            root_value = value(root_t)
            if abs(root_value) < TOL and (right - left) < mp.mpf("1e-50"):
                converged = True
                break
            if fleft * root_value <= 0:
                right, fright = root_t, root_value
            else:
                left, fleft = root_t, root_value
        if not converged:
            row["error"] = "bounded bisection did not reach residual and width limits"
            row["root_t_last"] = s(root_t)
            row["root_residual_last"] = s(root_value)
            return row

    x = 2 * mp.exp(-root_t)
    residual = abs(value(root_t))
    row.update(
        {
            "pass_bracket": True,
            "t_root": s(root_t),
            "x_root": s(x),
            "root_residual": s(residual),
            "pass_residual": bool(residual < TOL),
        }
    )
    return row


def bessel_equation_rows(nu: mp.mpf, r0: mp.mpf, K: mp.mpf, first_x: mp.mpf) -> list[dict[str, Any]]:
    """Differentiate the negative-energy radial Bessel solution at fixed radii."""
    kappa = first_x / r0
    radii = (r0 * mp.mpf("1.25"), r0 * mp.mpf("2.0"), r0 * mp.mpf("3.5"))
    rows: list[dict[str, Any]] = []
    for radius in radii:
        def f(rr: mp.mpf) -> mp.mpf:
            return mp.re(mp.besselk(1j * nu, kappa * rr))

        value = f(radius)
        first = mp.diff(f, radius)
        second = mp.diff(f, radius, 2)
        residual = second + first / radius + (nu * nu / (radius * radius) - kappa * kappa) * value
        rows.append(
            {
                "radius": s(radius),
                "kappa": s(kappa),
                "equation_residual": s(residual),
                "normalized_residual": s(abs(residual) / (1 + abs(value) + abs(first) + abs(second))),
                "pass": bool(abs(residual) < TOL),
            }
        )
    return rows


def base_receipt(inputs: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "precision_digits": DPS,
        "tolerance": s(TOL),
        "fixed_radial_pieces": INTEGRATION_PIECES,
        "bisection_limit": BISECTION_LIMIT,
        "inputs": inputs,
        "formulas": {
            "hamiltonian": "H_l = -K_Cx Delta_2/2 - gamma/r^2 with angular barrier K_Cx*l^2/(2*r^2)",
            "trial": "chi(r)=sin(pi*log(r/R0)/L) on [R0,R0*exp(L)], zero elsewhere",
            "direct_quadratic_form": "2*pi*integral_[R0,R1] [K_Cx/2*(chi'(r)^2+l^2*chi(r)^2/r^2)-gamma*chi(r)^2/r^2] r dr",
            "A_rho": "m^2*a*(4*d*v^2)^2*(1-c0^2)/(4*lambda_rho*(a*rho0+4*d*v^2)^2)",
            "gamma": "gamma=eta_C*A_rho",
            "exact_norm": "pi*R0^2*(exp(2*L)-1)*(pi/L)^2/(2*(1+(pi/L)^2))",
            "log_numerator": "pi*K_Cx*L/2*((pi/L)^2-nu^2)",
            "nu_squared": "nu^2=2*gamma/K_Cx-l^2",
            "binding_energy": "E_bind=K_Cx*x_n^2/(2*R0^2)",
            "bessel_equation": "f''+f'/r+(nu^2/r^2-kappa^2)f=0 for f(r)=K_(i nu)(kappa*r)",
        },
        "rows": [],
        "roots": [],
        "energy_ratios": [],
        "bessel_equation_rows": [],
        "checks": {},
        "failures": [],
        "interpretation": {
            "disjoint_log_annulus_min_max": "For a true attractive r^-2 asymptotic tail, translate any sufficiently long negative log-coordinate trial into mutually disjoint annuli. Their disjoint supports make the quadratic form negative on the span of N such trials; the min-max principle then gives at least N negative transverse eigenvalues for every N, hence an infinite bound-mode tower.",
            "finite_loop_size": "A finite loop or finite exterior truncates the available log length and therefore can truncate the tower; it is a separate finite-domain question.",
            "empty_sector_conservation": "A negative exterior eigenvalue is only a spectral qualification. Empty-sector or particle-number conservation remains a separate dynamical constraint and does not populate a mode or establish matter formation.",
            "spacing_caveat": "The reported exp(-2*pi/nu) is an asymptotic comparison measurement; finite-n roots need not obey exact geometric spacing, and no new threshold is asserted.",
        },
        "complete_physical_matter_formation": False,
        "verdict": "FAIL",
    }


def calculate() -> dict[str, Any]:
    mp.mp.dps = DPS
    phi = (1 + mp.sqrt(5)) / 2
    rho0 = mp.mpf("1.2")
    a = mp.mpf("0.83")
    d = mp.mpf("1.25")
    v = mp.mpf("0.9")
    c0 = phi ** (-3)
    m = mp.mpf(1)
    lambda_rho = mp.mpf(1)
    lambda_phi = mp.mpf(1)
    lambda_H = mp.mpf(1)
    K = mp.mpf(1)
    eta_C = mp.mpf(1)
    R0 = mp.mpf(1)
    four_dv2 = 4 * d * v * v
    A_rho = m * m * a * four_dv2 * four_dv2 * (1 - c0 * c0) / (4 * lambda_rho * (a * rho0 + four_dv2) ** 2)
    gamma = eta_C * A_rho
    nu2 = 2 * gamma / K
    nu = mp.sqrt(nu2)
    inputs = {
        "rho0": s(rho0),
        "a": s(a),
        "d": s(d),
        "v": s(v),
        "phi": s(phi),
        "c0": s(c0),
        "m": s(m),
        "lambda_rho": s(lambda_rho),
        "lambda_phi": s(lambda_phi),
        "lambda_H": s(lambda_H),
        "K_Cx": s(K),
        "eta_C": s(eta_C),
        "R0": s(R0),
        "A_rho": s(A_rho),
        "gamma": s(gamma),
        "nu_squared_s_wave": s(nu2),
        "nu_s_wave": s(nu),
    }
    receipt = base_receipt(inputs)
    rows: list[dict[str, Any]] = receipt["rows"]
    checks: dict[str, bool] = receipt["checks"]

    attractive_rows: list[dict[str, Any]] = []
    for label, L in (
        ("L_pi_over_2nu", mp.pi / (2 * nu)),
        ("L_pi_over_nu", mp.pi / nu),
        ("L_2pi_over_nu", 2 * mp.pi / nu),
    ):
        form = trial_form(L, r0=R0, K=K, gamma=gamma, ell=0)
        row = {"label": label, "ell": 0, "gamma": s(gamma), **{key: s(value) for key, value in form.items()}}
        row["direct_log_normalized_error"] = s(normalized_error(form["radial_form"], form["log_numerator"]))
        row["pass_direct_log"] = bool(normalized_error(form["radial_form"], form["log_numerator"]) < TOL)
        row["pass_norm_positive"] = bool(form["direct_norm"] > 0)
        rows.append(row)
        attractive_rows.append(row)

    checks["L_pi_over_2nu_positive"] = bool(mp.mpf(attractive_rows[0]["log_numerator"]) > 0)
    checks["direct_log_form_agreement"] = all(row["pass_direct_log"] for row in attractive_rows)
    midpoint_value = mp.mpf(attractive_rows[1]["log_numerator"])
    checks["L_pi_over_nu_zero_normalized"] = bool(abs(midpoint_value) < TOL)
    checks["L_2pi_over_nu_negative"] = bool(mp.mpf(attractive_rows[2]["log_numerator"]) < 0)

    largest_L = 2 * mp.pi / nu
    controls = (
        ("control_gamma_zero", 0, mp.mpf(0)),
        ("control_gamma_negative", 0, -abs(gamma)),
        ("control_ell_one", 1, gamma),
    )
    control_rows: list[dict[str, Any]] = []
    for label, ell, control_gamma in controls:
        form = trial_form(largest_L, r0=R0, K=K, gamma=control_gamma, ell=ell)
        row = {"label": label, "ell": ell, "gamma": s(control_gamma), **{key: s(value) for key, value in form.items()}}
        row["direct_log_normalized_error"] = s(normalized_error(form["radial_form"], form["log_numerator"]))
        row["pass_direct_log"] = bool(normalized_error(form["radial_form"], form["log_numerator"]) < TOL)
        row["pass_positive_numerator"] = bool(form["log_numerator"] > 0)
        rows.append(row)
        control_rows.append(row)
    checks["largest_L_controls_positive"] = all(row["pass_positive_numerator"] for row in control_rows)
    checks["largest_L_controls_direct_agreement"] = all(row["pass_direct_log"] for row in control_rows)

    checks["all_norms_positive"] = all(mp.mpf(row["direct_norm"]) > 0 for row in rows)
    checks["all_norms_agree"] = all(mp.mpf(row["norm_normalized_error"]) < TOL for row in rows)
    root_rows: list[dict[str, Any]] = []
    for n in range(1, 5):
        root_rows.append(bracket_root(nu, n))
    receipt["roots"] = root_rows
    checks["all_bessel_brackets"] = all(bool(row.get("pass_bracket", False)) for row in root_rows)
    checks["all_bessel_residuals"] = all(bool(row.get("pass_residual", False)) for row in root_rows)

    valid_roots = [row for row in root_rows if row.get("pass_bracket", False) and "x_root" in row]
    energies: list[mp.mpf] = []
    if len(valid_roots) == 4:
        energies = [K * mp.mpf(row["x_root"]) ** 2 / (2 * R0 * R0) for row in valid_roots]
        for row, energy in zip(valid_roots, energies):
            row["binding_energy"] = s(energy)
        ratios = []
        successive = []
        for i, energy in enumerate(energies):
            ratios.append({"n": i + 1, "E_n_over_E_1": s(energy / energies[0])})
            if i:
                successive.append({"from_n": i, "to_n": i + 1, "E_next_over_E": s(energy / energies[i - 1])})
        receipt["energy_ratios"] = ratios
        receipt["successive_energy_ratios"] = successive
        receipt["asymptotic_energy_ratio_exp_minus_2pi_over_nu"] = s(mp.exp(-2 * mp.pi / nu))
    checks["roots_t_increasing"] = bool(len(valid_roots) == 4 and all(mp.mpf(valid_roots[i]["t_root"]) < mp.mpf(valid_roots[i + 1]["t_root"]) for i in range(3)))
    checks["roots_x_decreasing"] = bool(len(valid_roots) == 4 and all(mp.mpf(valid_roots[i]["x_root"]) > mp.mpf(valid_roots[i + 1]["x_root"]) > 0 for i in range(3)))
    checks["binding_energies_positive_decreasing"] = bool(len(energies) == 4 and all(energies[i] > energies[i + 1] > 0 for i in range(3)))

    if len(valid_roots) == 4:
        first_x = mp.mpf(valid_roots[0]["x_root"])
        equation_rows = bessel_equation_rows(nu, R0, K, first_x)
        receipt["bessel_equation_rows"] = equation_rows
        checks["bessel_radial_equation"] = all(bool(row["pass"]) for row in equation_rows)
    else:
        checks["bessel_radial_equation"] = False
        receipt["failures"].append("Bessel radial-equation check skipped because one or more roots is missing")

    checks["all_checks"] = all(checks.values())
    receipt["verdict"] = "PASS" if checks["all_checks"] else "FAIL"
    if not checks["all_checks"]:
        receipt["failures"].extend(name for name, passed in checks.items() if not passed and name != "all_checks")
    return receipt


def main() -> int:
    try:
        receipt = calculate()
    except Exception as exc:  # Keep failures visible while preserving strict JSON output.
        mp.mp.dps = DPS
        receipt = base_receipt({})
        receipt["failures"] = [f"{type(exc).__name__}: {exc}"]
        receipt["checks"] = {"calculation_completed": False, "all_checks": False}
        receipt["verdict"] = "INCONCLUSIVE"
    payload = json.dumps(receipt, ensure_ascii=False, allow_nan=False, sort_keys=True)
    print(payload)
    return 0 if receipt.get("verdict") == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
