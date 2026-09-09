#!/usr/bin/env python3
"""Independent, source-bound scalar-scattering qualification for notebook §66.

The verifier deliberately rebuilds the canonical polynomial, its fourth-derivative
four-tensor, and the normalized two-particle matrix instead of importing either
of the other quantum-coupling calculations.  Scientific rows are produced only
after all manifest, source, section, and accepted-review guards pass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Sequence

import sympy as sp


SCHEMA = "matter-formation-quantum-coupling-v1"
MANIFEST_SCHEMA = "matter-formation-quantum-coupling-manifest-v1"
ROLE = "scattering"
VERDICT = "SUPPORTS-conditional scalar quantum coupling constraints"
HEADING_66 = "## 66. Working notes: quantum coupling normalization and radiative closure"
HEADING_64 = "## 64. Working notes: matching quantum conversion to the scalar action"
NOTEBOOK = "computations/matter-formation-continuum-report.md"
PARENT_ACTION = "foundations/particle-stationary-action-closure.md"
PROGRAM = "computations/verify_matter_formation_scalar_scattering.py"
PRIMARY = "computations/matter_formation_quantum_coupling.py"
RADIATIVE = "computations/verify_matter_formation_scalar_radiative.py"
SOURCE_PATHS = (PRIMARY, PROGRAM, RADIATIVE, PARENT_ACTION)
H_STRINGS = ("0", "2", "2.9598260763447164", "6")
N_VALUES = (1, 4, 16, 64)

# §66.1 fixed inputs.  SymPy rationals keep all reconstruction identities exact.
A = sp.Rational(1, 16)
C_PSI = sp.Rational(1, 8)
U_RHO = sp.Integer(4)
U_C = sp.Integer(1)
K_CX = sp.Integer(1)
E_C = sp.Rational(3, 4)


class GuardError(Exception):
    """A prerequisite failure which must be reported before scientific rows."""


def canonical_bytes(data: bytes) -> bytes:
    """Apply the manifest's sole canonicalization rule."""
    return data.replace(b"\r\n", b"\n")


def canonical_sha256(path: Path) -> str:
    return hashlib.sha256(canonical_bytes(path.read_bytes())).hexdigest()


def _safe_relative(root: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise GuardError(f"{label} must be a non-empty relative path")
    candidate = Path(value)
    if candidate.is_absolute():
        raise GuardError(f"{label} must be relative to ROOT")
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise GuardError(f"{label} escapes ROOT: {value}") from exc
    return resolved


def _require_sha(value: object, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise GuardError(f"{label} must be a 64-character SHA-256")
    lowered = value.lower()
    if any(ch not in "0123456789abcdef" for ch in lowered):
        raise GuardError(f"{label} is not hexadecimal SHA-256")
    return lowered


def _reject_json_constant(token: str) -> object:
    raise ValueError(f"non-standard JSON constant {token}")


def _read_json(path: Path) -> object:
    try:
        with path.open("r", encoding="utf-8", newline="") as stream:
            return json.load(stream, parse_constant=_reject_json_constant)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise GuardError(f"cannot read manifest JSON: {exc}") from exc


def _section_bytes(data: bytes, heading: str, label: str) -> bytes:
    text = canonical_bytes(data).decode("utf-8")
    lines = text.splitlines(keepends=True)
    matching = [index for index, line in enumerate(lines) if line.rstrip("\n") == heading]
    if len(matching) != 1:
        raise GuardError(f"{label} has {len(matching)} copies of exact heading {heading!r}")
    start = matching[0]
    stop = len(lines)
    for index in range(start + 1, len(lines)):
        if lines[index].startswith("## "):
            stop = index
            break
    return ("".join(lines[start:stop]).rstrip() + "\n").encode("utf-8")


def _manifest_entry_map(entries: object, label: str, required_keys: Sequence[str]) -> list[dict[str, object]]:
    if not isinstance(entries, list):
        raise GuardError(f"manifest {label} must be an array")
    result: list[dict[str, object]] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise GuardError(f"manifest {label}[{index}] must be an object")
        missing = [key for key in required_keys if key not in entry]
        if missing:
            raise GuardError(f"manifest {label}[{index}] missing {','.join(missing)}")
        result.append(entry)
    return result


def _validate_manifest(manifest_path: Path, root: Path) -> None:
    manifest = _read_json(manifest_path)
    if not isinstance(manifest, dict):
        raise GuardError("manifest root must be an object")
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise GuardError("manifest schema mismatch")

    sections = _manifest_entry_map(manifest.get("sections"), "sections", ("path", "heading", "snapshot", "sha256"))
    if len(sections) != 2:
        raise GuardError("manifest sections must contain exactly two entries")
    expected_section_keys = {(NOTEBOOK, HEADING_66), (NOTEBOOK, HEADING_64)}
    section_keys: set[tuple[str, str]] = set()
    for index, entry in enumerate(sections):
        path_value = entry["path"]
        heading_value = entry["heading"]
        key = (str(path_value), str(heading_value))
        if key not in expected_section_keys:
            raise GuardError(f"manifest sections[{index}] is not a required §66/§64 entry")
        if key in section_keys:
            raise GuardError("manifest sections contain duplicates")
        section_keys.add(key)
        live_path = _safe_relative(root, path_value, f"sections[{index}].path")
        snapshot_path = _safe_relative(root, entry["snapshot"], f"sections[{index}].snapshot")
        declared = _require_sha(entry["sha256"], f"sections[{index}].sha256")
        try:
            live_bytes = live_path.read_bytes()
            snapshot_bytes = snapshot_path.read_bytes()
        except (OSError, UnicodeError) as exc:
            raise GuardError(f"cannot read section live/snapshot: {exc}") from exc
        live_section = _section_bytes(live_bytes, str(heading_value), f"live section {path_value}")
        snapshot_section = _section_bytes(snapshot_bytes, str(heading_value), f"snapshot section {entry['snapshot']}")
        if live_section != snapshot_section:
            raise GuardError(f"section live/snapshot bytes differ for {heading_value}")
        if hashlib.sha256(live_section).hexdigest() != declared:
            raise GuardError(f"section hash mismatch for {heading_value}")
    if section_keys != expected_section_keys:
        raise GuardError("manifest sections do not cover exactly §66 and §64")

    sources = _manifest_entry_map(manifest.get("sources"), "sources", ("path", "snapshot", "sha256"))
    if len(sources) != len(SOURCE_PATHS):
        raise GuardError(f"manifest sources must contain exactly {len(SOURCE_PATHS)} entries")
    seen_sources: set[str] = set()
    for index, entry in enumerate(sources):
        path_value = entry["path"]
        if path_value not in SOURCE_PATHS:
            raise GuardError(f"manifest sources[{index}] has an unexpected path")
        if path_value in seen_sources:
            raise GuardError(f"manifest sources duplicate {path_value}")
        seen_sources.add(str(path_value))
        live_path = _safe_relative(root, path_value, f"sources[{index}].path")
        snapshot_path = _safe_relative(root, entry["snapshot"], f"sources[{index}].snapshot")
        declared = _require_sha(entry["sha256"], f"sources[{index}].sha256")
        try:
            live_hash = canonical_sha256(live_path)
            snapshot_hash = canonical_sha256(snapshot_path)
        except (OSError, UnicodeError) as exc:
            raise GuardError(f"cannot hash source live/snapshot {path_value}: {exc}") from exc
        if live_hash != snapshot_hash or live_hash != declared:
            raise GuardError(f"source hash mismatch for {path_value}")
    if seen_sources != set(SOURCE_PATHS):
        raise GuardError("manifest sources do not cover the required four paths")

    reviews = _manifest_entry_map(manifest.get("mathematical_reviews"), "mathematical_reviews", ("role", "accepted", "snapshot", "sha256"))
    if len(reviews) != 2:
        raise GuardError("manifest mathematical_reviews must contain exactly two entries")
    seen_roles: set[str] = set()
    for index, entry in enumerate(reviews):
        role = entry["role"]
        if role not in ("scattering", "radiative"):
            raise GuardError(f"manifest mathematical_reviews[{index}] has an unexpected role")
        if role in seen_roles:
            raise GuardError(f"manifest mathematical_reviews duplicate role {role}")
        seen_roles.add(str(role))
        if entry["accepted"] is not True:
            raise GuardError(f"{role} mathematical review is not accepted")
        snapshot_path = _safe_relative(root, entry["snapshot"], f"mathematical_reviews[{index}].snapshot")
        declared = _require_sha(entry["sha256"], f"mathematical_reviews[{index}].sha256")
        try:
            review_data = canonical_bytes(snapshot_path.read_bytes()).decode("utf-8")
        except (OSError, UnicodeError) as exc:
            raise GuardError(f"cannot read {role} review snapshot: {exc}") from exc
        accepted_lines = [line.strip() for line in review_data.split("\n") if line.strip().startswith("accepted:")]
        if accepted_lines != ["accepted: true"]:
            raise GuardError(f"{role} review must contain exactly one line 'accepted: true'")
        if hashlib.sha256(review_data.encode("utf-8")).hexdigest() != declared:
            raise GuardError(f"review hash mismatch for {role}")
    if seen_roles != {"scattering", "radiative"}:
        raise GuardError("manifest mathematical_reviews does not cover both roles")


def _build_potential() -> dict[str, object]:
    """Reconstruct §66 W by substituting the §64 shifted canonical fields."""
    ns, hs = sp.symbols("N h", positive=True)
    sigma, px, py = sp.symbols("sigma pX pY", real=True)
    S, X, Y = sp.symbols("S X Y", real=True)
    c = 1 / sp.sqrt(C_PSI)
    c32 = c ** sp.Rational(3, 2)
    v = sp.sqrt(ns * C_PSI)
    m2 = 2 * U_RHO / C_PSI
    M2 = (E_C + 1 / (4 * A)) / A
    lambda3 = 3 * m2 / v
    lambda4 = 3 * m2 / v**2
    g = 2 * hs / (A * v)
    g2 = g / v
    carrier2 = (px**2 + py**2) / 2
    V = (
        m2 * sigma**2 / 2
        + M2 * carrier2
        + lambda3 * sigma**3 / 6
        + lambda4 * sigma**4 / 24
        + g * sigma * carrier2
        + g2 * sigma**2 * carrier2 / 2
        + U_C * (carrier2**2) / (2 * ns * A**2)
    )
    shifted = sp.expand(c**3 * V.subs({
        sigma: (S - c32 * v) / c32,
        px: X / c32,
        py: Y / c32,
    }))
    L = sp.simplify(sp.diff(shifted, S, 4))
    P = sp.simplify(sp.diff(shifted, S, 2, X, 2))
    U = sp.simplify(sp.diff(shifted, X, 4) / 3)
    mu_s2 = -U_RHO / C_PSI
    mu_c2 = (E_C + 1 / (4 * A) - hs) / A
    lambda0 = ns * c**3 * U_RHO / 4
    canonical = sp.expand(
        lambda0
        + mu_s2 * S**2 / 2
        + mu_c2 * (X**2 + Y**2) / 2
        + L * S**4 / 24
        + P * S**2 * (X**2 + Y**2) / 4
        + U * (X**2 + Y**2)**2 / 8
    )
    poly = sp.Poly(shifted, S, X, Y)
    odd_terms = [monomial for monomial, coefficient in poly.terms() if any(power % 2 for power in monomial) and coefficient != 0]
    return {
        "N": ns,
        "h": hs,
        "S": S,
        "X": X,
        "Y": Y,
        "c": c,
        "shifted": shifted,
        "canonical": canonical,
        "L": L,
        "P": P,
        "U": U,
        "muS2": mu_s2,
        "muC2": mu_c2,
        "Lambda0": lambda0,
        "odd_terms": odd_terms,
    }


def _four_tensor(potential: sp.Expr, fields: Sequence[sp.Symbol]) -> dict[tuple[int, int, int, int], sp.Expr]:
    tensor: dict[tuple[int, int, int, int], sp.Expr] = {}
    for i in range(3):
        for j in range(3):
            for k in range(3):
                for l in range(3):
                    tensor[(i, j, k, l)] = sp.simplify(sp.diff(potential, fields[i], fields[j], fields[k], fields[l]))
    return tensor


def _pair_denominator(pair: tuple[int, int]) -> int:
    return 1 + int(pair[0] == pair[1])


def _channel_matrix(tensor: dict[tuple[int, int, int, int], sp.Expr]) -> sp.Matrix:
    pairs = ((0, 0), (1, 1), (2, 2), (0, 1), (0, 2), (1, 2))
    matrix = sp.zeros(6, 6)
    for alpha, (i, j) in enumerate(pairs):
        for beta, (k, l) in enumerate(pairs):
            matrix[alpha, beta] = sp.simplify(
                tensor[(i, j, k, l)]
                / sp.sqrt(_pair_denominator((i, j)) * _pair_denominator((k, l)))
            )
    return matrix


def _matrix_zero(matrix: sp.Matrix) -> bool:
    return all(sp.simplify(value) == 0 for value in matrix)


def _matrix_to_floats(matrix: sp.Matrix, substitutions: dict[sp.Symbol, object]) -> list[list[float]]:
    return [[float(sp.N(matrix[row, col].subs(substitutions), 17)) for col in range(matrix.cols)] for row in range(matrix.rows)]


def _matrix_close(left: Sequence[Sequence[float]], right: Sequence[Sequence[float]], tolerance: float = 1e-9) -> bool:
    if len(left) != len(right) or any(len(a) != len(b) for a, b in zip(left, right)):
        return False
    residual = math.hypot(*(a - b for ar, br in zip(left, right) for a, b in zip(ar, br)))
    scale = max(1.0, math.hypot(*(value for row in right for value in row)))
    return residual / scale <= tolerance


def _derive_controls(data: dict[str, object]) -> tuple[dict[str, bool], dict[str, str]]:
    S = data["S"]
    X = data["X"]
    Y = data["Y"]
    L = data["L"]
    P = data["P"]
    U = data["U"]
    canonical = data["canonical"]
    tensor = _four_tensor(canonical, (S, X, Y))
    C = _channel_matrix(tensor)
    z = sp.symbols("z")
    expected_C = sp.Matrix([
        [L / 2, P / 2, P / 2, 0, 0, 0],
        [P / 2, 3 * U / 2, U / 2, 0, 0, 0],
        [P / 2, U / 2, 3 * U / 2, 0, 0, 0],
        [0, 0, 0, P, 0, 0],
        [0, 0, 0, 0, P, 0],
        [0, 0, 0, 0, 0, U],
    ])
    # Independent generic symbols keep the symmetry controls genuine limits,
    # rather than substitutions into the retained h/N family.
    ell, pp, uu = sp.symbols("ell pp uu", real=True)
    generic_C = sp.Matrix([
        [ell / 2, pp / 2, pp / 2, 0, 0, 0],
        [pp / 2, 3 * uu / 2, uu / 2, 0, 0, 0],
        [pp / 2, uu / 2, 3 * uu / 2, 0, 0, 0],
        [0, 0, 0, pp, 0, 0],
        [0, 0, 0, 0, pp, 0],
        [0, 0, 0, 0, 0, uu],
    ])
    q = sp.sqrt(2)
    Q = sp.Matrix([
        [1, 0, 0, 0, 0, 0],
        [0, 1 / q, 1 / q, 0, 0, 0],
        [0, 1 / q, -1 / q, 0, 0, 0],
        [0, 0, 0, 1, 0, 0],
        [0, 0, 0, 0, 1, 0],
        [0, 0, 0, 0, 0, 1],
    ])
    o2_decomposed = sp.simplify(Q * C * Q.T)
    o2_expected = sp.Matrix([
        [L / 2, P / q, 0, 0, 0, 0],
        [P / q, 2 * U, 0, 0, 0, 0],
        [0, 0, U, 0, 0, 0],
        [0, 0, 0, P, 0, 0],
        [0, 0, 0, 0, P, 0],
        [0, 0, 0, 0, 0, U],
    ])
    charpoly = sp.factor(C.charpoly(z).as_expr())
    expected_charpoly = sp.factor(
        (z - P) ** 2 * (z - U) ** 2 * ((z - L / 2) * (z - 2 * U) - P**2 / 2)
    )
    lambda_minus = L / 4 + U - sp.sqrt((L - 4 * U) ** 2 + 8 * P**2) / 4
    lambda_plus = L / 4 + U + sp.sqrt((L - 4 * U) ** 2 + 8 * P**2) / 4
    eigen_product = sp.factor((z - P) ** 2 * (z - U) ** 2 * (z - lambda_minus) * (z - lambda_plus))
    generic_charpoly = sp.factor(
        (z - pp) ** 2 * (z - uu) ** 2 * ((z - ell / 2) * (z - 2 * uu) - pp**2 / 2)
    )

    pairs = ((0, 0), (1, 1), (2, 2), (0, 1), (0, 2), (1, 2))
    cut = sp.zeros(6, 6)
    for alpha, (i, j) in enumerate(pairs):
        external_denominator = sp.sqrt(_pair_denominator((i, j)))
        for beta, (k, l) in enumerate(pairs):
            total = 0
            for m, n in pairs:
                internal_denominator = _pair_denominator((m, n))
                total += tensor[(i, j, m, n)] * tensor[(m, n, k, l)] / (
                    external_denominator * sp.sqrt(_pair_denominator((k, l))) * internal_denominator
                )
            cut[alpha, beta] = sp.simplify(total)
    a0 = -C / (16 * sp.pi)
    cut_im_a0 = cut / (256 * sp.pi**2)
    a0_product = sp.simplify(a0 * a0.T)

    lambda_y = sp.symbols("lambda_Y", real=True)
    single_T = sp.diff(lambda_y * S**4 / 4, S, 4)
    single_C = single_T / 2
    single_a0 = -single_C / (16 * sp.pi)
    correct_a0 = -3 * lambda_y / (16 * sp.pi)
    correct_bound = 8 * sp.pi / 3

    rotation_residual = sp.expand(-Y * sp.diff(canonical, X) + X * sp.diff(canonical, Y))
    generic_quartic = ell * S**4 / 24 + pp * S**2 * (X**2 + Y**2) / 4 + uu * (X**2 + Y**2)**2 / 8
    o3_quartic = sp.expand(generic_quartic.subs({ell: 3 * uu, pp: uu}, simultaneous=True))
    o3_expected_quartic = sp.expand(uu * (S**2 + X**2 + Y**2) ** 2 / 8)
    o3_charpoly = sp.factor(generic_charpoly.subs({ell: 3 * uu, pp: uu}, simultaneous=True))
    o3_expected_charpoly = sp.factor((z - sp.Rational(5, 2) * uu) * (z - uu) ** 5)
    decoupled = generic_C.subs({pp: 0, uu: 0}, simultaneous=True)
    decoupled_expected = sp.diag(ell / 2, 0, 0, 0, 0, 0)
    gaussian = generic_C.subs({ell: 0, pp: 0, uu: 0}, simultaneous=True)

    checks = {
        "equal_cone_relation_exact": sp.simplify(C_PSI - 2 * A / K_CX) == 0,
        "canonical_potential_substitution_exact": sp.simplify(data["shifted"] - canonical) == 0,
        "fourth_derivative_L_exact": sp.simplify(L - 48 * sp.sqrt(2) / data["N"]) == 0,
        "fourth_derivative_P_exact": sp.simplify(P - 8 * sp.sqrt(2) * data["h"] / data["N"]) == 0,
        "fourth_derivative_U_exact": sp.simplify(U - 8 * sp.sqrt(2) / data["N"]) == 0,
        "canonical_odd_monomials_absent": data["odd_terms"] == [],
        "normalized_channel_matrix_exact": _matrix_zero(C - expected_C),
        "o2_decomposition_exact": _matrix_zero(o2_decomposed - o2_expected),
        "characteristic_polynomial_exact": sp.factor(charpoly - expected_charpoly) == 0,
        "characteristic_roots_exact": sp.factor(charpoly - eigen_product) == 0,
        "two_particle_cut_C_squared_exact": _matrix_zero(cut - C * C),
        "two_particle_cut_unitarity_exact": _matrix_zero(cut_im_a0 - a0_product),
        "single_real_scalar_fourth_derivative_exact": sp.simplify(single_T - 6 * lambda_y) == 0,
        "single_real_scalar_a0_bound_exact": sp.simplify(single_a0 - correct_a0) == 0 and sp.simplify(abs(single_a0.subs(lambda_y, correct_bound)) - sp.Rational(1, 2)) == 0,
        "decoupled_real_scalar_control": _matrix_zero(decoupled - decoupled_expected),
        "o2_rotation_control": rotation_residual == 0,
        "o3_symmetric_control": sp.simplify(o3_quartic - o3_expected_quartic) == 0 and sp.factor(o3_charpoly - o3_expected_charpoly) == 0,
        "gaussian_control": _matrix_zero(gaussian),
    }
    symbolic = {
        "canonical_potential": "W=Lambda0+muS2*S^2/2+muC2*(X^2+Y^2)/2+L*S^4/24+P*S^2*(X^2+Y^2)/4+U*(X^2+Y^2)^2/8",
        "derived_couplings": "(L,P,U)=(48*sqrt(2)/N,8*sqrt(2)*h/N,8*sqrt(2)/N)",
        "channel_order": "SS,XX,YY,SX,SY,XY; identical-pair denominator d_ij=1+delta_ij",
        "o2_irreducible_channels": "(SS,(XX+YY)/sqrt(2)) block; (XX-YY)/sqrt(2) eigenvalue U; SX,SY doublet eigenvalue P; XY eigenvalue U",
        "characteristic_polynomial": "(z-P)^2*(z-U)^2*((z-L/2)*(z-2U)-P^2/2)",
        "eigenvalues": "U,U,P,P,L/4+U +/- sqrt((L-4U)^2+8P^2)/4",
        "two_particle_cut": "sum_(m<=n) T_ijmn*T_mnkl/[sqrt(d_ij*d_kl)*d_mn]=C^2; Im(a0)=C^2/(256*pi^2)=a0*a0^dagger",
        "single_real_scalar": "W=lambdaY*S^4/4 => T=6*lambdaY, C=3*lambdaY, a0=-3*lambdaY/(16*pi), |lambdaY|<=8*pi/3",
    }
    data["tensor"] = tensor
    data["C"] = C
    data["lambda_minus"] = lambda_minus
    data["lambda_plus"] = lambda_plus
    data["checks"] = checks
    data["symbolic"] = symbolic
    return checks, symbolic


def _scientific_rows(data: dict[str, object]) -> list[dict[str, object]]:
    ns = data["N"]
    hs = data["h"]
    L = data["L"]
    P = data["P"]
    U = data["U"]
    C = data["C"]
    lambda_minus = data["lambda_minus"]
    lambda_plus = data["lambda_plus"]
    rows: list[dict[str, object]] = []
    for n_value in N_VALUES:
        for h_string in H_STRINGS:
            h_exact = sp.Rational(h_string)
            substitutions = {ns: n_value, hs: h_exact}
            coupling_values = [float(sp.N(expression.subs(substitutions), 17)) for expression in (L, P, U)]
            matrix_values = _matrix_to_floats(C, substitutions)
            eigen_values = sorted([
                float(sp.N(U.subs(substitutions), 17)),
                float(sp.N(U.subs(substitutions), 17)),
                float(sp.N(P.subs(substitutions), 17)),
                float(sp.N(P.subs(substitutions), 17)),
                float(sp.N(lambda_minus.subs(substitutions), 17)),
                float(sp.N(lambda_plus.subs(substitutions), 17)),
            ])
            a0_radius = max(abs(value) for value in eigen_values) / (16 * math.pi)
            rows.append({
                "key": f"N{n_value}-h{h_string}",
                "N": n_value,
                "h": float(h_string),
                "c": float(sp.N(data["c"], 17)),
                "couplings": coupling_values,
                "C": matrix_values,
                "eigenvalues": eigen_values,
                "a0_radius": float(a0_radius),
                "N_min_tree": float(2 * n_value * a0_radius),
                "tree_bound_pass": bool(a0_radius <= 0.5),
            })
    return rows


def _row_checks(rows: Sequence[dict[str, object]], data: dict[str, object]) -> dict[str, bool]:
    expected_keys = [f"N{n_value}-h{h_string}" for n_value in N_VALUES for h_string in H_STRINGS]
    checks: dict[str, bool] = {
        "sixteen_rows_in_fixed_order": [row["key"] for row in rows] == expected_keys,
        "row_count_exact": len(rows) == 16,
        "coupling_relation_numeric": True,
        "matrix_numeric_finite": True,
        "spectrum_numeric_finite": True,
        "tree_bound_decisions_boolean": True,
    }
    expected_C = data["C"]
    for row in rows:
        n_value = int(row["N"])
        h_exact = sp.Rational(str(row["h"]))
        substitutions = {data["N"]: n_value, data["h"]: h_exact}
        relation_couplings = [8 * math.sqrt(2) * value / n_value for value in (6.0, float(row["h"]), 1.0)]
        checks["coupling_relation_numeric"] = checks["coupling_relation_numeric"] and _matrix_close([row["couplings"]], [relation_couplings])
        checks["matrix_numeric_finite"] = checks["matrix_numeric_finite"] and all(math.isfinite(value) for matrix_row in row["C"] for value in matrix_row)
        checks["spectrum_numeric_finite"] = checks["spectrum_numeric_finite"] and all(math.isfinite(value) for value in row["eigenvalues"])
        checks["tree_bound_decisions_boolean"] = checks["tree_bound_decisions_boolean"] and isinstance(row["tree_bound_pass"], bool)
        # The retained matrix must agree with its exact symbolic reconstruction.
        expected_matrix_values = _matrix_to_floats(expected_C, substitutions)
        checks.setdefault("matrix_numeric_reconstruction", True)
        checks["matrix_numeric_reconstruction"] = checks["matrix_numeric_reconstruction"] and _matrix_close(row["C"], expected_matrix_values)
    return checks


def _strict_value(value: object) -> object:
    """Convert SymPy/NumPy-like scalars and containers to strict JSON values."""
    if isinstance(value, dict):
        return {str(key): _strict_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_strict_value(item) for item in value]
    if isinstance(value, bool) or value is None or isinstance(value, str) or isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite float in JSON receipt")
        return value
    if isinstance(value, sp.Integer):
        return int(value)
    if isinstance(value, sp.Rational):
        converted = float(value)
        if not math.isfinite(converted):
            raise ValueError("non-finite SymPy rational in JSON receipt")
        return converted
    if isinstance(value, sp.Float):
        converted = float(value)
        if not math.isfinite(converted):
            raise ValueError("non-finite SymPy float in JSON receipt")
        return converted
    if isinstance(value, sp.Basic):
        if value.is_number and value.is_real:
            converted = float(value)
            if not math.isfinite(converted):
                raise ValueError("non-finite SymPy number in JSON receipt")
            return converted
        return str(value)
    item_method = getattr(value, "item", None)
    if callable(item_method):
        return _strict_value(item_method())
    raise TypeError(f"unsupported JSON value type {type(value).__name__}")


def _write_json(path: Path, payload: object) -> None:
    converted = _strict_value(payload)
    text = json.dumps(converted, allow_nan=False, indent=2, sort_keys=True) + "\n"
    # Parse constants explicitly so a future serializer change cannot emit NaN/Infinity.
    json.loads(text, parse_constant=lambda token: (_ for _ in ()).throw(ValueError(f"invalid JSON constant {token}")))
    path.write_text(text, encoding="utf-8", newline="\n")


def _guard_receipt(error: str) -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "role": ROLE,
        "verdict": "INCONCLUSIVE",
        "numeric_pass": False,
        "error": error,
        "complete_physical_matter_formation": False,
        "checks": {},
        "symbolic": {},
        "rows": [],
    }


def _scientific_receipt(rows: list[dict[str, object]], checks: dict[str, bool], symbolic: dict[str, str], error: str = "") -> dict[str, object]:
    numeric_pass = all(checks.values()) and not error
    return {
        "schema": SCHEMA,
        "role": ROLE,
        "verdict": VERDICT if numeric_pass else "INCONCLUSIVE",
        "numeric_pass": bool(numeric_pass),
        "error": error or None,
        "complete_physical_matter_formation": False,
        "checks": checks,
        "symbolic": symbolic,
        "rows": rows,
        "proof": {
            "scope": "high-energy elastic scalar contact scattering only; masses and exchange terms are neglected",
            "channel_order": ["SS", "XX", "YY", "SX", "SY", "XY"],
            "normalization": "identical external pairs carry 1/sqrt(2); internal unordered pair cut weight is 1/(1+delta_ij)",
            "tree_unitarity": "a0=-C/(16*pi), |Re(a0)|<=1/2, a0_radius<=1/2",
            "physical_status": "conditional scalar quantum coupling constraints; no absolute production rate or physical microscopic selection",
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, help="sealed source/review manifest")
    parser.add_argument("--output", required=True, help="fresh output directory")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    output = Path(args.output).expanduser()
    if not output.is_absolute():
        output = (Path.cwd() / output).resolve()
    if output.exists():
        print(f"refusing existing output directory: {output}", file=sys.stderr)
        return 1
    try:
        output.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        print(f"cannot create fresh output directory: {exc}", file=sys.stderr)
        return 1

    try:
        manifest_path = Path(args.manifest).expanduser()
        if not manifest_path.is_absolute():
            manifest_path = (Path.cwd() / manifest_path).resolve()
        _validate_manifest(manifest_path, root)
    except (GuardError, OSError, ValueError) as exc:
        _write_json(output / "result.json", _guard_receipt(str(exc)))
        return 1

    rows: list[dict[str, object]] = []
    try:
        data = _build_potential()
        checks, symbolic = _derive_controls(data)
        rows = _scientific_rows(data)
        checks.update(_row_checks(rows, data))
        errors = [name for name, passed in checks.items() if not passed]
        error = "failed checks: " + ", ".join(errors) if errors else ""
        _write_json(output / "result.json", _scientific_receipt(rows, checks, symbolic, error))
        return 0 if not error else 1
    except (ArithmeticError, KeyError, TypeError, ValueError, sp.SympifyError) as exc:
        _write_json(output / "result.json", _scientific_receipt(rows, {}, {}, f"scientific reconstruction failure: {exc}"))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
