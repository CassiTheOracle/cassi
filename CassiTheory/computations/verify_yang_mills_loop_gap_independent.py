#!/usr/bin/env python3
"""Independent verifier for the frozen pure SU(2) loop-gap spectrum protocol.

Usage:
    python computations/verify_yang_mills_loop_gap_independent.py \
        --input  <dir or file>/primary.json \
        --output <fresh path>/independent.json

This program is the independent measurement path for the receipt schema
``cassi.yang-mills.loop-gap.v1``. It never constructs, imports, or reuses the
primary program's tridiagonal electric-basis operator. Its spectrum is obtained
from the Mathieu/Dirichlet eigenproblem below, evaluated by two-sided
Pruefer-phase shooting. It uses neither a representation cutoff nor
the primary matrix.

Derivation (self-contained; cross-checked in reasoning against
arXiv:2307.11829 Eqs. (55)-(56), (62) and Appendix B, but imported nowhere).

1. Chosen lattice Hamiltonian (open cubic box, lattice spacing a, no sources):

       H = (g^2 / 2a) sum_links E_link^2
         + (1 / 2 g^2 a) sum_unoriented_plaquettes Tr(2I - U_p - U_p^dagger).

   Generators are sigma^a/2, so a spin-j representation carries the quadratic
   Casimir j(j+1); on a physical (gauge-invariant) class function of one loop
   variable the induced radial electric operator is -sin^-2(theta) d_theta
   sin^2(theta) d_theta with eigenvalues n(n+2), n = 2j = 0,1,2,...  The single
   square (one plaquette universe, open-boundary box aside) is an exact
   finite-graph CONTROL of the full interacting many-plaquette Hamiltonian, not
   an invariant restriction: a 2-site-per-side open cubic box has six
   unoriented plaquettes and twelve electric links. The graph theorem's
   periodic extension requires girth four; no periodic graph is enumerated.

2. Physical radial problem. Write the plaquette holonomy as
   U_p = exp(i theta n_hat.sigma), theta in (0, pi), Tr U_p = 2 cos(theta).
   Gauge-invariant states are class functions psi(theta) with normalized Haar
   measure (2/pi) sin^2(theta) d(theta). The character basis
   chi_{n/2}(theta) = sin((n+1) theta)/sin(theta) is orthonormal for that
   measure. The Hamiltonian on this domain is

       H psi = (g^2 / 2a) [ -sin^-2(theta) d_theta sin^2(theta) d_theta ] psi
             + (2 / g^2 a) (1 - cos theta) psi.

   Matrix elements: electric term is diagonal, (g^2/2a) n(n+2) delta_nm
   (e.g. n=1: -Laplacian(2 cos theta) = 6 cos theta = 3 * chi_{1/2}, matching
   n(n+2)=3). For the magnetic term, sin((n+1)theta) cos(theta)
   = (1/2)[sin((n+2)theta) + sin(n theta)] gives cos(theta) chi_n
   = (chi_{n+1} + chi_{n-1})/2, and <cos>_nn = 0, so

       H_nm = (g^2/2a) n(n+2) delta_nm + (2/g^2 a) delta_nm
              - (1/g^2 a) (delta_{n,m+1} + delta_{n,m-1}),        (frozen matrix)

   which is the primary's half-line (n >= 0) Dirichlet-tail tridiagonal
   operator, reproduced here only as a statement of what is being verified.

3. Transformation to Mathieu form. Substitute psi = u(theta)/sin(theta); the
   inner product for u uses (2/pi) d(theta), with u(0) = u(pi) = 0, and
   -sin^-2 (sin^2 psi')' = sin^-1 (-u'' - u). Hence

       -(g^2/2a) u'' + (2/g^2 a)(1 - cos theta) u = (E + g^2/2a) u,
       -u'' + (4/g^4)(1 - cos theta) u = (2aE/g^2 + 1) u  (scaled).

   With theta = 2z:  u_zz + [4lambda - 16/g^4 + (16/g^4) cos 2z] u = 0,
   lambda = 2aE/g^2 + 1.  Comparing u'' + (A - 2q cos 2z) u = 0 gives
   A = 4 lambda - 16/g^4, q = -8/g^4. Regularity of psi = u/sin(theta) selects
   the odd pi-periodic Mathieu functions se_{2(n+1)}(z, q) (at q = 0 they are
   sin(2(n+1) z) = sin((n+1) theta), i.e. exactly u_n = sin((n+1)theta)), so
   A = b_{2(n+1)}(-8/g^4) and

       E_n(g, a) = (g^2/8a) [ b_{2(n+1)}(-8/g^4) - 4 ] + 2/(g^2 a).   (*)

   At a = 1 this matches Appendix B Eq. (B10) of arXiv:2307.11829
   (lambda_n = 2/g^2 + (g^2/8)(b_n(q) - 4), n = 2,4,6,...) term for term,
   which is the promised cross-check; (*) is re-derived above and used as the
   independent measurement.

4. Weak-coupling limit g -> 0 (|q| -> infinity). Saddle at theta = 0:
   H ~ (g^2/2a)(-d^2/dtheta^2) + theta^2/(g^2 a), an oscillator with
   omega = sqrt(2)/a on the odd-u sector (u(0) = 0 kills even oscillator
   states), so consecutive physical levels are spaced 2*omega = 2*sqrt(2)/a;
   at a = 1 the spacing is 2*sqrt(2), and the -g^2/2a uniform shift in step 3
   does not affect spacings.

5. Small-x scaled single-square gap. In units h = (2a/g^2) H with
   x = 2/g^4:  h = D + 2x I - x A, D|n> = n(n+2)|n>, A = nearest-neighbour
   adjacency on n >= 0. W = diag((-1)^n) maps h - 2x I = D - x A to
   D + x A = its x -> -x partner, so the GAP is exactly even in x.
   Rayleigh-Schrodinger perturbation theory gives
   E0 = 2x - x^2/3 + O(x^4), E1 = 3 + 2x + (2/15)x^2 + O(x^4),
   hence  gap(h) = 3 + (7/15) x^2 + O(x^4). The same coefficients follow from
   the b-series: b2 = 4 - q^2/12 + O(q^4), b4 = 16 + q^2/30 + O(q^4) give
   gap(h) = (b4 - b2)/4 = 3 + 7q^2/240, q = -4x. Labels: "3" is the
   pure-electric (g -> infinity) single-square gap in h units, i.e.
   (3/2) g^2 / a in physical units; the O(x^2) term is the finite-square
   magnetic tunnelling correction of the CONTROL, not a statement about the
   full many-plaquette lattice gap or the continuum theory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

from scipy.integrate import solve_ivp
from scipy.optimize import brentq
import scipy  # noqa: F401  (recorded in the receipt for provenance)

ROOT = Path(__file__).resolve().parents[1]
SELF_PATH = Path(__file__).resolve()

PRIMARY_SCHEMA = "cassi.yang-mills.loop-gap.v1"
RECEIPT_SCHEMA = "cassi.yang-mills.loop-gap.independent.v1"

# Frozen protocol constants (independently declared; the row inventory and all
# comparisons are scoped exactly to these values).
COUPLINGS = (0.125, 0.25, 0.5, 1.0, 2.0, 4.0)
CUTOFFS = (32, 64, 128)
LATTICE_SPACING = 1.0
ENERGY_LEVELS = 3
NORMALIZED_TOLERANCE = 1e-8
GAP_IDENTITY_TOLERANCE = 1e-12

REQUIRED_PRIMARY_KEYS = ("schema", "status", "identities", "spectrum_rows")
IDENTITY_KEYS = ("protocol", "primary", "independent")
ROW_KEYS = frozenset({"coupling", "cutoff", "energies", "gap"})
SNAPSHOT_DIRNAME = "primary.sources"
INPUTS_BASENAME = "primary.inputs.json"  # adjacent manifest carrying the identical identities map
SELF_BASENAME = "verify_yang_mills_loop_gap_independent.py"
PRIMARY_BASENAME = "verify_yang_mills_loop_gap.py"
PREREG_BASENAME = "yang-mills-loop-gap-prereg.md"
EXPECTED_IDENTITY_BASENAMES = {
    "protocol": PREREG_BASENAME,
    "primary": PRIMARY_BASENAME,
    "independent": SELF_BASENAME,
}

# Analytic landmarks of the independent path, recorded in every receipt.
PURE_ELECTRIC_SCALED_GAP = 3.0
SMALL_X_GAP_QUADRATIC = 7.0 / 15.0
WEAK_COUPLING_SPACING = 2.0 * math.sqrt(2.0)

# Numerical evaluation of the fixed characteristic-value problem.
PHASE_RTOL = 2e-12
PHASE_ATOL = 2e-13
ENERGY_XTOL = 2e-12


class VerificationError(Exception):
    """Raised for input/contract inconsistencies that must fail closed."""


# --------------------------------------------------------------------------
# independent spectrum: Mathieu eigenproblem by two-sided phase shooting
# --------------------------------------------------------------------------

def independent_level(g: float, n: int, a: float = LATTICE_SPACING) -> float:
    """Evaluate the nth Dirichlet eigenvalue without a matrix truncation.

    In -u'' + Q(theta)u = lambda*u, Q=4(1-cos(theta))/g^4 and
    lambda=1+2aE/g^2. Write u=r*sin(phi), u'=kappa*r*cos(phi).
    Then phi'=kappa*cos(phi)^2+(lambda-Q)*sin(phi)^2/kappa.
    Integrate from both Dirichlet endpoints with phi=0. At the meeting
    point, phi_left-phi_right=(n+1)*pi selects the nth eigenvalue.
    Two-sided integration avoids propagating a decaying amplitude through
    the exponentially forbidden region. The matching point changes no
    boundary condition or spectrum.
    """
    kappa = math.sqrt(1.0 + 1.0 / (g * g))
    meeting = min(math.pi / 2.0, 3.0 * g)
    potential_scale = 4.0 / (g ** 4)

    def mismatch(energy_a: float) -> float:
        lam = 1.0 + 2.0 * energy_a / (g * g)

        def phase_rhs(theta: float, phase: Any) -> tuple[float]:
            sine = math.sin(float(phase[0]))
            cosine = math.cos(float(phase[0]))
            wave_number_sq = lam - potential_scale * (1.0 - math.cos(theta))
            return (kappa * cosine * cosine + wave_number_sq * sine * sine / kappa,)

        # Resolve oscillations even when a step estimator sees repeated phases.
        max_step = min(0.05, math.pi / (8.0 * math.sqrt(max(1.0, lam))))
        phases = []
        for endpoint in (0.0, math.pi):
            solution = solve_ivp(
                phase_rhs, (endpoint, meeting), (0.0,), method="DOP853",
                rtol=PHASE_RTOL, atol=PHASE_ATOL, max_step=max_step,
                t_eval=(meeting,),
            )
            if not solution.success or not math.isfinite(float(solution.y[0, -1])):
                raise VerificationError(f"Dirichlet phase integration failed: {solution.message}")
            phases.append(float(solution.y[0, -1]))
        return phases[0] - phases[1] - (n + 1) * math.pi

    # Min-max bound from 0 <= V <= 4/g^2 and the free Dirichlet spectrum.
    upper_bound = g * g * n * (n + 2) / 2.0 + 4.0 / (g * g)
    upper = min(upper_bound, 1.0 + g * g * n * (n + 2) / 2.0
                + math.sqrt(2.0) * (2 * n + 1.5))
    upper_residual = mismatch(upper)
    while upper_residual <= 0.0 and upper < upper_bound:
        upper = min(2.0 * upper, upper_bound)
        upper_residual = mismatch(upper)
    if upper_residual <= 0.0:
        raise VerificationError(f"Dirichlet eigenvalue bracket failed at g={g}, n={n}")
    energy_a = brentq(mismatch, 0.0, upper, xtol=ENERGY_XTOL, rtol=2e-13)
    return float(energy_a / a)


def independent_row(g: float) -> dict[str, Any]:
    energies = [independent_level(g, n) for n in range(ENERGY_LEVELS)]
    gap = energies[1] - energies[0]
    return {
        "coupling": g,
        "cutoff": None,  # numerical Dirichlet solution without a basis cutoff
        "energies": energies,
        "gap": gap,
        "mathieu_q": -8.0 / (g ** 4),
        "mathieu_b": [4.0 + 8.0 * LATTICE_SPACING * energy / (g * g)
                      - 16.0 / (g ** 4) for energy in energies],
    }


def independent_diagnostics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Non-gating analytic consistency probes of the independent path."""
    per_coupling = []
    for row in rows:
        g = row["coupling"]
        x = 2.0 / (g ** 4)
        scaled_gap = (2.0 * LATTICE_SPACING / (g * g)) * row["gap"]
        per_coupling.append({
            "coupling": g,
            "x": x,
            "scaled_gap_exact": scaled_gap,
            "scaled_gap_series_3_plus_7x2_over_15": PURE_ELECTRIC_SCALED_GAP + SMALL_X_GAP_QUADRATIC * x * x,
            "abs_deviation_from_series": abs(scaled_gap
                                             - (PURE_ELECTRIC_SCALED_GAP + SMALL_X_GAP_QUADRATIC * x * x)),
        })
    weakest = min(COUPLINGS)
    weak_spacing = next(row["gap"] for row in rows if row["coupling"] == weakest)
    return {
        "pure_electric_scaled_gap": PURE_ELECTRIC_SCALED_GAP,
        "small_x_gap_quadratic_coefficient": SMALL_X_GAP_QUADRATIC,
        "weak_coupling_spacing_expected_2sqrt2_at_a1": WEAK_COUPLING_SPACING,
        "weak_coupling_spacing_observed": weak_spacing,
        "per_coupling": per_coupling,
    }


# --------------------------------------------------------------------------
# hashing / path resolution
# --------------------------------------------------------------------------

def sha256_raw(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve_manifest_path(spec: str) -> Path | None:
    """Manifest paths may be root-relative, parent-relative, or absolute."""
    candidate = Path(spec)
    if candidate.is_absolute():
        return candidate if candidate.is_file() else None
    for base in (ROOT, ROOT.parent, Path.cwd()):
        probe = base / candidate
        if probe.is_file():
            return probe.resolve()
    return None


def json_load_strict(path: Path) -> Any:
    def reject_constant(token: str) -> float:
        raise VerificationError(f"non-finite JSON token {token!r} in {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    except json.JSONDecodeError as exc:
        raise VerificationError(f"primary input is not valid JSON: {exc}") from exc


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) \
        and math.isfinite(float(value))


def all_numbers_finite(value: Any) -> bool:
    if isinstance(value, bool):
        return True
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    if isinstance(value, dict):
        return all(all_numbers_finite(v) for v in value.values())
    if isinstance(value, list):
        return all(all_numbers_finite(v) for v in value)
    return True


# --------------------------------------------------------------------------
# primary receipt validation scoped to the fixed protocol
# --------------------------------------------------------------------------

def validate_identities(primary: dict[str, Any]) -> dict[str, dict[str, str]]:
    identities = primary.get("identities")
    if not isinstance(identities, dict):
        raise VerificationError("primary.identities must be an object")
    if set(identities) != set(IDENTITY_KEYS):
        raise VerificationError(
            f"primary.identities keys must be exactly {list(IDENTITY_KEYS)}, got {sorted(identities)}")
    resolved: dict[str, dict[str, str]] = {}
    for name in IDENTITY_KEYS:
        entry = identities[name]
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256"}:
            raise VerificationError(f"primary.identities.{name} must have keys exactly [path, sha256]")
        path, digest = entry["path"], entry["sha256"]
        if not isinstance(path, str) or not path:
            raise VerificationError(f"primary.identities.{name}.path must be a non-empty string")
        if not isinstance(digest, str) or len(digest) != 64 \
                or any(ch not in "0123456789abcdef" for ch in digest):
            raise VerificationError(f"primary.identities.{name}.sha256 must be 64 lowercase hex chars")
        base = Path(path.replace("\\", "/")).name
        expected = EXPECTED_IDENTITY_BASENAMES[name]
        if base != expected:
            raise VerificationError(
                f"primary.identities.{name}.path must name {expected}, got {base}")
        resolved[name] = {"path": path, "sha256": digest}
    if len({entry["path"] for entry in resolved.values()}) != len(IDENTITY_KEYS):
        raise VerificationError("primary.identities paths must name three distinct sources")
    return resolved


def validate_rows(primary: dict[str, Any]) -> dict[tuple[float, int], dict[str, float]]:
    """Exact full 6x3 inventory; returns (coupling, cutoff) -> {e0,e1,e2,gap}."""
    rows = primary.get("spectrum_rows")
    if not isinstance(rows, list):
        raise VerificationError("primary.spectrum_rows must be a list")
    inventory: dict[tuple[float, int], dict[str, float]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise VerificationError(f"spectrum_rows[{index}] must be an object")
        if frozenset(row) != ROW_KEYS:
            raise VerificationError(
                f"spectrum_rows[{index}] keys must be exactly "
                f"{sorted(ROW_KEYS)}, got {sorted(row)}")
        coupling, cutoff = row["coupling"], row["cutoff"]
        if not is_number(coupling):
            raise VerificationError(f"spectrum_rows[{index}].coupling must be a finite number")
        if not is_number(cutoff) or int(cutoff) != cutoff:
            raise VerificationError(f"spectrum_rows[{index}].cutoff must be a finite integer")
        energies, gap = row["energies"], row["gap"]
        if not isinstance(energies, list) or len(energies) != ENERGY_LEVELS \
                or not all(is_number(v) for v in energies):
            raise VerificationError(
                f"spectrum_rows[{index}].energies must be exactly {ENERGY_LEVELS} finite numbers")
        if not is_number(gap):
            raise VerificationError(f"spectrum_rows[{index}].gap must be a finite number")
        key = (float(coupling), int(cutoff))
        if key in inventory:
            raise VerificationError(f"duplicate spectrum row for (coupling, cutoff) = {key}")
        inventory[key] = {f"e{n}": float(energies[n]) for n in range(ENERGY_LEVELS)} | {"gap": float(gap)}
    expected = {(g, n) for g in COUPLINGS for n in CUTOFFS}
    if len(inventory) != len(expected):
        raise VerificationError(
            f"spectrum row inventory mismatch: expected exactly {len(expected)} rows "
            f"{sorted(expected)}, got {len(inventory)} rows {sorted(inventory)}")
    if set(inventory) != expected:
        missing = sorted(expected - set(inventory))
        extra = sorted(set(inventory) - expected)
        raise VerificationError(f"spectrum row inventory mismatch: missing={missing}, extra={extra}")
    return inventory


def check_gap_identity(inventory: dict[tuple[float, int], dict[str, float]]) -> list[str]:
    failures = []
    for key, row in sorted(inventory.items()):
        delta = abs(row["gap"] - (row["e1"] - row["e0"]))
        if delta > GAP_IDENTITY_TOLERANCE * max(1.0, abs(row["gap"])):
            failures.append(
                f"row {key}: gap {row['gap']!r} inconsistent with energies[1]-energies[0] "
                f"by {delta:.3e} > {GAP_IDENTITY_TOLERANCE:.0e}")
    return failures


# --------------------------------------------------------------------------
# source binding: manifest == frozen snapshot == live file, twice
# --------------------------------------------------------------------------

def bind_sources(identities: dict[str, dict[str, str]],
                 snapshot_dir: Path) -> tuple[dict[str, Any], list[str]]:
    """Returns a per-source binding record and the list of binding failures.

    Manifest hashes bind raw bytes only (no CRLF-normalized alternatives), and
    each live source must be byte-identical to its frozen snapshot under
    ``primary.sources/``.
    """
    binding: dict[str, Any] = {}
    failures: list[str] = []
    for name in IDENTITY_KEYS:
        record = identities[name]
        entry: dict[str, Any] = {"declared_path": record["path"], "manifest_sha256": record["sha256"]}
        target = resolve_manifest_path(record["path"])
        if target is None:
            failures.append(f"identity '{name}': declared path does not resolve to a file: {record['path']}")
            binding[name] = entry
            continue
        entry["resolved_path"] = str(target)
        if name == "independent" and target != SELF_PATH:
            failures.append(
                f"identity 'independent' resolves to {target}, not this running verifier {SELF_PATH}")
        snapshot = snapshot_dir / target.name
        entry["snapshot_path"] = str(snapshot)
        live_before = sha256_raw(target)
        if snapshot.is_file():
            entry["snapshot_sha256"] = sha256_raw(snapshot)
        else:
            entry["snapshot_sha256"] = None
            failures.append(f"identity '{name}': frozen snapshot missing under {snapshot_dir}")
        digest = record["sha256"]
        if digest != live_before:
            failures.append(
                f"identity '{name}': manifest sha256 {digest} does not match the raw bytes "
                f"of {target} ({live_before})")
        if entry["snapshot_sha256"] is not None and entry["snapshot_sha256"] != live_before:
            failures.append(
                f"identity '{name}': live source {target} drifted from frozen snapshot "
                f"(live {live_before} != snapshot {entry['snapshot_sha256']})")
        entry["live_sha256_at_bind"] = live_before
        binding[name] = entry
    return binding, failures


def recheck_live_sources(binding: dict[str, Any]) -> list[str]:
    """A source changed *during* verification must fail: hash again, compare."""
    failures = []
    for name in IDENTITY_KEYS:
        entry = binding.get(name) or {}
        target = entry.get("resolved_path")
        before = entry.get("live_sha256_at_bind")
        if not target or before is None:
            failures.append(f"identity '{name}': cannot recheck live source hash (unresolved at bind time)")
            continue
        after = sha256_raw(Path(target))
        entry["live_sha256_at_check"] = after
        if after != before:
            failures.append(
                f"identity '{name}': source changed during verification ({Path(target).name}: "
                f"{before} -> {after})")
    return failures


# --------------------------------------------------------------------------
# comparisons
# --------------------------------------------------------------------------

def normalized_error(left: float, right: float) -> float:
    """Frozen protocol definition: |v - w| / max(1, |v|, |w|)."""
    return abs(left - right) / max(1.0, abs(left), abs(right))


def compare_cutoff128(inventory: dict[tuple[float, int], dict[str, float]],
                      independent_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    comparisons = []
    for row in independent_rows:
        g = row["coupling"]
        primary_row = inventory[(g, CUTOFFS[-1])]
        primary_values = [primary_row[f"e{n}"] for n in range(ENERGY_LEVELS)] + [primary_row["gap"]]
        indep_values = row["energies"] + [row["gap"]]
        errors = [abs(p - i) for p, i in zip(primary_values, indep_values)]
        norm = [normalized_error(p, i) for p, i in zip(primary_values, indep_values)]
        worst = max(norm)
        comparisons.append({
            "coupling": g,
            "cutoff": CUTOFFS[-1],
            "quantities": ["energy_n0", "energy_n1", "energy_n2", "gap"],
            "primary": primary_values,
            "independent": indep_values,
            "absolute_errors": errors,
            "normalized_errors": norm,
            "worst_normalized_error": worst,
            "pass": worst < NORMALIZED_TOLERANCE,
        })
    return comparisons


def check_primary_convergence(inventory: dict[tuple[float, int], dict[str, float]]) -> list[dict[str, Any]]:
    rows = []
    for g in COUPLINGS:
        low, high = inventory[(g, CUTOFFS[-2])], inventory[(g, CUTOFFS[-1])]
        primary_values = [low[f"e{n}"] for n in range(ENERGY_LEVELS)] + [low["gap"]]
        reference_values = [high[f"e{n}"] for n in range(ENERGY_LEVELS)] + [high["gap"]]
        norm = [normalized_error(p, r) for p, r in zip(primary_values, reference_values)]
        worst = max(norm)
        rows.append({
            "coupling": g,
            "cutoff_low": CUTOFFS[-2],
            "cutoff_high": CUTOFFS[-1],
            "quantities": ["energy_n0", "energy_n1", "energy_n2", "gap"],
            "values_low": primary_values,
            "values_high": reference_values,
            "normalized_errors": norm,
            "worst_normalized_error": worst,
            "pass": worst < NORMALIZED_TOLERANCE,
        })
    return rows


def check_inputs_manifest(inputs_path: Path,
                          expected_identities: dict[str, dict[str, str]]) -> list[str]:
    """``primary.inputs.json`` is the adjacent manifest carrying the identical
    identities map (protocol prereg + both script paths); compare it exactly."""
    failures: list[str] = []
    if not inputs_path.is_file():
        return [f"adjacent inputs manifest missing: {inputs_path}"]
    try:
        data = json_load_strict(inputs_path)
    except VerificationError as exc:
        return [str(exc)]
    if not isinstance(data, dict):
        return [f"{inputs_path.name}: top level must be a JSON object"]
    if not all_numbers_finite(data):
        failures.append(f"{inputs_path.name}: contains a non-finite number")
    if not expected_identities:
        failures.append(
            f"{inputs_path.name}: cannot compare identities; primary identity map unusable")
        return failures
    try:
        manifest_identities = validate_identities(data)
    except VerificationError as exc:
        failures.append(f"{inputs_path.name}: {exc}")
    else:
        if manifest_identities != expected_identities:
            failures.append(
                f"{inputs_path.name}: identities map differs from primary.json: "
                f"{json.dumps(manifest_identities, sort_keys=True)} != "
                f"{json.dumps(expected_identities, sort_keys=True)}")
    return failures


# --------------------------------------------------------------------------
# receipt assembly and exclusive write
# --------------------------------------------------------------------------

def build_receipt(status: str, checks: list[dict[str, Any]], failures: list[str],
                  payload: dict[str, Any]) -> dict[str, Any]:
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "receipt_role": "independent",
        "protocol": {
            "primary_schema": PRIMARY_SCHEMA,
            "couplings": list(COUPLINGS),
            "cutoffs": list(CUTOFFS),
            "lattice_spacing": LATTICE_SPACING,
            "energy_levels": ENERGY_LEVELS,
            "independent_method": "Mathieu/Dirichlet spectrum via two-sided Pruefer shooting",
            "independent_formula": "E_n = (g^2/8a)[b_{2(n+1)}(-8/g^4) - 4] + 2/(g^2 a)",
            "normalized_error_definition": "|v - w| / max(1, |v|, |w|) applied to "
            "primary-vs-independent energies and gaps and to cutoff-64-vs-cutoff-128 rows",
            "normalized_tolerance": NORMALIZED_TOLERANCE,
            "phase_rtol": PHASE_RTOL,
            "phase_atol": PHASE_ATOL,
            "energy_xtol": ENERGY_XTOL,
        },
        "runtime": {
            "python": sys.version.split()[0],
            "scipy": scipy.__version__,
        },
        "status": status,
        "checks": checks,
        "failures": failures,
    }
    receipt.update(payload)
    return receipt


def write_exclusive(path: Path, receipt: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing receipt: {path}")
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(receipt, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")


def make_check(name: str, failures: list[str], gate: list[str]) -> dict[str, Any]:
    caught = [f for f in gate if f]
    failures.extend(caught)
    return {"name": name, "pass": not caught}


def run(input_path: Path, output_path: Path) -> int:
    payload: dict[str, Any] = {
        "input_path": str(input_path), "input_sha256": None,
        "source_binding": {}, "inputs_manifest": {},
        "independent_rows": [], "comparisons": [], "convergence_rows": [],
        "diagnostics": {},
    }
    checks: list[dict[str, Any]] = []
    failures: list[str] = []

    # --- raw receipt hash (also anchors "changed during verification") ----
    if input_path.is_file():
        input_hash_before = sha256_raw(input_path)
        payload["input_sha256"] = input_hash_before

    primary: Any = None
    structural: list[str] = []
    try:
        if not input_path.is_file():
            raise VerificationError(f"primary input not found: {input_path}")
        primary = json_load_strict(input_path)
        if not isinstance(primary, dict):
            raise VerificationError("primary.json top level must be a JSON object")
        for key in REQUIRED_PRIMARY_KEYS:
            if key not in primary:
                structural.append(f"primary.json missing required key '{key}'")
        unexpected = sorted(k for k in primary if k not in REQUIRED_PRIMARY_KEYS
                            and k not in ("checks", "failures"))
        if unexpected:
            payload["unrecognized_primary_keys"] = unexpected
    except VerificationError as exc:
        structural.append(str(exc))
    checks.append(make_check("primary_parse", failures, structural))

    schema_problems: list[str] = []
    if primary is not None and not structural:
        if primary.get("schema") != PRIMARY_SCHEMA:
            schema_problems.append(f"primary.schema {primary.get('schema')!r} != {PRIMARY_SCHEMA!r}")
        if primary.get("status") != "PASS":
            schema_problems.append(f"primary.status {primary.get('status')!r} != 'PASS'")
        primary_checks = primary.get("checks")
        if not (isinstance(primary_checks, list) and primary_checks
                and all(isinstance(c, dict) and c.get("passed") is True for c in primary_checks)):
            schema_problems.append(
                "primary.checks must be a non-empty list of entries with passed == true")
        primary_failures = primary.get("failures")
        if not isinstance(primary_failures, list) or primary_failures:
            schema_problems.append(
                f"primary.failures must be present and empty for a PASS receipt, got {primary_failures!r}")
        if not all_numbers_finite(primary):
            schema_problems.append("primary.json contains a non-finite number")
    checks.append(make_check("primary_schema_and_status", failures, schema_problems))

    # --- identities + source bindings (frozen and stable) -----------------
    identities: dict[str, dict[str, str]] = {}
    ident_problems: list[str] = []
    if primary is not None and not structural and not schema_problems:
        try:
            identities = validate_identities(primary)
        except VerificationError as exc:
            ident_problems.append(str(exc))
    checks.append(make_check("identity_manifest_shape", failures, ident_problems))

    binding: dict[str, Any] = {}
    bind_problems: list[str] = []
    inputs_path = input_path.parent / INPUTS_BASENAME
    snapshot_dir = input_path.parent / SNAPSHOT_DIRNAME
    if identities:
        binding, bind_problems = bind_sources(identities, snapshot_dir)
    payload["source_binding"] = binding
    checks.append(make_check("source_bindings_frozen", failures, bind_problems))

    # --- exact 6x3 row inventory and finiteness ----------------------------
    inventory: dict[tuple[float, int], dict[str, float]] | None = None
    inventory_problems: list[str] = []
    if primary is not None and not structural and not schema_problems:
        try:
            inventory = validate_rows(primary)
        except VerificationError as exc:
            inventory_problems.append(str(exc))
    checks.append(make_check("row_inventory_exact_6x3", failures, inventory_problems))

    gap_problems = check_gap_identity(inventory) if inventory else ["row inventory unavailable"]
    checks.append(make_check("gap_identity", failures, gap_problems))

    finite_problems: list[str] = []
    if inventory is not None:
        for key, row in sorted(inventory.items()):
            for field, value in row.items():
                if not math.isfinite(value):
                    finite_problems.append(f"row {key} field {field} non-finite: {value!r}")
    else:
        finite_problems.append("row inventory unavailable")
    checks.append(make_check("finite_values", failures, finite_problems))

    # --- adjacent inputs manifest: identical identities map ----------------
    inputs_problems = check_inputs_manifest(inputs_path, identities) if not structural else \
        ["inputs manifest skipped: primary.json unusable"]
    payload["inputs_manifest"] = {
        "path": str(inputs_path),
        "sha256": sha256_raw(inputs_path) if inputs_path.is_file() else None,
    }
    checks.append(make_check("inputs_manifest_identities_match", failures, inputs_problems))

    # --- independent measurement + comparisons ------------------------------
    comparison_problems: list[str] = []
    convergence_problems: list[str] = []
    if inventory is not None:
        try:
            payload["independent_rows"] = [independent_row(g) for g in COUPLINGS]
            payload["diagnostics"] = independent_diagnostics(payload["independent_rows"])
        except VerificationError as exc:
            comparison_problems.append(str(exc))
        if not comparison_problems:
            comparisons = compare_cutoff128(inventory, payload["independent_rows"])
            payload["comparisons"] = comparisons
            for row in comparisons:
                if not row["pass"]:
                    comparison_problems.append(
                        f"coupling {row['coupling']!r}: worst normalized error "
                        f"{row['worst_normalized_error']:.3e} >= {NORMALIZED_TOLERANCE:.0e} "
                        f"vs cutoff-{CUTOFFS[-1]} primary")
            convergence_rows = check_primary_convergence(inventory)
            payload["convergence_rows"] = convergence_rows
            for row in convergence_rows:
                if not row["pass"]:
                    convergence_problems.append(
                        f"coupling {row['coupling']!r}: primary {CUTOFFS[-2]}-vs-{CUTOFFS[-1]} "
                        f"normalized error {row['worst_normalized_error']:.3e} >= "
                        f"{NORMALIZED_TOLERANCE:.0e}")
    else:
        comparison_problems.append("comparison skipped: primary row inventory invalid")
        convergence_problems.append("convergence skipped: primary row inventory invalid")
    checks.append(make_check("independent_vs_primary_cutoff128", failures, comparison_problems))
    checks.append(make_check("primary_cutoff64_to_128_convergence", failures, convergence_problems))

    # --- drift guard: anything changed during this verification fails ------
    drift_problems = recheck_live_sources(binding) if binding else ["source binding unavailable"]
    if input_path.is_file() and payload["input_sha256"] != sha256_raw(input_path):
        drift_problems.append(
            f"primary input changed during verification: {input_path}")
    checks.append(make_check("sources_stable_during_verification", failures, drift_problems))

    status = "PASS" if not failures else "FAIL"
    receipt = build_receipt(status, checks, failures, payload)
    write_exclusive(output_path, receipt)
    return 0 if status == "PASS" else 1


def emergency_receipt(output_path: Path, input_path: Path, exc: BaseException) -> None:
    receipt = build_receipt(
        "FAIL",
        [{"name": "unhandled_exception", "pass": False}],
        [f"verification failure: {type(exc).__name__}: {exc}"],
        {"input_path": str(input_path), "input_sha256": None, "source_binding": {},
         "inputs_manifest": {}, "independent_rows": [], "comparisons": [],
         "convergence_rows": [], "diagnostics": {}},
    )
    write_exclusive(output_path, receipt)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", required=True, type=Path,
                        help="path to Main's raw primary.json (or its directory)")
    parser.add_argument("--output", required=True, type=Path,
                        help="fresh path for the independent.json receipt")
    args = parser.parse_args(argv)
    input_path = args.input.expanduser().resolve()
    if input_path.is_dir():
        input_path = input_path / "primary.json"
    output_path = args.output.expanduser().resolve()
    try:
        return run(input_path, output_path)
    except FileExistsError as exc:
        # Never overwrite a receipt; the refusal itself is the failure signal.
        print(f"verification aborted: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - fail closed with a written receipt
        try:
            emergency_receipt(output_path, input_path, exc)
        except Exception as write_exc:  # noqa: BLE001
            print(f"verification failure: {type(exc).__name__}: {exc}; "
                  f"receipt write failed: {write_exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
