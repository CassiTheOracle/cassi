#!/usr/bin/env python3
"""Independent symbolic check of the massive-vacuum phase-vortex far tail.

This is deliberately source-local: it reconstructs the PA2/PA12 potential and
J from their displayed formulas rather than importing another computation or
parsing the working report.  The receipt is a finite strict JSON object.
"""
from __future__ import annotations

import json
import math
from typing import Any

import sympy as sp


# Source-local symbols.  rho is the fundamental density, u=|Phi|, and c is
# the relative composition cosine.  The PA2 denominator is the fixed v_Q.
rho, u, c = sp.symbols("rho u c", real=True)
rho0, a, d, v = sp.symbols("rho0 a d v", positive=True)
lam_rho, lam_phi, lam_H = sp.symbols("lambda_rho lambda_phi lambda_H", positive=True)
phi = sp.symbols("phi", positive=True)
c0 = sp.symbols("c0", real=True)
m = sp.symbols("m", real=True, nonzero=True)

D = a * rho0 + 4 * d * v**2

# PA2 and PA12 restricted to the composition variables used by the winding
# exterior.  Delta_phi = rho*(1+phi)/2*((u/v)*c-c0).
composition = (u * c / v - c0)
W = (
    lam_rho * (rho - rho0) ** 2 / 4
    + lam_phi * rho**2 * (1 + phi) ** 2 * composition**2 / 8
    + lam_H * (u**2 - v**2) ** 2 / 4
)
J = 4 * a * rho * d * u**2 * (1 - c**2) / (a * rho + 4 * d * u**2)

variables = (rho, u, c)
vacuum = {rho: rho0, u: v, c: c0}
H = sp.simplify(sp.hessian(W, variables).subs(vacuum))
grad_J = sp.Matrix([sp.diff(J, x).subs(vacuum) for x in variables])

L_comp = lam_phi * rho0**2 * (1 + phi) ** 2 / 4
k_comp = c0 / v
H_expected = sp.Matrix(
    [
        [lam_rho / 2, 0, 0],
        [0, 2 * lam_H * v**2 + L_comp * k_comp**2, L_comp * k_comp],
        [0, L_comp * k_comp, L_comp],
    ]
)
grad_expected = sp.Matrix(
    [
        16 * a * d**2 * v**4 * (1 - c0**2) / D**2,
        8 * a**2 * d * rho0**2 * v * (1 - c0**2) / D**2,
        -8 * a * d * rho0 * v**2 * c0 / D,
    ]
)

# The leading algebraic Euler equation is H delta = -m^2 grad(J)/(8 r^2).
# q is the signed coefficient in delta=q/r^2.
s = m**2 / 8
q_rho = sp.factor(-s * grad_expected[0] / (lam_rho / 2))
q_h = sp.factor(-s * grad_expected[2] / L_comp)  # q_h = q_c + (c0/v) q_u
q_u = sp.factor(-s * (grad_expected[1] - k_comp * grad_expected[2]) / (2 * lam_H * v**2))
q_c = sp.factor(q_h - k_comp * q_u)
q = sp.Matrix([q_rho, q_u, q_c])
A_rho = m**2 * a * (4 * d * v**2) ** 2 * (1 - c0**2) / (4 * lam_rho * D**2)

# A second radial-amplitude reconstruction uses f=sqrt(rho), preventing a
# density-coordinate factor from being inherited without checking it.
f = sp.symbols("f", positive=True)
f0 = sp.sqrt(rho0)
W_f = W.subs(rho, f**2)
J_f = J.subs(rho, f**2)
H_f = sp.simplify(sp.diff(W_f, f, 2).subs({f: f0, u: v, c: c0}))
g_f = sp.simplify(sp.diff(J_f, f).subs({f: f0, u: v, c: c0}))
q_f = sp.factor(-s * g_f / H_f)

# Exact transverse radial-Laplacian controls.  A vortex exterior is two
# dimensional in (r,phi), hence Delta_perp = d2/dr2 + r^-1 d/dr.
r = sp.symbols("r", positive=True)
qtest = sp.symbols("qtest", real=True)
log_lap = sp.simplify(
    sp.diff(sp.log(r) ** 2 / 2, r, 2) + sp.diff(sp.log(r) ** 2 / 2, r) / r
)
rminus2_lap = sp.simplify(
    sp.diff(qtest / r**2, r, 2) + sp.diff(qtest / r**2, r) / r
)
radial_derivative_ratio_limit = sp.limit(rminus2_lap / (1 / r**2), r, sp.oo)


def reduced(value: Any) -> Any:
    if isinstance(value, sp.MatrixBase):
        return value.applyfunc(lambda x: sp.factor(sp.cancel(sp.simplify(x))))
    return sp.factor(sp.cancel(sp.simplify(value)))


def exact_zero(value: Any) -> bool:
    value = reduced(value)
    if isinstance(value, sp.MatrixBase):
        return all(item == 0 for item in value)
    return value == 0


def finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def number(value: Any) -> float:
    result = float(sp.N(value, 17))
    if not math.isfinite(result):
        raise ValueError("non-finite witness value")
    return result


def json_value(value: Any) -> Any:
    if isinstance(value, sp.MatrixBase):
        return [json_value(item) for item in value]
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, sp.Basic):
        return str(sp.sstr(value))
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite JSON value")
        return value
    return value


def main() -> int:
    checks: dict[str, bool] = {}
    residuals: dict[str, str] = {}

    h_residual = reduced(H - H_expected)
    g_residual = reduced(grad_J - grad_expected)
    leading_residual = reduced(H * q + s * grad_J)
    density_residual = reduced(q_rho + A_rho)
    amplitude_residual = reduced(2 * f0 * q_f - q_rho)
    amplitude_equation_residual = reduced(H_f * q_f + s * g_f)
    hdet_massive = reduced(H_expected.det())

    residuals.update(
        {
            "hessian": str(h_residual),
            "J_gradient": str(g_residual),
            "leading_Euler": str(leading_residual),
            "density_candidate": str(density_residual),
            "sqrt_density_conversion": str(amplitude_residual),
            "massive_Hessian_determinant": str(hdet_massive),
            "transverse_log_squared_laplacian": str(log_lap - 1 / r**2),
            "r_minus_2_laplacian": str(rminus2_lap - 4 * qtest / r**4),
            "massive_derivative_source_ratio_limit": str(radial_derivative_ratio_limit),
        }
    )
    checks.update(
        {
            "Hessian_reconstructed": exact_zero(h_residual),
            "J_gradient_reconstructed": exact_zero(g_residual),
            "leading_Euler_solved": exact_zero(leading_residual),
            "A_rho_matches_signed_density": exact_zero(density_residual),
            "sqrt_rho_factor_checked": exact_zero(amplitude_residual) and exact_zero(amplitude_equation_residual),
            "massive_Hessian_nondegenerate_symbolically": hdet_massive != 0,
            "exact_transverse_log_squared_control": exact_zero(log_lap - 1 / r**2),
            "exact_massive_tail_derivative_order": exact_zero(rminus2_lap - 4 * qtest / r**4),
            "massive_derivative_source_ratio_vanishes": radial_derivative_ratio_limit == 0,
        }
    )

    # Frozen numeric witness.  R0 is kept strictly inside the surrogate
    # exterior spectral control below; it is not a vacuum or core radius.
    phi_num = (1 + sp.sqrt(5)) / 2
    numeric_subs = {
        rho0: sp.Rational(6, 5),
        a: sp.Rational(83, 100),
        d: sp.Rational(5, 4),
        v: sp.Rational(9, 10),
        c0: phi_num ** -3,
        m: sp.Integer(1),
        lam_rho: sp.Integer(1),
        lam_phi: sp.Integer(1),
        lam_H: sp.Integer(1),
        phi: phi_num,
    }
    H_num = H_expected.subs(numeric_subs)
    grad_num = grad_expected.subs(numeric_subs)
    q_num = q.subs(numeric_subs)
    A_num = A_rho.subs(numeric_subs)
    c0_num = numeric_subs[c0]
    J_num = J.subs(numeric_subs).subs({rho: numeric_subs[rho0], u: numeric_subs[v], c: c0_num})
    principal_minors = [number(H_num[:n, :n].det()) for n in (1, 2, 3)]

    # Positive witness curvature is checked through Sylvester's criterion.
    sign_checks = {
        "witness_positive_Hessian": all(value > 0 for value in principal_minors),
        "witness_nonaligned_composition": abs(number(c0_num)) < 1,
        "witness_A_rho_positive": number(A_num) > 0,
        "witness_signed_density_coefficient_negative": number(q_num[0]) < 0,
        "witness_adjoint_coefficient_negative": number(q_num[1]) < 0,
        "witness_composition_coefficient_finite": finite(number(q_num[2])),
    }
    checks.update(sign_checks)

    # Zero-winding and aligned controls concern the density response only.  At
    # c=+/-1 the phase coordinate is singular, so these are not claims about a
    # positive-definite angular-coordinate Hessian.
    aligned_plus = reduced(A_rho.subs({c0: 1, m: 1}))
    aligned_minus = reduced(A_rho.subs({c0: -1, m: 1}))
    zero_winding = reduced(A_rho.subs(m, 0))
    checks.update(
        {
            "zero_winding_density_control": exact_zero(zero_winding),
            "aligned_plus_density_control": exact_zero(aligned_plus),
            "aligned_minus_density_control": exact_zero(aligned_minus),
        }
    )
    residuals.update(
        {
            "zero_winding_A_rho": str(zero_winding),
            "aligned_plus_A_rho": str(aligned_plus),
            "aligned_minus_A_rho": str(aligned_minus),
        }
    )

    # lambda_H=0 is a genuine singular limit.  The null tangent is
    # n=(1,-c0/v) in (u,c), and its forcing is g_t = g_u-(c0/v)g_c.
    null_H = reduced(H_expected.subs(lam_H, 0))
    null_vector = sp.Matrix([0, 1, -k_comp])
    null_residual = reduced(null_H * null_vector)
    tangent_forcing = reduced((null_vector.T * grad_expected)[0])
    checks["lambda_H_zero_Hessian_singular"] = reduced(null_H.det()) == 0 and exact_zero(null_residual)
    checks["lambda_H_zero_tangent_forcing_not_silently_inverted"] = tangent_forcing != 0
    residuals["lambda_H_zero_null_vector_residual"] = str(null_residual)
    residuals["lambda_H_zero_tangent_forcing"] = str(tangent_forcing)

    # Eliminate the radial gauge component before projecting the null tangent.
    beta_prime, b_radial = sp.symbols("beta_prime b_radial", real=True)
    radial_energy = a * rho0 * (beta_prime + b_radial) ** 2 / 8 + d * v**2 * b_radial**2 / 2
    radial_b_min = sp.solve(sp.diff(radial_energy, b_radial), b_radial)[0]
    beta_metric = reduced(sp.diff(radial_energy.subs(b_radial, radial_b_min), beta_prime, 2))
    kappa_c = a * rho0 * (4 * d * v**2) / (4 * D * (1 - c0**2))
    checks["screened_radial_metric_reconstructed"] = exact_zero(beta_metric - (1 - c0**2) * kappa_c)
    residuals["screened_radial_metric"] = str(reduced(beta_metric - (1 - c0**2) * kappa_c))
    kappa_t = sp.factor(d + k_comp**2 * kappa_c)
    source_t = sp.factor(m**2 * tangent_forcing / 8)
    massless_log_coefficient = sp.factor(source_t / (2 * kappa_t))
    checks["projected_radial_metric_positive_at_witness"] = number(kappa_t.subs(numeric_subs)) > 0
    checks["massless_tangent_forcing_positive_at_witness"] = number(source_t.subs(numeric_subs)) > 0
    massless_equation = kappa_t * massless_log_coefficient * 2 * log_lap - source_t / r**2
    checks["massless_log_squared_equation_solved"] = exact_zero(massless_equation)
    residuals["massless_log_squared_equation"] = str(reduced(massless_equation))
    residuals["massless_null_tangent"] = str(null_vector)
    residuals["massless_projected_radial_metric"] = str(kappa_t)
    residuals["massless_projected_source"] = str(source_t)
    residuals["massless_log_squared_coefficient"] = str(massless_log_coefficient)

    # The neutral carrier sees -eta_C*(rho0-rho) = -eta_C*A_rho/r^2 at
    # leading order.  This is an attractive tail when eta_C*A_rho>0, but it
    # is only an exterior inverse-square surrogate, not a formation result.
    K_Cx, eta_C, R0 = sp.symbols("K_Cx eta_C R0", positive=True)
    carrier_strength = sp.factor(eta_C * A_rho)
    carrier_potential = sp.factor(-carrier_strength / R0**2)
    carrier_dimensionless = sp.factor(2 * carrier_strength / K_Cx)
    carrier_subs = dict(numeric_subs)
    carrier_subs.update({K_Cx: 1, eta_C: 1, R0: 1})
    carrier_values = {
        "R0": number(R0.subs(carrier_subs)),
        "potential_at_R0": number(carrier_potential.subs(carrier_subs)),
        "inverse_square_strength": number(carrier_strength.subs(carrier_subs)),
        "dimensionless_2_eta_A_over_K": number(carrier_dimensionless.subs(carrier_subs)),
    }
    checks["carrier_tail_attractive_for_positive_eta"] = carrier_values["potential_at_R0"] < 0

    # Maxwell and radial derivative terms are subleading in the massive tail:
    # Delta_perp(q/r^2)=4q/r^4, while the angular source is O(r^-2).
    order_limits = {
        "massive_radial_derivative_over_angular_source": "O(r^-2) -> 0",
        "radial_connection_variation": "b=b0+O(r^-2), partial_r b=O(r^-3); no O(r^-2) algebraic source",
        "Maxwell_curvature_correction": "curvature variation enters at O(r^-4) or smaller in the projected modulus equation",
        "massless_null_mode": "nonzero projected r^-2 source gives (source/(2*kappa_t))*log(r)^2 + C*log(r)+D in Delta_perp",
    }

    witness = {
        "vacuum": {
            "rho0": number(numeric_subs[rho0]),
            "u0": number(numeric_subs[v]),
            "c0": number(c0_num),
            "phi": number(phi_num),
            "m": number(numeric_subs[m]),
        },
        "Hessian": [[number(item) for item in row] for row in H_num.tolist()],
        "Hessian_leading_principal_minors": principal_minors,
        "J_gradient": [number(item) for item in grad_num],
        "J_at_vacuum": number(J_num),
        "signed_r_minus_2_coefficients": {
            "q_rho": number(q_num[0]),
            "q_u": number(q_num[1]),
            "q_c": number(q_num[2]),
        },
        "A_rho": number(A_num),
        "massless_projected_metric": number(kappa_t.subs(numeric_subs)),
        "massless_projected_source": number(source_t.subs(numeric_subs)),
        "massless_log_squared_coefficient": number(massless_log_coefficient.subs(numeric_subs)),
        "carrier_surrogate": carrier_values,
    }

    result = {
        "schema": "matter-formation-vortex-tail-verification-v1",
        "verdict": "PASS" if all(checks.values()) else "FAIL",
        "checks": {key: bool(value) for key, value in checks.items()},
        "raw": {
            "inputs": {
                "source": "foundations/particle-stationary-action-closure.md PA2, PA12",
                "W": "lambda_rho*(rho-rho0)^2/4 + lambda_phi*rho^2*(1+phi)^2*((u/v)*c-c0)^2/8 + lambda_H*(u^2-v^2)^2/4",
                "J": "4*a*rho*d*u^2*(1-c^2)/(a*rho+4*d*u^2)",
                "leading_equation": "H_W*delta = -m^2*grad(J)/(8*r^2)",
                "numeric_witness": "rho0=1.2, a=0.83, d=1.25, v=0.9, c0=phi^-3, m=1, lambda_rho=lambda_phi=lambda_H=K_Cx=eta_C=1",
                "R0_scope": "R0=1 appears only in the surrogate exterior carrier spectral control",
            },
            "formulas": {
                "vacuum_Hessian": json_value(H_expected),
                "vacuum_J_gradient": json_value(grad_expected),
                "signed_coefficients": json_value(q),
                "A_rho": json_value(A_rho),
                "sqrt_rho_Hessian": str(H_f),
                "sqrt_rho_gradient": str(g_f),
                "massless_null_tangent": str(null_vector),
                "massless_radial_solution": "delta_t=(source_t/(2*kappa_t))*log(r)^2+C*log(r)+D for kappa_t*Delta_perp(delta_t)=source_t/r^2",
                "carrier_potential": "V_C(r)=-eta_C*A_rho/r^2+o(r^-2)",
            },
            "residuals": residuals,
            "scope_and_limits": {
                "dimensions": "Coefficients are in the supplied source/model units; a physical length or energy requires the action's unit conversion.",
                "source_units": "The PA12 coefficients carry source-unit dimensions; the displayed inverse-square coefficients inherit those dimensions and are not physical fits.",
                "massive_tail": "Conditional on a smooth stationary vortex approaching the massive nonaligned vacuum, the r^-2 response is the leading balance; radial and Maxwell contributions to the modulus equations enter at absolute order r^-4 or smaller.",
                "lambda_H_zero": "No inverse of the zero Hessian is taken. The massless null tangent is tested with a positive projected radial metric, and its generic nonzero r^-2 forcing is logarithmic-squared rather than decaying.",
                "aligned_controls": "m=0 and c0=+/-1 only control the density coefficient A_rho; aligned phase coordinates are singular and are not positive-definite Hessian claims.",
                "formation_boundary": "This calculation establishes the conditional density tail and its carrier attraction. Existence of the stationary core, its full spectrum and complete physical matter formation are not supplied.",
                "neglected_terms": order_limits,
            },
        },
        "witness": witness,
        "complete_physical_matter_formation": False,
    }
    print(json.dumps(json_value(result), allow_nan=False, separators=(",", ":"), sort_keys=True))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
