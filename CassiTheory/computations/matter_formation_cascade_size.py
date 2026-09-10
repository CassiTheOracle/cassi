#!/usr/bin/env python3
"""Frozen conditional cascade-size normalization test (primary program).

Implements `computations/matter-formation-cascade-size-prereg.md` exactly as
frozen: a theta-coordinate massive chiral hedgehog boundary-value problem
solved with SciPy `solve_bvp` on geometric meshes, a 33-point logarithmic
size-equation scan in `mu` over the frozen bracket, unique sign-change
enforcement with a bracketed Brent root, adaptive profile integrals with an
explicit regular-origin segment, independent domain repetition at L=48/96
once the canonical scan yields one qualifying root, size-first coefficient
extraction from the registered pion mass and the directly registered
splitting (never recomputed from absolute masses), the withheld absolute-mass
comparisons applied only after predictions are fixed, and the frozen analytic
radius-rejection semantics of the verdict tree.

Run from the repository root:

    python computations/matter_formation_cascade_size.py --output <new-dir> [--prereg <path>]

This program never imports the independent verifier. The immutable structure
receipt is read only for the reference reconstruction comparison and can
never substitute for a failed reconstruction.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
import traceback
import warnings
from pathlib import Path
from typing import Any, Callable

import numpy as np
import scipy
from scipy.interpolate import CubicHermiteSpline
from scipy.integrate import IntegrationWarning, quad, solve_bvp
from scipy.optimize import brentq

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREREG = ROOT / "computations" / "matter-formation-cascade-size-prereg.md"
DEFAULT_OUTPUT = ROOT / "runs" / "20260909_matter_formation_cascade_size"
VERIFY_SOURCE = ROOT / "computations" / "verify_matter_formation_cascade_size.py"
REFERENCE_RECEIPT = (
    ROOT
    / "runs"
    / "20260907_matter_formation_chiral_lattice"
    / "structure_recovery1"
    / "results.json"
)

SCHEMA = "cassi.matter-formation.cascade-size.v1"

# --- Frozen constants (preregistration section 2) ----------------------------
# The step-95 length is an external scale-selection input (Mapped), never a
# prediction; every receipt labels it as such.
ELL_PL_M = 1.616255e-35
ELL_95_STEP = 95
HBARC_MEV_FM = 197.3269804
M_PI_MEV = 138.039
# Registered collective-rotation input. Deliberately a literal: it must never
# be calculated from the withheld absolute masses inside this program.
D_SPLITTING_MEV = 293.081246
# Withheld absolute comparison values (section 2): read only after both
# predicted masses have been fixed, inside `withheld_mass_comparisons`.
M_N_OBS_MEV = 938.918754
M_DELTA_OBS_MEV = 1232.0
R_ISO_OBS_FM = 0.769
ANALYTIC_RADIUS_RATIO_REGISTERED = 0.5010991027235701
MU_REF = 0.5266577616452649
EPSILON = 1.0e-5
L_CANONICAL = 64.0
L_REPEAT = (48.0, 96.0)
MU_LO = 0.1
MU_HI = 2.5
N_SCAN = 33
BVP_TOL = 1.0e-8
BVP_MAX_NODES = 100_000
BVP_INITIAL_NODES = 801

# --- Frozen thresholds (preregistration sections 3 and 5) --------------------
TOL_SIZE_RESIDUAL_FM = 1.0e-10
TOL_RMS_RESIDUAL = 3.0e-8
TOL_DEGREE = 2.0e-8
TOL_F_AT_L = 2.0e-10
TOL_VIRIAL_RELATIVE = 2.0e-7
TOL_RECON_RELATIVE = 2.0e-10
TOL_REFERENCE_RELATIVE = 8.0e-5
TOL_DOMAIN_RELATIVE = 3.0e-4
TOL_AGREEMENT_RELATIVE = 8.0e-5
TOL_ANALYTIC_RATIO_ABSOLUTE = 1.0e-12
TOL_NPZ_MATCH_RELATIVE = 1.0e-12
MASS_PERCENT_THRESHOLD = 0.10

# --- Frozen verdict strings (preregistration sections 2 and 7) ---------------
EMDASH = "\u2014"
VERDICT_RADIUS_CONTRADICTS = (
    f"CONTRADICTS{EMDASH}step-95 radius misses the empirical isoscalar radius by 50.1099 percent"
)
VERDICT_SIZE_FIRST_REJECT = (
    f"REJECT{EMDASH}step-95 isoscalar-radius assignment fails the analytic discriminator"
)
VERDICT_MATTER_INCONCLUSIVE = (
    f"INCONCLUSIVE{EMDASH}conditional normalization does not select or form physical matter"
)
VERDICT_ROOT_SUPPORTS = f"SUPPORTS{EMDASH}unique size-normalization root on the frozen scan"
VERDICT_NUCLEON_SUPPORTS = (
    f"SUPPORTS{EMDASH}conditional size-implied nucleon mass agrees within 10 percent"
)
VERDICT_NUCLEON_CONTRADICTS = (
    f"CONTRADICTS{EMDASH}conditional size-implied nucleon mass misses 10 percent"
)
VERDICT_DELTA_SUPPORTS = (
    f"SUPPORTS{EMDASH}conditional size-implied Delta mass agrees within 10 percent"
)
VERDICT_DELTA_CONTRADICTS = (
    f"CONTRADICTS{EMDASH}conditional size-implied Delta mass misses 10 percent"
)
VERDICT_NON_IDENTIFIABLE = (
    f"INCONCLUSIVE{EMDASH}size normalization is non-identifiable on the frozen scan"
)
VERDICT_NO_UNIQUE_MASS = f"INCONCLUSIVE{EMDASH}no unique size-implied mass"
VERDICT_ROOT_SOLVER_FAILED = (
    f"INCONCLUSIVE{EMDASH}root solver failed its frozen numerical condition"
)
VERDICT_PLAIN_INCONCLUSIVE = "INCONCLUSIVE"

BRANCH_ROOT = "root"
BRANCH_NON_IDENTIFIABLE = "non_identifiable"
BRANCH_ROOT_SOLVER_FAILURE = "root_solver_failure"
BRANCH_NUMERICAL_FAILURE = "numerical_failure"

PHI = (1.0 + math.sqrt(5.0)) / 2.0
ELL_95_M = ELL_PL_M * PHI**ELL_95_STEP
ELL_95_FM = ELL_95_M * 1.0e15


class ContractError(RuntimeError):
    """Typed failure of a frozen evidence contract."""


class MissingPreregistration(ContractError):
    """The frozen preregistration file itself is absent (control condition)."""


# ---------------------------------------------------------------------------
# Identity, hashing, and serialization helpers
# ---------------------------------------------------------------------------

def canonical_bytes(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def canonical_text_sha256(path: Path) -> str:
    return hashlib.sha256(canonical_bytes(path.read_bytes())).hexdigest()


def raw_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relpath(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, np.ndarray):
        return json_ready(value.tolist())
    if isinstance(value, (np.floating, np.integer, np.bool_)):
        return json_ready(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        raise ContractError("attempted to serialize a nonfinite float")
    return value


def compact(value: Any) -> Any:
    """Drop null-valued keys so scan rows and optional blocks never emit null."""
    if isinstance(value, dict):
        return {key: compact(item) for key, item in value.items() if item is not None}
    if isinstance(value, list):
        return [compact(item) for item in value if item is not None]
    return value


def write_json_exclusive(path: Path, payload: dict[str, Any]) -> None:
    text = json.dumps(json_ready(payload), indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(text)


def prepare_output(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise ContractError(f"output directory is not empty: {path}")
    path.mkdir(parents=True, exist_ok=True)


def source_identity(path: Path, required: bool) -> dict[str, Any]:
    if path.is_file():
        return {
            "path": relpath(path),
            "canonical_text_sha256": canonical_text_sha256(path),
            "status": "present",
        }
    if required:
        raise MissingPreregistration(f"missing required source: {relpath(path)}")
    # The independent verifier source is hashed best-effort so this program is
    # robust while the sibling source may exist only by central execution
    # time; a pending entry is an explicit non-hash, never a fabricated
    # identity.
    return {"path": relpath(path), "canonical_text_sha256": None, "status": "pending-not-present"}


def validate_sources(prereg: Path) -> dict[str, Any]:
    return {
        "preregistration": source_identity(prereg, required=True),
        "primary_source": source_identity(Path(__file__).resolve(), required=True),
        "verifier_source": source_identity(VERIFY_SOURCE, required=False),
    }


def artifact_by_name(path: Path) -> dict[str, Any]:
    return {"path": path.name, "sha256": raw_sha256(path), "bytes": path.stat().st_size}


def frozen_constants_block() -> dict[str, Any]:
    return {
        "phi": PHI,
        "ell_pl_m": ELL_PL_M,
        "ell95_step": ELL_95_STEP,
        "ell95_m": ELL_95_M,
        "ell95_fm": ELL_95_FM,
        "ell95_provenance": "external scale-selection input (Mapped step-95); not a prediction",
        "hbarc_mev_fm": HBARC_MEV_FM,
        "m_pi_mev": M_PI_MEV,
        "d_mev": D_SPLITTING_MEV,
        "d_provenance": "registered_literal; never computed from absolute masses",
        "m_n_obs_mev": M_N_OBS_MEV,
        "m_delta_obs_mev": M_DELTA_OBS_MEV,
        "withheld_provenance": "withheld_comparison values; applied only after predictions were fixed",
        "r_iso_obs_fm": R_ISO_OBS_FM,
        "analytic_radius_ratio_registered": ANALYTIC_RADIUS_RATIO_REGISTERED,
        "mu_ref": MU_REF,
        "epsilon": EPSILON,
        "L_canonical": L_CANONICAL,
        "repeat_L": list(L_REPEAT),
        "mu_lo": MU_LO,
        "mu_hi": MU_HI,
        "n_scan": int(N_SCAN),
        "bvp_tol": BVP_TOL,
        "bvp_max_nodes": int(BVP_MAX_NODES),
        "bvp_initial_nodes": int(BVP_INITIAL_NODES),
        "analytic_ratio_tol": TOL_ANALYTIC_RATIO_ABSOLUTE,
        "size_residual_tol_fm": TOL_SIZE_RESIDUAL_FM,
        "rms_tol": TOL_RMS_RESIDUAL,
        "degree_tol": TOL_DEGREE,
        "boundary_value_tol": TOL_F_AT_L,
        "virial_tol": TOL_VIRIAL_RELATIVE,
        "reconstruction_tol": TOL_RECON_RELATIVE,
        "reference_tol": TOL_REFERENCE_RELATIVE,
        "domain_tol": TOL_DOMAIN_RELATIVE,
        "agreement_tol": TOL_AGREEMENT_RELATIVE,
        "npz_match_tol": TOL_NPZ_MATCH_RELATIVE,
        "mass_percent_threshold": MASS_PERCENT_THRESHOLD,
    }


def safe_relpath(path: Path) -> str:
    """Repository-relative display path that never raises on foreign roots."""
    try:
        return relpath(path)
    except ValueError:
        return str(path)


def minimal_failure_payload(prereg: Path, failure_type: str, message: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "control": True,
        "numerical_pass": False,
        "complete_physical_matter_formation": False,
        "failure": {"type": failure_type, "detail": message},
        "requested_preregistration": safe_relpath(prereg),
        "verdicts": {
            "cascade_size_root": VERDICT_PLAIN_INCONCLUSIVE,
            "absolute_nucleon_mass": VERDICT_PLAIN_INCONCLUSIVE,
            "absolute_delta_mass": VERDICT_PLAIN_INCONCLUSIVE,
            "cascade_radius_assignment": VERDICT_PLAIN_INCONCLUSIVE,
            "size_first_normalization": VERDICT_PLAIN_INCONCLUSIVE,
            "matter_formation": VERDICT_PLAIN_INCONCLUSIVE,
        },
    }


def failure_receipt(output: Path, prereg: Path, failure_type: str, message: str) -> None:
    """Typed failure-only receipt; it cannot express a scientific pass.

    The caller guarantees the output directory was prepared by this run
    (`output_prepared`), so receipt writing never touches a user-owned
    non-empty directory. If this run already wrote its completed results.json,
    the completed receipt is kept and never overwritten.
    """
    output.mkdir(parents=True, exist_ok=True)
    target = output / "results.json"
    if target.exists():
        return
    payload = minimal_failure_payload(prereg, failure_type, message)
    # Best-effort constants and sources block; the receipt stays typed even
    # when the preregistration itself is the missing artifact.
    try:
        payload["constants"] = frozen_constants_block()
        if prereg.is_file():
            payload["sources"] = validate_sources(prereg)
        write_json_exclusive(target, payload)
    except Exception:
        try:
            write_json_exclusive(target, minimal_failure_payload(prereg, failure_type, message))
        except Exception:
            # A directory that cannot accept an exclusive write is outside the
            # contract; the exit status and stderr report remain.
            pass


def extract_frozen_protocol(prereg: Path) -> bytes:
    """Exact canonical-LF text between the H1 and the `## References` heading.

    Preregistration section 6 freezes the protocol file as the text *between*
    the H1 and References headings with LF line endings: both heading lines
    are excluded, interior blank lines are preserved verbatim, trailing blank
    lines before the References heading are dropped, and the file ends with
    exactly one trailing newline.
    """
    text = canonical_bytes(prereg.read_bytes()).decode("utf-8")
    lines = text.split("\n")
    h1_index = None
    references_index = None
    for index, line in enumerate(lines):
        if h1_index is None:
            if line.startswith("# ") and not line.startswith("## "):
                h1_index = index
            continue
        if line.strip() == "## References":
            references_index = index
            break
    if h1_index is None or references_index is None:
        raise ContractError("preregistration lacks the H1 or '## References' heading for protocol extraction")
    body = lines[h1_index + 1 : references_index]
    while body and body[-1] == "":
        body.pop()
    if not body:
        raise ContractError("preregistration has no text between the H1 and References headings")
    return ("\n".join(body) + "\n").encode("utf-8")


def make_gate(name: str, passed: bool, applicable: bool = True, detail: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"name": name, "applicable": bool(applicable), "passed": bool(passed), "detail": compact(detail or {})}


# ---------------------------------------------------------------------------
# Boundary-value problem in theta = pi - F (preregistration section 3)
# ---------------------------------------------------------------------------

def theta_acceleration(x: np.ndarray, theta: np.ndarray, thetap: np.ndarray, mu: float) -> np.ndarray:
    s = np.sin(theta)
    denominator = x * x + 2.0 * s * s
    numerator = (
        -2.0 * x * thetap
        - np.sin(2.0 * theta) * (thetap * thetap - 1.0 - s * s / (x * x))
        - mu * mu * x * x * s
    )
    return numerator / denominator


def solve_profile(mu: float, L: float) -> dict[str, Any]:
    """Solve the frozen massive BVP in theta on a geometric mesh.

    Reports diagnostics instead of raising so a single unqualified profile
    becomes a failed gate rather than an invented verdict.
    """
    x0 = np.geomspace(EPSILON, L, BVP_INITIAL_NODES)
    trial_r = 1.0 / math.sqrt(2.0)
    theta0 = 2.0 * np.arctan(x0 / trial_r)
    theta0[-1] = math.pi
    thetap0 = 2.0 * trial_r / (x0 * x0 + trial_r * trial_r)

    def fun(x: np.ndarray, y: np.ndarray) -> np.ndarray:
        return np.vstack((y[1], theta_acceleration(x, y[0], y[1], mu)))

    def bc(left: np.ndarray, right: np.ndarray) -> np.ndarray:
        # theta(eps) - eps*theta'(eps) = 0  <=>  F(eps) - eps*F'(eps) = pi
        # theta(L) - pi = 0                 <=>  F(L) = 0
        return np.array([left[0] - EPSILON * left[1], right[0] - math.pi])

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", IntegrationWarning)
            sol = solve_bvp(
                fun,
                bc,
                x0,
                np.vstack((theta0, thetap0)),
                tol=BVP_TOL,
                max_nodes=BVP_MAX_NODES,
                verbose=0,
            )
    except Exception as exc:
        return {
            "converged": False,
            "status": -1,
            "message": f"{type(exc).__name__}: {exc}",
            "n_nodes": 0,
            "max_rms_residual": None,
        }
    x = np.asarray(sol.x, dtype=np.float64)
    theta = np.asarray(sol.y[0], dtype=np.float64)
    thetap = np.asarray(sol.y[1], dtype=np.float64)
    status = int(sol.status)
    message = str(sol.message)
    n_nodes = int(x.size)
    try:
        rms = np.asarray(sol.rms_residuals, dtype=np.float64)
        max_rms = float(np.max(rms)) if rms.size else None
    except Exception:
        max_rms = None
    arrays_finite = bool(
        n_nodes >= 2
        and np.all(np.isfinite(x))
        and np.all(np.isfinite(theta))
        and np.all(np.isfinite(thetap))
        and max_rms is not None
        and math.isfinite(max_rms)
    )
    if status != 0 or not arrays_finite:
        return {"converged": False, "status": status, "message": message, "n_nodes": n_nodes, "max_rms_residual": max_rms}
    return {
        "converged": True,
        "status": status,
        "message": message,
        "n_nodes": n_nodes,
        "max_rms_residual": max_rms,
        "x": x,
        "F": math.pi - theta,
        "F_x": -thetap,
    }


def _safe_ratio(numerator: float, r: float, power: int) -> float:
    if r == 0.0:
        return 0.0
    return numerator / (r**power)


def profile_integrals(spline: CubicHermiteSpline, F: np.ndarray, F_x: np.ndarray, mu: float, L: float) -> dict[str, Any]:
    """Frozen section 3 integrals plus degree and the G_A integral.

    The regular-origin segment [0, epsilon] is evaluated analytically to
    leading order, F(r) = pi + F_x(epsilon) r, and every remaining integral is
    adaptive quadrature over the collocation spline with breakpoints at each
    interior collocation node.
    """
    origin_slope = float(F_x[0])

    densities: dict[str, Callable[[float, float, float], float]] = {
        "e2": lambda r, fv, pv: r * r * pv * pv + 2.0 * math.sin(fv) ** 2,
        "e4": lambda r, fv, pv: 2.0 * math.sin(fv) ** 2 * pv * pv + _safe_ratio(math.sin(fv) ** 4, r, 2),
        "em": lambda r, fv, pv: mu * mu * r * r * (1.0 - math.cos(fv)),
        "degree": lambda r, fv, pv: -(2.0 / math.pi) * math.sin(fv) ** 2 * pv,
        "lambda": lambda r, fv, pv: 8.0
        * r
        * r
        * math.sin(fv) ** 2
        * (1.0 + pv * pv + _safe_ratio(math.sin(fv) ** 2, r, 2)),
        "r0sq": lambda r, fv, pv: -(2.0 / math.pi) * r * r * math.sin(fv) ** 2 * pv,
        "rm_den": lambda r, fv, pv: r * r * math.sin(fv) ** 2 * pv,
        "rm_num": lambda r, fv, pv: r**4 * math.sin(fv) ** 2 * pv,
        "ga": lambda r, fv, pv: 4.0
        * r
        * r
        * (
            pv
            + _safe_ratio(math.sin(2.0 * fv), r, 1)
            + _safe_ratio(math.sin(2.0 * fv) * pv * pv, r, 1)
            + _safe_ratio(2.0 * math.sin(fv) ** 2 * pv, r, 2)
            + _safe_ratio(math.sin(fv) ** 2 * math.sin(2.0 * fv), r, 3)
        ),
    }
    raw: dict[str, float] = {}
    errors: dict[str, float] = {}
    for name, density in densities.items():

        def origin(r: float, _density: Callable[[float, float, float], float] = density) -> float:
            return _density(r, math.pi + origin_slope * r, origin_slope)

        def interior(r: float, _density: Callable[[float, float, float], float] = density) -> float:
            return _density(r, float(spline(r)), float(spline(r, 1)))

        knots = np.asarray(spline.x[1:-1], dtype=np.float64)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", IntegrationWarning)
                value0, error0 = quad(origin, 0.0, EPSILON, epsabs=2.0e-10, epsrel=2.0e-10, limit=200)
                value1, error1 = quad(
                    interior,
                    EPSILON,
                    L,
                    epsabs=2.0e-10,
                    epsrel=2.0e-10,
                    points=knots,
                    limit=max(1200, int(spline.x.size) + 100),
                )
        except Exception:
            return {"integration_failed": True}
        raw[name] = float(value0 + value1)
        errors[name] = float(error0 + error1)

    e2 = 4.0 * math.pi * raw["e2"]
    e4 = 4.0 * math.pi * raw["e4"]
    em = 8.0 * math.pi * raw["em"]
    rm_den = raw["rm_den"]
    if rm_den == 0.0:
        return {"integration_failed": True}
    total = e2 + e4 + em
    if total == 0.0:
        return {"integration_failed": True}
    fx_L = float(F_x[-1])
    boundary_term = 4.0 * math.pi * L**3 * fx_L * fx_L
    return {
        "integration_failed": False,
        "E2": e2,
        "E4": e4,
        "Em": em,
        "s": total / 4.0,
        "Lambda": raw["lambda"],
        "R0_sq": raw["r0sq"],
        "RM0_sq": raw["rm_num"] / rm_den,
        "degree": raw["degree"],
        "G_A_int": raw["ga"],
        "virial_relative": abs(e2 - e4 + 3.0 * em + boundary_term) / total,
        "origin_slope": origin_slope,
        "Fx_at_L": fx_L,
        "F_at_L": float(F[-1]),
        "quadrature_error_sum": float(sum(errors.values())),
    }


ROW_SOLVE_KEYS = ("converged", "status", "message", "n_nodes", "max_rms_residual")
ROW_SCALAR_KEYS = (
    "E2", "E4", "Em", "s", "Lambda", "R0_sq", "RM0_sq", "degree", "G_A_int",
    "F_at_L", "Fx_at_L", "virial_relative", "origin_slope", "quadrature_error_sum", "g_fm",
)


def profile_record(mu: float, L: float) -> dict[str, Any]:
    """One frozen scan/reference profile: solve, integrate, qualify items 1-5."""
    solved = solve_profile(mu, L)
    row: dict[str, Any] = {"mu": float(mu), "L": float(L), "qualified": False}
    for key in ROW_SOLVE_KEYS:
        row[key] = solved[key]
    for key in ROW_SCALAR_KEYS:
        row[key] = None
    row["finite"] = False
    if not solved["converged"]:
        return row
    spline = CubicHermiteSpline(solved["x"], solved["F"], solved["F_x"])
    integrals = profile_integrals(spline, solved["F"], solved["F_x"], float(mu), L)
    if integrals.get("integration_failed"):
        return row
    for key in ROW_SCALAR_KEYS:
        if key != "g_fm" and integrals.get(key) is not None:
            row[key] = float(integrals[key])
    finite = bool(all(math.isfinite(float(row[key])) for key in ROW_SCALAR_KEYS if key != "g_fm" and row[key] is not None))
    r0_sq = row["R0_sq"]
    if finite and r0_sq is not None and r0_sq > 0.0:
        # G(mu) = hbar*c*mu/M_pi * sqrt(R0^2) - ell_95, in fm (section 3 box).
        row["g_fm"] = HBARC_MEV_FM * float(mu) / M_PI_MEV * math.sqrt(r0_sq) - ELL_95_FM
        finite = bool(finite and math.isfinite(row["g_fm"]))
    row["finite"] = finite
    max_rms = row["max_rms_residual"]
    row["qualified"] = bool(
        finite
        and row["status"] == 0
        and max_rms is not None
        and max_rms < TOL_RMS_RESIDUAL
        and row["degree"] is not None and abs(row["degree"] - 1.0) <= TOL_DEGREE
        and row["F_at_L"] is not None and abs(row["F_at_L"]) <= TOL_F_AT_L
        and row["virial_relative"] is not None and row["virial_relative"] <= TOL_VIRIAL_RELATIVE
    )
    # Private mesh entries feed the conditional NPZ; scan JSON rows are
    # projected onto public keys so the mesh never reaches results.json here.
    row["_x"] = solved["x"]
    row["_F"] = solved["F"]
    row["_F_x"] = solved["F_x"]
    return row


def scan_row_json(row: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "mu": row["mu"],
        "L": row["L"],
        "qualified": bool(row["qualified"]),
        "converged": bool(row["converged"]),
        "finite": bool(row["finite"]),
        "solver": {
            "status": int(row["status"]),
            "message": str(row["message"]),
            "n_nodes": int(row["n_nodes"]),
            "max_rms_residual": row["max_rms_residual"],
        },
    }
    for key in ROW_SCALAR_KEYS:
        payload[key] = row[key]
    return compact(payload)


# ---------------------------------------------------------------------------
# Logarithmic scan and bracketed Brent root (preregistration section 3)
# ---------------------------------------------------------------------------

class SizeScan:
    def __init__(self, L: float) -> None:
        self.L = float(L)
        self.cache: dict[float, dict[str, Any]] = {}
        self.grid = np.geomspace(MU_LO, MU_HI, N_SCAN)
        self.rows: list[dict[str, Any]] = []
        self.sign_change_pairs: list[dict[str, Any]] = []
        self.all_profiles_qualified = False
        self.grid_zero_count = 0

    def row(self, mu: float) -> dict[str, Any]:
        key = float(mu)
        cached = self.cache.get(key)
        if cached is None:
            cached = profile_record(key, self.L)
            self.cache[key] = cached
        return cached

    def g(self, mu: float) -> float:
        value = self.row(mu)["g_fm"]
        if value is None:
            raise ContractError(f"size residual unavailable at mu={float(mu)!r} on L={self.L!r}")
        return float(value)

    def run_scan(self) -> None:
        self.rows = [self.row(float(mu)) for mu in self.grid]
        self.all_profiles_qualified = all(row["qualified"] for row in self.rows)
        self.grid_zero_count = sum(1 for row in self.rows if row["g_fm"] == 0.0)
        if not self.all_profiles_qualified:
            # Pair counting is only defined for a well-resolved qualified scan;
            # an unqualified profile already makes the run a numerical failure.
            return
        for index in range(len(self.rows) - 1):
            left = self.rows[index]["g_fm"]
            right = self.rows[index + 1]["g_fm"]
            if left is None or right is None:
                continue
            if float(left) * float(right) < 0.0:
                self.sign_change_pairs.append(
                    {
                        "index": index,
                        "mu_left": float(self.grid[index]),
                        "mu_right": float(self.grid[index + 1]),
                    }
                )

    def solve_root(self) -> dict[str, Any]:
        if len(self.sign_change_pairs) != 1:
            return {
                "solved": False,
                "reason": f"{len(self.sign_change_pairs)} sign-changing adjacent pairs on the frozen scan",
            }
        pair = self.sign_change_pairs[0]
        a = float(pair["mu_left"])
        b = float(pair["mu_right"])
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", IntegrationWarning)
                xopt, info = brentq(
                    self.g, a, b, xtol=1.0e-13, rtol=4.0 * np.finfo(float).eps, maxiter=200, full_output=True
                )
        except Exception as exc:
            return {"solved": False, "bracket": [a, b], "reason": f"brentq raised {type(exc).__name__}: {exc}"}
        residual = float(self.g(xopt))
        return {
            "solved": bool(info.converged),
            "bracket": [a, b],
            "mu_root": float(xopt),
            "brent_converged": bool(info.converged),
            "brent_inside_bracket": bool(a <= xopt <= b),
            "n_brent_evaluations": int(info.function_calls),
            "iterations": int(info.iterations),
            "size_residual_fm": residual,
            "abs_size_residual_fm": abs(residual),
            "reason": None if info.converged else "brentq reported non-convergence",
        }


def root_gate_ok(root: dict[str, Any]) -> bool:
    """Section 3 qualification: Brent remains inside the pair within residual."""
    return bool(
        root.get("solved")
        and root.get("brent_converged")
        and root.get("brent_inside_bracket")
        and math.isfinite(root.get("abs_size_residual_fm", math.inf))
        and root["abs_size_residual_fm"] <= TOL_SIZE_RESIDUAL_FM
    )


# ---------------------------------------------------------------------------
# Coefficient extraction and predictions (preregistration section 4).
# Absolute baryon masses are never read here: only M_pi, the registered
# splitting d, and profile integrals enter.
# ---------------------------------------------------------------------------

def extract_coefficients(root_row: dict[str, Any], mu_root: float) -> dict[str, Any]:
    r0_sq = float(root_row["R0_sq"])
    rm0_sq = float(root_row["RM0_sq"])
    s = float(root_row["s"])
    lam = float(root_row["Lambda"])
    g_a_int = float(root_row["G_A_int"])
    lambda_B_fm = ELL_95_FM / math.sqrt(r0_sq)
    P = M_PI_MEV / float(mu_root)
    A = 9.0 * P * P / (2.0 * math.pi * lam * D_SPLITTING_MEV)
    e_B = math.sqrt(P / A)
    f_B = math.sqrt(P * A)
    I0 = math.pi * A / (3.0 * P * P)
    M_cl = 2.0 * s * A
    M_N_pred = M_cl + D_SPLITTING_MEV / 4.0
    M_Delta_pred = M_cl + 5.0 * D_SPLITTING_MEV / 4.0
    g_A = -math.pi * g_a_int / (3.0 * e_B * e_B)
    g_piNN = M_N_pred / f_B * g_A
    recon = {
        "eBfB_vs_P": abs(e_B * f_B - P) / abs(P),
        "fB_over_eB_vs_A": abs(f_B / e_B - A) / abs(A),
        "M_pi_vs_mu_P": abs(mu_root * P - M_PI_MEV) / M_PI_MEV,
        "splitting_vs_d": abs(9.0 * P * P / (2.0 * math.pi * A * lam) - D_SPLITTING_MEV) / D_SPLITTING_MEV,
    }
    scalars = (
        lambda_B_fm, P, A, e_B, f_B, I0, M_cl, M_N_pred, M_Delta_pred,
        lambda_B_fm * math.sqrt(r0_sq), lambda_B_fm * math.sqrt(rm0_sq), g_A, g_piNN,
    )
    return {
        "lambda_B_fm": lambda_B_fm,
        "P_mev": P,
        "P_from_lambda_B_mev": HBARC_MEV_FM / lambda_B_fm,
        "A": A,
        "e_B": e_B,
        "f_B": f_B,
        "I0": I0,
        "M_cl_MeV": M_cl,
        "M_N_pred_MeV": M_N_pred,
        "M_Delta_pred_MeV": M_Delta_pred,
        "r_I0_fm": lambda_B_fm * math.sqrt(r0_sq),
        "r_M_I0_fm": lambda_B_fm * math.sqrt(rm0_sq),
        "g_A": g_A,
        "g_piNN": g_piNN,
        "reconstruction_residuals": recon,
        "positive_scales": bool(
            r0_sq > 0.0 and rm0_sq > 0.0 and s > 0.0 and lam > 0.0
            and A > 0.0 and e_B > 0.0 and f_B > 0.0 and I0 > 0.0
        ),
        "recon_within_threshold": bool(all(value < TOL_RECON_RELATIVE for value in recon.values())),
        "coefficients_finite": bool(
            all(math.isfinite(float(value)) for value in scalars)
            and all(math.isfinite(float(value)) for value in recon.values())
        ),
    }


PREDICTION_KEYS = (
    "M_cl_MeV", "M_N_pred_MeV", "M_Delta_pred_MeV", "r_I0_fm", "r_M_I0_fm", "g_A", "g_piNN",
)


def predictions_from(coefficients: dict[str, Any]) -> dict[str, Any]:
    payload = {key: coefficients[key] for key in PREDICTION_KEYS}
    payload["lambda_B_fm"] = coefficients["lambda_B_fm"]
    payload["P_mev"] = coefficients["P_mev"]
    payload["A"] = coefficients["A"]
    payload["e_B"] = coefficients["e_B"]
    payload["f_B"] = coefficients["f_B"]
    payload["I0"] = coefficients["I0"]
    return payload


# ---------------------------------------------------------------------------
# Reference reconstruction (preregistration section 2, context only)
# ---------------------------------------------------------------------------

def reference_reconstruction() -> dict[str, Any]:
    """Rebuild the frozen mu_ref profile independently and compare with the receipt."""
    receipt: dict[str, Any] = {"path": relpath(REFERENCE_RECEIPT)}
    values: tuple[float, float, float] | None = None
    if REFERENCE_RECEIPT.is_file():
        try:
            receipt["sha256"] = raw_sha256(REFERENCE_RECEIPT)
            receipt["bytes"] = REFERENCE_RECEIPT.stat().st_size
            data = json.loads(REFERENCE_RECEIPT.read_text(encoding="utf-8"))
            values = (
                float(data["massive_static"]["s"]),
                float(data["massive_static"]["Lambda"]),
                float(data["massive_static"]["R0_squared"]),
            )
            receipt["s"] = values[0]
            receipt["Lambda"] = values[1]
            receipt["R0_squared"] = values[2]
        except Exception as exc:
            receipt["status"] = f"unreadable: {type(exc).__name__}: {exc}"
            values = None
    else:
        receipt["status"] = "missing"
    row = profile_record(MU_REF, L_CANONICAL)
    relative_differences = None
    item_10 = False
    if values is not None and row["qualified"]:
        relative_differences = {
            "s": abs(row["s"] - values[0]) / abs(values[0]),
            "Lambda": abs(row["Lambda"] - values[1]) / abs(values[1]),
            "R0_sq": abs(row["R0_sq"] - values[2]) / abs(values[2]),
        }
        item_10 = all(value <= TOL_REFERENCE_RELATIVE for value in relative_differences.values())
    return {
        "mu_ref": MU_REF,
        "L": L_CANONICAL,
        "row": row,
        "receipt": compact(receipt),
        "relative_differences": relative_differences,
        "qualified": bool(row["qualified"]),
        "item_10_within_threshold": bool(item_10),
    }


# ---------------------------------------------------------------------------
# Analytic precheck, withheld comparisons, and the frozen verdict tree
# ---------------------------------------------------------------------------

def analytic_radius_precheck() -> dict[str, Any]:
    """Reproduce the section 2 analytic ratio before any profile solve."""
    computed = ELL_95_FM / R_ISO_OBS_FM - 1.0
    difference = abs(computed - ANALYTIC_RADIUS_RATIO_REGISTERED)
    if difference > TOL_ANALYTIC_RATIO_ABSOLUTE:
        raise ContractError(
            "analytic radius precheck failed to reproduce the registered ratio: "
            f"computed {computed!r}, registered {ANALYTIC_RADIUS_RATIO_REGISTERED!r}, difference {difference!r}"
        )
    return {
        "relative_mismatch": computed,
        "registered_literal": ANALYTIC_RADIUS_RATIO_REGISTERED,
        "absolute_discrepancy": difference,
        "exceeds_ten_percent": bool(abs(computed) > MASS_PERCENT_THRESHOLD),
        "fixed_cascade_radius_assignment": VERDICT_RADIUS_CONTRADICTS,
        "fixed_size_first_normalization": VERDICT_SIZE_FIRST_REJECT,
    }


def withheld_mass_comparisons(predictions: dict[str, Any] | None, branch: str) -> dict[str, Any]:
    """Read the withheld absolute masses only here, after predictions are fixed."""
    if predictions is None:
        return {"applied": False, "reason": f"no size-implied predictions exist on the {branch} branch"}
    rel_n = abs(predictions["M_N_pred_MeV"] / M_N_OBS_MEV - 1.0)
    rel_d = abs(predictions["M_Delta_pred_MeV"] / M_DELTA_OBS_MEV - 1.0)
    return {
        "applied": True,
        "note": "withheld absolute comparison values applied only after M_N_pred and M_Delta_pred were fixed",
        "M_N_obs_mev": M_N_OBS_MEV,
        "M_Delta_obs_mev": M_DELTA_OBS_MEV,
        "abs_rel_dev_M_N": rel_n,
        "abs_rel_dev_M_Delta": rel_d,
        "threshold": MASS_PERCENT_THRESHOLD,
        "nucleon_within_10_percent": bool(rel_n <= MASS_PERCENT_THRESHOLD),
        "delta_within_10_percent": bool(rel_d <= MASS_PERCENT_THRESHOLD),
    }


def scientific_verdicts(branch: str, mass_comparisons: dict[str, Any]) -> dict[str, str]:
    if branch == BRANCH_ROOT:
        root = VERDICT_ROOT_SUPPORTS
        nucleon = VERDICT_NUCLEON_SUPPORTS if mass_comparisons["nucleon_within_10_percent"] else VERDICT_NUCLEON_CONTRADICTS
        delta = VERDICT_DELTA_SUPPORTS if mass_comparisons["delta_within_10_percent"] else VERDICT_DELTA_CONTRADICTS
    elif branch == BRANCH_NON_IDENTIFIABLE:
        root = VERDICT_NON_IDENTIFIABLE
        nucleon = VERDICT_NO_UNIQUE_MASS
        delta = VERDICT_NO_UNIQUE_MASS
    elif branch == BRANCH_ROOT_SOLVER_FAILURE:
        root = VERDICT_ROOT_SOLVER_FAILED
        nucleon = VERDICT_ROOT_SOLVER_FAILED
        delta = VERDICT_ROOT_SOLVER_FAILED
    else:
        root = VERDICT_PLAIN_INCONCLUSIVE
        nucleon = VERDICT_PLAIN_INCONCLUSIVE
        delta = VERDICT_PLAIN_INCONCLUSIVE
    return {
        "cascade_size_root": root,
        "absolute_nucleon_mass": nucleon,
        "absolute_delta_mass": delta,
        "cascade_radius_assignment": VERDICT_RADIUS_CONTRADICTS,
        "size_first_normalization": VERDICT_SIZE_FIRST_REJECT,
        "matter_formation": VERDICT_MATTER_INCONCLUSIVE,
    }


# ---------------------------------------------------------------------------
# Conditional root-profile NPZ with the fixed 30-scalar basis
# ---------------------------------------------------------------------------

NPZ_SCALAR_INDEX = {
    0: "mu_root",
    1: "s",
    2: "Lambda",
    3: "R0_sq",
    4: "RM0_sq",
    5: "P",
    6: "A",
    7: "e_B",
    8: "f_B",
    9: "I0",
    10: "M_cl",
    11: "M_N_pred",
    12: "M_Delta_pred",
    13: "r_I0_fm",
    14: "r_M_I0_fm",
    15: "G_A_int",
    16: "g_A",
    17: "g_piNN",
    18: "degree",
    19: "F_at_L",
    20: "virial_relative",
    21: "max_rms_residual",
    22: "solver_status",
    23: "L",
    24: "ell95_fm",
    25: "size_residual_fm",
    26: "mu_ref",
    27: "ref_s",
    28: "ref_Lambda",
    29: "ref_R0_sq",
}


def npz_scalars(
    root_row: dict[str, Any],
    coefficients: dict[str, Any],
    root_record: dict[str, Any],
    reference_row: dict[str, Any],
) -> np.ndarray:
    values = [
        float(root_record["mu_root"]),
        float(root_row["s"]),
        float(root_row["Lambda"]),
        float(root_row["R0_sq"]),
        float(root_row["RM0_sq"]),
        float(coefficients["P_mev"]),
        float(coefficients["A"]),
        float(coefficients["e_B"]),
        float(coefficients["f_B"]),
        float(coefficients["I0"]),
        float(coefficients["M_cl_MeV"]),
        float(coefficients["M_N_pred_MeV"]),
        float(coefficients["M_Delta_pred_MeV"]),
        float(coefficients["r_I0_fm"]),
        float(coefficients["r_M_I0_fm"]),
        float(root_row["G_A_int"]),
        float(coefficients["g_A"]),
        float(coefficients["g_piNN"]),
        float(root_row["degree"]),
        float(root_row["F_at_L"]),
        float(root_row["virial_relative"]),
        float(root_row["max_rms_residual"]),
        float(root_row["status"]),
        float(L_CANONICAL),
        float(ELL_95_FM),
        float(root_record["size_residual_fm"]),
        float(MU_REF),
        float(reference_row["s"]),
        float(reference_row["Lambda"]),
        float(reference_row["R0_sq"]),
    ]
    array = np.asarray(values, dtype=np.float64)
    if array.size != 30 or not bool(np.all(np.isfinite(array))):
        raise ContractError("root-profile scalar basis is not 30 finite float64 values")
    return array


def write_root_profile_npz(
    path: Path,
    root_row: dict[str, Any],
    coefficients: dict[str, Any],
    root_record: dict[str, Any],
    reference_row: dict[str, Any],
) -> dict[str, Any]:
    x = np.asarray(root_row["_x"], dtype=np.float64)
    F = np.asarray(root_row["_F"], dtype=np.float64)
    F_x = np.asarray(root_row["_F_x"], dtype=np.float64)
    scalars = npz_scalars(root_row, coefficients, root_record, reference_row)
    for name, array in (("x", x), ("F", F), ("F_x", F_x), ("scalars", scalars)):
        if array.dtype != np.float64 or not bool(np.all(np.isfinite(array))):
            raise ContractError(f"npz array {name} is not finite float64")
    if not (x.ndim == 1 and F.shape == x.shape and F_x.shape == x.shape):
        raise ContractError("npz profile arrays must be matching 1-D vectors")
    if x.size < 2 or not bool(np.all(np.diff(x) > 0.0)) or x[0] != EPSILON or x[-1] != L_CANONICAL:
        raise ContractError("npz mesh must be strictly increasing from epsilon to the canonical domain")
    # savez takes no allow_pickle parameter: an extra keyword would be stored
    # as an array member, so only the frozen four keys are passed.
    with path.open("xb") as stream:
        np.savez(stream, x=x, F=F, F_x=F_x, scalars=scalars)
    with np.load(path, allow_pickle=False) as reloaded:
        if set(reloaded.files) != {"x", "F", "F_x", "scalars"}:
            raise ContractError("npz key set drifted from the frozen basis")
        for name in ("x", "F", "F_x", "scalars"):
            array = np.asarray(reloaded[name])
            if array.dtype != np.float64 or not bool(np.all(np.isfinite(array))):
                raise ContractError(f"reloaded npz array {name} is not finite float64")
        if np.asarray(reloaded["scalars"]).shape != (30,):
            raise ContractError("reloaded npz scalar basis is not length 30")
    return {
        "dtypes": ["float64"],
        "scalar_count": 30,
        "x_monotone": True,
    }


# ---------------------------------------------------------------------------
# Domain drivers
# ---------------------------------------------------------------------------

def run_domain_scan(L: float) -> SizeScan:
    scan = SizeScan(L)
    scan.run_scan()
    return scan


def domain_json(
    scan: SizeScan,
    root: dict[str, Any] | None,
    coefficients: dict[str, Any] | None,
    root_qualified: bool,
) -> dict[str, Any]:
    root_json: dict[str, Any] | None = None
    if root is not None:
        root_json = {
            "mu": root.get("mu_root"),
            "bracket": root.get("bracket"),
            "brent_converged": root.get("brent_converged"),
            "brent_inside_bracket": root.get("brent_inside_bracket"),
            "n_brent_evaluations": root.get("n_brent_evaluations"),
            "size_residual_fm": root.get("size_residual_fm"),
            "abs_size_residual_fm": root.get("abs_size_residual_fm"),
            "root_qualified": bool(root_qualified),
            "reason": root.get("reason"),
        }
    observables = None
    payload_coefficients = None
    predictions = None
    reconstruction_residuals = None
    if root_qualified and coefficients is not None:
        root_row = scan.cache.get(float(root["mu_root"]))
        if root_row is not None:
            observables = scan_row_json(root_row)
        payload_coefficients = coefficients
        predictions = predictions_from(coefficients)
        reconstruction_residuals = coefficients["reconstruction_residuals"]
    return compact(
        {
            "L": scan.L,
            "scan_rows": [scan_row_json(row) for row in scan.rows],
            "all_profiles_qualified": bool(scan.all_profiles_qualified),
            "sign_change_pair_count": int(len(scan.sign_change_pairs)),
            "grid_zero_count": int(scan.grid_zero_count),
            "unique_candidate": bool(len(scan.sign_change_pairs) == 1),
            "root": root_json,
            "observables": observables,
            "coefficients": payload_coefficients,
            "predictions": predictions,
            "reconstruction_residuals": reconstruction_residuals,
        }
    )


def root_stage_qualified(scan: SizeScan, root: dict[str, Any]) -> tuple[dict[str, Any] | None, bool]:
    """Extract coefficients for a gate-qualified root; report finiteness honestly."""
    if not root_gate_ok(root):
        return None, False
    row = scan.row(float(root["mu_root"]))
    if not row["qualified"]:
        return None, False
    try:
        coefficients = extract_coefficients(row, float(root["mu_root"]))
    except Exception:
        return None, False
    qualified = bool(
        coefficients["positive_scales"]
        and coefficients["recon_within_threshold"]
        and coefficients["coefficients_finite"]
    )
    return coefficients, qualified


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="fresh output directory")
    parser.add_argument("--prereg", type=Path, default=DEFAULT_PREREG, help="frozen preregistration file")
    args = parser.parse_args()
    prereg = args.prereg.resolve()
    output = args.output.resolve()

    output_prepared = False
    try:
        prepare_output(output)
        output_prepared = True
        identities = validate_sources(prereg)
        protocol_path = output / "frozen_protocol.txt"
        protocol_bytes = extract_frozen_protocol(prereg)
        with protocol_path.open("xb") as stream:
            stream.write(protocol_bytes)

        # The analytic radius precheck must reproduce before any profile solve
        # (preregistration section 7); a mismatch is a typed contract failure.
        analytic = analytic_radius_precheck()

        canonical_scan = run_domain_scan(L_CANONICAL)
        reference = reference_reconstruction()

        canonical_qualified = bool(canonical_scan.all_profiles_qualified)
        reference_qualified = bool(reference["qualified"])
        reference_item_10 = bool(reference["item_10_within_threshold"])
        scan_stage_ok = bool(canonical_qualified and reference_qualified and reference_item_10)
        pair_count = len(canonical_scan.sign_change_pairs) if canonical_qualified else -1

        root: dict[str, Any] | None = None
        bracket_passed = False
        canonical_coefficients: dict[str, Any] | None = None
        canonical_root_qualified = False
        root_present = False
        npz_artifact: dict[str, Any] | None = None
        npz_manifest: dict[str, Any] | None = None
        repeat_domains: list[dict[str, Any]] = []
        repeat_qualified: dict[float, bool] = {}
        consistency: dict[str, Any] = {}
        all_repeat_roots_present = True

        if scan_stage_ok and pair_count == 1:
            root = canonical_scan.solve_root()
            bracket_passed = root_gate_ok(root)
            if bracket_passed:
                canonical_coefficients, canonical_root_qualified = root_stage_qualified(canonical_scan, root)
                # Coherence rule: identifiability.root_present is exactly the
                # NPZ-artifact condition — one canonical Brent/residual-
                # qualifying root whose frozen scalar basis is representable
                # in finite float64, even if a later positivity,
                # reconstruction, or domain gate then fails. The NPZ finiteness
                # clause of section 6 wins only when the basis is not
                # representable at all.
                if canonical_coefficients is not None and canonical_coefficients["coefficients_finite"]:
                    root_row = canonical_scan.row(float(root["mu_root"]))
                    npz_path = output / "root_profile.npz"
                    npz_manifest = write_root_profile_npz(
                        npz_path, root_row, canonical_coefficients, root, reference["row"]
                    )
                    npz_artifact = dict(artifact_by_name(npz_path))
                    npz_artifact["n_nodes"] = int(npz_manifest.pop("n_nodes", root_row["n_nodes"]))
                    npz_artifact["manifest"] = {
                        "dtypes": npz_manifest["dtypes"],
                        "scalar_count": npz_manifest["scalar_count"],
                        "x_monotone": npz_manifest["x_monotone"],
                    }
                    root_present = True
                # Independent domain repetition (section 5) runs only after the
                # canonical scan yields one qualifying root.
                for L_repeat in L_REPEAT:
                    scan_repeat = run_domain_scan(L_repeat)
                    root_repeat = scan_repeat.solve_root() if scan_repeat.all_profiles_qualified and len(scan_repeat.sign_change_pairs) == 1 else {
                        "solved": False,
                        "reason": (
                            "repeat scan profiles not all qualified"
                            if not scan_repeat.all_profiles_qualified
                            else f"{len(scan_repeat.sign_change_pairs)} sign-changing adjacent pairs"
                        ),
                    }
                    coefficients_repeat, qualified_repeat = (
                        root_stage_qualified(scan_repeat, root_repeat) if root_gate_ok(root_repeat) else (None, False)
                    )
                    repeat_qualified[L_repeat] = qualified_repeat
                    if not qualified_repeat:
                        all_repeat_roots_present = False
                    repeat_domains.append(domain_json(scan_repeat, root_repeat, coefficients_repeat, qualified_repeat))

        # Domain repetition consistency (section 5 item 9) once all roots exist.
        repetition_applicable = bool(
            bracket_passed
            and all_repeat_roots_present
            and len(repeat_qualified) == len(L_REPEAT)
        )
        repetition_passed = False
        if repetition_applicable and canonical_coefficients is not None and root is not None:
            comparisons = {}
            for scan_repeat_payload in repeat_domains:
                tag = f"L{int(scan_repeat_payload['L'])}"
                mu_other = scan_repeat_payload.get("root", {}).get("mu")
                coefficient_block = scan_repeat_payload.get("coefficients")
                if mu_other is None or coefficient_block is None:
                    comparisons[f"mu_{tag}"] = None
                    comparisons[f"MN_{tag}"] = None
                    continue
                comparisons[f"mu_{tag}"] = abs(float(mu_other) - float(root["mu_root"])) / abs(float(root["mu_root"]))
                comparisons[f"MN_{tag}"] = (
                    abs(float(coefficient_block["M_N_pred_MeV"]) - float(canonical_coefficients["M_N_pred_MeV"]))
                    / abs(float(canonical_coefficients["M_N_pred_MeV"]))
                )
            consistency = {"relative_differences": comparisons, "threshold": TOL_DOMAIN_RELATIVE}
            repetition_passed = bool(
                comparisons
                and all(value is not None and value <= TOL_DOMAIN_RELATIVE for value in comparisons.values())
            )

        # Branch determination follows the frozen section 7 tree exactly; the
        # root branch requires every applicable numerical gate to pass so the
        # verdict tree stays coherent with numerical_pass.
        if not scan_stage_ok:
            branch = BRANCH_NUMERICAL_FAILURE
        elif pair_count != 1:
            branch = BRANCH_NON_IDENTIFIABLE
        elif root is None or not root_gate_ok(root):
            branch = BRANCH_ROOT_SOLVER_FAILURE
        elif (
            canonical_root_qualified
            and len(repeat_qualified) == len(L_REPEAT)
            and all(repeat_qualified.values())
            and repetition_applicable
            and repetition_passed
        ):
            branch = BRANCH_ROOT
        else:
            branch = BRANCH_NUMERICAL_FAILURE

        if branch == BRANCH_ROOT:
            predictions = predictions_from(canonical_coefficients)
            predictions["descriptive_only"] = (
                "magnetic radius, g_A, and g_piNN carry no decision weight (section 4)"
            )
        else:
            predictions = None
        # Withheld absolute comparisons are read only here, after any
        # prediction has been fixed (section 2).
        mass_comparisons = withheld_mass_comparisons(predictions, branch)
        verdicts = scientific_verdicts(branch, mass_comparisons)

        per_domain_scan_detail = {
            "canonical_L64": {
                "n_profiles": len(canonical_scan.rows),
                "n_qualified": sum(1 for row in canonical_scan.rows if row["qualified"]),
                "all_qualified": canonical_qualified,
            }
        }
        for scan_repeat_payload in repeat_domains:
            tag = f"L{int(scan_repeat_payload['L'])}"
            per_domain_scan_detail[tag] = {
                "n_profiles": len(scan_repeat_payload["scan_rows"]),
                "n_qualified": sum(1 for row in scan_repeat_payload["scan_rows"] if row["qualified"]),
                "all_qualified": scan_repeat_payload["all_profiles_qualified"],
            }

        gates = [
            make_gate("analytic_radius_precheck", True, detail=analytic),
            make_gate(
                "output_contract",
                True,
                detail={"exclusive_writes": True, "directory": relpath(output)},
            ),
            make_gate(
                "scan_profiles_items_1_to_5",
                scan_stage_ok,
                detail=per_domain_scan_detail,
            ),
            make_gate(
                "reference_reconstruction_items",
                reference_qualified and reference_item_10,
                detail={
                    "items_1_to_5": reference_qualified,
                    "item_10_within_threshold": reference_item_10,
                    "relative_differences": reference["relative_differences"],
                    "receipt": reference["receipt"],
                },
            ),
            make_gate(
                "unique_sign_change_scan",
                True,
                applicable=scan_stage_ok,
                detail={
                    "canonical_pair_count": pair_count,
                    "canonical_grid_zero_count": canonical_scan.grid_zero_count,
                    "repeat_pair_counts": {
                        f"L{int(item['L'])}": item["sign_change_pair_count"] for item in repeat_domains
                    },
                },
            ),
            make_gate(
                "root_bracket_and_residual",
                bool(bracket_passed),
                applicable=bool(scan_stage_ok and pair_count == 1),
                detail=compact(
                    {
                        "canonical_root": root,
                        "threshold_fm": TOL_SIZE_RESIDUAL_FM,
                        "npz_written": root_present,
                    }
                ),
            ),
            make_gate(
                "root_items_6_to_7",
                bool(canonical_root_qualified and repeat_qualified and all(repeat_qualified.values())),
                applicable=bool(bracket_passed),
                detail={
                    "canonical": canonical_root_qualified,
                    "repeats": {f"L{int(key)}": value for key, value in repeat_qualified.items()},
                },
            ),
            make_gate(
                "domain_repetition_item_9",
                repetition_passed,
                applicable=repetition_applicable,
                detail=compact(consistency),
            ),
        ]

        names = [item["name"] for item in gates]
        if len(set(names)) != len(names):
            raise ContractError("duplicate gate names in the primary receipt")

        evidence = make_gate(
            "evidence_contract",
            True,
            detail={
                "files_written": sorted(path.name for path in output.iterdir()),
                "protocol_raw_hash_matches": raw_sha256(protocol_path) == hashlib.sha256(protocol_bytes).hexdigest(),
                "root_profile_present": npz_artifact is not None,
                "root_profile_manifest": npz_manifest,
                "npz_scalar_index": {str(index): name for index, name in NPZ_SCALAR_INDEX.items()},
                "gate_names_unique": True,
            },
        )
        gates.append(evidence)

        numerical_pass = bool(all(item["passed"] for item in gates if item["applicable"]))

        canonical_domain_row = domain_json(canonical_scan, root, canonical_coefficients, canonical_root_qualified)
        domains_payload = [*repeat_domains, canonical_domain_row]
        domains_payload.sort(key=lambda item: float(item["L"]))

        payload: dict[str, Any] = {
            "schema": SCHEMA,
            "control": False,
            "complete_physical_matter_formation": False,
            "numerical_pass": numerical_pass,
            "identities": identities,
            "constants": frozen_constants_block(),
            "analytic_radius": analytic,
            "identifiability": {
                "canonical_L": L_CANONICAL,
                "all_scans_qualified": bool(canonical_qualified and reference_qualified and reference_item_10),
                "canonical_sign_change_pair_count": pair_count,
                "canonical_grid_zero_count": int(canonical_scan.grid_zero_count),
                "canonical_branch": branch,
                "root_present": root_present,
            },
            "protocol_artifact": artifact_by_name(protocol_path),
            "canonical_domain": int(L_CANONICAL),
            "domains": domains_payload,
            "reference": compact({
                "mu_ref": reference["mu_ref"],
                "L": reference["L"],
                "qualified": reference_qualified,
                "solver": scan_row_json(reference["row"])["solver"],
                "observables": scan_row_json(reference["row"]),
                "receipt": reference["receipt"],
                "relative_differences": reference["relative_differences"],
                "item_10_within_threshold": reference_item_10,
            }),
            "withheld_mass_comparisons": mass_comparisons,
            "gates": gates,
            "verdicts": verdicts,
            "artifacts": {
                "frozen_protocol.txt": artifact_by_name(protocol_path),
                "root_profile.npz": npz_artifact,
            },
            "environment": {
                "python": sys.version.split()[0],
                "platform": platform.platform(),
                "numpy": np.__version__,
                "scipy": scipy.__version__,
            },
            "limitations": [
                "step-95 radius assignment is an external Mapped scale-selection input contradicted analytically before execution",
                "size-normalization root is numerical uniqueness on a 33-point scan, not a continuum theorem",
                "leading massive chiral benchmark only; no colour, QCD, quantum vacuum, or renormalization derivation",
                "descriptive out-of-fit radii, g_A, and g_piNN carry no decision weight",
                "no degree-zero formation or physical-matter completion result",
            ],
        }
        if branch == BRANCH_ROOT and canonical_coefficients is not None:
            payload["coefficient_extraction"] = canonical_coefficients
            payload["predictions"] = predictions

        write_json_exclusive(output / "results.json", payload)
        print(
            json.dumps(
                json_ready({"branch": branch, "numerical_pass": numerical_pass, "verdicts": verdicts}),
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0
    except Exception as exc:
        failure_type = "MissingPreregistration" if isinstance(exc, MissingPreregistration) else type(exc).__name__
        if output_prepared:
            try:
                failure_receipt(output, prereg, failure_type, str(exc))
            except Exception:
                pass
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        if not isinstance(exc, ContractError):
            traceback.print_exc()
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
