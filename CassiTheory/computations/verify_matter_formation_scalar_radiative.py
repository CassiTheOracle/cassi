"""Standalone source-bound one-loop scalar radiative verifier.

The program deliberately reconstructs the scalar potential from the canonical
parent action, rather than importing another calculation.  It is sealed by a
manifest supplied by the integration owner and only evaluates the frozen
Cartesian product of normalization witnesses.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

import sympy as sp


SCHEMA = "matter-formation-quantum-coupling-manifest-v1"
RECEIPT_SCHEMA = "matter-formation-quantum-coupling-v1"
ROLE = "radiative"
SUCCESS_VERDICT = "SUPPORTS-conditional scalar quantum coupling constraints"
FAIL_VERDICT = "INCONCLUSIVE"
NOTEBOOK = "computations/matter-formation-continuum-report.md"
PARENT_ACTION = "foundations/particle-stationary-action-closure.md"
PRIMARY = "computations/matter_formation_quantum_coupling.py"
SCATTERING = "computations/verify_matter_formation_scalar_scattering.py"
RADIATIVE = "computations/verify_matter_formation_scalar_radiative.py"
HEADING_66 = "## 66. Working notes: quantum coupling normalization and radiative closure"
HEADING_64 = "## 64. Working notes: matching quantum conversion to the scalar action"
H_VALUES = ("0", "2", "2.9598260763447164", "6")
N_VALUES = (1, 4, 16, 64)
TOLERANCE = 1.0e-9


class GuardError(Exception):
    """A prerequisite failed before scientific rows were allowed."""


def canonical_bytes(path: Path) -> bytes:
    """Canonicalize only CRLF, as required by the sealed manifest."""
    return path.read_bytes().replace(b"\r\n", b"\n")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def relative_root_path(root: Path, raw: Any, label: str) -> Path:
    if not isinstance(raw, str) or not raw:
        raise GuardError(f"{label} must be a non-empty relative path")
    candidate = Path(raw)
    if candidate.is_absolute() or any(part == ".." for part in candidate.parts):
        raise GuardError(f"{label} must be ROOT-relative without '..'")
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise GuardError(f"{label} escapes ROOT") from exc
    return resolved


def strict_load(path: Path) -> Any:
    def reject_constant(value: str) -> Any:
        raise ValueError(f"non-finite JSON constant {value}")

    try:
        return json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise GuardError(f"cannot load strict JSON manifest {path}: {exc}") from exc


def exact_keys(value: Any, required: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != required:
        raise GuardError(f"{label} has the wrong keys")
    return value


def section_bytes(root: Path, path: Path, heading: str) -> bytes:
    try:
        text = canonical_bytes(path).decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise GuardError(f"cannot read section source {path}: {exc}") from exc
    lines = text.splitlines(keepends=True)
    matches = [index for index, line in enumerate(lines) if line.rstrip("\n") == heading]
    if len(matches) != 1:
        raise GuardError(f"heading {heading!r} is not unique in {path}")
    start = matches[0]
    stop = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].startswith("## "):
            stop = index
            break
    return ("".join(lines[start:stop]).rstrip() + "\n").encode("utf-8")


def validate_manifest(root: Path, manifest_path: Path) -> None:
    manifest = strict_load(manifest_path)
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
        raise GuardError("manifest schema mismatch")

    sections = manifest.get("sections")
    if not isinstance(sections, list) or len(sections) != 2:
        raise GuardError("manifest must contain exactly two sections")
    expected_sections = {HEADING_66, HEADING_64}
    seen_sections: set[str] = set()
    for index, item in enumerate(sections):
        record = exact_keys(item, {"path", "heading", "snapshot", "sha256"}, f"sections[{index}]")
        heading = record["heading"]
        if heading not in expected_sections or heading in seen_sections:
            raise GuardError("section headings are not exactly 64 and 66")
        seen_sections.add(heading)
        if record["path"] != NOTEBOOK:
            raise GuardError("section path mismatch")
        snapshot = relative_root_path(root, record["snapshot"], f"sections[{index}].snapshot")
        digest = record["sha256"]
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise GuardError(f"sections[{index}].sha256 is not lowercase SHA-256")
        live = section_bytes(root, root / NOTEBOOK, heading)
        if sha256_bytes(live) != digest:
            raise GuardError(f"live section hash mismatch for {heading}")
        try:
            snap = canonical_bytes(snapshot)
        except OSError as exc:
            raise GuardError(f"cannot read section snapshot {snapshot}: {exc}") from exc
        if sha256_bytes(snap) != digest:
            raise GuardError(f"section snapshot hash mismatch for {heading}")
    if seen_sections != expected_sections:
        raise GuardError("section heading set mismatch")

    sources = manifest.get("sources")
    required_sources = {PRIMARY, SCATTERING, RADIATIVE, PARENT_ACTION}
    if not isinstance(sources, list) or len(sources) != 4:
        raise GuardError("manifest must contain exactly four sources")
    seen_sources: set[str] = set()
    for index, item in enumerate(sources):
        record = exact_keys(item, {"path", "snapshot", "sha256"}, f"sources[{index}]")
        source_path = record["path"]
        if source_path not in required_sources or source_path in seen_sources:
            raise GuardError("source paths are not the required unique four")
        seen_sources.add(source_path)
        snapshot = relative_root_path(root, record["snapshot"], f"sources[{index}].snapshot")
        digest = record["sha256"]
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise GuardError(f"sources[{index}].sha256 is not lowercase SHA-256")
        try:
            live = canonical_bytes(root / source_path)
            snap = canonical_bytes(snapshot)
        except OSError as exc:
            raise GuardError(f"cannot read source or snapshot for {source_path}: {exc}") from exc
        if sha256_bytes(live) != digest or sha256_bytes(snap) != digest:
            raise GuardError(f"source hash mismatch for {source_path}")
    if seen_sources != required_sources:
        raise GuardError("source path set mismatch")

    reviews = manifest.get("mathematical_reviews")
    if not isinstance(reviews, list) or len(reviews) != 2:
        raise GuardError("manifest must contain exactly two mathematical reviews")
    seen_roles: set[str] = set()
    for index, item in enumerate(reviews):
        record = exact_keys(item, {"role", "accepted", "snapshot", "sha256"}, f"mathematical_reviews[{index}]")
        role = record["role"]
        if role not in {"scattering", "radiative"} or role in seen_roles:
            raise GuardError("review roles are not exactly scattering and radiative")
        seen_roles.add(role)
        if record["accepted"] is not True:
            raise GuardError(f"{role} review is not accepted")
        snapshot = relative_root_path(root, record["snapshot"], f"mathematical_reviews[{index}].snapshot")
        digest = record["sha256"]
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise GuardError(f"{role} review sha256 is not lowercase SHA-256")
        try:
            review_text = canonical_bytes(snapshot).decode("utf-8")
        except (OSError, UnicodeError) as exc:
            raise GuardError(f"cannot read {role} review snapshot: {exc}") from exc
        if sha256_bytes(review_text.encode("utf-8")) != digest:
            raise GuardError(f"{role} review hash mismatch")
        accepted_lines = [line.strip() for line in review_text.splitlines() if line.strip().startswith("accepted:")]
        if accepted_lines != ["accepted: true"]:
            raise GuardError(f"{role} review must contain exactly one accepted: true line")
    if seen_roles != {"scattering", "radiative"}:
        raise GuardError("review role set mismatch")


def finite_float(value: Any, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{label} is not numeric") from exc
    if not math.isfinite(result):
        raise ValueError(f"{label} is not finite")
    return result


def relative_error(actual: list[float], expected: list[float]) -> float:
    numerator = math.sqrt(sum((a - b) ** 2 for a, b in zip(actual, expected)))
    denominator = max(1.0, math.sqrt(sum(b * b for b in expected)))
    return numerator / denominator


def real_value(expr: sp.Expr, label: str) -> float:
    return finite_float(sp.N(expr, 40), label)


def zero(expr: sp.Expr) -> bool:
    return sp.simplify(sp.expand(expr)) == 0


def canonical_action_symbols() -> tuple[sp.Symbol, ...]:
    return sp.symbols("S X Y L P U muS2 muC2 Lambda0", real=True)


def canonical_action_w(ng: sp.Expr, hg: sp.Expr) -> tuple[sp.Expr, dict[str, sp.Expr], dict[str, sp.Expr]]:
    S, X, Y = sp.symbols("S X Y", real=True)
    a = sp.Rational(1, 16)
    cpsi = sp.Rational(1, 8)
    urho = sp.Integer(4)
    uc = sp.Integer(1)
    ec = sp.Rational(3, 4)
    c = 1 / sp.sqrt(cpsi)
    v = sp.sqrt(ng * cpsi)
    m2 = 2 * urho / cpsi
    B = ec + 1 / (4 * a)
    M2 = B / a
    lambda3 = 3 * m2 / v
    lambda4 = 3 * m2 / v**2
    g = 2 * hg / (a * v)
    g2 = g / v
    sigma = S / c ** sp.Rational(3, 2) - v
    phi_norm_sq = (X**2 + Y**2) / (2 * c**3)
    potential = (
        m2 * sigma**2 / 2
        + M2 * phi_norm_sq
        + lambda3 * sigma**3 / 6
        + lambda4 * sigma**4 / 24
        + g * sigma * phi_norm_sq
        + g2 * sigma**2 * phi_norm_sq / 2
        + uc * phi_norm_sq**2 / (2 * ng * a**2)
    )
    W = sp.expand(c**3 * potential)
    derived = {
        "c": c,
        "L": sp.simplify(lambda4 / c**3),
        "P": sp.simplify(g2 / c**3),
        "U": sp.simplify(uc / (ng * a**2 * c**3)),
        "muS2": sp.simplify(-urho / cpsi),
        "muC2": sp.simplify((ec + 1 / (4 * a) - hg) / a),
        "Lambda0": sp.simplify(ng * c**3 * urho / 4),
    }
    expected = (
        derived["Lambda0"]
        + derived["muS2"] * S**2 / 2
        + derived["muC2"] * (X**2 + Y**2) / 2
        + derived["L"] * S**4 / 24
        + derived["P"] * S**2 * (X**2 + Y**2) / 4
        + derived["U"] * (X**2 + Y**2) ** 2 / 8
    )
    return W, derived, {"S": S, "X": X, "Y": Y, "expected": expected}


def derive_hessian_betas() -> tuple[dict[str, sp.Expr], dict[str, Any]]:
    S, X, Y, L, P, U, muS2, muC2, lambda0 = canonical_action_symbols()
    rho = X**2 + Y**2
    W = lambda0 + muS2 * S**2 / 2 + muC2 * rho / 2 + L * S**4 / 24 + P * S**2 * rho / 4 + U * rho**2 / 8
    hessian = sp.hessian(W, (S, X, Y))
    trace_half = sp.expand(sum(hessian[i, j] ** 2 for i in range(3) for j in range(3)) / 2)
    expected = {
        "L": 3 * L**2 + 6 * P**2,
        "P": P * (L + 4 * U + 4 * P),
        "U": 10 * U**2 + P**2,
        "muS2": L * muS2 + 2 * P * muC2,
        "muC2": P * muS2 + 4 * U * muC2,
        "Lambda0": (muS2**2 + 2 * muC2**2) / 2,
    }
    beta_polynomial = (
        expected["Lambda0"]
        + expected["muS2"] * S**2 / 2
        + expected["muC2"] * rho / 2
        + expected["L"] * S**4 / 24
        + expected["P"] * S**2 * rho / 4
        + expected["U"] * rho**2 / 8
    )
    residual = sp.expand(trace_half - beta_polynomial)
    poly = sp.Poly(trace_half, S, X, Y)
    unsupported: list[tuple[int, int, int]] = []
    for exponents in itertools.product(range(5), repeat=3):
        if sum(exponents) <= 4:
            if exponents not in {(0, 0, 0), (2, 0, 0), (0, 2, 0), (0, 0, 2), (4, 0, 0), (2, 2, 0), (2, 0, 2), (0, 4, 0), (0, 2, 2), (0, 0, 4)}:
                if poly.coeff_monomial(S**exponents[0] * X**exponents[1] * Y**exponents[2]) != 0:
                    unsupported.append(exponents)
    extracted = {
        "L": sp.expand(24 * poly.coeff_monomial(S**4)),
        "P": sp.expand(4 * poly.coeff_monomial(S**2 * X**2)),
        "U": sp.expand(8 * poly.coeff_monomial(X**4)),
        "muS2": sp.expand(2 * poly.coeff_monomial(S**2)),
        "muC2": sp.expand(2 * poly.coeff_monomial(X**2)),
        "Lambda0": sp.expand(poly.coeff_monomial(1)),
    }
    support = {
        "S": S,
        "X": X,
        "Y": Y,
        "L": L,
        "P": P,
        "U": U,
        "muS2": muS2,
        "muC2": muC2,
        "Lambda0": lambda0,
        "trace_half": trace_half,
        "residual": residual,
        "unsupported": unsupported,
        "extracted": extracted,
        "expected": expected,
    }
    return extracted, support


def symbolic_scientific_checks() -> tuple[dict[str, bool], dict[str, Any], dict[str, sp.Expr]]:
    extracted, support = derive_hessian_betas()
    expected = support["expected"]
    checks: dict[str, bool] = {}
    checks["hessian_trace_coefficient_identity"] = zero(support["residual"])
    checks["hessian_basis_closed"] = support["unsupported"] == []
    checks["hessian_no_odd_monomials"] = all(power % 2 == 0 for m in sp.Poly(support["trace_half"], support["S"], support["X"], support["Y"]).monoms() for power in m)
    poly = sp.Poly(support["trace_half"], support["S"], support["X"], support["Y"])
    checks["hessian_O2_XY_symmetry"] = (
        poly.coeff_monomial(support["X"]**2) == poly.coeff_monomial(support["Y"]**2)
        and poly.coeff_monomial(support["X"]**4) == poly.coeff_monomial(support["Y"]**4)
        and poly.coeff_monomial(support["S"]**2 * support["X"]**2) == poly.coeff_monomial(support["S"]**2 * support["Y"]**2)
    )
    checks["beta_L_formula"] = zero(extracted["L"] - expected["L"])
    checks["beta_P_formula"] = zero(extracted["P"] - expected["P"])
    checks["beta_U_formula"] = zero(extracted["U"] - expected["U"])
    checks["beta_muS2_formula"] = zero(extracted["muS2"] - expected["muS2"])
    checks["beta_muC2_formula"] = zero(extracted["muC2"] - expected["muC2"])
    checks["beta_Lambda0_formula"] = zero(extracted["Lambda0"] - expected["Lambda0"])

    L, P, U = support["L"], support["P"], support["U"]
    ms, mc = support["muS2"], support["muC2"]
    checks["decoupled_real_limit"] = (
        zero(extracted["L"].subs({P: 0, U: 0}) - 3 * L**2)
        and zero(extracted["P"].subs({P: 0, U: 0}))
        and zero(extracted["U"].subs({P: 0, U: 0}))
        and zero(extracted["muS2"].subs({P: 0, U: 0, mc: 0}) - L * ms)
    )
    checks["O2_limit"] = (
        zero(extracted["U"].subs({L: 0, P: 0}) - 10 * U**2)
        and zero(extracted["muC2"].subs({L: 0, P: 0, ms: 0}) - 4 * U * mc)
        and zero(extracted["Lambda0"].subs({ms: 0}) - mc**2)
    )
    o3 = {L: 3 * U, P: U, ms: mc}
    checks["O3_limit"] = (
        zero(extracted["L"].subs(o3) - 3 * extracted["U"].subs(o3))
        and zero(extracted["P"].subs(o3) - extracted["U"].subs(o3))
        and zero(extracted["muS2"].subs(o3) - extracted["muC2"].subs(o3))
    )
    checks["Gaussian_limit"] = (
        all(zero(extracted[name].subs({L: 0, P: 0, U: 0})) for name in ("L", "P", "U"))
        and all(
            zero(extracted[name].subs({L: 0, P: 0, U: 0, ms: 0, mc: 0}))
            for name in ("muS2", "muC2", "Lambda0")
        )
    )
    checks["Gaussian_only_real_proof_L_square_sum"] = zero(extracted["L"] - (3 * L**2 + 6 * P**2))
    checks["Gaussian_only_real_proof_U_square_sum"] = zero(extracted["U"] - (10 * U**2 + P**2))

    beta_x = sp.simplify(sp.diff(3 * P / L, L) * extracted["L"] + sp.diff(3 * P / L, P) * extracted["P"])
    beta_x_closed = (3 * P / L) * (-2 * L + 4 * U + 4 * P - 6 * P**2 / L)
    ray = sp.expand(extracted["L"] - 6 * extracted["U"])
    checks["beta_x_derivation"] = zero(beta_x - beta_x_closed)
    checks["ray_drift_identity"] = zero(ray.subs({L: 6 * U}) - 48 * U**2)
    checks["cancellation_h2_drift"] = zero(beta_x.subs({L: 6 * U, P: 2 * U}) + 4 * U)
    checks["cancellation_h6_drift"] = zero(beta_x.subs({L: 6 * U, P: 6 * U}) + 60 * U)

    formula_text = {
        "beta_L_num": "3*L**2 + 6*P**2",
        "beta_P_num": "P*(L + 4*U + 4*P)",
        "beta_U_num": "10*U**2 + P**2",
        "beta_muS2_num": "L*muS2 + 2*P*muC2",
        "beta_muC2_num": "P*muS2 + 4*U*muC2",
        "beta_Lambda0_num": "(muS2**2 + 2*muC2**2)/2",
        "beta_x_num": "x*(-2*L + 4*U + 4*P - 6*P**2/L), x=3*P/L",
        "ray_drift_num": "beta_L_num - 6*beta_U_num = 48*U**2 when L=6*U",
        "hessian_trace": "16*pi**2 beta_W = (1/2)*tr((W\'\')**2)",
        "odd_monomials": "all coefficients outside the Z2(S) x O(2)(X,Y) basis are exactly zero",
        "gaussian_proof": "beta_L_num=3*L**2+6*P**2 and beta_U_num=10*U**2+P**2 are nonnegative squares",
    }
    residuals = {
        "hessian_trace": str(sp.simplify(support["residual"])),
        "beta_x": str(sp.simplify(beta_x - beta_x_closed)),
        "ray_drift_on_L6U": str(sp.simplify(ray.subs({L: 6 * U}) - 48 * U**2)),
        "h2": str(sp.simplify(beta_x_closed.subs({L: 6 * U, P: 2 * U}) + 4 * U)),
        "h6": str(sp.simplify(beta_x_closed.subs({L: 6 * U, P: 6 * U}) + 60 * U)),
    }
    formulas = {**formula_text, "residuals": residuals}
    return checks, formulas, {"beta_x": beta_x, "ray": ray, **extracted}


def scientific_rows() -> tuple[list[dict[str, Any]], dict[str, bool], dict[str, Any], str | None]:
    checks, symbolic, beta = symbolic_scientific_checks()
    errors: list[str] = []
    rows: list[dict[str, Any]] = []
    expected_vector_checks: list[bool] = []
    potential_checks: list[bool] = []
    canonical_relation_checks: list[bool] = []
    ray_checks: list[bool] = []
    cancellation_checks: list[bool] = []

    for n_value in N_VALUES:
        ng = sp.Integer(n_value)
        for h_text in H_VALUES:
            hg = sp.Rational(h_text)
            key = f"N{n_value}-h{h_text}"
            try:
                W, derived, coordinate = canonical_action_w(ng, hg)
                action_residual = sp.simplify(sp.expand(W - coordinate["expected"]))
                potential_ok = action_residual == 0
                potential_checks.append(potential_ok)
                L_expr = derived["L"]
                P_expr = derived["P"]
                U_expr = derived["U"]
                expected_couplings = [8 * sp.sqrt(2) * 6 / ng, 8 * sp.sqrt(2) * hg / ng, 8 * sp.sqrt(2) / ng]
                coupling_values = [real_value(value, f"{key} coupling") for value in (L_expr, P_expr, U_expr)]
                expected_values = [real_value(value, f"{key} expected coupling") for value in expected_couplings]
                vector_ok = relative_error(coupling_values, expected_values) <= TOLERANCE
                expected_vector_checks.append(vector_ok)
                canonical_relation_checks.append(
                    zero(L_expr - 6 * U_expr)
                    and zero(P_expr - hg * U_expr)
                    and zero(U_expr - 8 * sp.sqrt(2) / ng)
                )
                masses = [derived["muS2"], derived["muC2"]]
                # Use the symbols from the beta expressions by name, avoiding any source import.
                Ls, Ps, Us, MSs, MCs = sp.symbols("L P U muS2 muC2", real=True)
                subs_beta = {Ls: L_expr, Ps: P_expr, Us: U_expr, MSs: masses[0], MCs: masses[1]}
                # Match the same real symbols used by the Hessian reconstruction.
                bL = beta["L"].subs(subs_beta)
                bP = beta["P"].subs(subs_beta)
                bU = beta["U"].subs(subs_beta)
                bMS = beta["muS2"].subs(subs_beta)
                bMC = beta["muC2"].subs(subs_beta)
                bLambda = beta["Lambda0"].subs(subs_beta)
                bx = beta["beta_x"].subs(subs_beta)
                bray = beta["ray"].subs(subs_beta)
                row = {
                    "key": key,
                    "N": n_value,
                    "h": finite_float(hg, f"{key} h"),
                    "c": real_value(derived["c"], f"{key} c"),
                    "couplings": coupling_values,
                    "beta_quartic_numerator": [real_value(bL, f"{key} beta_L"), real_value(bP, f"{key} beta_P"), real_value(bU, f"{key} beta_U")],
                    "mass2": [real_value(masses[0], f"{key} muS2"), real_value(masses[1], f"{key} muC2")],
                    "beta_mass_numerator": [real_value(bMS, f"{key} beta_muS2"), real_value(bMC, f"{key} beta_muC2")],
                    "beta_constant_numerator": real_value(bLambda, f"{key} beta_Lambda0"),
                    "beta_x_numerator": real_value(bx, f"{key} beta_x"),
                    "ray_drift_numerator": real_value(bray, f"{key} ray drift"),
                }
                rows.append(row)
                ray_checks.append(zero(bray - 48 * U_expr**2) and real_value(bray, f"{key} ray") > 0)
                if h_text == "2":
                    cancellation_checks.append(real_value(bx, f"{key} beta_x h2") < 0 and zero(bx + 4 * U_expr))
                elif h_text == "6":
                    cancellation_checks.append(real_value(bx, f"{key} beta_x h6") < 0 and zero(bx + 60 * U_expr))
            except (TypeError, ValueError, ZeroDivisionError) as exc:
                errors.append(f"{key}: {exc}")

    checks["all_potential_reconstructions"] = all(potential_checks) and len(potential_checks) == 16
    checks["all_coupling_vectors"] = all(expected_vector_checks) and len(expected_vector_checks) == 16
    checks["all_retained_ratio_identities"] = all(canonical_relation_checks) and len(canonical_relation_checks) == 16
    checks["all_ray_drifts_positive"] = all(ray_checks) and len(ray_checks) == 16
    checks["h2_and_h6_cancellation_drifts"] = all(cancellation_checks) and len(cancellation_checks) == 8
    checks["row_count"] = len(rows) == 16
    numeric_fields = (
        "h",
        "c",
        "couplings",
        "beta_quartic_numerator",
        "mass2",
        "beta_mass_numerator",
        "beta_constant_numerator",
        "beta_x_numerator",
        "ray_drift_numerator",
    )
    checks["rows_finite"] = all(
        math.isfinite(float(value))
        for row in rows
        for field in numeric_fields
        for value in ([row[field]] if not isinstance(row[field], list) else row[field])
    )
    if not all(checks.values()):
        errors.append("one or more symbolic, closure, limit, or scheduled-row checks failed")
    return rows, checks, symbolic, "; ".join(errors) if errors else None


def receipt_base(error: str | None = None) -> dict[str, Any]:
    return {
        "schema": RECEIPT_SCHEMA,
        "role": ROLE,
        "verdict": FAIL_VERDICT,
        "numeric_pass": False,
        "error": error,
        "complete_physical_matter_formation": False,
        "checks": {},
        "symbolic": {},
        "rows": [],
    }


def write_receipt(output: Path, receipt: dict[str, Any]) -> None:
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.mkdir(parents=False, exist_ok=False)
        (output / "result.json").write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    except FileExistsError as exc:
        raise GuardError(f"refusing to modify existing output directory {output}") from exc
    except OSError as exc:
        raise GuardError(f"cannot create or write output {output}: {exc}") from exc


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    root = Path(__file__).resolve().parents[1]
    output = Path(args.output).resolve()
    if output.exists():
        print(f"refusing to modify existing output directory {output}", file=sys.stderr)
        return 1
    try:
        validate_manifest(root, Path(args.manifest).resolve())
    except GuardError as exc:
        try:
            write_receipt(output, {**receipt_base(str(exc)), "error": str(exc)})
        except GuardError as output_error:
            print(str(output_error), file=sys.stderr)
            return 1
        return 1

    try:
        rows, checks, symbolic, error = scientific_rows()
        numeric_pass = error is None and all(checks.values()) and len(rows) == 16
        receipt = {
            "schema": RECEIPT_SCHEMA,
            "role": ROLE,
            "verdict": SUCCESS_VERDICT if numeric_pass else FAIL_VERDICT,
            "numeric_pass": numeric_pass,
            "error": error,
            "complete_physical_matter_formation": False,
            "checks": checks,
            "symbolic": symbolic,
            "rows": rows,
            "scope": {
                "claim": "conditional scalar quantum coupling constraints at one scalar loop in MS-bar",
                "not_claimed": [
                    "nonperturbative ultraviolet completion",
                    "physical action normalization",
                    "loop production amplitudes or rates",
                    "complete physical matter formation",
                ],
            },
        }
        write_receipt(output, receipt)
    except (GuardError, ValueError, TypeError, ZeroDivisionError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0 if numeric_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
