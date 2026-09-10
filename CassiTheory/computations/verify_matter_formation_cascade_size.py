#!/usr/bin/env python3
"""Independent verifier for the frozen conditional cascade-size normalization test.

Protocol: ``computations/matter-formation-cascade-size-numerical-recovery-prereg.md``
(§§2-7), which re-freezes only the numerical representation of
``computations/matter-formation-cascade-size-prereg.md`` after the retained
direct-F collocation floor documented in its §1. Every physical input,
equation, scan point, threshold, comparison, gate, and verdict is unchanged.

This program never imports or executes the primary
``computations/matter_formation_cascade_size.py``.  It reconstructs the entire
calculation from its own numerics:

* it evolves the recovery collocation state ``theta = pi - F`` for the massive
  chiral profile with the regular-origin boundary conditions ``theta(eps) -
  eps*theta_x(eps) = 0`` and ``theta(L) = pi``, using SciPy ``solve_bvp`` on
  separately constructed mixed linear/geometric meshes, tolerance ``3e-9``, at
  most ``150000`` nodes; it evaluates the algebraically exact transformed
  equation directly in ``theta_rhs`` and reconstructs ``F = pi - theta`` and
  ``F_x = -theta_x`` before evaluating any observable;
* every integral is evaluated by fixed 24-point Gauss-Legendre quadrature on
  every refined mesh panel over ``[eps, L]`` (regular-origin integrands vanish
  as ``O(x)`` or better, so the excluded ``[0, eps]`` segment is far below every
  frozen tolerance);
* it performs its own 33-point logarithmic scan of the frozen interval
  ``0.1 <= mu <= 2.5`` on the canonical domain ``L = 64``, its own bracketed
  Brent root, its own reference-point reconstruction at ``mu_ref``, and - only
  when the canonical scan has exactly one qualifying root - repeats the scan
  and root at ``L = 48`` and ``L = 96``, all before any primary scalar is read;
* only then does it open the primary receipt and re-derive every reported
  quantity (virial with the frozen ``+4*pi*L^3*F'(L)^2`` boundary term, ``s``,
  ``G``, sign-change counts, item-9 domain consistency, item-10 reference
  comparison, NPZ scalar basis, source identities, raw artifact hashes) before
  the 8e-5 relative comparison.

The §2 analytic radius discriminator (+50.1099 percent, reproduced from frozen
constants before any profile solve) fixes ``cascade_radius_assignment`` =
CONTRADICTS and ``size_first_normalization`` = REJECT under every execution
outcome; the combined normalization can therefore never support, and the BVP
result is only the bounded descriptive mass implication of the contradicted
assignment.  A scan with zero or multiple sign-changing pairs (or an extra
exact grid zero) is a valid negative identifiability result: no root is
selected, no size-implied mass is calculated, no root-profile NPZ is written,
and execution stops at the canonical scan.  Exactly one sign-changing pair
whose Brent bracket, in-bracket condition, or final 1e-10 fm size residual
fails is a numerical failure carrying the root-solver-failure verdict trio.

The measured nucleon-Delta splitting ``d = 293.081246 MeV`` is registered here
as a literal; it is never computed from the withheld absolute masses
``M_N^obs`` and ``M_Delta^obs``, which enter only the descriptive 10-percent
mass verdicts after the predictions are fixed.

Usage:
    python computations/verify_matter_formation_cascade_size.py \
        --input  runs/20260909_matter_formation_cascade_size_recovery3 \
        --output runs/20260909_matter_formation_cascade_size_verification_recovery3 \
        [--prereg computations/matter-formation-cascade-size-numerical-recovery-prereg.md]

Completed runs (including ``numerical_pass=false``) write
``verification.json`` and ``frozen_protocol.txt``, plus
``independent_root_profile.npz`` when and only when the frozen scan has one
qualifying root, and exit 0.  Typed failure controls (missing preregistration,
missing primary receipt files, protocol-literal drift, analytic precheck
mismatch, non-serializable payload, unexpected error) retain only a typed
failure ``verification.json`` and exit 2.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import sys
import traceback
from pathlib import Path
from typing import Any

import numpy as np
from numpy.polynomial.legendre import leggauss
from scipy.integrate import solve_bvp
from scipy.optimize import brentq

ROOT = Path(__file__).resolve().parents[1]

SCHEMA = "cassi.matter-formation.cascade-size.verification.v1"
PRIMARY_SCHEMA = "cassi.matter-formation.cascade-size.v1"

DEFAULT_PREREG = ROOT / "computations" / \
    "matter-formation-cascade-size-numerical-recovery-prereg.md"
PREREG_REL = "computations/matter-formation-cascade-size-numerical-recovery-prereg.md"
PRIMARY_SOURCE_REL = "computations/matter_formation_cascade_size.py"
OWN_SOURCE_REL = "computations/verify_matter_formation_cascade_size.py"
REFERENCE_RECEIPT_REL = "runs/20260907_matter_formation_chiral_lattice/structure_recovery1/results.json"
REFERENCE_RECEIPT = ROOT / REFERENCE_RECEIPT_REL

# ---------------------------------------------------------------------------
# §2 frozen inputs
# ---------------------------------------------------------------------------
PHI = (1.0 + math.sqrt(5.0)) / 2.0
ELL_PL_M = 1.616255e-35
ELL95_STEP = 95
ELL95_FM = ELL_PL_M * PHI ** ELL95_STEP * 1.0e15
HBARC_MEV_FM = 197.3269804
M_PI_MEV = 138.039
D_MEV = 293.081246  # registered spectroscopy literal; sole collective-rotation input
M_N_OBS_MEV = 938.918754  # withheld absolute comparison value
M_DELTA_OBS_MEV = 1232.0  # withheld absolute comparison value
R_ISO_OBS_FM = 0.769
ANALYTIC_RADIUS_RATIO_REGISTERED = 0.5010991027235701
ANALYTIC_RATIO_TOL = 1.0e-12
MASS_SUPPORT_THRESHOLD = 0.10
MU_REF = 0.5266577616452649
EPS = 1.0e-5
MU_LO = 0.1
MU_HI = 2.5
N_SCAN = 33
L_CANONICAL = 64.0
L_REPEAT_DOMAINS = (48.0, 96.0)

# ---------------------------------------------------------------------------
# §3/§5 frozen tolerances and the independent method's solver contract
# ---------------------------------------------------------------------------
TOL_SIZE_RESIDUAL_FM = 1.0e-10
TOL_RMS = 3.0e-8
TOL_DEGREE = 2.0e-8
TOL_F_L = 2.0e-10
TOL_VIRIAL = 2.0e-7
TOL_RECON = 2.0e-10
TOL_AGREE = 8.0e-5
TOL_DOMAIN = 3.0e-4
BVP_TOL = 3.0e-9
BVP_MAX_NODES = 150000
GL_ORDER = 24
GEO_END = 1.0  # geometric segment eps..GEO_END, linear segment GEO_END..L
GEO_RATIO = 1.015
LIN_STEP = 0.05
RECHECK_ABS = 1.0e-9
RECHECK_REL = 1.0e-9

SCAN_GRID = np.geomspace(MU_LO, MU_HI, N_SCAN)

# ---------------------------------------------------------------------------
# §7 frozen verdict strings (the em-dash is part of the protocol text)
# ---------------------------------------------------------------------------
V_INCONCLUSIVE = "INCONCLUSIVE"
V_RADIUS = "CONTRADICTS—step-95 radius misses the empirical isoscalar radius by 50.1099 percent"
V_NORMALIZATION = "REJECT—step-95 isoscalar-radius assignment fails the analytic discriminator"
V_MATTER = "INCONCLUSIVE—conditional normalization does not select or form physical matter"
V_ROOT_SUPPORTS = "SUPPORTS—unique size-normalization root on the frozen scan"
V_ROOT_NONIDENT = "INCONCLUSIVE—size normalization is non-identifiable on the frozen scan"
V_ROOT_SOLVER_FAIL = "INCONCLUSIVE—root solver failed its frozen numerical condition"
V_MASS_NO_MASS = "INCONCLUSIVE—no unique size-implied mass"
V_MN_SUPPORTS = "SUPPORTS—conditional size-implied nucleon mass agrees within 10 percent"
V_MN_CONTRADICTS = "CONTRADICTS—conditional size-implied nucleon mass misses 10 percent"
V_MD_SUPPORTS = "SUPPORTS—conditional size-implied Delta mass agrees within 10 percent"
V_MD_CONTRADICTS = "CONTRADICTS—conditional size-implied Delta mass misses 10 percent"

VERDICT_KEYS = (
    "cascade_size_root",
    "absolute_nucleon_mass",
    "absolute_delta_mass",
    "cascade_radius_assignment",
    "size_first_normalization",
    "matter_formation",
)

# Frozen literals this source embeds; their presence in the preregistration
# text guards against a stale or drifted protocol (a changed constant must
# fail, not silently rerun under old numbers).
PREREG_FROZEN_MARKERS = (
    "## Status: Hypothesized cascade assignment / Mapped empirical inputs—September 2026",
    "0.5010991027235701",
    V_RADIUS,
    V_NORMALIZATION,
    V_ROOT_NONIDENT,
    V_ROOT_SOLVER_FAIL,
    V_MASS_NO_MASS,
    V_ROOT_SUPPORTS,
    V_MN_SUPPORTS,
    V_MN_CONTRADICTS,
    V_MD_SUPPORTS,
    V_MD_CONTRADICTS,
    V_MATTER,
    "d=293.081246",
    "1.616255",
    "197.3269804",
    "M_\\pi=138.039",
    "938.918754",
    "M_\\Delta^{\\rm obs}=1232.0",
    "0.769",
    "\\mu_{\\rm ref}=0.5266577616452649",
    "33 logarithmically spaced points",
    "0.1\\le\\mu\\le2.5",
    "10^{-10}\\ \\mathrm{fm}",
    "3\\times10^{-9}",
    "150,000",
    "24-point Gauss–Legendre",
    "\\mathcal E_2-\\mathcal E_4+3\\mathcal E_m+4\\pi L^3F_x(L)^2",
    "2\\times10^{-7}",
    "2\\times10^{-8}",
    "2\\times10^{-10}",
    "8\\times10^{-5}",
    "3\\times10^{-4}",
    "runs/20260909_matter_formation_cascade_size",
    "runs/20260909_matter_formation_cascade_size_verification",
    "complete_physical_matter_formation",
    PRIMARY_SOURCE_REL,
    OWN_SOURCE_REL,
)

# §5/§6/§7 canonical gate names shared with the primary receipt (required set,
# not exclusive: this verifier additionally carries evidence_* and
# independent_agreement_* gates of its own).
CANONICAL_GATES = (
    "analytic_radius_precheck",
    "output_contract",
    "scan_profiles_items_1_to_5",
    "reference_reconstruction_items",
    "unique_sign_change_scan",
    "root_bracket_and_residual",
    "root_items_6_to_7",
    "domain_repetition_item_9",
    "evidence_contract",
)

# Quantities compared between the two independent methods (item 8).
COMPARISON_QUANTITIES = (
    ("mu", "root", "mu"),
    ("s", "observables", "s"),
    ("Lambda", "observables", "Lambda"),
    ("R0_sq", "observables", "R0_sq"),
    ("RM0_sq", "observables", "RM0_sq"),
    ("P", "coefficients", "P_mev"),
    ("A", "coefficients", "A"),
    ("e_B", "coefficients", "e_B"),
    ("f_B", "coefficients", "f_B"),
    ("M_N_pred", "predictions", "M_N_pred_MeV"),
    ("M_Delta_pred", "predictions", "M_Delta_pred_MeV"),
)

# Root-profile NPZ scalar basis: fixed 30-entry float64 order shared with the
# primary receipt contract.
SCALAR_BASIS = (
    "mu_root", "s", "Lambda", "R0_sq", "RM0_sq", "P_mev", "A", "e_B", "f_B", "I0",
    "M_cl", "M_N_pred", "M_Delta_pred", "r_I0_fm", "r_M_I0_fm", "G_A_int", "g_A",
    "g_piNN", "degree", "F_at_L", "virial_relative", "max_rms_residual",
    "solver_status", "L_canonical", "ell95_fm", "size_residual_fm", "mu_ref",
    "ref_s", "ref_Lambda", "ref_R0_sq",
)
SCALAR_COUNT = len(SCALAR_BASIS)


class TypedFailure(Exception):
    """Failure that must yield a typed failure-only receipt and nonzero exit."""

    def __init__(self, kind: str, detail: str) -> None:
        super().__init__(f"{kind}: {detail}")
        self.kind = kind
        self.detail = detail


# ---------------------------------------------------------------------------
# Byte / JSON / number helpers
# ---------------------------------------------------------------------------

def canonical_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def root_rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def is_num(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def finite_num(value: Any) -> bool:
    return is_num(value) and math.isfinite(float(value))


def num_eq(a: Any, b: Any, rel: float = 1.0e-12, abs_floor: float = 1.0e-15) -> bool:
    if not finite_num(a) or not finite_num(b):
        return False
    aa, bb = float(a), float(b)
    return abs(aa - bb) <= max(abs_floor, rel * max(abs(aa), abs(bb)))


def rel_diff(a: float, b: float) -> float:
    denom = max(abs(a), abs(b))
    return 0.0 if denom == 0.0 else abs(a - b) / denom


def strict_json(raw: bytes, label: str) -> Any:
    """Parse JSON rejecting duplicate keys and NaN/Infinity constants."""

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in items:
            if key in out:
                raise ValueError(f"duplicate key {key!r} in {label}")
            out[key] = value
        return out

    def constant(token: str) -> Any:
        raise ValueError(f"forbidden JSON constant {token!r} in {label}")

    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)


def iter_nonfinite(obj: Any, trail: str = "$") -> list[str]:
    """Paths whose float payload is NaN or +/-Infinity."""
    bad: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            bad.extend(iter_nonfinite(value, f"{trail}.{key}"))
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            bad.extend(iter_nonfinite(value, f"{trail}[{index}]"))
    elif isinstance(obj, float) and not isinstance(obj, bool):
        if not math.isfinite(obj):
            bad.append(trail)
    return bad


def write_bytes_exclusive(path: Path, data: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(data)


def write_json_exclusive(path: Path, payload: Any) -> int:
    text = json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    data = text.encode("utf-8")
    write_bytes_exclusive(path, data)
    return len(data)


def protocol_slice(canonical_text: str) -> str:
    """Frozen protocol: lines after the H1 title and before ``## References``
    (both headings excluded), trailing blank lines trimmed, LF endings, and
    exactly one terminal LF."""
    lines = canonical_text.split("\n")
    h1 = None
    references = None
    for index, line in enumerate(lines):
        if h1 is None and line.startswith("# "):
            h1 = index
        if line.strip() == "## References":
            references = index
            break
    if h1 is None or references is None or references <= h1:
        raise TypedFailure(
            "PreregistrationStructureMismatch",
            "preregistration lacks an H1 title before the '## References' heading",
        )
    body = lines[h1 + 1:references]
    while body and not body[-1].strip():
        body.pop()
    return "\n".join(body) + "\n"


def file_identity(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": root_rel(path), "sha256": sha256_hex(raw), "bytes": len(raw)}


# ---------------------------------------------------------------------------
# Independent numerics: recovered theta=pi-F BVP state over the exact direct-F
# RHS identity, mixed mesh, fixed 24-point GL panels
# ---------------------------------------------------------------------------

GL_NODES, GL_WEIGHTS = leggauss(GL_ORDER)


def initial_mesh(L: float) -> np.ndarray:
    """Mixed mesh: geometric from EPS to GEO_END, then linear GEO_END..L."""
    geo = [EPS]
    x = EPS
    while x < GEO_END:
        x = min(x * GEO_RATIO, GEO_END)
        geo.append(x)
    if geo[-1] < GEO_END:
        geo.append(GEO_END)
    n_linear = max(int(math.ceil((L - GEO_END) / LIN_STEP)), 1)
    lin = GEO_END + (L - GEO_END) * np.arange(1, n_linear + 1, dtype=float) / n_linear
    return np.unique(np.concatenate((np.asarray(geo, dtype=float), lin)))


HALF_PI = 0.5 * math.pi


def stable_sin_pair(F: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """sin(F) and sin(2F) via a branch-cut-free identity for F >= pi/2.

    Direct-F profiles sit at F ~= pi near the origin, where the plain sine
    is evaluated through the binary64 representation of pi (itself off by
    ~1.2e-16) and the resulting absolute error is then divided by x^2 on
    the geometric mesh down to EPS = 1e-5. For F >= pi/2 the subtraction
    pi - F is exact in binary64 (Sterbenz), and the algebraic identities
    sin(F) = sin(pi - F), sin(2F) = -sin(2(pi - F)) move both evaluations
    onto a small exactly represented argument. Masked subsets are the only
    ones ever passed to libm, so the near-pi call is removed outright, not
    merely discarded. This is an algebraic identity only: F itself, the
    ODE, the equation of state, and every frozen parameter are unchanged.
    """
    sinF = np.empty_like(F)
    sin2F = np.empty_like(F)
    low = F < HALF_PI
    high = ~low
    sinF[low] = np.sin(F[low])
    sin2F[low] = np.sin(2.0 * F[low])
    theta = math.pi - F[high]
    sinF[high] = np.sin(theta)
    sin2F[high] = -np.sin(2.0 * theta)
    return sinF, sin2F


def theta_rhs(x: np.ndarray, theta: np.ndarray, theta_x: np.ndarray,
              mu: float) -> np.ndarray:
    """Algebraically exact transformed second derivative for theta = pi - F.

    With a = sin(theta)/x and b = sin(2 theta)/x, the field equation gives

        theta_xx = [2(b/2-theta_x) - b(theta_x-a)(theta_x+a)
                    - mu^2 x sin(theta)] / [x(1+2a^2)].

    Evaluating theta itself removes the lossy binary64 round trip
    theta -> pi-theta -> pi-F at the regular origin. ``np.sinc`` evaluates
    the removable sin(theta)/theta factors without dividing two small
    independently rounded numbers. This is an algebraic representation of
    the frozen equation only; no physical input or boundary datum changes.
    """
    u = theta / x
    a = u * np.sinc(theta / math.pi)
    b = 2.0 * u * np.sinc(2.0 * theta / math.pi)
    numerator = (
        2.0 * (0.5 * b - theta_x)
        - b * (theta_x - a) * (theta_x + a)
        - mu * mu * x * np.sin(theta)
    )
    return numerator / (x * (1.0 + 2.0 * a * a))


def solve_profile(mu: float, L: float) -> tuple[Any, dict[str, Any]]:
    mesh = initial_mesh(L)
    # Recovery §4: the collocation state is theta = pi - F. The seed is the
    # regular standard hedgehog in theta form, theta(x) = 2*atan(x/a) with
    # fixed a = 1/sqrt(2), independent of mu; no primary output or profile is
    # used as a guess. The mixed mesh, tolerance, and node budget remain the
    # independently frozen verifier contract. theta_rhs evaluates the exact
    # transformed field equation without reconstructing F inside the
    # collocation residual. The BCs below are the frozen F-boundary data under
    # F = pi - theta.
    hedgehog_a = 1.0 / math.sqrt(2.0)
    y_guess = np.vstack((
        2.0 * np.arctan(mesh / hedgehog_a),
        2.0 * hedgehog_a / (mesh * mesh + hedgehog_a * hedgehog_a),
    ))

    def fun(x: np.ndarray, y: np.ndarray) -> np.ndarray:
        return np.vstack((y[1], theta_rhs(x, y[0], y[1], mu)))

    def bc(ya: np.ndarray, yb: np.ndarray) -> np.ndarray:
        return np.array([ya[0] - EPS * ya[1], yb[0] - math.pi])

    diag: dict[str, Any] = {"status": -1, "message": "", "n_nodes": int(len(mesh)),
                            "max_rms_residual": None}
    try:
        sol = solve_bvp(fun, bc, mesh, y_guess, tol=BVP_TOL, max_nodes=BVP_MAX_NODES)
    except Exception as exc:  # a solver blow-up is an unqualified profile, not a crash
        diag["message"] = f"solve_bvp raised {type(exc).__name__}: {exc}"[:200]
        return None, diag
    diag["status"] = int(sol.status)
    diag["message"] = str(sol.message)[:200]
    diag["n_nodes"] = int(len(sol.x))
    try:
        rms = float(np.max(sol.rms_residuals)) if len(sol.rms_residuals) else float("nan")
    except Exception:
        rms = float("nan")
    diag["max_rms_residual"] = rms if math.isfinite(rms) else None
    return sol, diag


def panel_integrals(sol: Any, mu: float, L: float) -> dict[str, float]:
    """Fixed 24-point Gauss-Legendre quadrature over every refined mesh panel.

    The solver state is the recovery variable theta = pi - F; ``F`` and
    ``F_x`` are reconstructed from theta before any integrand is formed.
    """
    mesh = np.asarray(sol.x, dtype=float)
    if mesh.size < 2:
        raise ValueError("refined mesh has fewer than two nodes")
    a = mesh[:-1]
    b = mesh[1:]
    half = 0.5 * (b - a)
    mid = 0.5 * (a + b)
    keys = ("i_x2Fx2", "i_2s2", "i_2s2Fx2", "i_s4x2", "i_m2x2v", "i_Lam",
            "i_R0", "i_RMnum", "i_deg", "i_GA")
    acc = {key: 0.0 for key in keys}
    block = 4096
    n_panel = a.size
    for start in range(0, n_panel, block):
        sl = slice(start, min(start + block, n_panel))
        xv = (mid[sl][:, None] + half[sl][:, None] * GL_NODES[None, :]).ravel()
        wv = (half[sl][:, None] * GL_WEIGHTS[None, :]).ravel()
        Fs = math.pi - np.asarray(sol.sol(xv)[0], dtype=float)
        Fxs = -np.asarray(sol.sol(xv, 1)[0], dtype=float)
        sinF, sin2F = stable_sin_pair(Fs)
        cosF = np.cos(Fs)
        s2 = sinF * sinF
        x2 = xv * xv
        acc["i_x2Fx2"] += float(wv @ (x2 * Fxs * Fxs))
        acc["i_2s2"] += float(wv @ (2.0 * s2))
        acc["i_2s2Fx2"] += float(wv @ (2.0 * s2 * Fxs * Fxs))
        acc["i_s4x2"] += float(wv @ (s2 * s2 / x2))
        acc["i_m2x2v"] += float(wv @ (x2 * (1.0 - cosF)))
        acc["i_Lam"] += float(wv @ (x2 * s2 * (1.0 + Fxs * Fxs + s2 / x2)))
        acc["i_R0"] += float(wv @ (x2 * s2 * Fxs))
        acc["i_RMnum"] += float(wv @ (x2 * x2 * s2 * Fxs))
        acc["i_deg"] += float(wv @ (s2 * Fxs))
        acc["i_GA"] += float(wv @ (x2 * (Fxs + sin2F / xv + (sin2F / xv) * Fxs * Fxs
                                        + 2.0 * s2 / x2 * Fxs + s2 * sin2F / (x2 * xv))))
    E2 = 4.0 * math.pi * (acc["i_x2Fx2"] + acc["i_2s2"])
    E4 = 4.0 * math.pi * (acc["i_2s2Fx2"] + acc["i_s4x2"])
    Em = 8.0 * math.pi * mu * mu * acc["i_m2x2v"]
    F_L = math.pi - float(sol.sol(L)[0])
    Fx_L = -float(sol.sol(L, 1)[0])
    total = E2 + E4 + Em
    boundary = 4.0 * math.pi * L ** 3 * Fx_L * Fx_L
    out = {
        "E2": E2,
        "E4": E4,
        "Em": Em,
        "s": total / 4.0,
        "Lambda": 8.0 * acc["i_Lam"],
        "R0_sq": -(2.0 / math.pi) * acc["i_R0"],
        "RM0_sq": (acc["i_RMnum"] / acc["i_R0"]) if acc["i_R0"] != 0.0 else math.inf,
        "degree": -(2.0 / math.pi) * acc["i_deg"],
        "F_at_L": F_L,
        "Fx_at_L": Fx_L,
        "G_A_int": 4.0 * acc["i_GA"],
        "virial_relative": abs(E2 - E4 + 3.0 * Em + boundary) / abs(total)
        if total != 0.0
        else math.inf,
    }
    return out


def g_size_mu(mu: float, R0_sq: Any) -> float:
    """G(mu) = hbar c mu sqrt(R0^2)/M_pi - ell_95 in fm (§3 boxed equation)."""
    if not finite_num(R0_sq) or float(R0_sq) <= 0.0:
        return math.nan
    return HBARC_MEV_FM * mu * math.sqrt(float(R0_sq)) / M_PI_MEV - ELL95_FM


OBS_KEYS = ("E2", "E4", "Em", "s", "Lambda", "R0_sq", "RM0_sq", "degree",
            "F_at_L", "Fx_at_L", "virial_relative", "G_A_int")


def profile_item_reasons(diag: dict[str, Any], obs: dict[str, float]) -> list[str]:
    """§5 items 1-5 for a solved profile (finiteness, BVP, degree, F(L), virial)."""
    reasons: list[str] = []
    for key in OBS_KEYS:
        if not math.isfinite(obs.get(key, math.nan)):
            reasons.append(f"item1:nonfinite:{key}")
    if diag["status"] != 0:
        reasons.append(f"item2:status:{diag['status']}")
    rms = diag["max_rms_residual"]
    if not (finite_num(rms) and float(rms) < TOL_RMS):
        reasons.append("item2:rms")
    if math.isfinite(obs.get("degree", math.nan)) and abs(obs["degree"] - 1.0) > TOL_DEGREE:
        reasons.append("item3:degree")
    if math.isfinite(obs.get("F_at_L", math.nan)) and abs(obs["F_at_L"]) > TOL_F_L:
        reasons.append("item4:F_L")
    if not (finite_num(obs.get("virial_relative"))
            and float(obs["virial_relative"]) <= TOL_VIRIAL):
        reasons.append("item5:virial")
    return reasons


def make_row(mu: float, L: float) -> dict[str, Any]:
    sol, diag = solve_profile(mu, L)
    row: dict[str, Any] = {
        "mu": float(mu),
        "solver": {
            "status": int(diag["status"]),
            "message": str(diag["message"]),
            "n_nodes": int(diag["n_nodes"]),
        },
    }
    if diag["max_rms_residual"] is not None:
        row["solver"]["max_rms_residual"] = float(diag["max_rms_residual"])
    obs: dict[str, float] = {}
    if sol is not None:
        try:
            obs = panel_integrals(sol, mu, L)
        except Exception as exc:
            row["quadrature_error"] = f"{type(exc).__name__}: {exc}"[:200]
    reasons = profile_item_reasons(diag, obs) if obs else ["solver_unavailable"]
    row["finite"] = bool(obs) and all(math.isfinite(float(v)) for v in obs.values())
    row["converged"] = diag["status"] == 0 and finite_num(diag["max_rms_residual"]) \
        and float(diag["max_rms_residual"]) < TOL_RMS
    row["qualified"] = len(reasons) == 0
    for key in OBS_KEYS:
        value = obs.get(key)
        if value is not None and math.isfinite(value):
            row[key] = float(value)
    g = g_size_mu(mu, obs.get("R0_sq"))
    if row["qualified"] and math.isfinite(g):
        row["g_fm"] = float(g)
    if reasons:
        row["reasons"] = reasons
    return row


def scan_domain(L: float) -> dict[str, Any]:
    rows = [make_row(float(mu), float(L)) for mu in SCAN_GRID]
    all_qualified = all(row["qualified"] for row in rows)
    pair_count = -1
    grid_zero_count = -1
    bracket: list[float] = []
    if all_qualified:
        gvals = [row["g_fm"] for row in rows]
        pair_count = sum(1 for i in range(N_SCAN - 1) if gvals[i] * gvals[i + 1] < 0.0)
        grid_zero_count = sum(1 for value in gvals if value == 0.0)
        if pair_count == 1 and grid_zero_count == 0:
            for i in range(N_SCAN - 1):
                if gvals[i] * gvals[i + 1] < 0.0:
                    bracket = [float(SCAN_GRID[i]), float(SCAN_GRID[i + 1])]
                    break
    return {
        "L": float(L),
        "scan_rows": rows,
        "all_profiles_qualified": bool(all_qualified),
        "sign_change_pair_count": int(pair_count),
        "grid_zero_count": int(grid_zero_count),
        "unique_candidate": bool(all_qualified and pair_count == 1 and grid_zero_count == 0),
        "bracket": bracket,
    }


def coefficient_block(mu_root: float, obs: dict[str, float]) -> dict[str, Any] | None:
    """§4 size-first coefficient extraction and predictions from own numbers."""
    if any(not math.isfinite(obs.get(key, math.nan)) for key in
           ("R0_sq", "RM0_sq", "s", "Lambda", "G_A_int")):
        return None
    if obs["R0_sq"] <= 0.0 or obs["Lambda"] <= 0.0:
        return None
    lambda_B = ELL95_FM / math.sqrt(obs["R0_sq"])
    P = HBARC_MEV_FM / lambda_B
    if lambda_B <= 0.0 or P <= 0.0:
        return None
    A = 9.0 * P * P / (2.0 * math.pi * obs["Lambda"] * D_MEV)
    if A <= 0.0:
        return None
    e_B = math.sqrt(P / A)
    f_B = math.sqrt(P * A)
    I0 = math.pi * A / (3.0 * P * P)
    M_cl = 2.0 * obs["s"] * A
    M_N = M_cl + D_MEV / 4.0
    M_Delta = M_cl + 5.0 * D_MEV / 4.0
    r_M = lambda_B * math.sqrt(obs["RM0_sq"]) if obs["RM0_sq"] > 0.0 else math.nan
    g_A = -math.pi * obs["G_A_int"] / (3.0 * e_B * e_B)
    g_piNN = M_N / f_B * g_A
    coefficients = {"lambda_B_fm": lambda_B, "P_mev": P, "A": A, "e_B": e_B,
                    "f_B": f_B, "I0": I0}
    predictions = {"M_cl_MeV": M_cl, "M_N_pred_MeV": M_N, "M_Delta_pred_MeV": M_Delta,
                   "r_I0_fm": lambda_B * math.sqrt(obs["R0_sq"]), "r_M_I0_fm": r_M,
                   "g_A": g_A, "g_piNN": g_piNN}
    for block in (coefficients, predictions):
        for key, value in block.items():
            if key == "r_M_I0_fm":
                continue  # positivity of RM0_sq is item-6 territory, finiteness gated there
            if not math.isfinite(value):
                return None
    if not math.isfinite(r_M):
        return None
    recon = {
        "eBfB_vs_P": abs(e_B * f_B - P) / P,
        "fB_over_eB_vs_A": abs(f_B / e_B - A) / A,
        "M_pi_vs_mu_P": abs(M_PI_MEV - mu_root * P) / M_PI_MEV,
        "splitting_vs_d": abs(9.0 * P * P / (2.0 * math.pi * A * obs["Lambda"]) - D_MEV) / D_MEV,
    }
    positivity = {
        "R0_sq": obs["R0_sq"] > 0.0, "RM0_sq": obs["RM0_sq"] > 0.0,
        "s": obs["s"] > 0.0, "Lambda": obs["Lambda"] > 0.0,
        "A": A > 0.0, "e_B": e_B > 0.0, "f_B": f_B > 0.0, "I0": I0 > 0.0,
    }
    return {"coefficients": coefficients, "predictions": predictions,
            "reconstruction_residuals": recon, "positivity": positivity}


def root_solve(L: float, bracket: list[float]) -> dict[str, Any]:
    """Own Brent root of G on the unique scan pair; §3 qualification tracked."""
    a, b = bracket
    evaluated: list[float] = []

    def gfun(mu: float) -> float:
        evaluated.append(float(mu))
        sol, _diag = solve_profile(mu, L)
        if sol is None:
            raise RuntimeError(f"bracketed profile solve unavailable at mu={mu!r}")
        obs = panel_integrals(sol, mu, L)
        g = g_size_mu(mu, obs.get("R0_sq"))
        if not math.isfinite(g):
            raise RuntimeError(f"non-finite G at mu={mu!r}")
        return g

    attempt: dict[str, Any] = {"brent_converged": False, "brent_inside_bracket": False,
                               "n_brent_evaluations": 0, "mu": None,
                               "size_residual_fm": None, "solver": None,
                               "observables": None, "profile_items_1_to_5": False,
                               "profile_reasons": [], "mesh": None,
                               "failure_reason": "not_started"}
    try:
        mu_root, rres = brentq(gfun, a, b, xtol=1.0e-12,
                               rtol=4.0 * float(np.finfo(float).eps),
                               maxiter=100, full_output=True)
        attempt["brent_converged"] = bool(rres.converged)
    except Exception as exc:
        attempt["failure_reason"] = f"brent_exception:{type(exc).__name__}"
        attempt["n_brent_evaluations"] = len(evaluated)
        return attempt
    attempt["n_brent_evaluations"] = len(evaluated)
    edge = 1.0e-13
    inside = all(a - edge <= m <= b + edge for m in evaluated) \
        and (a - edge <= float(mu_root) <= b + edge)
    attempt["brent_inside_bracket"] = bool(inside)
    attempt["mu"] = float(mu_root)

    sol, diag = solve_profile(float(mu_root), L)
    attempt["solver"] = diag
    if sol is None:
        attempt["failure_reason"] = "final_root_solve_unavailable"
        return attempt
    obs = panel_integrals(sol, float(mu_root), L)
    attempt["observables"] = obs
    g_root = g_size_mu(float(mu_root), obs.get("R0_sq"))
    if math.isfinite(g_root):
        attempt["size_residual_fm"] = float(abs(g_root))
    reasons = profile_item_reasons(diag, obs)
    attempt["profile_items_1_to_5"] = len(reasons) == 0
    attempt["profile_reasons"] = reasons
    attempt["mesh"] = {
        "x": np.asarray(sol.x, dtype=np.float64).copy(),
        "F": math.pi - np.asarray(sol.y[0], dtype=np.float64),
        "F_x": -np.asarray(sol.y[1], dtype=np.float64),
    }
    residual_ok = (finite_num(attempt["size_residual_fm"])
                   and float(attempt["size_residual_fm"]) <= TOL_SIZE_RESIDUAL_FM)
    attempt["bracket_residual_ok"] = bool(attempt["brent_converged"]
                                          and attempt["brent_inside_bracket"] and residual_ok)
    attempt["root_qualified"] = bool(attempt["bracket_residual_ok"]
                                     and attempt["profile_items_1_to_5"])
    return attempt


def domain_row(L: float, scan: dict[str, Any], root: dict[str, Any] | None,
               coefficients: dict[str, Any] | None) -> dict[str, Any]:
    row: dict[str, Any] = {
        "L": float(L),
        "scan_rows": scan["scan_rows"],
        "all_profiles_qualified": scan["all_profiles_qualified"],
        "sign_change_pair_count": scan["sign_change_pair_count"],
        "grid_zero_count": scan["grid_zero_count"],
        "unique_candidate": scan["unique_candidate"],
    }
    if root is None:
        return row
    entry: dict[str, Any] = {
        "mu": float(root["mu"]) if finite_num(root["mu"]) else -1.0,
        "bracket": [float(v) for v in scan["bracket"]],
        "brent_converged": bool(root["brent_converged"]),
        "brent_inside_bracket": bool(root["brent_inside_bracket"]),
        "n_brent_evaluations": int(root["n_brent_evaluations"]),
        "root_qualified": bool(root.get("root_qualified", False)),
    }
    if finite_num(root.get("size_residual_fm")):
        entry["size_residual_fm"] = float(root["size_residual_fm"])
    row["root"] = entry
    diag = root.get("solver")
    obs = root.get("observables")
    obs_block: dict[str, Any] = {}
    if isinstance(obs, dict):
        obs_block = {key: float(obs[key]) for key in OBS_KEYS
                     if math.isfinite(obs.get(key, math.nan))}
    if isinstance(diag, dict):
        solver_block: dict[str, Any] = {"status": int(diag["status"]),
                                        "message": str(diag["message"]),
                                        "n_nodes": int(diag["n_nodes"])}
        if finite_num(diag.get("max_rms_residual")):
            solver_block["max_rms_residual"] = float(diag["max_rms_residual"])
        obs_block["solver"] = solver_block
    if obs_block:
        row["observables"] = obs_block
    if root.get("profile_reasons"):
        row["root_profile_reasons"] = list(root["profile_reasons"])[:8]
    if coefficients is not None:
        row["coefficients"] = coefficients["coefficients"]
        row["predictions"] = coefficients["predictions"]
        row["reconstruction_residuals"] = coefficients["reconstruction_residuals"]
        row["positivity"] = coefficients["positivity"]
    return row


# ---------------------------------------------------------------------------
# Reference reconstruction (§2/§5 item 10): own solve first, receipt second
# ---------------------------------------------------------------------------

def reference_reconstruction() -> dict[str, Any]:
    sol, diag = solve_profile(MU_REF, L_CANONICAL)
    block: dict[str, Any] = {
        "mu_ref": MU_REF,
        "L": L_CANONICAL,
        "solver": {"status": int(diag["status"]), "message": str(diag["message"]),
                   "n_nodes": int(diag["n_nodes"])},
    }
    if finite_num(diag.get("max_rms_residual")):
        block["solver"]["max_rms_residual"] = float(diag["max_rms_residual"])
    obs: dict[str, float] = {}
    reasons: list[str] = []
    if sol is not None:
        try:
            obs = panel_integrals(sol, MU_REF, L_CANONICAL)
        except Exception as exc:
            reasons = [f"quadrature:{type(exc).__name__}"]
    if obs:
        reasons = profile_item_reasons(diag, obs)
    else:
        reasons = reasons or ["solver_unavailable"]
    block["qualified"] = len(reasons) == 0
    if reasons:
        block["reasons"] = reasons[:10]
    block["observables"] = {key: float(obs[key]) for key in OBS_KEYS if key != "G_A_int"
                            and math.isfinite(obs.get(key, math.nan))}
    receipt_block: dict[str, Any] = {"path": REFERENCE_RECEIPT_REL}
    comparison: dict[str, Any] = {}
    item10 = False
    parameters_match = False
    try:
        raw = REFERENCE_RECEIPT.read_bytes()
        receipt = strict_json(raw, REFERENCE_RECEIPT_REL)
        static = receipt["massive_static"]
        parameters = receipt["parameters"]
        receipt_block["sha256"] = sha256_hex(raw)
        receipt_block["bytes"] = len(raw)
        receipt_block["s"] = float(static["s"])
        receipt_block["Lambda"] = float(static["Lambda"])
        receipt_block["R0_squared"] = float(static["R0_squared"])
        parameters_match = (
            receipt["schema"] == "matter-formation-chiral-lattice-structure-v1"
            and num_eq(float(parameters["mu"]), MU_REF)
            and num_eq(float(parameters["L"]), L_CANONICAL)
        )
        if parameters_match and block["qualified"]:
            comparison = {
                "s": rel_diff(obs["s"], receipt_block["s"]),
                "Lambda": rel_diff(obs["Lambda"], receipt_block["Lambda"]),
                "R0_sq": rel_diff(obs["R0_sq"], receipt_block["R0_squared"]),
            }
            item10 = all(value <= TOL_AGREE for value in comparison.values())
    except Exception as exc:
        receipt_block["error"] = f"{type(exc).__name__}: {exc}"[:200]
    receipt_block["parameters_match"] = bool(parameters_match)
    block["receipt"] = receipt_block
    block["relative_differences"] = comparison
    block["item10_within_tol"] = bool(item10)
    block["_obs"] = obs
    return block


# ---------------------------------------------------------------------------
# Gate ledger
# ---------------------------------------------------------------------------

class GateBook:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self.names: set[str] = set()

    def add(self, name: str, applicable: bool, passed: bool, **detail: Any) -> None:
        if name in self.names:
            raise TypedFailure("UnexpectedVerifierError", f"duplicate internal gate name {name!r}")
        self.names.add(name)
        self.rows.append({
            "name": name,
            "applicable": bool(applicable),
            "passed": bool(applicable and passed),
            "detail": detail,
        })

    def failed(self) -> list[str]:
        return [row["name"] for row in self.rows
                if row["applicable"] and not row["passed"]]


# ---------------------------------------------------------------------------
# Primary receipt validation (evidence before scientific comparison)
# ---------------------------------------------------------------------------

class PrimaryView:
    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data

    def domains_by_L(self) -> dict[float, dict[str, Any]]:
        out: dict[float, dict[str, Any]] = {}
        domains = self.data.get("domains")
        if isinstance(domains, list):
            for entry in domains:
                if isinstance(entry, dict) and is_num(entry.get("L")):
                    out[float(entry["L"])] = entry
        return out

    def identifiability(self) -> dict[str, Any]:
        ident = self.data.get("identifiability")
        return ident if isinstance(ident, dict) else {}


def check_primary_schema(view: PrimaryView) -> tuple[bool, list[str]]:
    data = view.data
    issues: list[str] = []
    if data.get("schema") != PRIMARY_SCHEMA:
        issues.append("schema mismatch")
    if data.get("control") is not False:
        issues.append("control must be false in a completed primary receipt")
    if data.get("complete_physical_matter_formation") is not False:
        issues.append("complete_physical_matter_formation must be false")
    if not isinstance(data.get("numerical_pass"), bool):
        issues.append("numerical_pass missing or not boolean")
    for key in ("identities", "constants", "analytic_radius", "identifiability",
                "domains", "reference", "gates", "artifacts", "verdicts"):
        if key not in data:
            issues.append(f"missing top-level key {key}")
    ident = data.get("identifiability")
    if isinstance(ident, dict):
        for key in ("canonical_L", "all_scans_qualified", "canonical_sign_change_pair_count",
                    "canonical_grid_zero_count", "canonical_branch", "root_present"):
            if key not in ident:
                issues.append(f"identifiability missing {key}")
        if ident.get("canonical_branch") not in ("root", "non_identifiable",
                                                 "root_solver_failure", "numerical_failure"):
            issues.append("identifiability.canonical_branch outside frozen enum")
        if not isinstance(ident.get("root_present"), bool):
            issues.append("identifiability.root_present not boolean")
        if not num_eq(ident.get("canonical_L", math.nan), L_CANONICAL):
            issues.append("identifiability.canonical_L != 64")
    else:
        issues.append("identifiability not an object")
    return len(issues) == 0, issues


def check_primary_identities(view: PrimaryView, own: dict[str, Any]) -> tuple[bool, list[str]]:
    issues: list[str] = []
    identities = view.data.get("identities")
    if not isinstance(identities, dict):
        return False, ["identities missing"]
    expected_paths = {
        "preregistration": own["prereg"]["path"],
        "primary_source": PRIMARY_SOURCE_REL,
        "verifier_source": OWN_SOURCE_REL,
    }
    expected_sha = {
        "preregistration": own["prereg"]["canonical_text_sha256"],
        "primary_source": own["primary_source"]["canonical_text_sha256"],
        "verifier_source": own["verifier_source"]["canonical_text_sha256"],
    }
    for name, path in expected_paths.items():
        record = identities.get(name)
        if not isinstance(record, dict):
            issues.append(f"identities.{name} missing")
            continue
        if record.get("path") != path:
            issues.append(f"identities.{name}.path != {path}")
        digest = record.get("canonical_text_sha256")
        expected = expected_sha[name]
        if not isinstance(digest, str) or digest != expected:
            issues.append(f"identities.{name}.canonical_text_sha256 stale or malformed")
    return len(issues) == 0, issues


PRIMARY_CONSTANT_EXACT = {
    "phi": PHI,
    "ell_pl_m": ELL_PL_M,
    "ell95_fm": ELL95_FM,
    "hbarc_mev_fm": HBARC_MEV_FM,
    "m_pi_mev": M_PI_MEV,
    "d_mev": D_MEV,
    "m_n_obs_mev": M_N_OBS_MEV,
    "m_delta_obs_mev": M_DELTA_OBS_MEV,
    "r_iso_obs_fm": R_ISO_OBS_FM,
    "mu_ref": MU_REF,
    "epsilon": EPS,
    "mu_lo": MU_LO,
    "mu_hi": MU_HI,
    "L_canonical": L_CANONICAL,
    "size_residual_tol_fm": TOL_SIZE_RESIDUAL_FM,
    "rms_tol": TOL_RMS,
    "degree_tol": TOL_DEGREE,
    "boundary_value_tol": TOL_F_L,
    "virial_tol": TOL_VIRIAL,
    "reconstruction_tol": TOL_RECON,
    "agreement_tol": TOL_AGREE,
    "domain_tol": TOL_DOMAIN,
    "analytic_radius_ratio_registered": ANALYTIC_RADIUS_RATIO_REGISTERED,
    "analytic_ratio_tol": ANALYTIC_RATIO_TOL,
}


def check_primary_constants(view: PrimaryView) -> tuple[bool, list[str]]:
    issues: list[str] = []
    constants = view.data.get("constants")
    if not isinstance(constants, dict):
        return False, ["constants missing"]
    for name, value in PRIMARY_CONSTANT_EXACT.items():
        if name not in constants:
            issues.append(f"constants.{name} missing")
        elif not num_eq(constants[name], value, rel=1.0e-12, abs_floor=1.0e-12):
            issues.append(f"constants.{name} differs from frozen value")
    if constants.get("ell95_step") != ELL95_STEP:
        issues.append("constants.ell95_step != 95")
    if constants.get("n_scan") != N_SCAN:
        issues.append("constants.n_scan != 33")
    if constants.get("bvp_max_nodes") != 100000:
        issues.append("constants.bvp_max_nodes != 100000 (primary method budget)")
    if not num_eq(constants.get("bvp_tol", math.nan), 1.0e-8):
        issues.append("constants.bvp_tol != 1e-8 (primary method tolerance)")
    provenance = constants.get("ell95_provenance")
    if not isinstance(provenance, str) or "external scale-selection input" not in provenance:
        issues.append("ell95_provenance must label step-95 as an external scale-selection input")
    d_provenance = constants.get("d_provenance")
    if not isinstance(d_provenance, str) or "literal" not in d_provenance:
        issues.append("d_provenance must register d as a direct literal")
    return len(issues) == 0, issues


def check_primary_analytic_radius(view: PrimaryView) -> tuple[bool, list[str]]:
    issues: list[str] = []
    ratio = ELL95_FM / R_ISO_OBS_FM - 1.0
    analytic = view.data.get("analytic_radius")
    if not isinstance(analytic, dict):
        return False, ["analytic_radius missing"]
    if not num_eq(analytic.get("relative_mismatch", math.nan), ratio,
                  rel=1.0e-12, abs_floor=1.0e-12):
        issues.append("analytic_radius.relative_mismatch not re-derivable")
    if not num_eq(analytic.get("registered_literal", math.nan),
                  ANALYTIC_RADIUS_RATIO_REGISTERED, rel=0.0, abs_floor=1.0e-15):
        issues.append("analytic_radius.registered_literal differs from §2 value")
    discrepancy = analytic.get("absolute_discrepancy")
    if not finite_num(discrepancy) or float(discrepancy) > ANALYTIC_RATIO_TOL:
        issues.append("analytic_radius.absolute_discrepancy above 1e-12")
    if analytic.get("exceeds_ten_percent") is not True:
        issues.append("analytic radius exceedance of the 10 percent discriminator not recorded")
    return len(issues) == 0, issues


def check_primary_domain(view: PrimaryView, L: float) -> tuple[bool, dict[str, Any]]:
    """Re-derive §5 items 1-5, G/virial/s arithmetic, and scan uniqueness."""
    issues: list[str] = []
    entry = view.domains_by_L().get(L)
    summary = {"L": L, "all_profiles_qualified": False, "sign_change_pair_count": -1,
               "grid_zero_count": -1, "unique_candidate": False, "issues": issues}
    if entry is None:
        issues.append(f"domain L={L} missing")
        return False, summary
    rows = entry.get("scan_rows")
    if not isinstance(rows, list) or len(rows) != N_SCAN:
        issues.append(f"domain L={L} scan_rows malformed")
        return False, summary
    gvals: list[float] = []
    all_ok = True
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            issues.append(f"scan row {index} not object")
            all_ok = False
            continue
        if not num_eq(row.get("mu", math.nan), float(SCAN_GRID[index]),
                      rel=1.0e-12, abs_floor=1.0e-15):
            issues.append(f"scan row {index} mu off frozen grid")
            all_ok = False
        if row.get("qualified") is not True:
            all_ok = False
            continue
        g = row.get("g_fm")
        if not finite_num(g):
            issues.append(f"scan row {index} qualified without finite g_fm")
            all_ok = False
            continue
        gvals.append(float(g))
        missing = [key for key in OBS_KEYS if not finite_num(row.get(key))]
        if missing:
            issues.append(f"scan row {index} missing/non-finite {missing[:4]}")
            all_ok = False
            continue
        if row.get("converged") is not True or row.get("finite") is not True:
            issues.append(f"scan row {index} qualified without converged/finite flags")
            all_ok = False
        E2, E4, Em = row["E2"], row["E4"], row["Em"]
        if abs(row["degree"] - 1.0) > TOL_DEGREE:
            issues.append(f"scan row {index} item3 degree")
            all_ok = False
        if abs(row["F_at_L"]) > TOL_F_L:
            issues.append(f"scan row {index} item4 F(L)")
            all_ok = False
        expected_virial = abs(E2 - E4 + 3.0 * Em
                              + 4.0 * math.pi * L ** 3 * row["Fx_at_L"] ** 2) / abs(E2 + E4 + Em)
        if abs(expected_virial - row["virial_relative"]) > RECHECK_ABS * max(1.0, expected_virial) \
                or row["virial_relative"] > TOL_VIRIAL:
            issues.append(f"scan row {index} item5 virial")
            all_ok = False
        if abs(row["s"] - (E2 + E4 + Em) / 4.0) > RECHECK_ABS:
            issues.append(f"scan row {index} s arithmetic")
            all_ok = False
        if row["R0_sq"] > 0.0:
            expected_g = HBARC_MEV_FM * row["mu"] * math.sqrt(row["R0_sq"]) / M_PI_MEV - ELL95_FM
            if abs(expected_g - row["g_fm"]) > RECHECK_ABS:
                issues.append(f"scan row {index} G arithmetic")
                all_ok = False
        else:
            issues.append(f"scan row {index} non-positive R0_sq on qualified row")
            all_ok = False
        solver = row.get("solver")
        if not isinstance(solver, dict) or solver.get("status") != 0 \
                or not finite_num(solver.get("max_rms_residual")) \
                or not (float(solver["max_rms_residual"]) < TOL_RMS) \
                or not isinstance(solver.get("n_nodes"), int):
            issues.append(f"scan row {index} solver diagnostics")
            all_ok = False
    pair_count = -1
    zero_count = -1
    bracket: list[float] = []
    if all_ok and len(gvals) == N_SCAN:
        pair_count = sum(1 for i in range(N_SCAN - 1) if gvals[i] * gvals[i + 1] < 0.0)
        zero_count = sum(1 for value in gvals if value == 0.0)
        if pair_count == 1 and zero_count == 0:
            for i in range(N_SCAN - 1):
                if gvals[i] * gvals[i + 1] < 0.0:
                    bracket = [float(SCAN_GRID[i]), float(SCAN_GRID[i + 1])]
                    break
    unique = bool(all_ok and pair_count == 1 and zero_count == 0)
    if bool(entry.get("all_profiles_qualified")) != all_ok:
        issues.append(f"domain L={L} reported qualification disagrees with recheck")
    if all_ok and is_num(entry.get("sign_change_pair_count")) \
            and int(entry["sign_change_pair_count"]) != pair_count:
        issues.append(f"domain L={L} reported pair count disagrees")
    if bool(entry.get("unique_candidate")) != unique:
        issues.append(f"domain L={L} reported unique_candidate disagrees")
    summary.update({"all_profiles_qualified": bool(all_ok),
                    "sign_change_pair_count": int(pair_count),
                    "grid_zero_count": int(zero_count),
                    "unique_candidate": unique, "bracket": bracket})
    return all_ok and len(issues) == 0, summary


def primary_root_expectations(view: PrimaryView, L: float, summary: dict[str, Any],
                              must_have_root: bool) -> tuple[bool, list[str]]:
    """Validate a primary root block and its coefficient/prediction arithmetic."""
    issues: list[str] = []
    entry = view.domains_by_L().get(L)
    if not isinstance(entry, dict):
        return False, [f"domain L={L} missing"]
    root = entry.get("root")
    if not must_have_root and root is None:
        return True, issues
    if not isinstance(root, dict):
        return False, [f"domain L={L} expected a root block"]
    if not finite_num(root.get("mu")) or not (MU_LO <= float(root["mu"]) <= MU_HI):
        issues.append("root mu outside frozen interval")
    if root.get("brent_converged") is not True or root.get("brent_inside_bracket") is not True:
        issues.append("root brent flags not both true")
    if not isinstance(root.get("n_brent_evaluations"), int) or root["n_brent_evaluations"] < 1:
        issues.append("root n_brent_evaluations invalid")
    bracket = root.get("bracket")
    if not isinstance(bracket, list) or len(bracket) != 2:
        issues.append("root bracket malformed")
    elif summary.get("bracket"):
        if not num_eq(bracket[0], summary["bracket"][0], rel=1.0e-12, abs_floor=1.0e-15) \
                or not num_eq(bracket[1], summary["bracket"][1], rel=1.0e-12, abs_floor=1.0e-15):
            issues.append("root bracket differs from recomputed sign-change pair")
    resid_abs = root.get("abs_size_residual_fm")
    if not finite_num(resid_abs) and finite_num(root.get("size_residual_fm")):
        resid_abs = abs(float(root["size_residual_fm"]))
    if not finite_num(resid_abs) or float(resid_abs) > TOL_SIZE_RESIDUAL_FM:
        issues.append("root size residual above frozen threshold")
    obs = entry.get("observables")
    if isinstance(obs, dict) and finite_num(resid_abs) and is_num(root.get("mu")) \
            and finite_num(obs.get("R0_sq")) and obs["R0_sq"] > 0.0:
        expected_resid = abs(HBARC_MEV_FM * float(root["mu"]) * math.sqrt(obs["R0_sq"])
                             / M_PI_MEV - ELL95_FM)
        if abs(expected_resid - float(resid_abs)) > RECHECK_ABS:
            issues.append("root residual disagrees with reported root observables")
    solver = obs.get("solver") if isinstance(obs, dict) else None
    if not isinstance(solver, dict) or solver.get("status") != 0 \
            or not finite_num(solver.get("max_rms_residual")) \
            or float(solver["max_rms_residual"]) >= TOL_RMS:
        issues.append("root solver diagnostics not qualified")
    coefficients = entry.get("coefficients")
    predictions = entry.get("predictions")
    recon = entry.get("reconstruction_residuals")
    if not isinstance(obs, dict) or not isinstance(coefficients, dict) \
            or not isinstance(predictions, dict) or not isinstance(recon, dict):
        issues.append("qualified root missing observables/coefficients/predictions/recon")
        return len(issues) == 0, issues
    try:
        P = float(coefficients["P_mev"])
        A = float(coefficients["A"])
        e_B = float(coefficients["e_B"])
        f_B = float(coefficients["f_B"])
        I0 = float(coefficients["I0"])
        lam = float(coefficients["lambda_B_fm"])
        Lambda = float(obs["Lambda"])
        s_val = float(obs["s"])
        R0 = float(obs["R0_sq"])
        M_cl = float(predictions["M_cl_MeV"])
        M_N = float(predictions["M_N_pred_MeV"])
        M_D = float(predictions["M_Delta_pred_MeV"])
        g_A = float(predictions["g_A"])
        g_pi = float(predictions["g_piNN"])
        G_A = float(obs["G_A_int"])
        if not num_eq(lam, ELL95_FM / math.sqrt(R0), rel=RECHECK_REL):
            issues.append("lambda_B arithmetic")
        if not num_eq(P, HBARC_MEV_FM / lam, rel=RECHECK_REL):
            issues.append("P from lambda_B arithmetic")
        if not num_eq(A, 9.0 * P * P / (2.0 * math.pi * Lambda * D_MEV), rel=RECHECK_REL):
            issues.append("A extraction arithmetic")
        if not num_eq(e_B, math.sqrt(P / A), rel=RECHECK_REL):
            issues.append("e_B arithmetic")
        if not num_eq(f_B, math.sqrt(P * A), rel=RECHECK_REL):
            issues.append("f_B arithmetic")
        if not num_eq(I0, math.pi * A / (3.0 * P * P), rel=RECHECK_REL):
            issues.append("I0 arithmetic")
        if not num_eq(M_cl, 2.0 * s_val * A, rel=RECHECK_REL):
            issues.append("M_cl arithmetic")
        if abs(M_N - (M_cl + D_MEV / 4.0)) > 1.0e-6:
            issues.append("M_N_pred arithmetic")
        if abs(M_D - (M_cl + 5.0 * D_MEV / 4.0)) > 1.0e-6:
            issues.append("M_Delta_pred arithmetic")
        if abs(predictions["r_I0_fm"] - ELL95_FM) > 1.0e-6:
            issues.append("r_I0_fm must equal ell95 at a size-normalized root")
        if not num_eq(g_A, -math.pi * G_A / (3.0 * e_B * e_B), rel=RECHECK_REL):
            issues.append("g_A arithmetic")
        if not num_eq(g_pi, M_N / f_B * g_A, rel=1.0e-6):
            issues.append("g_piNN arithmetic")
        for key in ("eBfB_vs_P", "fB_over_eB_vs_A", "M_pi_vs_mu_P", "splitting_vs_d"):
            value = recon.get(key)
            if not finite_num(value) or float(value) >= TOL_RECON:
                issues.append(f"reconstruction residual {key} at/above tol")
        for name, source in (("R0_sq", obs), ("RM0_sq", obs), ("s", obs), ("Lambda", obs),
                             ("A", coefficients), ("e_B", coefficients),
                             ("f_B", coefficients), ("I0", coefficients)):
            value = source.get(name)
            if not finite_num(value) or float(value) <= 0.0:
                issues.append(f"positivity violated for {name}")
        for key in ("degree", "F_at_L", "virial_relative"):
            value = obs.get(key)
            if not finite_num(value):
                issues.append(f"root observables missing {key}")
        if finite_num(obs.get("degree")) and abs(obs["degree"] - 1.0) > TOL_DEGREE:
            issues.append("root item3 degree")
        if finite_num(obs.get("F_at_L")) and abs(obs["F_at_L"]) > TOL_F_L:
            issues.append("root item4 F(L)")
        if finite_num(obs.get("virial_relative")) and obs["virial_relative"] > TOL_VIRIAL:
            issues.append("root item5 virial")
    except Exception as exc:
        issues.append(f"root re-derivation error {type(exc).__name__}: {exc}"[:200])
    return len(issues) == 0, issues


def check_primary_root_attempt(view: PrimaryView, L: float,
                               summary: dict[str, Any],
                               require_failed: bool = False) -> tuple[bool, list[str]]:
    """Validate a root-attempt block without demanding a qualifying basis."""
    issues: list[str] = []
    row = view.domains_by_L().get(L)
    if not isinstance(row, dict):
        return False, [f"domain L={L} missing"]
    root = row.get("root")
    if not isinstance(root, dict):
        return (False, [f"domain L={L} root-attempt block missing"]) if require_failed else (True, [])
    qualified = root.get("root_qualified")
    if require_failed and qualified is not False:
        issues.append("failed root attempt must set root_qualified=false")
    if qualified is not True and qualified is not False:
        issues.append("root attempt root_qualified is not boolean")
    for key in ("brent_converged", "brent_inside_bracket"):
        if not isinstance(root.get(key), bool):
            issues.append(f"root attempt {key} is not boolean")
    if not isinstance(root.get("n_brent_evaluations"), int) or root["n_brent_evaluations"] < 0:
        issues.append("root attempt n_brent_evaluations malformed")
    if "mu" in root and not finite_num(root["mu"]):
        issues.append("root attempt mu is non-finite")
    if "size_residual_fm" in root and not finite_num(root["size_residual_fm"]):
        issues.append("root attempt size_residual_fm malformed")
    if "abs_size_residual_fm" in root and (
            not finite_num(root["abs_size_residual_fm"])
            or float(root["abs_size_residual_fm"]) < 0.0):
        issues.append("root attempt abs_size_residual_fm malformed")
    bracket = root.get("bracket")
    expected = summary.get("bracket")
    if expected and (not isinstance(bracket, list) or len(bracket) != 2
                     or not num_eq(bracket[0], expected[0])
                     or not num_eq(bracket[1], expected[1])):
        issues.append("root attempt bracket differs from sign-change pair")
    if qualified is not True:
        for key in ("coefficients", "predictions", "reconstruction_residuals", "positivity"):
            if key in row:
                issues.append(f"failed root attempt carries {key}")
    return len(issues) == 0, issues


def check_primary_reference(view: PrimaryView) -> tuple[bool, list[str]]:
    issues: list[str] = []
    reference = view.data.get("reference")
    if not isinstance(reference, dict):
        return False, ["reference missing"]
    if not num_eq(reference.get("mu_ref", math.nan), MU_REF):
        issues.append("reference mu_ref mismatch")
    if not num_eq(reference.get("L", math.nan), L_CANONICAL):
        issues.append("reference L mismatch")
    if reference.get("qualified") is not True:
        issues.append("reference profile not qualified")
    obs = reference.get("observables")
    receipt = reference.get("receipt")
    rels = reference.get("relative_differences")
    if not isinstance(obs, dict) or not isinstance(receipt, dict) or not isinstance(rels, dict):
        issues.append("reference observables/receipt/relative_differences malformed")
        return len(issues) == 0, issues
    try:
        disk_raw = REFERENCE_RECEIPT.read_bytes()
        disk = strict_json(disk_raw, REFERENCE_RECEIPT_REL)
        static = disk["massive_static"]
        if receipt.get("path") != REFERENCE_RECEIPT_REL:
            issues.append("reference receipt path mismatch")
        if receipt.get("sha256") != sha256_hex(disk_raw):
            issues.append("reference receipt hash stale")
        if receipt.get("bytes") != len(disk_raw):
            issues.append("reference receipt byte size stale")
        for reported, actual in (("s", static["s"]), ("Lambda", static["Lambda"]),
                                 ("R0_squared", static["R0_squared"])):
            if not num_eq(receipt.get(reported, math.nan), actual,
                          rel=1.0e-12, abs_floor=1.0e-12):
                issues.append(f"reference receipt value {reported} disagrees with immutable file")
        for own_key, source_key, receipt_key in (("s", "s", "s"),
                                                 ("Lambda", "Lambda", "Lambda"),
                                                 ("R0_sq", "R0_sq", "R0_squared")):
            if not finite_num(obs.get(source_key)) or not finite_num(receipt.get(receipt_key)):
                issues.append(f"reference comparison inputs missing for {own_key}")
                continue
            recomputed = rel_diff(float(obs[source_key]), float(receipt[receipt_key]))
            if not num_eq(rels.get(own_key, math.nan), recomputed, rel=1.0e-6, abs_floor=1.0e-12):
                issues.append(f"reference relative difference {own_key} not re-derivable")
            if recomputed > TOL_AGREE:
                issues.append(f"reference item-10 violation for {own_key}")
        for key in ("degree", "F_at_L", "virial_relative"):
            value = obs.get(key)
            if not finite_num(value):
                issues.append(f"reference observables missing {key}")
        if finite_num(obs.get("degree")) and abs(obs["degree"] - 1.0) > TOL_DEGREE:
            issues.append("reference item3 degree")
        if finite_num(obs.get("F_at_L")) and abs(obs["F_at_L"]) > TOL_F_L:
            issues.append("reference item4 F(L)")
        if finite_num(obs.get("virial_relative")) and obs["virial_relative"] > TOL_VIRIAL:
            issues.append("reference item5 virial")
    except Exception as exc:
        issues.append(f"reference recheck error {type(exc).__name__}: {exc}"[:200])
    return len(issues) == 0, issues


def check_primary_gates_and_verdicts(view: PrimaryView) -> tuple[bool, list[str]]:
    issues: list[str] = []
    gates = view.data.get("gates")
    gate_map: dict[str, dict[str, Any]] = {}
    if not isinstance(gates, list):
        issues.append("primary gates missing")
    else:
        names = [row.get("name") for row in gates if isinstance(row, dict)]
        if len(set(names)) != len(names):
            issues.append("duplicate primary gate names")
        missing = [name for name in CANONICAL_GATES if name not in names]
        if missing:
            issues.append(f"primary gates missing canonical names {missing}")
        for row in gates:
            if not isinstance(row, dict) or not isinstance(row.get("name"), str) \
                    or not isinstance(row.get("applicable"), bool) \
                    or not isinstance(row.get("passed"), bool):
                issues.append("primary gate row malformed")
                continue
            if not row["applicable"] and row["passed"]:
                issues.append(f"inapplicable primary gate {row['name']} marked passed")
            if iter_nonfinite(row.get("detail", {})):
                issues.append(f"primary gate {row['name']} detail not finite")
            gate_map[str(row["name"])] = row
    numerical_pass = view.data.get("numerical_pass")
    if isinstance(gates, list) and isinstance(numerical_pass, bool):
        conjunction = all(row["passed"] for row in gate_map.values()
                          if row["applicable"])
        if numerical_pass != conjunction:
            issues.append("numerical_pass is not the conjunction of applicable gate outcomes")
    verdicts = view.data.get("verdicts")
    if not isinstance(verdicts, dict) or set(verdicts) != set(VERDICT_KEYS):
        issues.append("primary verdict keys must be exactly the six frozen keys")
        return len(issues) == 0, issues
    if verdicts["cascade_radius_assignment"] != V_RADIUS:
        issues.append("primary radius verdict not the frozen analytic CONTRADICTS string")
    if verdicts["size_first_normalization"] != V_NORMALIZATION:
        issues.append("primary normalization verdict not the frozen REJECT string")
    if verdicts["matter_formation"] != V_MATTER:
        issues.append("primary matter_formation verdict not the frozen INCONCLUSIVE string")
    ident = view.identifiability()
    branch = ident.get("canonical_branch")
    trio = (verdicts["cascade_size_root"], verdicts["absolute_nucleon_mass"],
            verdicts["absolute_delta_mass"])
    if numerical_pass is True:
        if branch == "root":
            if trio[0] != V_ROOT_SUPPORTS:
                issues.append("primary root verdict inconsistent with qualifying root")
            entry = view.domains_by_L().get(L_CANONICAL, {})
            predictions = entry.get("predictions") if isinstance(entry, dict) else None
            if isinstance(predictions, dict) \
                    and finite_num(predictions.get("M_N_pred_MeV")) \
                    and finite_num(predictions.get("M_Delta_pred_MeV")):
                expected_n = V_MN_SUPPORTS \
                    if abs(predictions["M_N_pred_MeV"] / M_N_OBS_MEV - 1.0) <= MASS_SUPPORT_THRESHOLD \
                    else V_MN_CONTRADICTS
                expected_d = V_MD_SUPPORTS \
                    if abs(predictions["M_Delta_pred_MeV"] / M_DELTA_OBS_MEV - 1.0) <= MASS_SUPPORT_THRESHOLD \
                    else V_MD_CONTRADICTS
                if trio[1] != expected_n or trio[2] != expected_d:
                    issues.append("primary mass verdicts inconsistent with the 10-percent rule")
            else:
                issues.append("primary root branch without canonical predictions")
        elif branch == "non_identifiable":
            if trio != (V_ROOT_NONIDENT, V_MASS_NO_MASS, V_MASS_NO_MASS):
                issues.append("primary non-identifiable branch verdict strings wrong")
        else:
            issues.append("primary numerical_pass true with neither root nor non_identifiable branch")
    else:
        if branch == "root_solver_failure":
            if trio != (V_ROOT_SOLVER_FAIL,) * 3:
                issues.append("primary root-solver-failure branch verdict trio wrong")
        else:
            if trio != (V_INCONCLUSIVE,) * 3:
                issues.append("failed-numerics branch must carry the plain INCONCLUSIVE trio")
    artifacts = view.data.get("artifacts")
    if isinstance(artifacts, dict):
        npz_entry = artifacts.get("root_profile.npz")
        root_present = ident.get("root_present")
        if root_present is True and not isinstance(npz_entry, dict):
            issues.append("root_present true but npz artifact record null/missing")
        if root_present is False and npz_entry is not None:
            issues.append("root_present false but npz artifact record present")
    else:
        issues.append("primary artifacts missing")
    return len(issues) == 0, issues


def check_primary_npz(view: PrimaryView, input_dir: Path) -> tuple[bool, list[str]]:
    issues: list[str] = []
    ident = view.identifiability()
    artifacts = view.data.get("artifacts")
    entry = artifacts.get("root_profile.npz") if isinstance(artifacts, dict) else None
    npz_path = input_dir / "root_profile.npz"
    root_present = bool(ident.get("root_present"))
    if not root_present:
        if npz_path.exists():
            issues.append("primary wrote root_profile.npz without a qualifying root")
        return len(issues) == 0, issues
    if not isinstance(entry, dict):
        return False, ["primary root branch without npz artifact record"]
    if not npz_path.is_file():
        return False, ["primary root_profile.npz missing despite root branch"]
    try:
        raw = npz_path.read_bytes()
        if entry.get("sha256") != sha256_hex(raw):
            issues.append("primary npz raw hash stale")
        if entry.get("bytes") != len(raw):
            issues.append("primary npz raw byte size stale")
        with np.load(io.BytesIO(raw), allow_pickle=False) as archive:
            keys = set(archive.files)
            if keys != {"x", "F", "F_x", "scalars"}:
                issues.append(f"primary npz keys {sorted(keys)} != x,F,F_x,scalars")
                return len(issues) == 0, issues
            arrays = {name: np.asarray(archive[name], dtype=np.float64) for name in keys}
            for name, arr in arrays.items():
                if arr.ndim != 1 or arr.dtype != np.float64 or not np.all(np.isfinite(arr)):
                    issues.append(f"primary npz {name} not finite 1-D float64")
                    return len(issues) == 0, issues
            x, F, F_x, scalars = (arrays["x"], arrays["F"], arrays["F_x"], arrays["scalars"])
            if scalars.size != SCALAR_COUNT:
                issues.append(f"primary npz scalar basis size {scalars.size} != {SCALAR_COUNT}")
                return len(issues) == 0, issues
            if x.size < 2 or F.size != x.size or F_x.size != x.size:
                issues.append("primary npz array lengths disagree")
            elif x.size != entry.get("n_nodes"):
                issues.append("primary npz n_nodes disagrees with array length")
            if not np.all(np.diff(x) > 0.0):
                issues.append("primary npz x not strictly increasing")
            else:
                if not num_eq(float(x[0]), EPS, rel=1.0e-9, abs_floor=1.0e-12):
                    issues.append("primary npz mesh does not start at epsilon")
                if not num_eq(float(x[-1]), L_CANONICAL, rel=1.0e-9, abs_floor=1.0e-12):
                    issues.append("primary npz mesh does not end at canonical L")
            manifest = entry.get("manifest")
            if not isinstance(manifest, dict) or manifest.get("dtypes") != ["float64"] \
                    or manifest.get("scalar_count") != SCALAR_COUNT \
                    or manifest.get("x_monotone") is not True:
                issues.append("primary npz manifest malformed")
            row64 = view.domains_by_L().get(L_CANONICAL, {})
            reference = view.data.get("reference")
            ref_obs = reference.get("observables") if isinstance(reference, dict) else None
            scalar_expect = {
                0: (row64.get("root"), "mu"), 1: (row64.get("observables"), "s"),
                2: (row64.get("observables"), "Lambda"), 3: (row64.get("observables"), "R0_sq"),
                4: (row64.get("observables"), "RM0_sq"), 5: (row64.get("coefficients"), "P_mev"),
                6: (row64.get("coefficients"), "A"), 7: (row64.get("coefficients"), "e_B"),
                8: (row64.get("coefficients"), "f_B"), 9: (row64.get("coefficients"), "I0"),
                10: (row64.get("predictions"), "M_cl_MeV"),
                11: (row64.get("predictions"), "M_N_pred_MeV"),
                12: (row64.get("predictions"), "M_Delta_pred_MeV"),
                13: (row64.get("predictions"), "r_I0_fm"),
                14: (row64.get("predictions"), "r_M_I0_fm"),
                15: (row64.get("observables"), "G_A_int"),
                16: (row64.get("predictions"), "g_A"), 17: (row64.get("predictions"), "g_piNN"),
                18: (row64.get("observables"), "degree"),
                19: (row64.get("observables"), "F_at_L"),
                20: (row64.get("observables"), "virial_relative"),
            }
            root_block = row64.get("root")
            expected_resid: Any = None
            if isinstance(root_block, dict):
                expected_resid = root_block.get("abs_size_residual_fm")
                if not finite_num(expected_resid) \
                        and finite_num(root_block.get("size_residual_fm")):
                    expected_resid = abs(float(root_block["size_residual_fm"]))
            if finite_num(expected_resid) and not num_eq(
                    abs(float(scalars[25])), float(expected_resid),
                    rel=RECHECK_REL, abs_floor=RECHECK_ABS):
                issues.append("primary npz scalar size_residual_fm disagrees with JSON")
            for index, (block, key) in scalar_expect.items():
                if isinstance(block, dict) and finite_num(block.get(key)):
                    if not num_eq(float(scalars[index]), float(block[key]),
                                  rel=RECHECK_REL, abs_floor=RECHECK_ABS):
                        issues.append(f"primary npz scalar {SCALAR_BASIS[index]} disagrees with JSON")
            obs64 = row64.get("observables")
            solver = obs64.get("solver") if isinstance(obs64, dict) else None
            if isinstance(solver, dict) and finite_num(solver.get("max_rms_residual")):
                if not num_eq(float(scalars[21]), float(solver["max_rms_residual"]),
                              rel=RECHECK_REL, abs_floor=RECHECK_ABS):
                    issues.append("primary npz max_rms_residual disagrees")
                if float(scalars[22]) != float(solver.get("status", -1)):
                    issues.append("primary npz solver status disagrees")
            if not num_eq(float(scalars[23]), L_CANONICAL, rel=0.0, abs_floor=1.0e-9):
                issues.append("primary npz canonical L disagrees")
            if not num_eq(float(scalars[24]), ELL95_FM, rel=1.0e-12, abs_floor=1.0e-12):
                issues.append("primary npz ell95 disagrees")
            if not num_eq(float(scalars[26]), MU_REF, rel=1.0e-12, abs_floor=1.0e-12):
                issues.append("primary npz mu_ref disagrees")
            if isinstance(ref_obs, dict):
                for index, key in ((27, "s"), (28, "Lambda"), (29, "R0_sq")):
                    if finite_num(ref_obs.get(key)) and not num_eq(
                            float(scalars[index]), float(ref_obs[key]),
                            rel=RECHECK_REL, abs_floor=RECHECK_ABS):
                        issues.append(f"primary npz reference scalar {key} disagrees")
            if abs(float(F[-1]) - float(scalars[19])) > 2.0e-10:
                issues.append("primary npz F at L disagrees with reported boundary value")
    except Exception as exc:
        issues.append(f"primary npz load error {type(exc).__name__}: {exc}"[:200])
    return len(issues) == 0, issues




def validate_primary(view: PrimaryView, book: GateBook, input_dir: Path,
                     own_identities: dict[str, Any]) -> dict[str, Any]:
    """Run every pre-scientific evidence gate against the primary receipt."""
    ok, issues = check_primary_schema(view)
    book.add("evidence_primary_schema_keys", True, ok, issues=issues[:20])
    ok, issues = check_primary_identities(view, own_identities)
    book.add("evidence_primary_identities", True, ok, issues=issues[:20])
    ok, issues = check_primary_constants(view)
    book.add("evidence_primary_constants", True, ok, issues=issues[:20])
    ok, issues = check_primary_analytic_radius(view)
    book.add("evidence_primary_analytic_radius", True, ok, issues=issues[:20])

    ident = view.identifiability()
    root_present = bool(ident.get("root_present"))
    executed = {L_CANONICAL} | ({48.0, 96.0} if root_present else set())
    domains_reported = set(view.domains_by_L().keys())
    ok = executed.issubset(domains_reported) and domains_reported.issubset(executed)
    book.add("evidence_primary_domain_presence", True, bool(ok),
             expected=sorted(executed), reported=sorted(domains_reported),
             rule="L=64 always; L=48/96 iff the frozen scan has a qualifying root")

    summaries: dict[float, dict[str, Any]] = {}
    scan_ok = True
    scan_issues: list[str] = []
    for L in sorted(executed):
        ok_L, summary = check_primary_domain(view, L)
        summaries[L] = summary
        scan_issues.extend(summary["issues"][:5])
        if L == L_CANONICAL:
            scan_ok = scan_ok and ok_L
        elif root_present:
            scan_ok = scan_ok and ok_L
    book.add("evidence_primary_scan_rows", True, scan_ok, issues=scan_issues[:20])

    canonical = summaries.get(L_CANONICAL, {})
    p_qual_all = all(bool(s.get("all_profiles_qualified")) for s in summaries.values())
    p_unique = bool(canonical.get("unique_candidate"))
    reported_branch = ident.get("canonical_branch")
    reported_qual = ident.get("all_scans_qualified")
    reported_pair = ident.get("canonical_sign_change_pair_count")
    reported_zero = ident.get("canonical_grid_zero_count")
    issues = []
    if reported_qual is not p_qual_all:
        issues.append("identifiability.all_scans_qualified disagrees with recheck")
    if p_qual_all:
        if int(canonical.get("sign_change_pair_count", -2)) != (int(reported_pair)
                                                                if is_num(reported_pair) else -2):
            issues.append("canonical pair count disagrees with recheck")
        if int(canonical.get("grid_zero_count", -2)) != (int(reported_zero)
                                                         if is_num(reported_zero) else -2):
            issues.append("canonical grid-zero count disagrees with recheck")
    else:
        if is_num(reported_pair) and int(reported_pair) != -1:
            issues.append("pair-count sentinel must be -1 when scans are unqualified")
    branch_ok = False
    if not p_qual_all:
        branch_ok = reported_branch == "numerical_failure"
    elif not p_unique:
        branch_ok = reported_branch == "non_identifiable" and root_present is False
    else:
        branch_ok = reported_branch in ("root", "root_solver_failure", "numerical_failure")
        if reported_branch == "root_solver_failure" and root_present:
            branch_ok = False
        if reported_branch == "root" and not root_present:
            branch_ok = False
    book.add("evidence_primary_sign_change", True, not issues and branch_ok,
             issues=issues, branch=reported_branch, root_present=root_present,
             recomputed={"all_scans_qualified": p_qual_all, "canonical_unique": p_unique})

    root_issues: list[str] = []
    root_ok = True
    canonical_root = view.domains_by_L().get(L_CANONICAL, {}).get("root")
    if p_unique and root_present:
        ok_L, issues_L = primary_root_expectations(view, L_CANONICAL, canonical, True)
        root_ok = root_ok and ok_L
        root_issues.extend(issues_L[:6])
        for L in sorted(executed - {L_CANONICAL}):
            row = view.domains_by_L().get(L, {})
            row_unique = bool(row.get("unique_candidate"))
            ok_L, issues_L = primary_root_expectations(view, L, summaries.get(L, {}), row_unique)
            root_ok = root_ok and ok_L
            root_issues.extend(issues_L[:6])
    elif reported_branch == "root_solver_failure":
        ok_L, issues_L = check_primary_root_attempt(
            view, L_CANONICAL, canonical, require_failed=True)
        root_ok = root_ok and ok_L
        root_issues.extend(issues_L[:6])
    elif p_unique:
        ok_L, issues_L = check_primary_root_attempt(
            view, L_CANONICAL, canonical, require_failed=False)
        root_ok = root_ok and ok_L
        root_issues.extend(issues_L[:6])
    elif isinstance(canonical_root, dict):
        root_ok = False
        root_issues.append("root block reported without a unique sign-change pair")
    book.add("evidence_primary_root_consistency",
             bool(p_unique or reported_branch == "root_solver_failure"), root_ok,
             issues=root_issues[:20], branch=reported_branch)

    ok, issues = check_primary_reference(view)
    book.add("evidence_primary_reference", True, ok, issues=issues[:20])
    ok, issues = check_primary_gates_and_verdicts(view)
    book.add("evidence_primary_gates_and_verdicts", True, ok, issues=issues[:20])

    artifacts = view.data.get("artifacts")
    protocol_entry = artifacts.get("frozen_protocol.txt") if isinstance(artifacts, dict) else None
    return {
        "protocol_entry": protocol_entry,
        "root_present": root_present,
        "reported_branch": reported_branch,
        "canonical": view.domains_by_L().get(L_CANONICAL, {}),
    }


# ---------------------------------------------------------------------------
# Verdict decision (§7)
# ---------------------------------------------------------------------------

def decide_verdicts(numerical_pass: bool, branch: str,
                    predictions: dict[str, Any] | None) -> dict[str, str]:
    """§7 tree. The analytic radius CONTRADICTS and REJECT survive every outcome."""
    verdicts = {
        "cascade_radius_assignment": V_RADIUS,
        "size_first_normalization": V_NORMALIZATION,
        "matter_formation": V_MATTER,
    }
    if not numerical_pass:
        if branch == "root_solver_failure":
            root = mn = md = V_ROOT_SOLVER_FAIL
        else:
            root = mn = md = V_INCONCLUSIVE
    elif branch == "non_identifiable":
        root = V_ROOT_NONIDENT
        mn = md = V_MASS_NO_MASS
    elif branch == "root" and isinstance(predictions, dict) \
            and finite_num(predictions.get("M_N_pred_MeV")) \
            and finite_num(predictions.get("M_Delta_pred_MeV")):
        root = V_ROOT_SUPPORTS
        mn = V_MN_SUPPORTS if abs(predictions["M_N_pred_MeV"] / M_N_OBS_MEV - 1.0) \
            <= MASS_SUPPORT_THRESHOLD else V_MN_CONTRADICTS
        md = V_MD_SUPPORTS if abs(predictions["M_Delta_pred_MeV"] / M_DELTA_OBS_MEV - 1.0) \
            <= MASS_SUPPORT_THRESHOLD else V_MD_CONTRADICTS
    else:
        root = mn = md = V_INCONCLUSIVE
    verdicts["cascade_size_root"] = root
    verdicts["absolute_nucleon_mass"] = mn
    verdicts["absolute_delta_mass"] = md
    return {key: verdicts[key] for key in VERDICT_KEYS}


# ---------------------------------------------------------------------------
# Failure-only typed receipt and output preparation
# ---------------------------------------------------------------------------

def write_failure_only(output_dir: Path, kind: str, detail: str) -> None:
    receipt = {
        "schema": SCHEMA,
        "control": True,
        "complete_physical_matter_formation": False,
        "numerical_pass": False,
        "failure": {"type": kind, "detail": detail[:400]},
        "verdicts": {key: V_INCONCLUSIVE for key in VERDICT_KEYS},
    }
    write_json_exclusive(output_dir / "verification.json", receipt)


def prepare_output_dir(path: Path) -> Path:
    if path.exists():
        if not path.is_dir():
            raise OSError(f"--output {path} exists and is not a directory")
        if any(path.iterdir()):
            raise OSError(f"--output {path} is nonempty; refusing to overwrite")
    else:
        path.mkdir(parents=True)
    return path


# ---------------------------------------------------------------------------
# Main scientific run
# ---------------------------------------------------------------------------

def run(args: argparse.Namespace) -> int:
    output_dir = prepare_output_dir(Path(args.output).resolve())
    input_dir = Path(args.input).resolve()
    prereg_path = Path(args.prereg).resolve()

    # -- preregistration identity, staleness guard, frozen protocol slice ----
    if not prereg_path.is_file():
        raise TypedFailure("MissingPreregistration",
                           f"no preregistration at {root_rel(prereg_path)}")
    prereg_raw = prereg_path.read_bytes()
    prereg_canonical = canonical_bytes(prereg_path)
    prereg_text = prereg_canonical.decode("utf-8")
    missing_markers = [marker for marker in PREREG_FROZEN_MARKERS if marker not in prereg_text]
    if missing_markers:
        raise TypedFailure(
            "PreregistrationLiteralMismatch",
            "preregistration drifted from this source; missing literals: "
            + "; ".join(repr(marker[:60]) for marker in missing_markers[:8]),
        )
    protocol_text = protocol_slice(prereg_text)

    # -- §2 analytic radius discriminator, reproduced before any solve -------
    ratio = ELL95_FM / R_ISO_OBS_FM - 1.0
    analytic_discrepancy = abs(ratio - ANALYTIC_RADIUS_RATIO_REGISTERED)
    if not (math.isfinite(ratio) and analytic_discrepancy <= ANALYTIC_RATIO_TOL
            and abs(ratio) > MASS_SUPPORT_THRESHOLD):
        raise TypedFailure(
            "AnalyticPrecheckMismatch",
            f"computed ell95/r_obs-1={ratio!r} does not reproduce the registered "
            f"{ANALYTIC_RADIUS_RATIO_REGISTERED!r} and its 10-percent exceedance",
        )

    # -- source identities (both programs, canonical-LF SHA-256) --------------
    own_canonical = canonical_bytes(Path(__file__).resolve())
    primary_source_path = ROOT / PRIMARY_SOURCE_REL
    own_identities: dict[str, Any] = {
        "prereg": {"path": PREREG_REL if prereg_path.resolve() == DEFAULT_PREREG.resolve()
                   else root_rel(prereg_path),
                   "canonical_text_sha256": sha256_hex(prereg_canonical),
                   "bytes": len(prereg_canonical),
                   "raw_sha256": sha256_hex(prereg_raw),
                   "raw_bytes": len(prereg_raw)},
        "verifier_source": {"path": OWN_SOURCE_REL,
                            "canonical_text_sha256": sha256_hex(own_canonical),
                            "bytes": len(own_canonical)},
        "primary_source": {"path": PRIMARY_SOURCE_REL, "canonical_text_sha256": "",
                           "bytes": 0, "present": primary_source_path.is_file()},
    }
    if primary_source_path.is_file():
        primary_canonical = canonical_bytes(primary_source_path)
        own_identities["primary_source"]["canonical_text_sha256"] = sha256_hex(primary_canonical)
        own_identities["primary_source"]["bytes"] = len(primary_canonical)

    # -- primary presence precheck (missing input -> typed failure only) -----
    primary_results_path = input_dir / "results.json"
    primary_protocol_path = input_dir / "frozen_protocol.txt"
    if not input_dir.is_dir() or not primary_results_path.is_file():
        raise TypedFailure("MissingPrimaryReceipt",
                           f"no primary results.json under {input_dir.as_posix()}")
    if not primary_protocol_path.is_file():
        raise TypedFailure("MissingPrimaryArtifact",
                           f"no primary frozen_protocol.txt under {input_dir.as_posix()}")

    # =======================================================================
    # Independent numerics, entirely before any primary scalar is read.
    # Canonical scan and reference always; §7 stop rules otherwise.
    # =======================================================================
    canonical_scan = scan_domain(L_CANONICAL)
    reference_block = reference_reconstruction()
    reference_obs = reference_block.pop("_obs")
    scan_ok = bool(canonical_scan["all_profiles_qualified"])
    reference_items_ok = bool(reference_block["qualified"]
                              and reference_block["item10_within_tol"]
                              and reference_block["receipt"].get("parameters_match"))
    unique_canonical = bool(canonical_scan["unique_candidate"])

    branch = "numerical_failure"
    executed_domains: dict[float, dict[str, Any]] = {L_CANONICAL: canonical_scan}
    root_results: dict[float, dict[str, Any]] = {}
    coefficient_results: dict[float, dict[str, Any] | None] = {}
    domain_coefficients: dict[float, dict[str, Any] | None] = {}

    if scan_ok and unique_canonical:
        canonical_root = root_solve(L_CANONICAL, canonical_scan["bracket"])
        root_results[L_CANONICAL] = canonical_root
        if canonical_root.get("bracket_residual_ok"):
            # §3 bracket and residual condition passed: the profile items and
            # §4 coefficient extraction decide whether this is a qualifying root.
            obs = canonical_root.get("observables") or {}
            block = coefficient_block(canonical_root["mu"], obs) \
                if canonical_root["profile_items_1_to_5"] else None
            coefficient_results[L_CANONICAL] = block
            if block is not None:
                branch = "root"
                for L in L_REPEAT_DOMAINS:
                    repeat_scan = scan_domain(L)
                    executed_domains[L] = repeat_scan
                    if repeat_scan["unique_candidate"]:
                        repeat_root = root_solve(L, repeat_scan["bracket"])
                        root_results[L] = repeat_root
                        r_obs = repeat_root.get("observables") or {}
                        domain_coefficients[L] = coefficient_block(repeat_root["mu"], r_obs) \
                            if repeat_root.get("root_qualified") else None
            else:
                branch = "numerical_failure"  # finiteness/coefficients, §7 para 2
        else:
            branch = "root_solver_failure"  # §3/§7: frozen solver condition failed
    elif scan_ok and not unique_canonical:
        branch = "non_identifiable"

    canonical_candidate = root_results.get(L_CANONICAL)
    canonical_coefficients = coefficient_results.get(L_CANONICAL)
    npz_basis: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray] | None = None
    if (canonical_candidate is not None
            and canonical_candidate.get("root_qualified")
            and canonical_coefficients is not None):
        candidate_obs = canonical_candidate.get("observables") or {}
        candidate_solver = canonical_candidate.get("solver") or {}
        candidate_mesh = canonical_candidate.get("mesh") or {}
        try:
            npz_values = np.asarray([
                canonical_candidate["mu"], candidate_obs["s"], candidate_obs["Lambda"],
                candidate_obs["R0_sq"], candidate_obs["RM0_sq"],
                canonical_coefficients["coefficients"]["P_mev"],
                canonical_coefficients["coefficients"]["A"],
                canonical_coefficients["coefficients"]["e_B"],
                canonical_coefficients["coefficients"]["f_B"],
                canonical_coefficients["coefficients"]["I0"],
                canonical_coefficients["predictions"]["M_cl_MeV"],
                canonical_coefficients["predictions"]["M_N_pred_MeV"],
                canonical_coefficients["predictions"]["M_Delta_pred_MeV"],
                canonical_coefficients["predictions"]["r_I0_fm"],
                canonical_coefficients["predictions"]["r_M_I0_fm"],
                candidate_obs["G_A_int"], canonical_coefficients["predictions"]["g_A"],
                canonical_coefficients["predictions"]["g_piNN"], candidate_obs["degree"],
                candidate_obs["F_at_L"], candidate_obs["virial_relative"],
                candidate_solver["max_rms_residual"], candidate_solver["status"],
                L_CANONICAL, ELL95_FM, canonical_candidate["size_residual_fm"], MU_REF,
                reference_obs["s"], reference_obs["Lambda"], reference_obs["R0_sq"],
            ], dtype=np.float64)
            npz_x = np.asarray(candidate_mesh["x"], dtype=np.float64)
            npz_F = np.asarray(candidate_mesh["F"], dtype=np.float64)
            npz_F_x = np.asarray(candidate_mesh["F_x"], dtype=np.float64)
            basis_ok = (
                npz_values.size == SCALAR_COUNT
                and np.all(np.isfinite(npz_values))
                and npz_x.ndim == 1 and npz_x.size >= 2
                and npz_F.ndim == 1 and npz_F_x.ndim == 1
                and npz_F.size == npz_x.size and npz_F_x.size == npz_x.size
                and np.all(np.isfinite(npz_x)) and np.all(np.isfinite(npz_F))
                and np.all(np.isfinite(npz_F_x)) and np.all(np.diff(npz_x) > 0.0)
            )
            if basis_ok:
                npz_basis = (npz_values, npz_x, npz_F, npz_F_x)
        except (KeyError, TypeError, ValueError):
            npz_basis = None
    root_present = npz_basis is not None
    if branch == "root" and not root_present:
        branch = "numerical_failure"

    # A canonical qualifying root keeps the NPZ; failures in the repeated
    # domains demote the branch to numerical_failure without retracting it.
    if branch == "root":
        for L in L_REPEAT_DOMAINS:
            entry = root_results.get(L)
            block = domain_coefficients.get(L)
            if entry is None or not entry.get("root_qualified") or block is None:
                branch = "numerical_failure"
                break

    domain_rows: dict[float, dict[str, Any]] = {}
    for L, scan in executed_domains.items():
        root = root_results.get(L)
        block = coefficient_results.get(L) if L == L_CANONICAL else domain_coefficients.get(L)
        if root is not None and not root.get("root_qualified"):
            block = None
        domain_rows[L] = domain_row(L, scan, root, block)

    all_scans_qualified = all(row["all_profiles_qualified"] for row in domain_rows.values())
    canonical_predictions = None
    if coefficient_results.get(L_CANONICAL) is not None:
        canonical_predictions = coefficient_results[L_CANONICAL]["predictions"]

    # =======================================================================
    # Read and validate the primary receipt, then compare (own results exist).
    # =======================================================================
    book = GateBook()
    book.add("analytic_radius_precheck", True, True,
             ell95_fm=ELL95_FM, r_iso_obs_fm=R_ISO_OBS_FM,
             computed_relative_mismatch=ratio,
             registered_literal=ANALYTIC_RADIUS_RATIO_REGISTERED,
             absolute_discrepancy=analytic_discrepancy,
             ten_percent_threshold=MASS_SUPPORT_THRESHOLD,
             note="reproduced before any profile solve; fixes CONTRADICTS and REJECT")
    book.add("output_contract", True, True,
             output_dir_root_relative=root_rel(output_dir),
             exclusive_creation=True,
             overwrite_refusal="nonempty output directory aborted before any write",
             json_policy="no NaN or Infinity; strict parse with duplicate-key rejection")
    book.add("scan_profiles_items_1_to_5", True, all_scans_qualified,
             domains_executed=sorted(float(L) for L in domain_rows),
             profiles_per_domain=N_SCAN,
             failed_domains=sorted(float(L) for L, row in domain_rows.items()
                                   if not row["all_profiles_qualified"]))
    book.add("reference_reconstruction_items", True, reference_items_ok,
             profile_items_1_to_5=bool(reference_block["qualified"]),
             item10_within_tol=bool(reference_block["item10_within_tol"]),
             parameters_match=bool(reference_block["receipt"].get("parameters_match")),
             relative_differences=reference_block["relative_differences"],
             reasons=list(reference_block.get("reasons", []))[:10])
    book.add("unique_sign_change_scan", scan_ok and reference_items_ok, True,
             canonical_sign_change_pair_count=int(canonical_scan["sign_change_pair_count"]),
             canonical_grid_zero_count=int(canonical_scan["grid_zero_count"]),
             canonical_unique_candidate=unique_canonical,
             repeat_pair_counts={str(float(L)): int(row["sign_change_pair_count"])
                                 for L, row in domain_rows.items() if L != L_CANONICAL},
             note="pair count is the identifiability determination; non-uniqueness "
                  "is a scientific outcome, never a numerical gate failure")

    bracket_applicable = bool(scan_ok and unique_canonical)
    canonical_root = root_results.get(L_CANONICAL)
    if bracket_applicable and canonical_root is not None:
        book.add("root_bracket_and_residual", True,
                 bool(canonical_root.get("bracket_residual_ok")),
                 bracket=[float(v) for v in canonical_scan["bracket"]],
                 mu=float(canonical_root["mu"]) if finite_num(canonical_root.get("mu")) else -1.0,
                 size_residual_fm=float(canonical_root["size_residual_fm"])
                 if finite_num(canonical_root.get("size_residual_fm")) else -1.0,
                 brent_converged=bool(canonical_root["brent_converged"]),
                 brent_inside_bracket=bool(canonical_root["brent_inside_bracket"]),
                 n_brent_evaluations=int(canonical_root["n_brent_evaluations"]),
                 root_profile_items_1_to_5=bool(canonical_root["profile_items_1_to_5"]),
                 failure_reason=str(canonical_root.get("failure_reason", ""))[:200])
    else:
        book.add("root_bracket_and_residual", False, False, branch=branch,
                 note="not applicable without exactly one qualifying sign-changing pair")

    six_seven_applicable = bool(bracket_applicable and canonical_root is not None
                                and canonical_root.get("bracket_residual_ok"))
    if six_seven_applicable:
        six_seven_ok = True
        six_seven_failures: list[str] = []
        for L in (L_CANONICAL, *L_REPEAT_DOMAINS):
            entry = root_results.get(L)
            block = coefficient_results.get(L) if L == L_CANONICAL else domain_coefficients.get(L)
            if entry is None or not entry.get("root_qualified") or block is None:
                six_seven_ok = False
                six_seven_failures.append(f"L{int(L)}:root_or_coefficients_unavailable")
                continue
            for name, flag in block["positivity"].items():
                if not flag:
                    six_seven_ok = False
                    six_seven_failures.append(f"L{int(L)}:positivity:{name}")
            for name, value in block["reconstruction_residuals"].items():
                if not (isinstance(value, float) and math.isfinite(value) and value < TOL_RECON):
                    six_seven_ok = False
                    six_seven_failures.append(f"L{int(L)}:recon:{name}")
        book.add("root_items_6_to_7", True, six_seven_ok, failures=six_seven_failures[:12])
        checks: dict[str, list[dict[str, Any]]] = {"mu": [], "M_N_pred": []}
        base_root = root_results.get(L_CANONICAL, {})
        base_row = domain_rows.get(L_CANONICAL, {})
        mu64 = base_root.get("mu")
        m_n64 = (base_row.get("predictions") or {}).get("M_N_pred_MeV")
        for L in L_REPEAT_DOMAINS:
            entry = root_results.get(L, {})
            row = domain_rows.get(L, {})
            mu_other = entry.get("mu")
            m_n_other = (row.get("predictions") or {}).get("M_N_pred_MeV")
            for key, base_value, other_value in (("mu", mu64, mu_other),
                                                 ("M_N_pred", m_n64, m_n_other)):
                if finite_num(base_value) and finite_num(other_value):
                    checks[key].append({"L": float(L),
                                        "relative_difference": rel_diff(float(base_value),
                                                                        float(other_value))})
        item9_ok = all(len(checks[key]) == 2 for key in checks) and all(
            item["relative_difference"] <= TOL_DOMAIN
            for key in checks for item in checks[key])
        book.add("domain_repetition_item_9", True, item9_ok, per_domain=checks)
    else:
        book.add("root_items_6_to_7", False, False, branch=branch)
        book.add("domain_repetition_item_9", False, False, branch=branch)

    # -- primary evidence validation ----------------------------------------
    primary_results_raw = primary_results_path.read_bytes()
    primary_data: dict[str, Any] | None = None
    try:
        parsed = strict_json(primary_results_raw, "primary results.json")
        if not isinstance(parsed, dict):
            raise ValueError("primary receipt root is not an object")
        nonfinite = iter_nonfinite(parsed)
        if nonfinite:
            raise ValueError(f"non-finite numbers at {nonfinite[:5]}")
        primary_data = parsed
        book.add("evidence_primary_receipt_strict", True, True,
                 path="results.json", duplicate_keys="rejected", nan_infinity="rejected",
                 bytes=len(primary_results_raw))
    except Exception as exc:
        book.add("evidence_primary_receipt_strict", True, False,
                 error=f"{type(exc).__name__}: {exc}"[:300])

    primary_branch: Any = None
    primary_canonical_row: dict[str, Any] = {}
    primary_root_present = False
    if primary_data is not None:
        view = PrimaryView(primary_data)
        meta = validate_primary(view, book, input_dir, own_identities)
        primary_branch = meta["reported_branch"]
        primary_canonical_row = meta["canonical"]
        primary_root_present = meta["root_present"]
        artifacts = primary_data.get("artifacts") if isinstance(primary_data.get("artifacts"),
                                                                dict) else {}
        protocol_entry = artifacts.get("frozen_protocol.txt")
        protocol_raw = primary_protocol_path.read_bytes()
        ok = isinstance(protocol_entry, dict) \
            and protocol_entry.get("sha256") == sha256_hex(protocol_raw) \
            and protocol_entry.get("bytes") == len(protocol_raw) \
            and protocol_raw.decode("utf-8") == protocol_text
        book.add("evidence_primary_protocol_text", True, bool(ok),
                 recorded=protocol_entry if isinstance(protocol_entry, dict) else {},
                 own_slice_sha256=sha256_hex(protocol_text.encode("utf-8")),
                 rule="lines after H1 through before '## References' (both excluded), "
                      "trailing blanks trimmed, LF endings, one terminal LF")
        ok, issues = check_primary_npz(view, input_dir)
        book.add("evidence_primary_npz", True, ok, issues=issues[:20])
        book.add("evidence_branch_consistency", True, branch == primary_branch,
                 own_branch=branch, primary_branch=primary_branch)
        both_root = branch == "root" and primary_branch == "root" \
            and primary_root_present and canonical_predictions is not None
        if both_root:
            comparison: dict[str, Any] = {}
            agree_all = True
            coef_block = coefficient_results.get(L_CANONICAL)
            for short, section, key in COMPARISON_QUANTITIES:
                my_value = math.nan
                if section == "root":
                    my_value = float(canonical_root["mu"])
                elif section == "observables":
                    my_value = float((canonical_root.get("observables") or {}).get(key, math.nan))
                elif section == "coefficients" and coef_block is not None:
                    my_value = float(coef_block["coefficients"].get(key, math.nan))
                elif section == "predictions":
                    my_value = float(canonical_predictions.get(key, math.nan))
                theirs = primary_canonical_row.get(section)
                their_value = float(theirs.get(key, math.nan)) \
                    if isinstance(theirs, dict) and finite_num(theirs.get(key)) else math.nan
                comparable = bool(math.isfinite(my_value) and math.isfinite(their_value))
                within = False
                record: dict[str, Any] = {
                    "own": my_value if math.isfinite(my_value) else -1.0,
                    "primary": their_value if math.isfinite(their_value) else -1.0,
                    "comparable": comparable,
                }
                if comparable:
                    diff = rel_diff(my_value, their_value)
                    within = bool(diff <= TOL_AGREE)
                    record["relative_difference"] = float(diff)
                agree_all = agree_all and within
                comparison[short] = {**record, "within": within}
                book.add(f"independent_agreement_{short}", True, within,
                         **record, within=within, tol=TOL_AGREE)
            book.add("evidence_independent_comparison", True, agree_all, quantities=comparison)
        else:
            applicable = branch == "root" or primary_branch == "root"
            book.add("evidence_independent_comparison", applicable, not applicable,
                     own_branch=branch, primary_branch=primary_branch,
                     note="item 8 applies only when both methods solved a qualifying root")

    evidence_failed = [name for name in book.failed() if name.startswith("evidence_")]
    book.add("evidence_contract", True, len(evidence_failed) == 0,
             failed_evidence_gates=evidence_failed,
             duplicate_gate_names="none by construction",
             required_key_policy="missing required keys fail the evidence contract")

    numerical_pass = len(book.failed()) == 0
    verdicts = decide_verdicts(numerical_pass, branch, canonical_predictions)

    # =======================================================================
    # Emit contracted artifacts: protocol text, conditional NPZ, verification.
    # =======================================================================
    protocol_bytes = protocol_text.encode("utf-8")
    artifacts_block: dict[str, Any] = {
        "frozen_protocol.txt": {"path": "frozen_protocol.txt",
                                "sha256": sha256_hex(protocol_bytes),
                                "bytes": len(protocol_bytes)},
        "independent_root_profile.npz": None,
    }
    npz_bytes: bytes | None = None
    npz_written = False
    if root_present and npz_basis is not None:
        scalars, x, F, F_x = npz_basis
        stream = io.BytesIO()
        np.savez(stream, x=x, F=F, F_x=F_x, scalars=scalars)
        npz_bytes = stream.getvalue()
        artifacts_block["independent_root_profile.npz"] = {
            "path": "independent_root_profile.npz",
            "sha256": sha256_hex(npz_bytes), "bytes": len(npz_bytes),
            "n_nodes": int(x.size),
            "manifest": {"dtypes": ["float64"], "scalar_count": SCALAR_COUNT,
                         "x_monotone": bool(np.all(np.diff(x) > 0.0)),
                         "scalar_basis": list(SCALAR_BASIS)},
        }
        npz_written = True

    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "control": False,
        "complete_physical_matter_formation": False,
        "numerical_pass": bool(numerical_pass),
        "method": {
            "solver": "scipy.integrate.solve_bvp on theta=pi-F; physical F reconstructed before observables",
            "mesh": "mixed linear/geometric, separately constructed",
            "bvp_tol": BVP_TOL,
            "bvp_max_nodes": BVP_MAX_NODES,
            "quadrature": "fixed 24-point Gauss-Legendre on every refined mesh panel",
            "gl_order": GL_ORDER,
            "origin_segment_excluded": True,
            "excluded_origin_interval": EPS,
            "root_method": "own 33-point logarithmic scan plus own bracketed Brent",
            "virial_boundary_term_sign": "plus: E2 - E4 + 3*Em + 4*pi*L^3*Fx(L)^2",
            "imports_primary": False,
        },
        "identities": {
            "preregistration": {"path": own_identities["prereg"]["path"],
                                "canonical_text_sha256":
                                    own_identities["prereg"]["canonical_text_sha256"]},
            "primary_source": {"path": PRIMARY_SOURCE_REL,
                               "canonical_text_sha256": own_identities["primary_source"]
                               ["canonical_text_sha256"]},
            "verifier_source": {"path": OWN_SOURCE_REL,
                                "canonical_text_sha256":
                                    own_identities["verifier_source"]["canonical_text_sha256"]},
        },
        "constants": {
            "phi": PHI, "ell_pl_m": ELL_PL_M, "ell95_step": ELL95_STEP, "ell95_fm": ELL95_FM,
            "ell95_provenance": "external scale-selection input (Mapped step-95); not a prediction",
            "hbarc_mev_fm": HBARC_MEV_FM, "m_pi_mev": M_PI_MEV, "d_mev": D_MEV,
            "d_provenance": "registered spectroscopy literal; never computed from absolute masses",
            "m_n_obs_mev": M_N_OBS_MEV, "m_n_obs_usage": "withheld absolute comparison value",
            "m_delta_obs_mev": M_DELTA_OBS_MEV, "m_delta_obs_usage": "withheld absolute comparison value",
            "r_iso_obs_fm": R_ISO_OBS_FM, "mu_ref": MU_REF, "epsilon": EPS,
            "mu_lo": MU_LO, "mu_hi": MU_HI, "n_scan": N_SCAN, "L_canonical": L_CANONICAL,
            "L_domains": [48.0, 64.0, 96.0],
            "bvp_tol": BVP_TOL, "bvp_max_nodes": BVP_MAX_NODES, "gl_order": GL_ORDER,
            "analytic_radius_ratio_registered": ANALYTIC_RADIUS_RATIO_REGISTERED,
            "analytic_ratio_tol": ANALYTIC_RATIO_TOL,
            "size_residual_tol_fm": TOL_SIZE_RESIDUAL_FM, "rms_tol": TOL_RMS,
            "degree_tol": TOL_DEGREE, "boundary_value_tol": TOL_F_L, "virial_tol": TOL_VIRIAL,
            "reconstruction_tol": TOL_RECON, "agreement_tol": TOL_AGREE,
            "domain_tol": TOL_DOMAIN, "mass_support_threshold": MASS_SUPPORT_THRESHOLD,
        },
        "analytic_radius": {
            "ell95_fm": ELL95_FM, "r_iso_obs_fm": R_ISO_OBS_FM,
            "relative_mismatch": ratio,
            "registered_literal": ANALYTIC_RADIUS_RATIO_REGISTERED,
            "absolute_discrepancy": analytic_discrepancy,
            "exceeds_ten_percent": bool(abs(ratio) > MASS_SUPPORT_THRESHOLD),
        },
        "identifiability": {
            "canonical_L": L_CANONICAL,
            "domains_executed": sorted(float(L) for L in domain_rows),
            "all_scans_qualified": bool(all_scans_qualified),
            "canonical_sign_change_pair_count": int(canonical_scan["sign_change_pair_count"]),
            "canonical_grid_zero_count": int(canonical_scan["grid_zero_count"]),
            "canonical_branch": branch,
            "root_present": bool(npz_written),
        },
        "domains": [domain_rows[L] for L in sorted(domain_rows)],
        "reference": reference_block,
        "primary_receipt_identity": {"path": "results.json",
                                     "sha256": sha256_hex(primary_results_raw),
                                     "bytes": len(primary_results_raw)},
        "primary_protocol_identity": file_identity(primary_protocol_path),
        "primary_npz_identity": (
            file_identity(input_dir / "root_profile.npz")
            if (input_dir / "root_profile.npz").is_file()
            else {"path": "root_profile.npz", "present": False}),
        "gates": book.rows,
        "verdicts": verdicts,
        "verdict_sha256": {key: sha256_hex(verdicts[key].encode("utf-8"))
                           for key in VERDICT_KEYS},
        "artifacts": artifacts_block,
    }
    bad = iter_nonfinite({k: v for k, v in payload.items() if k != "artifacts"})
    if bad:
        raise TypedFailure("NonFiniteSerializedPayload", f"non-finite values at {bad[:5]}")
    try:
        json_data = (json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    except ValueError as exc:
        raise TypedFailure("NonFiniteSerializedPayload", str(exc)[:300]) from exc
    write_bytes_exclusive(output_dir / "frozen_protocol.txt", protocol_bytes)
    if npz_bytes is not None:
        write_bytes_exclusive(output_dir / "independent_root_profile.npz", npz_bytes)
    write_bytes_exclusive(output_dir / "verification.json", json_data)
    written = len(json_data)
    print(f"verification.json written: {written} bytes; numerical_pass={numerical_pass}; "
          f"branch={branch}; npz_written={npz_written}; verdicts="
          + json.dumps(verdicts, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Independent verifier for the frozen cascade-size normalization test.")
    parser.add_argument("--input", required=True,
                        help="directory holding the primary results.json and artifacts")
    parser.add_argument("--output", required=True,
                        help="fresh output directory for verification.json and artifacts")
    parser.add_argument("--prereg", default=str(DEFAULT_PREREG),
                        help="path to the frozen preregistration markdown")
    args = parser.parse_args()
    try:
        return run(args)
    except TypedFailure as failure:
        try:
            output_dir = Path(args.output).resolve()
            if not output_dir.exists():
                output_dir.mkdir(parents=True)
            elif output_dir.is_dir() and any(output_dir.iterdir()):
                print(f"cannot retain typed failure receipt: {output_dir} nonempty",
                      file=sys.stderr)
                return 2
            write_failure_only(output_dir, failure.kind, failure.detail)
        except Exception:
            print("typed failure receipt could not be retained", file=sys.stderr)
        print(f"typed failure: {failure.kind}: {failure.detail}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"output contract failure: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # last-resort typed receipt
        detail = f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=5)}"
        try:
            output_dir = Path(args.output).resolve()
            if not output_dir.exists():
                output_dir.mkdir(parents=True)
            if output_dir.is_dir() and not any(output_dir.iterdir()):
                write_failure_only(output_dir, "UnexpectedVerifierError", detail)
        except Exception:
            print("unexpected verifier failure receipt could not be retained", file=sys.stderr)
        print(f"unexpected verifier error: {detail[:400]}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
