#!/usr/bin/env python3
"""Independent coordinate branch for notebook section 70 quantum transfer.

This program derives every matrix element from the coordinate-space potential
by normalized Hermite and Laguerre quadrature: the even-mediator functions of
frequency m, and the carrier radial functions sqrt(w/pi)*(-1)^n*exp(-w r^2/2)
L_n(w r^2) under the measure 2*pi*r dr, which makes the r^2 off-diagonal
positive. All operator polynomials (S^4 and r^4 as unprojected coordinate
multiplication operators on the padded ((J+2)*(N+2)) grid, never as squares of
already-truncated matrices) are formed before projection; the discarded image
R = H_extended[outer, inner] is retained in full. The ground state comes from
this program's own sparse eigensolver; time and source evolution use the sparse
exponential action scipy.sparse.linalg.expm_multiply from the initial state,
with no re-projection, renormalization or state repair. The U = exp(-i delta D)
sign is the one whose coordinate action is
(U psi)(S) = exp(-delta/2) psi(exp(-delta) S), dilating S by F = sqrt(3/2).
The primary program, the residual auditor and every prior scientific
implementation are digested as bytes only; they are never imported, executed
or parsed. Band masking uses only the exact theoretical support of each
polynomial (|delta index| <= 1 for quadratic generators, <= 2 for quartic,
= 1 for the dilation generator); roundoff outside an analytically allowed
band is zeroed structurally, and no threshold is ever applied inside a
physical band.

python computations/verify_matter_formation_quantum_backreaction.py \
    --manifest PATH --output FRESH_DIR
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
import scipy
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import eigsh, expm_multiply

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = "computations/matter-formation-continuum-report.md"
SECTION_HEADINGS = (
    "## 25. Autonomous mediator oscillation in the scalar parent",
    "## 64. Working notes: matching quantum conversion to the scalar action",
    "## 70. Working notes: autonomous quantum transfer with the full scalar interaction",
)
SOURCE_PATHS = (
    "computations/matter_formation_quantum_backreaction.py",
    "computations/verify_matter_formation_quantum_backreaction.py",
    "computations/verify_matter_formation_quantum_residuals.py",
    "foundations/particle-stationary-action-closure.md",
)
INHERITED_PATHS = {
    "runs/20260907_matter_formation_autonomous_pump/results.json":
        "cad33ef760404c79807570be1269390dfb790574dc13bfe60d61d67c5b1bc9c5",
    "runs/20260907_matter_formation_autonomous_pump_verification/results.json":
        "a54c07d1a973f9a915355e26b7c23e7caa7ee75a468f09fda53e13a272959758",
}
PUMP_VERDICT = ("SUPPORTS\u2014neutral linear parametric amplification in the "
                "supplied temporal parent")
K_WITNESS = 2.675336705149658
HC_INHERITED = 2.9598260763447164

MANIFEST_SCHEMA = "matter-formation-quantum-backreaction-manifest-v1"
RESULT_SCHEMA = "matter-formation-quantum-backreaction-v1"
ROLE = "coordinate"
REVIEW_ROLES = {"coordinate", "residuals"}
VERDICT_AWAITING = "INCONCLUSIVE-awaiting joint quantum transfer qualification"
VERDICT_INCONCLUSIVE = "INCONCLUSIVE"

N_ACTION = 4
A = 1.0 / 16.0
C_PSI = 1.0 / 8.0
U_RHO = 4.0
U_C = 1.0
K_CX = 1.0
E_C = 3.0 / 4.0
B = E_C + 1.0 / (4.0 * A)
V_BOX = (2.0 * math.pi / K_WITNESS) ** 3
ETA = N_ACTION * V_BOX
V2 = ETA * C_PSI
M_MASS = math.sqrt(2.0 * U_RHO / C_PSI)
M_SQ = M_MASS * M_MASS
W_FREQ = math.sqrt((B + K_CX * K_WITNESS * K_WITNESS / 2.0) / A)
F_DIL = math.sqrt(3.0 / 2.0)
DELTA = math.log(F_DIL)

T_END = 16.0
N_TIMES = 513
N_SOURCE = 257
ROWS_SCHEDULE = (
    ("coupled_48_12", 48, 12, HC_INHERITED, DELTA),
    ("coupled_64_16", 64, 16, HC_INHERITED, DELTA),
    ("coupled_80_20", 80, 20, HC_INHERITED, DELTA),
    ("zero_pump_80_20", 80, 20, HC_INHERITED, 0.0),
    ("uncoupled_80_20", 80, 20, 0.0, DELTA),
)

GUARD_TOL = 1.0e-10
RECONSTRUCT_BOUND = 1.0e-9


# ---------------------------------------------------------------------------
# byte-identity guards, executed before any scientific reconstruction
# ---------------------------------------------------------------------------

def canonical_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def canonical_sha256(path: Path) -> str:
    return hashlib.sha256(canonical_bytes(path)).hexdigest()


def raw_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def within(base: Path, candidate: Path) -> Path:
    resolved = candidate.resolve()
    if resolved != base and base not in resolved.parents:
        raise ValueError(f"path escapes its sealed directory: {candidate}")
    if not resolved.is_file():
        raise ValueError(f"bound file missing: {candidate}")
    return resolved


def repo_file(relative: str) -> Path:
    if not relative or relative.startswith("/") or relative.startswith("\\") \
            or Path(relative).is_absolute():
        raise ValueError(f"path must be root-relative: {relative}")
    return within(ROOT, ROOT / relative)


def strict_json(path: Path):
    def pairs(pairs_in):
        out = {}
        for key, value in pairs_in:
            if key in out:
                raise ValueError(f"duplicate JSON key: {key}")
            out[key] = value
        return out

    def constant(value):
        raise ValueError(f"non-finite JSON constant: {value}")

    return json.loads(path.read_text(encoding="utf-8"),
                      object_pairs_hook=pairs, parse_constant=constant)


def section_bytes(text: str, heading: str) -> bytes:
    if text.count("\n" + heading + "\n") != 1:
        raise ValueError(f"heading must occur exactly once: {heading}")
    start = text.index("\n" + heading + "\n") + 1
    boundary = re.compile(r"\n(?=## )").search(text, start + len(heading) + 1)
    end = boundary.start() + 1 if boundary else len(text)
    return (text[start:end].rstrip() + "\n").encode("utf-8")


def _entry_row(row, keys):
    if not isinstance(row, dict):
        raise ValueError("manifest entry must be an object")
    if set(row) != set(keys):
        raise ValueError(f"manifest entry keys must be exactly {keys}")


def validate_manifest(manifest_path: Path) -> dict:
    manifest = strict_json(manifest_path)
    _entry_row(manifest, ("schema", "sections", "sources", "inherited",
                          "mathematical_reviews"))
    if manifest["schema"] != MANIFEST_SCHEMA:
        raise ValueError("unexpected manifest schema")
    for key in ("sections", "sources", "inherited", "mathematical_reviews"):
        if not isinstance(manifest[key], list):
            raise ValueError(f"manifest {key} must be a list")
    notebook_text = canonical_bytes(repo_file(NOTEBOOK)).decode("utf-8")

    sections = manifest["sections"]
    if len(sections) != len(SECTION_HEADINGS):
        raise ValueError("sections must cover exactly the three bound headings")
    if sorted(row["heading"] for row in sections) != sorted(SECTION_HEADINGS):
        raise ValueError("section heading coverage is incorrect or duplicated")
    for row in sections:
        _entry_row(row, ("path", "heading", "snapshot", "sha256"))
        if row["path"] != NOTEBOOK or row["heading"] not in SECTION_HEADINGS:
            raise ValueError(f"unexpected section binding: {row['heading']}")
        live = section_bytes(notebook_text, row["heading"])
        snapshot = repo_file(row["snapshot"])
        if hashlib.sha256(live).hexdigest() != row["sha256"] \
                or canonical_bytes(snapshot) != live:
            raise ValueError(f"section bytes mismatch: {row['heading']}")

    sources = manifest["sources"]
    if len(sources) != len(SOURCE_PATHS) or \
            sorted(row["path"] for row in sources) != sorted(SOURCE_PATHS):
        raise ValueError("sources must cover exactly the four bound paths")
    for row in sources:
        _entry_row(row, ("path", "snapshot", "sha256"))
        live = repo_file(row["path"])
        snapshot = repo_file(row["snapshot"])
        digest = canonical_sha256(live)
        if digest != row["sha256"] or canonical_sha256(snapshot) != digest:
            raise ValueError(f"source mismatch: {row['path']}")

    inherited = manifest["inherited"]
    if len(inherited) != 2 or \
            sorted(row["path"] for row in inherited) != sorted(INHERITED_PATHS):
        raise ValueError("inherited receipts must cover exactly the two bound paths")
    pinned = []
    for row in inherited:
        _entry_row(row, ("path", "snapshot", "sha256"))
        expected = INHERITED_PATHS[row["path"]]
        if row["sha256"] != expected:
            raise ValueError(f"inherited hash not pinned: {row['path']}")
        live = repo_file(row["path"])
        snapshot = repo_file(row["snapshot"])
        if raw_sha256(live) != expected or raw_sha256(snapshot) != expected:
            raise ValueError(f"inherited raw bytes mismatch: {row['path']}")
        pinned.append({"path": row["path"], "raw_sha256": expected})

    reviews = manifest["mathematical_reviews"]
    if len(reviews) != 2 or {row.get("role") for row in reviews} != REVIEW_ROLES:
        raise ValueError("mathematical reviews must cover exactly the two roles")
    for row in reviews:
        _entry_row(row, ("role", "accepted", "snapshot", "sha256"))
        if row["accepted"] is not True:
            raise ValueError(f"mathematical review not accepted: {row['role']}")
        snapshot = repo_file(row["snapshot"])
        if canonical_sha256(snapshot) != row["sha256"]:
            raise ValueError(f"review snapshot hash mismatch: {row['role']}")
        lines = canonical_bytes(snapshot).decode("utf-8").splitlines()
        accepted_lines = [line for line in lines
                          if re.fullmatch(r"accepted: (true|false)", line)]
        if len(accepted_lines) != 1 or accepted_lines[0] != "accepted: true":
            raise ValueError(
                f"review must carry exactly one accepted line: {row['role']}")

    # Scientific prerequisites of the two inherited receipts, validated before
    # k is used. Nothing is rerun; only these bound receipts are read.
    primary = strict_json(repo_file(
        "runs/20260907_matter_formation_autonomous_pump/results.json"))
    verification = strict_json(repo_file(
        "runs/20260907_matter_formation_autonomous_pump_verification/results.json"))
    for receipt in (primary, verification):
        if receipt.get("passed") is not True or receipt.get("qualified") is not True:
            raise ValueError("inherited receipt did not pass and qualify")
        if receipt.get("verdict") != PUMP_VERDICT:
            raise ValueError("inherited verdict is not the specified SUPPORTS verdict")
    gap3 = [row for row in primary.get("gaps", []) if row.get("j") == 3]
    if len(gap3) != 1 or gap3[0].get("accessible") is not True \
            or gap3[0].get("retained") is not True \
            or float(gap3[0].get("k")) != K_WITNESS:
        raise ValueError("primary gap-3 witness is not the retained pinned wave number")
    for receipt in (primary, verification):
        wit3 = [row for row in receipt.get("witnesses", []) if row.get("j") == 3]
        if len(wit3) != 1 or wit3[0].get("passed") is not True \
                or float(wit3[0].get("k")) != K_WITNESS:
            raise ValueError("witness j=3 is not a passed pinned-k entry in both receipts")
    if verification.get("mismatches") != []:
        raise ValueError("independent verification mismatches are not empty")
    return {"manifest_raw_sha256": raw_sha256(manifest_path),
            "sections": manifest["sections"], "sources": manifest["sources"],
            "inherited": pinned, "mathematical_reviews": reviews,
            "k": K_WITNESS}


# ---------------------------------------------------------------------------
# own normalized-Hermite / Laguerre quadrature construction
# ---------------------------------------------------------------------------

def hermite_functions(y, qmax, gaussian=True):
    """psi_q(y), q = 0..qmax: normalized unit-frequency oscillator functions
    psi_q = (2^q q! sqrt(pi))^{-1/2} H_q(y) exp(-y^2/2), by the stable
    three-term recurrence psi_{k+1} = sqrt(2/(k+1)) y psi_k
    - sqrt(k/(k+1)) psi_{k-1}. With gaussian=False the shared factor
    exp(-y^2/2) is omitted, returning the normalized polynomial factor
    chi_q = psi_q * exp(y^2/2); the recurrence is linear and homogeneous, so
    it holds verbatim for chi, whose zeros coincide with psi's."""
    y = np.asarray(y, dtype=np.float64)
    psi = np.zeros((y.size, qmax + 1))
    psi[:, 0] = math.pi ** -0.25 * (np.exp(-0.5 * y * y) if gaussian else 1.0)
    if qmax >= 1:
        psi[:, 1] = math.sqrt(2.0) * y * psi[:, 0]
    for k in range(1, qmax):
        psi[:, k + 1] = math.sqrt(2.0 / (k + 1)) * y * psi[:, k] \
            - math.sqrt(k / (k + 1.0)) * psi[:, k - 1]
    return psi


def hermite_derivatives(psi, qmax):
    """psi_q'(y) from the exact identity psi_q' = sqrt(q/2) psi_{q-1}
    - sqrt((q+1)/2) psi_{q+1}."""
    dpsi = np.zeros_like(psi)
    for k in range(0, qmax + 1):
        left = math.sqrt(k / 2.0) * psi[:, k - 1] if k >= 1 else 0.0
        right = math.sqrt((k + 1) / 2.0) * psi[:, k + 1] \
            if k + 1 <= qmax else 0.0
        dpsi[:, k] = left - right
    return dpsi


def gauss_hermite_nodes_weights(Q):
    """Own Q-point Gauss rule for the weight exp(-y^2) on the real line.
    Nodes: the Q simple zeros of psi_Q, found by dense-grid bracketing plus
    80 bisections each, so no asymptotic starting guess is trusted. Weights:
    w_k = exp(-x_k^2) / (Q psi_{Q-1}(x_k)^2) (Szego, normalized form),
    witnessed below against the exact monomial moments of the weight."""
    assert Q % 2 == 0 and Q >= 4
    mu = 2 * Q + 1
    lim = 1.02 * math.sqrt(mu)
    grid = np.linspace(-lim, lim, 20001)
    psi = hermite_functions(grid, Q)
    f = psi[:, Q]
    if f[0] * f[-1] <= 0.0:
        raise ValueError("Gauss-Hermite bracket endpoints must share a sign")
    brackets = np.nonzero(np.diff(np.signbit(f)).astype(int))[0]
    if len(brackets) != Q:
        raise ValueError(f"hermite node brackets {len(brackets)} != Q {Q}")
    nodes = np.empty(Q)
    for idx, lo in enumerate(brackets):
        a, b = float(grid[lo]), float(grid[lo + 1])
        fa = float(f[lo])
        for _ in range(80):
            mid = 0.5 * (a + b)
            fm = float(hermite_functions(np.array([mid]), Q)[0, Q])
            if fm == 0.0 or (fm < 0.0) == (fa < 0.0):
                a, fa = mid, fm
            else:
                b = mid
        nodes[idx] = 0.5 * (a + b)
    nodes.sort()
    weights = np.empty(Q)
    for idx, x in enumerate(nodes):
        psi_last = float(hermite_functions(np.array([x]), Q - 1)[0, Q - 1])
        weights[idx] = math.exp(
            -x * x - math.log(Q) - 2.0 * math.log(abs(psi_last)))
    sqrt_pi = math.sqrt(math.pi)
    m0 = float(np.sum(weights))
    m2 = float(np.sum(weights * nodes * nodes))
    m4 = float(np.sum(weights * nodes ** 4))
    if abs(m0 - sqrt_pi) > 1e-12 * sqrt_pi \
            or abs(m2 - 0.5 * sqrt_pi) > 1e-12 * sqrt_pi \
            or abs(m4 - 0.75 * sqrt_pi) > 1e-12 * sqrt_pi:
        raise ValueError("Gauss-Hermite rule failed its exact monomial moments")
    if np.any(weights <= 0.0) or np.any(np.diff(nodes) <= 0.0):
        raise ValueError("Gauss-Hermite rule produced nonpositive weights")
    return nodes, weights


def laguerre_rule(QL):
    """Gauss-Laguerre rule for weight exp(-x) on [0, inf); QL <= 24 here, far
    below the documented high-degree accuracy limit. Witnessed against the
    exact factorial moments int e^{-x} x^p = p!."""
    x, w = np.polynomial.laguerre.laggauss(QL)
    if abs(float(np.sum(w)) - 1.0) > 1e-12:
        raise ValueError("Gauss-Laguerre zeroth moment failed")
    fact = 1.0
    for power in range(1, QL):
        fact *= power
        if abs(float(np.sum(w * x ** power)) - fact) > 1e-9 * fact:
            raise ValueError(f"Gauss-Laguerre factorial moment failed at {power}")
    return x, w


def laguerre_values(x, nmax):
    L = np.zeros((x.size, nmax + 1))
    L[:, 0] = 1.0
    if nmax >= 1:
        L[:, 1] = 1.0 - x
    for k in range(1, nmax):
        L[:, k + 1] = ((2 * k + 1 - x) * L[:, k] - k * L[:, k - 1]) / (k + 1)
    return L


def band_mask(matrix, width, scale, name, checks):
    """Zero the analytically forbidden outer band; witness first that its raw
    quadrature roundoff is negligible relative to the matrix scale."""
    size = matrix.shape[0]
    off = 0.0
    for i in range(size):
        for j in range(size):
            if abs(i - j) > width:
                off = max(off, float(abs(matrix[i, j])))
    checks[name + "_band_support"] = bool(off <= GUARD_TOL * max(1.0, scale))
    masked = matrix.copy()
    for delta in range(width + 1, size):
        idx = np.arange(size - delta)
        masked[idx, idx + delta] = 0.0
        masked[idx + delta, idx] = 0.0
    return masked


def rel_err(matrix, closed, name, checks):
    scale = float(np.max(np.abs(closed))) if closed.size else 1.0
    err = float(np.max(np.abs(matrix - closed))) if matrix.size else 0.0
    checks[name + "_matches_closed_form"] = bool(err <= GUARD_TOL * max(1.0, scale))
    return err


def build_mediator_operators(J, checks):
    """Even-occupation (full occupation 2j) matrices of S^2, S^4, p_S^2 and D
    on the padded j = 0..J+1 grid. With y = sqrt(m) S the coordinate matrix
    elements are integrals of psi products over dy; the program integrates
    the Gaussian-stripped factors chi_q = psi_q exp(y^2/2) and
    Psi'_q = psi_q' exp(y^2/2) (the derivative identity psi_q' =
    sqrt(q/2) psi_{q-1} - sqrt((q+1)/2) psi_{q+1} is the same homogeneous
    combination of chi) with the exp(-y^2) Gauss rule, so each weighted sum
    is exactly int psi_i (polynomial) psi_j dy; then
    <S^p> = m^{-p/2} <y^p>_psi and <p_S^2> = m <psi_i'|psi_j'>, while
    D = -i (y d/dy + 1/2) in the y representation."""
    E = J + 2
    Q = 2 * J + 6
    y, w = gauss_hermite_nodes_weights(Q)
    psi = hermite_functions(y, 2 * E + 1, gaussian=False)
    dpsi = hermite_derivatives(psi, 2 * E + 1)
    even = np.arange(0, 2 * E, 2)
    phi = psi[:, even]
    dphi = dpsi[:, even]
    prefix = f"J{J}_"

    def quad_sym(left, right):
        matrix = left.T @ (right * w[:, None])
        return 0.5 * (matrix + matrix.T)

    def quad_anti(right):
        matrix = phi.T @ (right * w[:, None])
        return 0.5 * (matrix - matrix.T)

    s2_raw = quad_sym(phi, phi * (y * y)[:, None]) / M_MASS
    ps2_raw = M_MASS * quad_sym(dphi, dphi)
    s4_raw = quad_sym(phi, phi * (y ** 4)[:, None]) / M_SQ
    d_raw = quad_anti(y[:, None] * dphi + 0.5 * phi)
    s2 = band_mask(s2_raw, 1, float(np.max(np.abs(s2_raw))), prefix + "S2", checks)
    ps2 = band_mask(ps2_raw, 1, float(np.max(np.abs(ps2_raw))), prefix + "PS2", checks)
    s4 = band_mask(s4_raw, 2, float(np.max(np.abs(s4_raw))), prefix + "S4", checks)
    d_matrix = band_mask(-1j * d_raw, 1, float(np.max(np.abs(d_raw))),
                         prefix + "D", checks)
    d_matrix = 0.5 * (d_matrix + d_matrix.conj().T)

    j = np.arange(E)
    q = 2.0 * j
    diag = lambda matrix: np.diag(np.asarray(matrix, np.float64))
    upper = lambda matrix, offset: np.asarray(
        [matrix[i, i + offset] for i in range(E - offset)])
    s2_closed = (2 * j + 0.5) / M_MASS
    s2_off_closed = np.sqrt((q + 1) * (q + 2)) / (2 * M_MASS)
    ps2_closed = M_MASS * (2 * j + 0.5)
    ps2_off_closed = -M_MASS * np.sqrt((q + 1) * (q + 2)) / 2.0
    s4_diag_closed = 3 * (2 * q * q + 2 * q + 1) / (4 * M_SQ)
    s4_off1_closed = (4 * q + 6) * np.sqrt((q + 1) * (q + 2)) / (4 * M_SQ)
    s4_off2_closed = np.sqrt((q + 1) * (q + 2) * (q + 3) * (q + 4)) / (4 * M_SQ)
    d_closed = 1j * np.sqrt((q + 1) * (q + 2)) / 2.0
    rel_err(diag(s2), s2_closed, prefix + "S2_diag", checks)
    rel_err(upper(s2, 1), s2_off_closed[:-1], prefix + "S2_offdiag", checks)
    rel_err(diag(ps2), ps2_closed, prefix + "PS2_diag", checks)
    rel_err(upper(ps2, 1), ps2_off_closed[:-1], prefix + "PS2_offdiag", checks)
    rel_err(diag(s4), s4_diag_closed, prefix + "S4_diag", checks)
    rel_err(upper(s4, 1), s4_off1_closed[:-1], prefix + "S4_offdiag1", checks)
    rel_err(upper(s4, 2), s4_off2_closed[:-2], prefix + "S4_offdiag2", checks)
    rel_err(np.abs(np.diag(d_matrix)), np.zeros(E), prefix + "D_diag", checks)
    rel_err(upper(d_matrix, 1).conjugate(), d_closed[:-1],
            prefix + "D_raising", checks)
    # Unprojected-power identity: S4 = (S2 on the padded grid)^2 for
    # (rows <= J+1, columns <= J-1) because intermediates reach only j <= J.
    s4_identity = s2 @ s2
    rel_err(s4[:J, :J], s4_identity[:J, :J], prefix + "S4_squared_identity", checks)
    return s2, s4, ps2, d_matrix


def build_carrier_operators(N, checks):
    """<r^2>, <r^4> on the padded n = 0..N+1 grid from the normalized radial
    functions sqrt(w/pi)(-1)^n exp(-w r^2/2) L_n(w r^2) with measure
    2 pi r dr: <r^{2p}> = (-1)^{n+n'} w^{-p} int e^{-x} x^p L_n L_{n'} dx."""
    E = N + 2
    QL = N + 4
    x, w = laguerre_rule(QL)
    L = laguerre_values(x, E - 1)
    parity = np.where(((np.arange(E)[:, None] + np.arange(E)[None, :]) % 2) == 1,
                      -1.0, 1.0)
    prefix = f"N{N}_"

    def quad(power):
        matrix = parity * (L.T @ ((x ** power * w)[:, None] * L))
        return 0.5 * (matrix + matrix.T)

    r2_raw = quad(1) / W_FREQ
    r4_raw = quad(2) / (W_FREQ * W_FREQ)
    r2 = band_mask(r2_raw, 1, float(np.max(np.abs(r2_raw))), prefix + "R2", checks)
    r4 = band_mask(r4_raw, 2, float(np.max(np.abs(r4_raw))), prefix + "R4", checks)
    n = np.arange(E, dtype=np.float64)
    diag = lambda matrix: np.diag(np.asarray(matrix, np.float64))
    upper = lambda matrix, offset: np.asarray(
        [matrix[i, i + offset] for i in range(E - offset)])
    rel_err(diag(r2), (2 * n + 1) / W_FREQ, prefix + "R2_diag", checks)
    rel_err(upper(r2, 1), (n[:-1] + 1) / W_FREQ, prefix + "R2_offdiag", checks)
    rel_err(diag(r4), (6 * n * n + 6 * n + 2) / (W_FREQ * W_FREQ),
            prefix + "R4_diag", checks)
    rel_err(upper(r4, 1), 4 * (n[:-1] + 1) ** 2 / (W_FREQ * W_FREQ),
            prefix + "R4_offdiag1", checks)
    rel_err(upper(r4, 2), (n[:-2] + 1) * (n[:-2] + 2) / (W_FREQ * W_FREQ),
            prefix + "R4_offdiag2", checks)
    r4_identity = r2 @ r2
    rel_err(r4[:N, :N], r4_identity[:N, :N], prefix + "R4_squared_identity", checks)
    return r2, r4


# ---------------------------------------------------------------------------
# Hamiltonian assembly on the padded grid
# ---------------------------------------------------------------------------

def assemble(J, N, h, ops_m, ops_c):
    """H = pS^2/2 + m^2/(8 v^2)(S^4 - 2 v^2 S^2 + v^4 I) + HC0
       + h/(2a)(S^2/v^2 - I) (x) R^2 + uC/(8 eta a^2) I (x) R^4,
    formed entirely on the padded (J+2)x(N+2) grid (q-major j*(N+2)+n), then
    cut into HP = P H P and the discarded image R = (1-P) H P."""
    s2e, s4e, ps2e, de = ops_m
    r2e, r4e = ops_c
    JE, NE = J + 2, N + 2
    eye_j = np.eye(JE)
    eye_n = np.eye(NE)
    mediator = 0.5 * ps2e + (M_SQ / (8.0 * V2)) * (
        s4e - 2.0 * V2 * s2e + (V2 * V2) * eye_j)
    carrier = np.diag(W_FREQ * (2.0 * np.arange(NE) + 1.0)) \
        + (U_C / (8.0 * ETA * A * A)) * r4e
    hext = np.kron(mediator, eye_n) + np.kron(eye_j, carrier) \
        + (h / (2.0 * A)) * np.kron(s2e / V2 - eye_j, r2e)
    if float(np.max(np.abs(hext - hext.T))) != 0.0:
        raise ValueError("extended Hamiltonian is not exactly symmetric")
    inner = np.array([j * NE + n for j in range(J) for n in range(N)],
                     dtype=np.int64)
    outer = np.array([idx for idx in range(JE * NE)
                      if idx not in set(inner.tolist())], dtype=np.int64)
    if len(inner) != J * N or len(outer) != 2 * J + 2 * N + 4:
        raise ValueError("extended basis partition count failed")
    hp = hext[np.ix_(inner, inner)]
    rmat = hext[np.ix_(outer, inner)]
    dproj = np.kron(de[:J, :J], np.eye(N))
    if float(np.max(np.abs(dproj - dproj.conj().T))) != 0.0:
        raise ValueError("projected dilation generator is not exactly Hermitian")
    return hext, inner, outer, hp, rmat, dproj


def lowest_state(hp_dense):
    initial = np.zeros(hp_dense.shape[0])
    initial[0] = 1.0
    values, vectors = eigsh(csr_matrix(hp_dense), k=1, which="SA", tol=0.0,
                            v0=initial)
    ground = np.asarray(vectors[:, 0], dtype=np.float64)
    if ground[0] < 0.0:
        ground = -ground
    return float(values[0]), ground


# ---------------------------------------------------------------------------
# row computation: ground, source path, time evolution, observables
# ---------------------------------------------------------------------------

def compute_row(key, J, N, h, delta, cache, checks):
    if J not in cache["mediator"]:
        cache["mediator"][J] = build_mediator_operators(J, checks)
    if N not in cache["carrier"]:
        cache["carrier"][N] = build_carrier_operators(N, checks)
    ops_m, ops_c = cache["mediator"][J], cache["carrier"][N]
    built_key = (J, N, h)
    if built_key not in cache["built"]:
        hext, inner, outer, hp, rmat, dproj = assemble(J, N, h, ops_m, ops_c)
        eig_value, ground = lowest_state(hp)
        cache["built"][built_key] = {
            "inner": inner, "outer": outer, "hp": hp,
            "hp_csr": csr_matrix(hp), "r_csr": csr_matrix(rmat),
            "dproj": dproj, "eig_value": eig_value, "ground": ground,
            "hext": hext,
        }
    built = cache["built"][built_key]
    for name in ("hp_csr", "r_csr"):
        built[name].sort_indices()
    dim = J * N
    ground = built["ground"]
    eig_value = built["eig_value"]
    hp = built["hp"]

    # full-space ground residual ||(H - Eg) g|| including the discarded image
    padded_ground = np.zeros((J + 2) * (N + 2))
    padded_ground[built["inner"]] = ground
    residual_vector = built["hext"] @ padded_ground - eig_value * padded_ground
    ground_full_residual = float(np.linalg.norm(residual_vector))

    # source path U(tau) = exp(-i tau D_P) g on [0, delta]; delta = 0 is the
    # identity, kept as its own mathematically exact branch
    source_times = np.linspace(0.0, delta, N_SOURCE)
    if delta == 0.0:
        source_states = np.tile(ground.astype(np.complex128), (N_SOURCE, 1))
    else:
        source_states = expm_multiply(
            csr_matrix(-1j * built["dproj"]), ground,
            start=0.0, stop=delta, num=N_SOURCE, endpoint=True)
    prepared = np.asarray(source_states[-1], dtype=np.complex128)

    # time evolution exp[-i (HP - Eg) t] from the prepared state, no repair
    times = np.linspace(0.0, T_END, N_TIMES)
    shifted = csr_matrix(hp - eig_value * np.eye(dim), dtype=np.float64)
    states = np.asarray(expm_multiply(
        -1j * shifted, prepared, start=0.0, stop=T_END, num=N_TIMES,
        endpoint=True), dtype=np.complex128)

    # observables from the raw states, unnormalized expectations
    eye_j, eye_n = np.eye(J), np.eye(N)
    s2d = np.kron(ops_m[0][:J, :J], eye_n)
    s4d = np.kron(ops_m[1][:J, :J], eye_n)
    ps2d = np.kron(ops_m[2][:J, :J], eye_n)
    r4d = np.kron(eye_j, ops_c[1][:N, :N])
    hc0d = np.kron(eye_j, np.diag(W_FREQ * (2.0 * np.arange(N) + 1.0)))
    nd = np.kron(eye_j, np.diag(np.arange(N, dtype=np.float64)))
    mixd = np.kron(ops_m[0][:J, :J] / V2 - eye_j, ops_c[0][:N, :N])
    mixed_coeff = h / (2.0 * A)
    quartic_coeff = U_C / (8.0 * ETA * A * A)
    med_coeff = M_SQ / (8.0 * V2)

    def csr_expect(op, batch):
        applied = csr_matrix(op).dot(batch.T)
        return np.einsum("ti,ti->t", batch.conj(), applied.T).real

    def dense_expect(op, batch):
        row, column = np.nonzero(op)
        value = np.zeros(batch.shape[0])
        for offset in np.unique(column - row):
            first = max(0, -int(offset))
            last = min(op.shape[0], op.shape[0] - int(offset))
            value += np.einsum(
                "ti,i,ti->t", batch[:, first:last].conj(),
                np.diagonal(op, offset=int(offset)),
                batch[:, first + offset:last + offset]).real
        return value

    norms = np.einsum("ti,ti->t", states.conj(), states).real
    exp_s2 = csr_expect(s2d, states)
    exp_s4 = csr_expect(s4d, states)
    exp_ps2 = csr_expect(ps2d, states)
    exp_r4 = csr_expect(r4d, states)
    exp_hc0 = csr_expect(hc0d, states)
    f2 = exp_s2 / V2
    pairs = csr_expect(nd, states)
    pair_probability = (np.abs(states) ** 2).reshape(N_TIMES, J, N)[:, :, 1:] \
        .sum(axis=(1, 2))
    exp_mix = csr_expect(mixd, states)

    energy_terms = np.zeros((N_TIMES, 4))
    energy_terms[:, 0] = 0.5 * exp_ps2 + med_coeff * (
        exp_s4 - 2.0 * V2 * exp_s2 + (V2 * V2) * norms)
    energy_terms[:, 1] = exp_hc0
    energy_terms[:, 2] = quartic_coeff * exp_r4
    energy_terms[:, 3] = mixed_coeff * exp_mix
    totals = energy_terms.sum(axis=1)
    initial_energy = float(totals[0])
    norm_error = float(np.max(np.abs(norms - 1.0)))
    energy_error = float(np.max(np.abs(totals - initial_energy))
                         / max(1.0, abs(initial_energy)))

    # second-pass reconstruction of every array through dense band products
    recon_norms = np.sum(np.abs(states) ** 2, axis=1)
    recon_s2 = dense_expect(s2d, states)
    recon_terms = np.zeros_like(energy_terms)
    recon_terms[:, 0] = 0.5 * dense_expect(ps2d, states) + med_coeff * (
        dense_expect(s4d, states) - 2.0 * V2 * recon_s2 + (V2 * V2) * recon_norms)
    recon_terms[:, 1] = dense_expect(hc0d, states)
    recon_terms[:, 2] = quartic_coeff * dense_expect(r4d, states)
    recon_terms[:, 3] = mixed_coeff * dense_expect(mixd, states)
    recon_pairs = dense_expect(nd, states)
    recon_f2 = recon_s2 / V2
    recon_pair_probability = recon_norms \
        - np.sum(np.abs(states[:, np.arange(J) * N]) ** 2, axis=1)

    def max_relative(a, b):
        return float(np.max(np.abs(a - b) / np.maximum(1.0, np.abs(b))))

    reconstruction_error = max(
        max_relative(norms, recon_norms),
        max_relative(energy_terms, recon_terms),
        max_relative(f2, recon_f2),
        max_relative(pairs, recon_pairs),
        max_relative(pair_probability, recon_pair_probability))

    ground_pair_probability = float(
        (ground ** 2).reshape(J, N)[:, 1:].sum())
    hp_prepared_expectation = float(
        np.real(np.vdot(prepared, built["hp_csr"] @ prepared)))
    preparation_work = hp_prepared_expectation - eig_value
    peak_pair_probability_gain = float(
        np.max(pair_probability) - ground_pair_probability)

    source_pair_probability = (np.abs(source_states) ** 2) \
        .reshape(N_SOURCE, J, N)[:, :, 1:].sum(axis=(1, 2))
    source_norms = np.einsum("ti,ti->t", source_states.conj(), source_states).real
    carrier_invariance = float(np.max(np.abs(source_pair_probability
                                             - ground_pair_probability)))
    source_norm_error = float(np.max(np.abs(source_norms - 1.0)))

    checks[f"{key}_norm_bound"] = bool(norm_error <= 1.0e-10)
    checks[f"{key}_energy_bound"] = bool(energy_error <= 1.0e-9)
    checks[f"{key}_reconstruction_bound"] = bool(
        reconstruction_error <= RECONSTRUCT_BOUND)
    checks[f"{key}_source_carrier_invariance"] = bool(carrier_invariance <= 1.0e-12)
    checks[f"{key}_source_norm_bound"] = bool(source_norm_error <= 1.0e-10)
    checks[f"{key}_ground_sign"] = bool(ground[0] > 0.0)
    checks[f"{key}_ground_normalized"] = bool(
        abs(float(np.linalg.norm(ground)) - 1.0) <= 1e-12)
    checks[f"{key}_initial_energy_consistency"] = bool(
        abs(hp_prepared_expectation - initial_energy)
        <= 1e-10 * max(1.0, abs(initial_energy)))
    checks[f"{key}_grid_times_exact"] = bool(
        np.array_equal(times, np.linspace(0.0, T_END, N_TIMES))
        and np.array_equal(source_times, np.linspace(0.0, delta, N_SOURCE))
        and states.shape == (N_TIMES, dim)
        and source_states.shape == (N_SOURCE, dim))
    finite_arrays = all(np.all(np.isfinite(array)) for array in (
        times, states, ground, prepared, source_times, source_states, norms,
        energy_terms, f2, pairs, pair_probability, ops_m[0], ops_m[1], ops_m[2],
        ops_m[3], ops_c[0], ops_c[1], hp, built["r_csr"].data, built["dproj"]))
    checks[f"{key}_finite"] = bool(finite_arrays)

    hp_csr = built["hp_csr"]
    r_csr = built["r_csr"]
    archive = {
        "time": times, "state": states, "ground": ground, "prepared": prepared,
        "source_time": source_times, "source_state": source_states,
        "ground_energy": np.asarray(eig_value, dtype=np.float64),
        "norm": norms, "energy_terms": energy_terms, "f2": f2, "pairs": pairs,
        "pair_probability": pair_probability,
        "S2": ops_m[0][:J, :J].astype(np.complex128),
        "S4": ops_m[1][:J, :J].astype(np.complex128),
        "PS2": ops_m[2][:J, :J].astype(np.complex128),
        "R2": ops_c[0][:N, :N].astype(np.complex128),
        "R4": ops_c[1][:N, :N].astype(np.complex128),
        "D": ops_m[3][:J, :J].astype(np.complex128),
        "H_data": np.asarray(hp_csr.data, dtype=np.float64),
        "H_indices": np.asarray(hp_csr.indices),
        "H_indptr": np.asarray(hp_csr.indptr),
        "H_shape": np.asarray(hp_csr.shape, dtype=np.int64),
        "R_data": np.asarray(r_csr.data, dtype=np.float64),
        "R_indices": np.asarray(r_csr.indices),
        "R_indptr": np.asarray(r_csr.indptr),
        "R_shape": np.asarray(r_csr.shape, dtype=np.int64),
        "inner_indices": built["inner"], "outer_indices": built["outer"],
    }
    roundtrip = csr_matrix((archive["H_data"], archive["H_indices"],
                            archive["H_indptr"]),
                           shape=(int(archive["H_shape"][0]),
                                  int(archive["H_shape"][1])))
    partition_ok = (np.union1d(archive["inner_indices"],
                               archive["outer_indices"]).size
                    == (J + 2) * (N + 2)
                    and np.intersect1d(archive["inner_indices"],
                                       archive["outer_indices"]).size == 0)
    checks[f"{key}_csr_roundtrip_and_partition"] = bool(
        roundtrip.nnz == hp_csr.nnz
        and np.array_equal(roundtrip.data, np.asarray(hp_csr.data))
        and np.array_equal(roundtrip.indices, np.asarray(hp_csr.indices))
        and np.array_equal(roundtrip.indptr, np.asarray(hp_csr.indptr))
        and partition_ok
        and np.all(np.diff(archive["inner_indices"]) > 0)
        and np.all(np.diff(archive["outer_indices"]) > 0))
    row = {
        "key": key, "J": J, "N": N, "h": h, "delta": delta,
        "archive": key + ".npz",
        "ground_energy": eig_value,
        "ground_pair_probability": ground_pair_probability,
        "initial_energy": initial_energy,
        "preparation_work": float(preparation_work),
        "peak_pair_probability_gain": peak_pair_probability_gain,
        "norm_error": norm_error,
        "energy_error": energy_error,
        "ground_full_residual": ground_full_residual,
    }
    return row, archive, {"states": states, "J": J, "N": N}


def embed(state_batch, J_small, N_small, J_big, N_big):
    big = np.zeros((state_batch.shape[0], J_big * N_big), dtype=np.complex128)
    for j in range(J_small):
        big[:, j * N_big:j * N_big + N_small] = \
            state_batch[:, j * N_small:(j + 1) * N_small]
    return big


# ---------------------------------------------------------------------------
# scientific driver
# ---------------------------------------------------------------------------

def calculate(output_dir: Path, checks: dict, rows: list, per_row: dict):
    cache = {"mediator": {}, "carrier": {}, "built": {}}
    for key, J, N, h, delta in ROWS_SCHEDULE:
        row, archive, extras = compute_row(key, J, N, h, delta, cache, checks)
        archive_path = output_dir / row["archive"]
        np.savez(archive_path, **archive)
        row["archive_sha256"] = raw_sha256(archive_path)
        rows.append(row)
        per_row[key] = extras
    checks["five_rows_present"] = bool(
        [row["key"] for row in rows] == [entry[0] for entry in ROWS_SCHEDULE]
        and all((row["J"], row["N"], row["h"], row["delta"]) == schedule[1:]
                for row, schedule in zip(rows, ROWS_SCHEDULE)))
    embed_coarse_medium = float(np.max(np.linalg.norm(
        embed(per_row["coupled_48_12"]["states"], 48, 12, 64, 16)
        - per_row["coupled_64_16"]["states"], axis=1)))
    embed_medium_fine = float(np.max(np.linalg.norm(
        embed(per_row["coupled_64_16"]["states"], 64, 16, 80, 20)
        - per_row["coupled_80_20"]["states"], axis=1)))
    checks["embed_coarse_medium_bound"] = bool(embed_coarse_medium <= 1.0e-3)
    checks["embed_medium_fine_bound"] = bool(embed_medium_fine <= 1.0e-4)
    fine_residual = next(row["ground_full_residual"] for row in rows
                         if row["key"] == "coupled_80_20")
    checks["fine_ground_residual_bound"] = bool(16.0 * fine_residual <= 1.0e-5)
    for control in ("zero_pump_80_20", "uncoupled_80_20"):
        gain = next(row["peak_pair_probability_gain"] for row in rows
                    if row["key"] == control)
        checks[f"{control}_pair_change_bound"] = bool(abs(gain) <= 1.0e-8)
    for row in rows:
        for field, value in row.items():
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError(f"nonfinite row field {field} in {row['key']}")
    parameters = {
        "Naction": float(N_ACTION), "a": A, "cPsi": C_PSI, "uRho": float(U_RHO),
        "uC": float(U_C), "kCx": float(K_CX), "eC": E_C, "B": B,
        "k": K_WITNESS, "V": V_BOX, "eta": ETA, "v2": V2, "m": M_MASS,
        "w": W_FREQ, "F": F_DIL, "delta": DELTA, "Hc": HC_INHERITED,
    }
    return parameters


def jsonable(value):
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        print(json.dumps({"verdict": VERDICT_INCONCLUSIVE, "numeric_pass": False,
                          "error": "output directory already exists",
                          "complete_physical_matter_formation": False}))
        return 1
    args.output.mkdir(parents=True, exist_ok=False)
    receipt = {
        "schema": RESULT_SCHEMA, "role": ROLE, "verdict": VERDICT_INCONCLUSIVE,
        "numeric_pass": False, "error": None, "checks": {}, "parameters": {},
        "rows": [], "complete_physical_matter_formation": False,
    }
    checks: dict = {}
    rows: list = []
    per_row: dict = {}
    try:
        validate_manifest(args.manifest)
        checks["guards_pass"] = True
        parameters = calculate(args.output, checks, rows, per_row)
        receipt.update({
            "parameters": parameters,
            "checks": checks, "rows": jsonable(rows),
        })
        numeric_pass = all(value is True for value in checks.values())
        receipt["numeric_pass"] = bool(numeric_pass)
        receipt["verdict"] = VERDICT_AWAITING if numeric_pass else VERDICT_INCONCLUSIVE
        receipt["error"] = None if numeric_pass else "own numerical checks failed"
    except Exception as exc:  # retain attempted arrays and failed checks
        receipt.update({
            "checks": checks,
            "rows": jsonable(rows),
            "numeric_pass": False,
            "verdict": VERDICT_INCONCLUSIVE,
            "error": f"{type(exc).__name__}: {exc}",
        })
    (args.output / "result.json").write_text(
        json.dumps(jsonable(receipt), indent=2, allow_nan=False) + "\n",
        encoding="utf-8")
    print(json.dumps({key: receipt.get(key) for key in
                      ("verdict", "numeric_pass", "error",
                       "complete_physical_matter_formation")}))
    return 0 if receipt["numeric_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
