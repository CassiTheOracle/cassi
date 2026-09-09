#!/usr/bin/env python3
"""Independent raw-output residuals audit for notebook section 70.

python computations/verify_matter_formation_quantum_residuals.py --manifest PATH --primary DIR --independent DIR --output FRESH_DIR

This auditor rebuilds the whole finite-mode calculation from the sealed
polynomial matrix elements instead of trusting either evolution method: the
padded oscillator Hamiltonian, its projected block, the complete discarded
Hamiltonian image, the variational ground state with its full-space residual, the
dilation preparation, every propagated state, and every retained energy and
probability array.  From the raw archives it evaluates the Duhamel and
preparation-leakage integral bounds together with their Lipschitz quadrature
remainder, compares the two methods on all three bases, and applies the whole
frozen decision tree of section 70.

Neither evolution program is imported, parsed or otherwise consumed as an
implementation; the two bound scientific sources are digested as bytes only.

Scope of every retained number.  The bounds are analytic inequalities evaluated
in floating-point arithmetic, not interval-arithmetic certificates.  They
measure finite-mode occupation-truncation error only.  They do not bound the
distance of the variational ground state from the unique exact ground state,
they do not control unbounded energy or occupation expectations, and they do not
restore the omitted spatial modes.  The reference-pair probability counts
reference-basis pair excitations, not asymptotic out-particles.  Complete
physical matter formation remains unresolved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SELF_PATH = "computations/verify_matter_formation_quantum_residuals.py"
REPORT = "computations/matter-formation-continuum-report.md"
PRIMARY_SOURCE = "computations/matter_formation_quantum_backreaction.py"
COORDINATE_SOURCE = "computations/verify_matter_formation_quantum_backreaction.py"
PARENT_SOURCE = "foundations/particle-stationary-action-closure.md"
SOURCES = {PRIMARY_SOURCE, COORDINATE_SOURCE, SELF_PATH, PARENT_SOURCE}

MANIFEST_SCHEMA = "matter-formation-quantum-backreaction-manifest-v1"
RESULT_SCHEMA = "matter-formation-quantum-backreaction-v1"
SCHEMA = "matter-formation-quantum-backreaction-audit-v1"
REVIEW_ROLES = {"coordinate", "residuals"}
SECTION_HEADINGS = (
    "## 25. Autonomous mediator oscillation in the scalar parent",
    "## 64. Working notes: matching quantum conversion to the scalar action",
    "## 70. Working notes: autonomous quantum transfer with the full scalar interaction",
)
INHERITED_ROOTS = (
    "runs/20260907_matter_formation_autonomous_pump/results.json",
    "runs/20260907_matter_formation_autonomous_pump_verification/results.json",
)
INHERITED_RAW_SHA256 = {
    INHERITED_ROOTS[0]: "cad33ef760404c79807570be1269390dfb790574dc13bfe60d61d67c5b1bc9c5",
    INHERITED_ROOTS[1]: "a54c07d1a973f9a915355e26b7c23e7caa7ee75a468f09fda53e13a272959758",
}
PUMP_SCHEMAS = {
    INHERITED_ROOTS[0]: "cassi.matter-formation.autonomous-pump.v1",
    INHERITED_ROOTS[1]: "cassi.matter-formation.autonomous-pump-verification.v1",
}
PUMP_VERDICT = "SUPPORTS\u2014neutral linear parametric amplification in the supplied temporal parent"
WITNESS_J = 3
K_PINNED = 2.675336705149658
HC_PINNED = 2.9598260763447164
EVOLUTION_VERDICT = "INCONCLUSIVE-awaiting joint quantum transfer qualification"
VERDICT_SUPPORTS = "SUPPORTS-conditional autonomous quantum transfer in the full scalar mode Hamiltonian"
VERDICT_NO_TRANSFER = "INCONCLUSIVE-no resolved reference-pair transfer in the fixed window"
VERDICT_INCONCLUSIVE = "INCONCLUSIVE"

# Frozen dimensionless inputs of section 70.4.  Every derived quantity is
# computed from the receipt-read wave number; no scientific output is hardcoded.
N_ACTION = 4
A_COUPLING = 1/16
C_PSI = 1/8
U_RHO = 4
U_C = 1
K_CX = 1
E_CARRIER = 3/4
B_CARRIER = E_CARRIER + 1/(4*A_COUPLING)
DILATION_FACTOR = math.sqrt(3/2)
DILATION = math.log(DILATION_FACTOR)
MASS = math.sqrt(2*U_RHO/C_PSI)
QUARTIC_COEFFICIENT = U_C/(8*A_COUPLING*A_COUPLING)

COARSE, MEDIUM, FINE, ZERO_PUMP, UNCOUPLED = ("coupled_48_12", "coupled_64_16", "coupled_80_20",
                                              "zero_pump_80_20", "uncoupled_80_20")
CONTROL_KEYS = (ZERO_PUMP, UNCOUPLED)
TIME_SAMPLES, SOURCE_SAMPLES, TIME_HORIZON = 513, 257, 16.0
SCHEDULE = ((COARSE, 48, 12, HC_PINNED, DILATION),
            (MEDIUM, 64, 16, HC_PINNED, DILATION),
            (FINE, 80, 20, HC_PINNED, DILATION),
            (ZERO_PUMP, 80, 20, HC_PINNED, 0.0),
            (UNCOUPLED, 80, 20, 0.0, DILATION))
BASIS = {key: (J, N) for key, J, N, _h, _delta in SCHEDULE}
METHODS = {"primary": PRIMARY_SOURCE, "independent": COORDINATE_SOURCE}
RESULT_FIELDS = {"schema", "role", "numeric_pass", "verdict", "error", "checks", "parameters",
                 "rows", "complete_physical_matter_formation"}
ROW_SCALARS = ("ground_energy", "ground_pair_probability", "initial_energy", "preparation_work",
               "peak_pair_probability_gain", "norm_error", "energy_error", "ground_full_residual")
ROW_KEYS = {"key", "J", "N", "h", "delta", "archive", "archive_sha256", *ROW_SCALARS}
ARCHIVE_FIELDS = ("time", "state", "ground", "prepared", "source_time", "source_state", "ground_energy",
                  "norm", "energy_terms", "f2", "pairs", "pair_probability", "S2", "S4", "PS2", "R2",
                  "R4", "D", "H_data", "H_indices", "H_indptr", "H_shape", "R_data", "R_indices",
                  "R_indptr", "R_shape", "inner_indices", "outer_indices")
PRIMARY_ARCHIVE_FIELDS = ("eigenvalues", "eigenvectors", "source_eigenvalues", "source_eigenvectors")
OPERATOR_FIELDS = {"S2": "coordinate", "S4": "quartic", "PS2": "momentum", "R2": "radius",
                   "R4": "radial_quartic", "D": "dilation"}
ARRAY_FIELDS = ("norm", "energy_terms", "f2", "pairs", "pair_probability")

# Frozen numerical scope of section 70.4.  No threshold here is adjustable.
MATRIX_BOUND = 1e-11
DISCARDED_BOUND = 1e-11
GROUND_ENERGY_BOUND = 1e-9
STATE_BOUND = 1e-7
NORM_BOUND = 1e-10
TOTAL_ENERGY_BOUND = 1e-9
COARSE_MEDIUM_BOUND = 1e-3
MEDIUM_FINE_BOUND = 1e-4
PREPARATION_BOUND = 1e-6
EVOLUTION_BOUND = 1e-4
GROUND_RESIDUAL_BOUND = 1e-5
CONTROL_BOUND = 1e-8
RECONSTRUCTION_BOUND = 1e-9
TRANSFER_FLOOR = 1e-3
SPECTRUM_BOUND = 1e-9
PARAMETER_BOUND = 1e-12
GRID_BOUND = 1e-12

SCOPE = ("Exact quantum dynamics of one specified finite spatial-mode Hamiltonian approximated by "
         "oscillator-occupation projection, not a continuum field simulation.  The retained bounds are "
         "analytic inequalities evaluated in floating-point arithmetic; they supply finite-mode "
         "occupation-truncation error only, do not bound the variational ground state's distance from "
         "the unique exact ground state, and do not control unbounded energy or occupation expectations "
         "or the omitted spatial modes.  The reported probability counts reference-basis pair "
         "excitations, not asymptotic out-particles.  Complete physical matter formation remains "
         "unresolved.")


class GuardError(Exception):
    """A source, section, inherited, review, receipt, schema or archive-identity failure."""


class AuditError(Exception):
    """An internal reconstruction inconsistency, retained with the attempted arrays."""


def guard(condition: bool, message: str) -> None:
    if not condition:
        raise GuardError(message)


def demand(condition: bool, message: str) -> None:
    if not condition:
        raise AuditError(message)


def canonical(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def digest(path: Path, *, raw: bool = False) -> str:
    return hashlib.sha256(path.read_bytes() if raw else canonical(path)).hexdigest()


def reject_constant(token: str):
    raise ValueError(f"nonfinite JSON constant: {token}")


def within(root: Path, resolved: Path) -> bool:
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        return False
    return True


def rooted(relative, label: str) -> Path:
    guard(isinstance(relative, str) and bool(relative) and "\x00" not in relative,
          f"{label} must be a non-empty relative path")
    guard(not Path(relative).is_absolute() and "\\" not in relative, f"{label} must be a root-relative path")
    guard(all(part not in ("..", ".") for part in Path(relative).parts), f"{label} escapes the repository root")
    resolved = ROOT.joinpath(*Path(relative).parts).resolve()
    guard(within(ROOT, resolved), f"{label} escapes the repository root")
    return resolved



def load_json(path: Path, label: str) -> dict:
    guard(path.is_file(), f"{label} is missing: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    except ValueError as exc:
        raise GuardError(f"{label} is not strict finite JSON: {exc}") from exc
    guard(isinstance(value, dict), f"{label} must be a JSON object")
    json.dumps(value, allow_nan=False)
    return value


def exact_keys(record, names: set[str], label: str) -> dict:
    guard(isinstance(record, dict), f"{label} must be an object")
    guard(set(record) == names, f"{label} keys {sorted(record)} != {sorted(names)}")
    return record


def finite_number(value, label: str) -> float:
    guard(isinstance(value, (int, float)) and not isinstance(value, bool), f"{label} is not a number")
    number = float(value)
    guard(math.isfinite(number), f"{label} is not finite")
    return number


def section_bytes(lines: list[str], heading: str) -> bytes:
    starts = [index for index, line in enumerate(lines) if line.rstrip("\n") == heading]
    guard(len(starts) == 1, f"section heading must occur exactly once: {heading}")
    first = starts[0]
    last = next((index for index in range(first + 1, len(lines)) if lines[index].startswith("## ")), len(lines))
    return ("".join(lines[first:last]).rstrip() + "\n").encode("utf-8")


def validate_manifest(path: Path) -> dict:
    """Prove every common prerequisite before any scientific archive is opened."""
    manifest = load_json(path, "manifest")
    exact_keys(manifest, {"schema", "sections", "sources", "inherited", "mathematical_reviews"}, "manifest")
    guard(manifest["schema"] == MANIFEST_SCHEMA, "unexpected manifest schema")
    root = path.parent.resolve()
    lines = canonical(ROOT / REPORT).decode("utf-8").splitlines(keepends=True)

    sections = manifest["sections"]
    guard(isinstance(sections, list) and len(sections) == 3, "manifest must bind exactly three sections")
    for index, entry in enumerate(sections):
        exact_keys(entry, {"path", "heading", "snapshot", "sha256"}, f"sections[{index}]")
    guard({entry["heading"] for entry in sections} == set(SECTION_HEADINGS),
          "section bindings must cover sections 25, 64 and 70 exactly once")
    section_hashes = {}
    for index, entry in enumerate(sections):
        guard(entry["path"] == REPORT, f"sections[{index}] must bind the report")
        snapshot = rooted(entry["snapshot"], f"sections[{index}].snapshot")
        guard(snapshot.is_file(), f"sections[{index}] snapshot is missing")
        frozen = canonical(snapshot)
        live = section_bytes(lines, entry["heading"])
        guard(hashlib.sha256(live).hexdigest() == entry["sha256"], f"sections[{index}] live hash mismatch")
        guard(hashlib.sha256(frozen).hexdigest() == entry["sha256"], f"sections[{index}] snapshot hash mismatch")
        guard(frozen == live, f"sections[{index}] snapshot differs from the live section")
        section_hashes[entry["heading"]] = entry["sha256"]

    sources = manifest["sources"]
    guard(isinstance(sources, list) and len(sources) == 4, "manifest must bind exactly four sources")
    for index, entry in enumerate(sources):
        exact_keys(entry, {"path", "snapshot", "sha256"}, f"sources[{index}]")
    guard({entry["path"] for entry in sources} == SOURCES,
          "source bindings are not exactly primary, coordinate, residuals and parent")
    source_hashes = {}
    for index, entry in enumerate(sources):
        live = rooted(entry["path"], f"sources[{index}].path")
        snapshot = rooted(entry["snapshot"], f"sources[{index}].snapshot")
        guard(live.is_file(), f"live source is missing: {entry['path']}")
        guard(snapshot.is_file(), f"source snapshot is missing: {entry['path']}")
        # The primary and coordinate sources are digested, never read, imported or parsed.
        guard(digest(live) == entry["sha256"], f"live source mismatch: {entry['path']}")
        guard(digest(snapshot) == entry["sha256"], f"source snapshot mismatch: {entry['path']}")
        source_hashes[entry["path"]] = entry["sha256"]

    inherited = manifest["inherited"]
    guard(isinstance(inherited, list) and len(inherited) == 2, "manifest must bind exactly two inherited receipts")
    for index, entry in enumerate(inherited):
        exact_keys(entry, {"path", "snapshot", "sha256"}, f"inherited[{index}]")
    guard({entry["path"] for entry in inherited} == set(INHERITED_ROOTS),
          "inherited bindings are not exactly the two autonomous-pump receipts")
    inherited_hashes = {}
    for index, entry in enumerate(inherited):
        guard(INHERITED_RAW_SHA256[entry["path"]] == entry["sha256"],
              f"inherited[{index}] does not carry the pinned raw digest")
        live = rooted(entry["path"], f"inherited[{index}].path")
        snapshot = rooted(entry["snapshot"], f"inherited[{index}].snapshot")
        guard(live.is_file(), f"inherited receipt is missing: {entry['path']}")
        guard(snapshot.is_file(), f"inherited snapshot is missing: {entry['path']}")
        # Inherited receipts are sealed as RAW bytes: no CRLF normalization applies.
        guard(digest(live, raw=True) == entry["sha256"], f"inherited live raw-hash mismatch: {entry['path']}")
        guard(digest(snapshot, raw=True) == entry["sha256"],
              f"inherited snapshot raw-hash mismatch: {entry['path']}")
        inherited_hashes[entry["path"]] = entry["sha256"]

    reviews = manifest["mathematical_reviews"]
    guard(isinstance(reviews, list) and len(reviews) == 2, "manifest must bind exactly two mathematical reviews")
    for index, entry in enumerate(reviews):
        exact_keys(entry, {"role", "accepted", "snapshot", "sha256"}, f"mathematical_reviews[{index}]")
    guard({entry["role"] for entry in reviews} == REVIEW_ROLES,
          "review roles are not exactly coordinate and residuals")
    review_hashes = {}
    for index, entry in enumerate(reviews):
        # A false accepted flag is rejected even when the literal line occurs in the text.
        guard(entry["accepted"] is True, f"review role {entry['role']} is not accepted")
        snapshot = rooted(entry["snapshot"], f"mathematical_reviews[{index}].snapshot")
        guard(snapshot.is_file(), f"review snapshot is missing: {entry['role']}")
        guard(digest(snapshot) == entry["sha256"], f"review hash mismatch: {entry['role']}")
        accepted_lines = [line.strip() for line in canonical(snapshot).decode("utf-8").splitlines()
                          if line.strip().startswith("accepted:")]
        guard(len(accepted_lines) == 1, f"review must carry exactly one accepted: line: {entry['role']}")
        guard(accepted_lines[0] == "accepted: true", f"review accepted line is not true: {entry['role']}")
        review_hashes[entry["role"]] = entry["sha256"]

    return dict(manifest_sha256=digest(path), manifest_raw_sha256=digest(path, raw=True),
                evidence_root=str(root), sections=section_hashes, sources=source_hashes,
                inherited=inherited_hashes, mathematical_reviews=review_hashes)


def validate_inherited(prerequisites: dict) -> dict:
    """Scientific prerequisites of both inherited receipts, proven before ``k`` is used."""
    receipts = {}
    for relative in INHERITED_ROOTS:
        path = rooted(relative, "inherited receipt")
        receipt = load_json(path, f"inherited receipt {relative}")
        guard(digest(path, raw=True) == prerequisites["inherited"][relative],
              f"inherited receipt changed after sealing: {relative}")
        guard(receipt.get("schema") == PUMP_SCHEMAS[relative], f"inherited schema mismatch: {relative}")
        guard(receipt.get("verdict") == PUMP_VERDICT,
              f"inherited verdict is not the specified SUPPORTS verdict: {relative}")
        guard(receipt.get("passed") is True, f"inherited receipt did not pass: {relative}")
        guard(receipt.get("qualified") is True, f"inherited receipt is not qualified: {relative}")
        guard(receipt.get("error") is None, f"inherited receipt carries an error: {relative}")
        guard(receipt.get("complete_physical_matter_formation") is not True,
              f"inherited receipt claims physical completion: {relative}")
        receipts[relative] = receipt
    independent = receipts[INHERITED_ROOTS[1]]
    guard(isinstance(independent.get("mismatches"), list) and len(independent["mismatches"]) == 0,
          "independent inherited mismatches are not empty")
    observed = {}
    for label, receipt in (("primary", receipts[INHERITED_ROOTS[0]]), ("independent", independent)):
        witnesses = receipt.get("witnesses")
        guard(isinstance(witnesses, list) and bool(witnesses), f"inherited {label} witnesses are missing")
        selected = [row for row in witnesses if isinstance(row, dict) and row.get("j") == WITNESS_J]
        guard(len(selected) == 1, f"inherited {label} must carry exactly one witness with j={WITNESS_J}")
        witness = selected[0]
        guard(witness.get("passed") is True, f"inherited {label} witness j={WITNESS_J} did not pass")
        guard(witness.get("unstable") is True, f"inherited {label} witness j={WITNESS_J} is not the unstable branch")
        observed[label] = finite_number(witness.get("k"), f"inherited {label} witness j={WITNESS_J} wave number")
    guard(observed["primary"] == observed["independent"], "inherited witnesses disagree on the resolved wave number")
    wave_number = observed["primary"]
    guard(wave_number == K_PINNED, f"inherited wave number {wave_number!r} is not the pinned {K_PINNED!r}")

    volume = (2*math.pi/wave_number)**3
    eta = N_ACTION*volume
    parameters = {"Naction": float(N_ACTION), "a": A_COUPLING, "cPsi": C_PSI, "uRho": float(U_RHO),
                  "uC": float(U_C), "kCx": float(K_CX), "eC": E_CARRIER, "B": B_CARRIER, "k": wave_number,
                  "V": volume, "eta": eta, "v2": eta*C_PSI, "m": MASS,
                  "w": math.sqrt((B_CARRIER + K_CX*wave_number*wave_number/2)/A_COUPLING),
                  "F": DILATION_FACTOR, "delta": DILATION, "Hc": HC_PINNED}
    guard(all(math.isfinite(value) for value in parameters.values()), "frozen parameter is not finite")
    guard(eta > 0.0 and parameters["v2"] > 0.0 and parameters["w"] > 0.0, "frozen parameters are not positive")
    return dict(parameters=parameters, wave_number=wave_number, witnesses=observed)


# ---------------------------------------------------------------------------
# Independent operator reconstruction.
#
# Every element is the exact infinite-oscillator element evaluated on the fully
# padded (J+2) x (N+2) grid, and every polynomial power is formed there, before
# any projection.  In the even-mediator (radial-carrier) picture S^2 and r^2 have
# band one in the doubled index, so S^4 = (S^2)^2 and r^4 = (r^2)^2 need
# intermediates only up to min(row, column) + 1.  For the projected block (rows
# and columns below J and N) and for every discarded-image column, whose input
# index lies inside P, those intermediates reach at most J and N, which the
# padding contains, so both consumed blocks are exact.  The outermost padded
# diagonal entries can require one further intermediate; they are not exact here
# and they are never consumed.
# ---------------------------------------------------------------------------

def mediator_blocks(size: int, mass: float):
    """Even mediator occupations 2j of an oscillator of frequency ``mass``.

    ``coordinate`` is S^2, whose diagonal is (2j+1/2)/m and whose off-diagonal is
    ``step`` = sqrt((2j+1)(2j+2))/(2m).  ``momentum`` is p_S^2, whose diagonal is
    m(2j+1/2) and whose off-diagonal is -m^2*step = -m*sqrt((2j+1)(2j+2))/2, the
    sign-opposite band of the same oscillator algebra.  ``dilation`` is
    (S p_S + p_S S)/2 = i(a_+^2 - a_-^2)/2, whose raising entry is
    +i*sqrt((2j+1)(2j+2))/2 and whose lowering entry is negative, which is exactly
    the unitary whose coordinate-space action is psi(S) -> e^{-delta/2}
    psi(e^{-delta}S).
    """
    index = np.arange(size, dtype=np.float64)
    coordinate = np.zeros((size, size))
    np.fill_diagonal(coordinate, (2*index + 0.5)/mass)
    momentum = np.zeros((size, size))
    np.fill_diagonal(momentum, mass*(2*index + 0.5))
    step = np.sqrt((2*index[:-1] + 1.0)*(2*index[:-1] + 2.0))/(2*mass)
    raising = np.diag(step, -1)
    lowering = np.diag(step, 1)
    coordinate = coordinate + raising + lowering
    momentum = momentum - mass*mass*(raising + lowering)
    # ``raising`` carries the S^2 band magnitude, so mass*step is
    # sqrt((2j+1)(2j+2))/2: the raising entry is +i times that and the lowering
    # entry is its conjugate, which is the (S p_S + p_S S)/2 dilation whose
    # exp(-i delta D) widens the mediator wave function.
    dilation = 1j*mass*(raising - lowering)
    return coordinate, momentum, dilation


def carrier_blocks(size: int, frequency: float):
    """Circular carrier occupations n+ = n- = n of frequency ``frequency``."""
    index = np.arange(size, dtype=np.float64)
    radius = np.zeros((size, size))
    np.fill_diagonal(radius, (2*index + 1.0)/frequency)
    step = (index[:-1] + 1.0)/frequency
    radius = radius + np.diag(step, 1) + np.diag(step, -1)
    free = np.zeros((size, size))
    np.fill_diagonal(free, frequency*(2*index + 1.0))
    return radius, free


def symmetrize(block: np.ndarray) -> np.ndarray:
    """Enforce the exact real symmetry of a polynomial formed by matrix products."""
    return 0.5*(block + block.T)


def extended_indices(J: int, N: int):
    """Canonical extended flattening: extended index = j*(N+2) + n, q-major."""
    width = N + 2
    inner = np.array([j*width + n for j in range(J) for n in range(N)], dtype=np.int64)
    outer = np.array([j*width + n for j in range(J + 2) for n in range(N + 2) if j >= J or n >= N],
                     dtype=np.int64)
    return inner, outer, (J + 2)*(N + 2), width


def build_static(J: int, N: int, h: float, parameters: dict) -> dict:
    """Padded Hamiltonian, projected block, discarded image, spectra and generator data."""
    v2, mass, frequency, eta = parameters["v2"], parameters["m"], parameters["w"], parameters["eta"]
    M, C = J + 2, N + 2
    coordinate, momentum, dilation = mediator_blocks(M, mass)
    quartic = symmetrize(coordinate @ coordinate)
    radius, free = carrier_blocks(C, frequency)
    radial_quartic = symmetrize(radius @ radius)
    identity_m, identity_c = np.eye(M), np.eye(C)
    mediator_part = 0.5*momentum + (mass*mass/(8*v2))*(quartic - 2*v2*coordinate + v2*v2*identity_m)
    carrier_quadratic_part = free
    carrier_quartic_part = (QUARTIC_COEFFICIENT/eta)*radial_quartic
    mixed_part = (h/(2*A_COUPLING))*(coordinate/v2 - identity_m)
    padded = (np.kron(mediator_part, identity_c) + np.kron(identity_m, carrier_quadratic_part + carrier_quartic_part)
              + np.kron(mixed_part, radius))
    inner, outer, padded_size, width = extended_indices(J, N)
    demand(padded.shape == (padded_size, padded_size), "padded Hamiltonian has the wrong shape")
    demand(bool(np.isfinite(padded).all()), "padded Hamiltonian is nonfinite")
    projected = np.ascontiguousarray(padded[np.ix_(inner, inner)])
    discarded = np.ascontiguousarray(padded[np.ix_(outer, inner)])
    scale = max(1.0, float(np.linalg.norm(projected)))
    demand(float(np.max(np.abs(projected - projected.T))) <= 1e-9*scale, "projected Hamiltonian is not symmetric")
    demand(discarded.shape == (2*J + 2*N + 4, J*N), "discarded image has the wrong shape")

    values, vectors = np.linalg.eigh(projected)
    ground_energy = float(values[0])
    ground = np.array(vectors[:, 0], dtype=np.float64)
    if ground[0] < 0.0:
        ground = -ground
    demand(float(ground[0]) > 0.0, "ground-state first component is not positive")
    inside_defect = projected @ ground - ground_energy*ground
    outside_defect = discarded @ ground
    residual = float(math.sqrt(float(np.dot(inside_defect, inside_defect))
                               + float(np.dot(outside_defect, outside_defect))))

    generator = np.ascontiguousarray(dilation[:J, :J])
    generator_values, generator_vectors = np.linalg.eigh(generator)
    ground_rows = generator_vectors.conj().T @ ground.reshape(J, N)
    row_norms = np.linalg.norm(ground_rows, axis=1)
    leaked_generator = np.array(dilation[J, :J] @ generator_vectors, dtype=np.complex128)
    source_lipschitz = float(np.sum(row_norms*np.abs(generator_values)*np.abs(leaked_generator)))

    mediator_block = np.ascontiguousarray(coordinate[:J, :J])
    momentum_block = np.ascontiguousarray(momentum[:J, :J])
    quartic_block = np.ascontiguousarray(quartic[:J, :J])
    radius_block = np.ascontiguousarray(radius[:N, :N])
    radial_quartic_block = np.ascontiguousarray(radial_quartic[:N, :N])
    free_block = np.ascontiguousarray(free[:N, :N])
    identity_j = np.eye(J)
    energy_mediator = 0.5*momentum_block + (mass*mass/(8*v2))*(quartic_block - 2*v2*mediator_block
                                                               + v2*v2*identity_j)
    quartic_carrier = (QUARTIC_COEFFICIENT/eta)*radial_quartic_block
    mixed_mediator = (h/(2*A_COUPLING))*(mediator_block/v2 - identity_j)
    decomposition = (np.kron(energy_mediator, np.eye(N)) + np.kron(identity_j, free_block + quartic_carrier)
                     + np.kron(mixed_mediator, radius_block))
    occupation = np.tile(np.arange(N, dtype=np.float64), J)
    pair_mask = np.tile(np.arange(N, dtype=np.float64) >= 1.0, J)
    zero_mask = np.tile(np.arange(N, dtype=np.float64) == 0.0, J)
    return dict(J=J, N=N, h=h, size=J*N, width=width, inner=inner, outer=outer, padded_size=padded_size,
                padded=padded, projected=projected, discarded=discarded, coordinate=mediator_block,
                momentum=momentum_block, quartic=quartic_block, radius=radius_block,
                radial_quartic=radial_quartic_block, dilation=generator, padded_dilation=dilation,
                eigenvalues=values, eigenvectors=vectors, ground_energy=ground_energy, ground=ground,
                ground_residual=residual, generator_values=generator_values,
                generator_vectors=generator_vectors, leaked_generator=leaked_generator,
                carrier_row_norms=row_norms, source_lipschitz=source_lipschitz,
                energy_mediator=energy_mediator, free_carrier=free_block, quartic_carrier=quartic_carrier,
                mixed_mediator=mixed_mediator, identity_j=identity_j, identity_n=np.eye(N),
                decomposition_error=float(np.linalg.norm(decomposition - projected)/scale),
                occupation=occupation, pair_mask=pair_mask, zero_mask=zero_mask)


def build_dynamics(static: dict, delta: float) -> dict:
    """Dilation preparation and propagation from the static spectral data."""
    J, N = static["J"], static["N"]
    values, vectors = static["eigenvalues"], static["eigenvectors"]
    ground, ground_energy = static["ground"], static["ground_energy"]
    generator_values, generator_vectors = static["generator_values"], static["generator_vectors"]
    ground_rows = generator_vectors.conj().T @ ground.reshape(J, N)

    def dilated(step: float) -> np.ndarray:
        phases = np.exp(-1j*step*generator_values)
        rotated = generator_vectors @ (phases[:, None]*ground_rows)
        return np.array(rotated.reshape(J*N), dtype=np.complex128)

    prepared = dilated(delta)
    coefficients = vectors.T @ prepared
    times = np.linspace(0.0, TIME_HORIZON, TIME_SAMPLES)
    evolution = np.exp(-1j*np.outer(times, values - ground_energy))
    states = np.array((coefficients[None, :]*evolution) @ vectors.T, dtype=np.complex128)
    source_times = np.linspace(0.0, delta, SOURCE_SAMPLES)
    source_states = np.stack([dilated(step) for step in source_times])
    preparation_unitary = generator_vectors @ (np.exp(-1j*delta*generator_values)[:, None]
                                               * generator_vectors.conj().T)
    return dict(delta=delta, prepared=prepared, coefficients=coefficients, times=times, states=states,
                source_times=source_times, source_states=source_states,
                preparation_unitary=np.array(preparation_unitary, dtype=np.complex128))


# ---------------------------------------------------------------------------
# Observables reconstructed from the actual raw states.
# ---------------------------------------------------------------------------

def bilinear(states: np.ndarray, left: np.ndarray, right: np.ndarray) -> np.ndarray:
    """Unnormalized expectation of ``left tensor right`` on every raw state row."""
    carrier = np.einsum("nm,tjm->tjn", right, states, optimize=True)
    transformed = np.einsum("ji,tin->tjn", left, carrier, optimize=True)
    return np.real(np.einsum("tjn,tjn->t", states.conj(), transformed, optimize=True))


def reconstruct_arrays(static: dict, states: np.ndarray, parameters: dict) -> dict:
    """Norm, the four energy terms, f2, pairs and the reference-pair probability."""
    J, N, v2 = static["J"], static["N"], parameters["v2"]
    flat = np.array(states, dtype=np.complex128).reshape(-1, J*N)
    psi = flat.reshape(flat.shape[0], J, N)
    probability = np.abs(flat)**2
    return dict(norm=probability.sum(axis=1),
                energy_terms=np.column_stack((
                    bilinear(psi, static["energy_mediator"], static["identity_n"]),
                    bilinear(psi, static["identity_j"], static["free_carrier"]),
                    bilinear(psi, static["identity_j"], static["quartic_carrier"]),
                    bilinear(psi, static["mixed_mediator"], static["radius"]))),
                f2=bilinear(psi, static["coordinate"], static["identity_n"])/v2,
                pairs=probability @ static["occupation"],
                pair_probability=probability @ static["pair_mask"],
                zero_probability=probability @ static["zero_mask"])


def row_statistics(static: dict, dynamics: dict, arrays: dict, parameters: dict) -> dict:
    """Every retained scalar, rebuilt from the raw ground, prepared and propagated states."""
    ground_arrays = reconstruct_arrays(static, static["ground"][None, :], parameters)
    prepared_arrays = reconstruct_arrays(static, dynamics["prepared"][None, :], parameters)
    total = arrays["energy_terms"].sum(axis=1)
    initial_energy = float(total[0])
    baseline = float(ground_arrays["pair_probability"][0])
    return dict(ground_energy=float(static["ground_energy"]),
                ground_pair_probability=baseline,
                initial_energy=initial_energy,
                preparation_work=float(prepared_arrays["energy_terms"].sum()
                                       - ground_arrays["energy_terms"].sum()),
                peak_pair_probability_gain=float(np.max(arrays["pair_probability"]) - baseline),
                maximum_pair_probability_change=float(np.max(np.abs(arrays["pair_probability"] - baseline))),
                norm_error=float(np.max(np.abs(arrays["norm"] - 1.0))),
                energy_error=float(np.max(np.abs(total - initial_energy))/max(1.0, abs(initial_energy))),
                ground_full_residual=float(static["ground_residual"]))


def trapezoid(samples: np.ndarray, step: float) -> float:
    if samples.size < 2 or step == 0.0:
        return 0.0
    return float(step*(0.5*float(samples[0]) + float(np.sum(samples[1:-1])) + 0.5*float(samples[-1])))


def evolution_bound(static: dict, spectrum: dict, prepared: np.ndarray, states: np.ndarray,
                    times: np.ndarray) -> dict:
    """Duhamel bound for a propagated trajectory, with the Lipschitz remainder.

    The retained samples are ``||R psi(t)||`` for the actual raw states through
    the independently reconstructed discarded image ``R``.  The Lipschitz
    constant is the spectral expression ``sum_j |c_j| |E_j - E_P| ||R V_j||``
    with ``c = V^T prepared``, evaluated for whichever complete eigenpair set
    ``spectrum`` supplies: any eigenbasis of ``H_P`` gives a valid constant,
    because ``|d/dt ||R psi||| <= ||R d psi/dt||`` by the triangle inequality.
    """
    flat = np.array(states, dtype=np.complex128)
    vectors = np.asarray(spectrum["vectors"])
    values = np.asarray(spectrum["eigenvalues"], dtype=np.float64)
    ground_energy = float(spectrum["ground_energy"])
    discarded = static["discarded"]
    samples = np.linalg.norm(discarded @ flat.T, axis=0)
    coefficients = vectors.T @ np.asarray(prepared, dtype=np.complex128)
    leaked = discarded @ vectors
    lipschitz = float(np.sum(np.abs(coefficients)*np.abs(values - ground_energy)
                             * np.linalg.norm(leaked, axis=0)))
    phases = np.exp(-1j*np.outer(times, values - ground_energy))
    spectral_samples = np.linalg.norm((coefficients[None, :]*phases) @ leaked.T, axis=1)
    consistency = float(np.max(np.abs(spectral_samples - samples))/max(1.0, float(np.max(samples))))
    span = float(times[-1] - times[0])
    step = float(times[1] - times[0])
    integral = trapezoid(samples, step)
    remainder = lipschitz*span*step/4
    return dict(samples=samples, lipschitz=lipschitz, trapezoid=integral, remainder=remainder,
                upper=integral + remainder, spectral_consistency=consistency)


def preparation_bound(static: dict, source_states: np.ndarray, source_times: np.ndarray) -> dict:
    """Preparation-leakage bound over the generator interval, with Lipschitz remainder.

    ``D`` acts on the mediator only, so each discarded row keeps its carrier
    vector: the leaked generator image has exactly one additional mediator index
    ``J``, whose coefficient for the dilation eigenvector ``W_j`` is
    ``D[J, J-1] * W_j[J-1]``.  The Lipschitz constant is therefore
    ``sum_j ||d_j|| |dval_j| |(D W_j)[J]|`` with ``d_j`` the carrier vector of
    the ground state in the dilation eigenbasis.
    """
    J, N = static["J"], static["N"]
    generator = static["padded_dilation"]
    flat = np.array(source_states, dtype=np.complex128)
    samples = np.zeros(flat.shape[0])
    for index, row in enumerate(flat):
        padded = np.zeros((J + 2, N), dtype=np.complex128)
        padded[:J] = row.reshape(J, N)
        samples[index] = float(np.linalg.norm((generator @ padded)[J:]))
    span = float(source_times[-1] - source_times[0])
    step = float(source_times[1] - source_times[0])
    integral = trapezoid(samples, step)
    source_coefficients = static["generator_vectors"].conj().T @ flat[0].reshape(J, N)
    lipschitz = float(np.sum(np.linalg.norm(source_coefficients, axis=1)
                             * np.abs(static["generator_values"])
                             * np.abs(static["leaked_generator"])))
    remainder = lipschitz*span*step/4
    return dict(samples=samples, lipschitz=lipschitz, trapezoid=integral, remainder=remainder,
                upper=integral + remainder)


# ---------------------------------------------------------------------------
# Consumed raw archives
# ---------------------------------------------------------------------------

def array_field(archive, name: str, shape, kinds: str) -> np.ndarray:
    guard(name in archive.files, f"archive field is missing: {name}")
    value = np.asarray(archive[name])
    guard(value.dtype.kind in kinds, f"archive field {name} has dtype {value.dtype}")
    if shape is not None:
        guard(value.shape == shape, f"archive field {name} has shape {value.shape}, expected {shape}")
    guard(bool(np.isfinite(value).all()), f"archive field {name} is nonfinite")
    return value


def csr_block(archive, prefix: str, shape) -> np.ndarray:
    data = array_field(archive, prefix + "_data", None, "f")
    indices = array_field(archive, prefix + "_indices", None, "iu").astype(np.int64)
    indptr = array_field(archive, prefix + "_indptr", None, "iu").astype(np.int64)
    stored = array_field(archive, prefix + "_shape", (2,), "iu")
    rows, columns = int(shape[0]), int(shape[1])
    guard(tuple(int(value) for value in stored) == (rows, columns),
          f"{prefix} shape {tuple(int(value) for value in stored)} != {(rows, columns)}")
    guard(indptr.size == rows + 1, f"{prefix} indptr length differs")
    guard(int(indptr[0]) == 0 and int(indptr[-1]) == data.size, f"{prefix} indptr is not compressed")
    guard(data.size == indices.size, f"{prefix} data and index lengths differ")
    if indices.size:
        guard(int(np.min(indices)) >= 0 and int(np.max(indices)) < columns, f"{prefix} index is out of range")
    blocks = [indices[start:end] for start, end in zip(indptr[:-1], indptr[1:])]
    guard(all(bool(np.all(np.diff(block) > 0)) for block in blocks),
          f"{prefix} row indices are not strictly increasing")
    dense = np.zeros((rows, columns))
    dense[np.repeat(np.arange(rows, dtype=np.int64), np.diff(indptr)), indices] = data
    return dense


def validate_grid(times: np.ndarray, span: float, samples: int, label: str) -> None:
    guard(times.shape == (samples,), f"{label} must retain {samples} samples")
    guard(float(times[0]) == 0.0, f"{label} must start at zero")
    guard(abs(float(times[-1]) - span) <= GRID_BOUND*max(1.0, abs(span)),
          f"{label} endpoint differs from {span}")
    steps = np.diff(times)
    guard(float(np.max(steps) - np.min(steps)) <= GRID_BOUND*max(1.0, abs(span)),
          f"{label} is not equally spaced")


def validate_result(path: Path, role: str, parameters: dict) -> dict:
    """Receipt identity and frozen-metadata prerequisites, before any archive is opened."""
    receipt = load_json(path, f"{role} result")
    exact_keys(receipt, RESULT_FIELDS, f"{role} result")
    guard(receipt["schema"] == RESULT_SCHEMA, f"{role} result schema mismatch")
    guard(receipt["role"] == ("primary" if role == "primary" else "coordinate"),
          f"{role} result has the wrong declared role")
    guard(receipt["numeric_pass"] is True, f"{role} did not pass its own numerical checks")
    guard(receipt["verdict"] == EVOLUTION_VERDICT, f"{role} verdict is not the awaiting-joint-qualification string")
    guard(receipt["error"] is None, f"{role} result carries an error")
    guard(receipt["complete_physical_matter_formation"] is False, f"{role} result claims physical completion")
    checks = receipt["checks"]
    guard(isinstance(checks, dict) and bool(checks) and all(value is True for value in checks.values()),
          f"{role} own checks are not all true")
    received = receipt["parameters"]
    exact_keys(received, set(parameters), f"{role} parameters")
    for name, value in parameters.items():
        observed = finite_number(received[name], f"{role} parameters {name}")
        guard(abs(observed - value) <= PARAMETER_BOUND*max(1.0, abs(value)),
              f"{role} parameters {name} disagrees with the frozen inputs")
    rows = receipt["rows"]
    guard(isinstance(rows, list) and len(rows) == 5, f"{role} must retain exactly five rows")
    for index, (key, J, N, h, delta) in enumerate(SCHEDULE):
        row = rows[index]
        guard(isinstance(row, dict) and ROW_KEYS <= set(row), f"{role} rows[{index}] omits required fields")
        guard(row["key"] == key, f"{role} rows[{index}] key is {row['key']!r}, expected {key!r}")
        guard(row["J"] == J and row["N"] == N, f"{role} row {key} basis mismatch")
        guard(finite_number(row["h"], f"{role} row {key} h") == h, f"{role} row {key} coupling mismatch")
        guard(finite_number(row["delta"], f"{role} row {key} delta") == delta,
              f"{role} row {key} dilation mismatch")
        guard(row["archive"] == f"{key}.npz", f"{role} row {key} archive name mismatch")
        guard(re.fullmatch(r"[0-9a-f]{64}", str(row["archive_sha256"])) is not None,
              f"{role} row {key} archive hash is not lowercase SHA-256")
        for name in ROW_SCALARS:
            finite_number(row[name], f"{role} row {key} field {name}")
    return receipt


def consume(directory: Path, role: str, receipt: dict, index: int, static: dict) -> dict:
    """Open one raw archive and bind it to the independently reconstructed row."""
    key, J, N, h, delta = SCHEDULE[index]
    row = receipt["rows"][index]
    archive_path = directory / row["archive"]
    guard(archive_path.is_file(), f"{role} {key}: archive is missing")
    raw = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    guard(raw == row["archive_sha256"], f"{role} {key}: archive raw hash mismatch")
    size = J*N
    with np.load(archive_path, allow_pickle=False) as archive:
        required = list(ARCHIVE_FIELDS) + (list(PRIMARY_ARCHIVE_FIELDS) if role == "primary" else [])
        missing = [name for name in required if name not in archive.files]
        guard(not missing, f"{role} {key}: archive fields missing {missing}")
        times = array_field(archive, "time", (TIME_SAMPLES,), "f").astype(np.float64)
        source_times = array_field(archive, "source_time", (SOURCE_SAMPLES,), "f").astype(np.float64)
        states = array_field(archive, "state", (TIME_SAMPLES, size), "c").astype(np.complex128)
        prepared = array_field(archive, "prepared", (size,), "c").astype(np.complex128)
        source_states = array_field(archive, "source_state", (SOURCE_SAMPLES, size), "c").astype(np.complex128)
        ground = array_field(archive, "ground", (size,), "f").astype(np.float64)
        energy = array_field(archive, "ground_energy", None, "f")
        guard(energy.size == 1, f"{role} {key}: ground_energy must be a scalar")
        ground_energy = float(energy.item())
        stored = {name: array_field(archive, name, None, "f") for name in ARRAY_FIELDS}
        matrices = {name: array_field(archive, name, None, "fc") for name in OPERATOR_FIELDS}
        projected = csr_block(archive, "H", (size, size))
        discarded = csr_block(archive, "R", (2*J + 2*N + 4, size))
        inner = array_field(archive, "inner_indices", (size,), "iu").astype(np.int64)
        outer = array_field(archive, "outer_indices", (2*J + 2*N + 4,), "iu").astype(np.int64)
        spectral = {}
        if role == "primary":
            spectral = dict(eigenvalues=array_field(archive, "eigenvalues", (size,), "f").astype(np.float64),
                            eigenvectors=array_field(archive, "eigenvectors", (size, size), "f").astype(np.float64),
                            source_eigenvalues=array_field(archive, "source_eigenvalues", (J,), "f").astype(np.float64),
                            source_eigenvectors=array_field(archive, "source_eigenvectors", (J, J), "c")
                            .astype(np.complex128))
    validate_grid(times, TIME_HORIZON, TIME_SAMPLES, f"{role} {key}: time")
    validate_grid(source_times, delta, SOURCE_SAMPLES, f"{role} {key}: source time")
    guard(stored["norm"].shape == (TIME_SAMPLES,), f"{role} {key}: norm shape")
    guard(stored["energy_terms"].shape == (TIME_SAMPLES, 4), f"{role} {key}: energy_terms shape")
    for name in ("f2", "pairs", "pair_probability"):
        guard(stored[name].shape == (TIME_SAMPLES,), f"{role} {key}: {name} shape")
    for name, shape in (("S2", (J, J)), ("S4", (J, J)), ("PS2", (J, J)), ("D", (J, J)),
                        ("R2", (N, N)), ("R4", (N, N))):
        guard(matrices[name].shape == shape, f"{role} {key}: {name} shape")
    guard(float(np.max(np.abs(ground))) > 0.0, f"{role} {key}: ground vector vanishes")
    return dict(key=key, J=J, N=N, h=h, delta=delta, row=row, times=times, source_times=source_times,
                states=states, prepared=prepared, source_states=source_states, ground=ground,
                ground_energy=ground_energy, stored=stored, matrices=matrices, projected=projected,
                discarded=discarded, inner=inner, outer=outer, spectral=spectral,
                archive_sha256=raw, static=static)


def normalized_error(actual, reference) -> float:
    """``||actual - reference|| / max(1, ||reference||)``, the frozen comparison scale."""
    first = np.atleast_1d(np.asarray(actual))
    second = np.atleast_1d(np.asarray(reference))
    if first.shape != second.shape:
        demand(first.size == second.size == 1, f"comparison shape mismatch: {first.shape} vs {second.shape}")
        first, second = first.reshape(1), second.reshape(1)
    first = first.astype(np.complex128).reshape(-1)
    second = second.astype(np.complex128).reshape(-1)
    demand(bool(np.isfinite(first).all() and np.isfinite(second).all()), "nonfinite comparison")
    return float(np.linalg.norm(first - second)/max(1.0, float(np.linalg.norm(second))))


def row_error(actual, reference) -> float:
    """Largest per-time row difference, each divided by ``max(1, ||reference row||)``."""
    first = np.asarray(actual, dtype=np.complex128)
    second = np.asarray(reference, dtype=np.complex128)
    demand(first.ndim == 2 and first.shape == second.shape, "row comparison shape mismatch")
    demand(bool(np.isfinite(first).all() and np.isfinite(second).all()), "nonfinite row comparison")
    difference = np.linalg.norm(first - second, axis=1)
    scale = np.maximum(1.0, np.linalg.norm(second, axis=1))
    return float(np.max(difference/scale))


def embed_states(states: np.ndarray, J: int, N: int, target) -> np.ndarray:
    """q-major embedding of a coarser state grid into a larger basis."""
    big_J, big_N = target
    wide = np.zeros((states.shape[0], big_J, big_N), dtype=np.complex128)
    wide[:, :J, :N] = states.reshape(states.shape[0], J, N)
    return wide.reshape(states.shape[0], big_J*big_N)


# ---------------------------------------------------------------------------
# Audit driver
# ---------------------------------------------------------------------------

def audit(state: dict, prerequisites: dict, scientific: dict, primary_dir: Path, independent_dir: Path) -> None:
    """Fill ``state`` incrementally so a failure still retains the attempted evidence."""
    parameters = scientific["parameters"]
    statics: dict[tuple, dict] = {}
    for key, J, N, h, _delta in SCHEDULE:
        if (J, N, h) not in statics:
            statics[(J, N, h)] = build_static(J, N, h, parameters)
    dynamics = {key: build_dynamics(statics[(J, N, h)], delta) for key, J, N, h, delta in SCHEDULE}

    checks, errors, rows, arrays, hashes = (state["checks"], state["errors"], state["rows"],
                                            state["arrays"], state["hashes"])
    directories = {"primary": primary_dir, "independent": independent_dir}
    consumed: dict[tuple, dict] = {}
    for role, source in METHODS.items():
        directory = directories[role]
        guard(directory.is_dir(), f"{role} result directory is missing: {directory}")
        result_path = directory / "result.json"
        receipt = validate_result(result_path, role, parameters)
        hashes[role] = dict(result_raw_sha256=digest(result_path, raw=True),
                            bound_source_sha256=prerequisites["sources"][source],
                            result_path=str(result_path), archives={})
        for index, (key, _J, _N, _h, _delta) in enumerate(SCHEDULE):
            entry = consume(directory, role, receipt, index, statics[(_J, _N, _h)])
            consumed[(role, key)] = entry
            hashes[role]["archives"][key] = entry["archive_sha256"]

    for key, J, N, h, delta in SCHEDULE:
        static = statics[(J, N, h)]
        own = dynamics[key]
        errors[f"{key}:energy_decomposition"] = static["decomposition_error"]
        checks[f"{key}:energy_decomposition"] = static["decomposition_error"] <= MATRIX_BOUND
        row_report = dict(key=key, J=J, N=N, h=h, delta=delta, basis=dict(size=J*N, padded=static["padded_size"]),
                          discarded_rows=2*J + 2*N + 4, methods={})

        reconstructed_arrays: dict[str, dict] = {}
        for role in METHODS:
            prefix = f"{key}:{role}"
            entry = consumed[(role, key)]
            own_arrays = reconstruct_arrays(static, entry["states"], parameters)
            statistics = row_statistics(static, own, own_arrays, parameters)

            for name, field in OPERATOR_FIELDS.items():
                errors[f"{prefix}:{name}"] = normalized_error(entry["matrices"][name], static[field])
                checks[f"{prefix}:{name}"] = errors[f"{prefix}:{name}"] <= MATRIX_BOUND
            errors[f"{prefix}:projected"] = normalized_error(entry["projected"], static["projected"])
            checks[f"{prefix}:projected"] = errors[f"{prefix}:projected"] <= MATRIX_BOUND
            errors[f"{prefix}:discarded"] = normalized_error(entry["discarded"], static["discarded"])
            checks[f"{prefix}:discarded"] = errors[f"{prefix}:discarded"] <= DISCARDED_BOUND
            checks[f"{prefix}:index_map"] = bool(np.array_equal(entry["inner"], static["inner"])
                                                 and np.array_equal(entry["outer"], static["outer"]))
            checks[f"{prefix}:index_order"] = bool(np.all(np.diff(entry["inner"]) > 0)
                                                   and np.all(np.diff(entry["outer"]) > 0))
            checks[f"{prefix}:index_partition"] = bool(
                np.array_equal(np.sort(np.concatenate((entry["inner"], entry["outer"]))),
                               np.arange(static["padded_size"], dtype=np.int64)))
            errors[f"{prefix}:time_grid"] = normalized_error(entry["times"], own["times"])
            checks[f"{prefix}:time_grid"] = errors[f"{prefix}:time_grid"] <= GRID_BOUND
            errors[f"{prefix}:source_time_grid"] = normalized_error(entry["source_times"], own["source_times"])
            checks[f"{prefix}:source_time_grid"] = errors[f"{prefix}:source_time_grid"] <= GRID_BOUND

            errors[f"{prefix}:ground_energy"] = normalized_error(entry["ground_energy"], static["ground_energy"])
            checks[f"{prefix}:ground_energy"] = errors[f"{prefix}:ground_energy"] <= GROUND_ENERGY_BOUND
            errors[f"{prefix}:ground"] = normalized_error(entry["ground"], static["ground"])
            checks[f"{prefix}:ground"] = errors[f"{prefix}:ground"] <= STATE_BOUND
            errors[f"{prefix}:prepared"] = normalized_error(entry["prepared"], own["prepared"])
            checks[f"{prefix}:prepared"] = errors[f"{prefix}:prepared"] <= STATE_BOUND
            errors[f"{prefix}:states"] = row_error(entry["states"], own["states"])
            checks[f"{prefix}:states"] = errors[f"{prefix}:states"] <= STATE_BOUND
            errors[f"{prefix}:source_states"] = row_error(entry["source_states"], own["source_states"])
            checks[f"{prefix}:source_states"] = errors[f"{prefix}:source_states"] <= STATE_BOUND

            if role == "primary":
                spectral = entry["spectral"]
                errors[f"{prefix}:eigenvalues"] = normalized_error(spectral["eigenvalues"], static["eigenvalues"])
                checks[f"{prefix}:eigenvalues"] = errors[f"{prefix}:eigenvalues"] <= SPECTRUM_BOUND
                # Individual excited eigenvectors are not stably defined under
                # near-degeneracy, so the phase-invariant ground projector and the
                # preparation unitary are compared instead.
                stored_ground = np.asarray(spectral["eigenvectors"][:, 0], dtype=np.float64)
                errors[f"{prefix}:ground_projector"] = normalized_error(
                    np.outer(static["ground"], static["ground"]), np.outer(stored_ground, stored_ground))
                checks[f"{prefix}:ground_projector"] = errors[f"{prefix}:ground_projector"] <= STATE_BOUND
                errors[f"{prefix}:source_eigenvalues"] = normalized_error(spectral["source_eigenvalues"],
                                                                          static["generator_values"])
                checks[f"{prefix}:source_eigenvalues"] = errors[f"{prefix}:source_eigenvalues"] <= SPECTRUM_BOUND
                stored_generator = spectral["source_eigenvectors"]
                stored_unitary = stored_generator @ (np.exp(-1j*delta*spectral["source_eigenvalues"])[:, None]
                                                     * stored_generator.conj().T)
                errors[f"{prefix}:preparation_unitary"] = normalized_error(own["preparation_unitary"],
                                                                          stored_unitary)
                checks[f"{prefix}:preparation_unitary"] = errors[f"{prefix}:preparation_unitary"] <= STATE_BOUND

            for name in ARRAY_FIELDS:
                errors[f"{prefix}:{name}"] = float(np.max(
                    np.abs(entry["stored"][name] - own_arrays[name])
                    / np.maximum(1.0, np.abs(own_arrays[name]))))
                checks[f"{prefix}:{name}"] = errors[f"{prefix}:{name}"] <= RECONSTRUCTION_BOUND
            total = own_arrays["energy_terms"].sum(axis=1)
            stored_total = entry["stored"]["energy_terms"].sum(axis=1)
            initial = float(total[0])
            checks[f"{prefix}:term_sum_identity"] = bool(
                np.max(np.abs(stored_total - total)) <= RECONSTRUCTION_BOUND*max(1.0, abs(initial)))
            checks[f"{prefix}:pair_partition_identity"] = bool(
                np.max(np.abs(own_arrays["pair_probability"] + own_arrays["zero_probability"]
                              - own_arrays["norm"])) <= RECONSTRUCTION_BOUND)
            checks[f"{prefix}:norm_preservation"] = bool(
                np.max(np.abs(entry["stored"]["norm"] - 1.0)) <= NORM_BOUND
                and np.max(np.abs(own_arrays["norm"] - 1.0)) <= NORM_BOUND)
            checks[f"{prefix}:total_energy_preservation"] = bool(
                np.max(np.abs(stored_total - stored_total[0])) <= TOTAL_ENERGY_BOUND*max(1.0, abs(initial))
                and np.max(np.abs(total - initial)) <= TOTAL_ENERGY_BOUND*max(1.0, abs(initial)))
            for name in ROW_SCALARS:
                errors[f"{prefix}:row:{name}"] = normalized_error(entry["row"][name], statistics[name])
                checks[f"{prefix}:row:{name}"] = errors[f"{prefix}:row:{name}"] <= RECONSTRUCTION_BOUND

            # --- integral bounds --------------------------------------
            own_spectrum = dict(vectors=static["eigenvectors"], eigenvalues=static["eigenvalues"],
                                ground_energy=static["ground_energy"])
            if role == "primary":
                frozen_spectrum = dict(vectors=entry["spectral"]["eigenvectors"],
                                       eigenvalues=entry["spectral"]["eigenvalues"],
                                       ground_energy=float(entry["spectral"]["eigenvalues"][0]))
            else:
                frozen_spectrum = own_spectrum
            evolution = evolution_bound(static, frozen_spectrum, entry["prepared"], entry["states"],
                                        entry["times"])
            auditor_evolution = evolution_bound(static, own_spectrum, own["prepared"], own["states"], own["times"])
            preparation = preparation_bound(static, entry["source_states"], entry["source_times"])
            auditor_preparation = preparation_bound(static, own["source_states"], own["source_times"])
            bounds = dict(evolution_upper=float(evolution["upper"]),
                          evolution_trapezoid=float(evolution["trapezoid"]),
                          evolution_lipschitz=float(evolution["lipschitz"]),
                          evolution_remainder=float(evolution["remainder"]),
                          evolution_spectral_consistency=float(evolution["spectral_consistency"]),
                          preparation_upper=float(preparation["upper"]),
                          preparation_trapezoid=float(preparation["trapezoid"]),
                          preparation_lipschitz=float(preparation["lipschitz"]),
                          preparation_remainder=float(preparation["remainder"]),
                          full_space_duhamel=TIME_HORIZON*float(static["ground_residual"]),
                          projector_probability_error_bound=2*(float(evolution["upper"])
                                                              + float(preparation["upper"])),
                          independent_evolution_upper=float(auditor_evolution["upper"]),
                          independent_preparation_upper=float(auditor_preparation["upper"]),
                          independent_evolution_lipschitz=float(auditor_evolution["lipschitz"]),
                          independent_preparation_lipschitz=float(auditor_preparation["lipschitz"]),
                          independent_projector_probability_error_bound=2*(
                              float(auditor_evolution["upper"]) + float(auditor_preparation["upper"])))
            checks[f"{prefix}:preparation_interval"] = bool(
                bounds["preparation_upper"] == 0.0 if delta == 0.0
                else (bounds["preparation_upper"] >= bounds["preparation_trapezoid"] >= 0.0
                      and bounds["preparation_remainder"] >= 0.0))
            checks[f"{prefix}:evolution_interval"] = bool(
                bounds["evolution_upper"] >= bounds["evolution_trapezoid"] >= 0.0
                and bounds["evolution_remainder"] >= 0.0)
            for name, value in bounds.items():
                errors[f"{prefix}:{name}"] = float(value)
            arrays[f"{key}__{role}__leakage_samples"] = evolution["samples"]
            arrays[f"{key}__{role}__source_leakage_samples"] = preparation["samples"]
            arrays[f"{key}__{role}__auditor_leakage_samples"] = auditor_evolution["samples"]
            arrays[f"{key}__{role}__auditor_source_leakage_samples"] = auditor_preparation["samples"]
            for name in ARRAY_FIELDS:
                arrays[f"{key}__{role}__{name}"] = own_arrays[name]
            reconstructed_arrays[role] = own_arrays
            row_report["methods"][role] = dict(
                archive_sha256=entry["archive_sha256"],
                stored={name: float(entry["row"][name]) for name in ROW_SCALARS},
                reconstructed={name: float(value) for name, value in statistics.items()},
                bounds={name: float(value) for name, value in bounds.items()},
                errors={name: value for name, value in errors.items() if name.startswith(prefix + ":")})

        # --- same-basis cross-method comparison -----------------------
        first, second = consumed[("primary", key)], consumed[("independent", key)]
        for name, value, bound in (
                ("projected", normalized_error(first["projected"], second["projected"]), MATRIX_BOUND),
                ("discarded", normalized_error(first["discarded"], second["discarded"]), DISCARDED_BOUND),
                ("ground_energy", normalized_error(first["ground_energy"], second["ground_energy"]),
                 GROUND_ENERGY_BOUND),
                ("ground", normalized_error(first["ground"], second["ground"]), STATE_BOUND),
                ("prepared", normalized_error(first["prepared"], second["prepared"]), STATE_BOUND),
                ("states", row_error(first["states"], second["states"]), STATE_BOUND),
                ("source_states", row_error(first["source_states"], second["source_states"]), STATE_BOUND)):
            errors[f"{key}:cross:{name}"] = float(value)
            checks[f"{key}:cross:{name}"] = bool(value <= bound)
        for name in OPERATOR_FIELDS:
            value = normalized_error(first["matrices"][name], second["matrices"][name])
            errors[f"{key}:cross:{name}"] = float(value)
            checks[f"{key}:cross:{name}"] = bool(value <= MATRIX_BOUND)
        # The derived arrays are compared only through the auditor's own
        # reconstruction from each method's raw states, never by echoing one
        # stored archive against the other.
        for name in ARRAY_FIELDS:
            value = normalized_error(reconstructed_arrays["primary"][name],
                                     reconstructed_arrays["independent"][name])
            errors[f"{key}:cross:reconstructed:{name}"] = float(value)
            checks[f"{key}:cross:reconstructed:{name}"] = bool(value <= STATE_BOUND)

        # --- frozen gates on this row ---------------------------------
        if key == FINE:
            for role in METHODS:
                reported = row_report["methods"][role]["bounds"]
                for field, bound in (("evolution_upper", EVOLUTION_BOUND),
                                     ("preparation_upper", PREPARATION_BOUND),
                                     ("independent_evolution_upper", EVOLUTION_BOUND),
                                     ("independent_preparation_upper", PREPARATION_BOUND)):
                    errors[f"{key}:{role}:{field}_gate"] = reported[field]
                    checks[f"{key}:{role}:{field}_gate"] = bool(reported[field] <= bound)
                value = reported["full_space_duhamel"]
                errors[f"{key}:{role}:ground_residual_gate"] = value
                checks[f"{key}:{role}:ground_residual_gate"] = bool(value <= GROUND_RESIDUAL_BOUND)
        if key in CONTROL_KEYS:
            for role in METHODS:
                change = row_report["methods"][role]["reconstructed"]["maximum_pair_probability_change"]
                stored_change = float(np.max(np.abs(
                    consumed[(role, key)]["stored"]["pair_probability"]
                    - float(consumed[(role, key)]["row"]["ground_pair_probability"]))))
                errors[f"{key}:{role}:control_change"] = max(change, stored_change)
                checks[f"{key}:{role}:control_change"] = bool(max(change, stored_change) <= CONTROL_BOUND)
        rows.append(row_report)

    # --- basis embedding of the coupled trajectory ----------------------
    for role in METHODS:
        for small, large, bound in ((COARSE, MEDIUM, COARSE_MEDIUM_BOUND),
                                    (MEDIUM, FINE, MEDIUM_FINE_BOUND)):
            entry = consumed[(role, small)]
            value = row_error(embed_states(entry["states"], entry["J"], entry["N"], BASIS[large]),
                              consumed[(role, large)]["states"])
            errors[f"{role}:{small}->{large}"] = float(value)
            checks[f"{role}:{small}->{large}"] = bool(value <= bound)
            value = row_error(embed_states(dynamics[small]["states"], entry["J"], entry["N"], BASIS[large]),
                              dynamics[large]["states"])
            errors[f"{role}:independent:{small}->{large}"] = float(value)
            checks[f"{role}:independent:{small}->{large}"] = bool(value <= bound)

    # --- the frozen transfer floor (reported, never a numerical gate) ---
    gains = {}
    for role in METHODS:
        entry = consumed[(role, FINE)]
        own_arrays = reconstruct_arrays(entry["static"], entry["states"], parameters)
        ground_arrays = reconstruct_arrays(entry["static"], entry["static"]["ground"][None, :], parameters)
        gains[role] = float(np.max(own_arrays["pair_probability"])
                            - float(ground_arrays["pair_probability"][0]))
    numeric_pass = bool(checks) and all(value is True for value in checks.values())
    state["transfer"] = dict(fine_coupled_peak_gain=gains, floor=TRANSFER_FLOOR,
                             both_methods_above_floor=bool(numeric_pass
                                                           and all(value > TRANSFER_FLOOR for value in gains.values())))
    state["numeric_pass"] = numeric_pass

    # --- the auditor's own raw reconstruction, retained and hash-bound ---
    for key, J, N, h, _delta in SCHEDULE:
        static, own = statics[(J, N, h)], dynamics[key]
        arrays[f"{key}__auditor__ground"] = static["ground"]
        arrays[f"{key}__auditor__prepared"] = own["prepared"]
        arrays[f"{key}__auditor__discarded"] = static["discarded"]
        for name in ("coordinate", "momentum", "quartic", "radius", "radial_quartic", "dilation"):
            arrays[f"{key}__auditor__{name}"] = static[name]
        arrays[f"{key}__auditor__source_lipschitz_terms"] = (static["carrier_row_norms"]
                                                            * np.abs(static["generator_values"])
                                                            * np.abs(static["leaked_generator"]))
    for name, value in list(arrays.items()):
        array = np.asarray(value)
        demand(array.dtype.kind in "fc" and bool(np.isfinite(array).all()),
               f"audit array {name} is unusable")
        arrays[name] = array


def jsonable(value):
    if isinstance(value, np.ndarray):
        return [jsonable(item) for item in value.tolist()]
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        guard(math.isfinite(value), "nonfinite JSON number")
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, str) or value is None:
        return value
    if isinstance(value, complex):
        raise GuardError("complex values cannot enter the JSON receipt")
    if isinstance(value, dict):
        return {str(name): jsonable(item) for name, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    raise GuardError(f"unsupported JSON value: {type(value).__name__}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--primary", type=Path, required=True)
    parser.add_argument("--independent", type=Path, required=True)
    args = parser.parse_args()
    receipt = dict(schema=SCHEMA, role="residuals", verdict=VERDICT_INCONCLUSIVE, numeric_pass=False,
                   checks={}, failed_checks=[], numerical_errors={}, rows=[],
                   input_evidence_hashes={}, parameters={}, transfer={}, error=None,
                   complete_physical_matter_formation=False, scope=SCOPE)
    if args.output.exists():
        print(json.dumps(dict(verdict=VERDICT_INCONCLUSIVE, numeric_pass=False,
                              error="output directory already exists",
                              complete_physical_matter_formation=False), allow_nan=False))
        return 1
    try:
        args.output.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        print(json.dumps(dict(verdict=VERDICT_INCONCLUSIVE, numeric_pass=False,
                              error=f"output directory cannot be created: {exc}",
                              complete_physical_matter_formation=False), allow_nan=False))
        return 1
    state = dict(checks={}, errors={}, rows=[], arrays={}, hashes={}, transfer={}, numeric_pass=False)
    guard_failure = False
    try:
        prerequisites = validate_manifest(args.manifest)
        scientific = validate_inherited(prerequisites)
        receipt["manifest_sha256"] = prerequisites["manifest_sha256"]
        receipt["evidence_root"] = prerequisites["evidence_root"]
        receipt["parameters"] = jsonable(scientific["parameters"])
        receipt["prerequisites"] = jsonable(dict(
            sections=prerequisites["sections"], sources=prerequisites["sources"],
            inherited=prerequisites["inherited"], mathematical_reviews=prerequisites["mathematical_reviews"],
            wave_number=scientific["wave_number"], witnesses=scientific["witnesses"],
            pump_verdict=PUMP_VERDICT))
        receipt["input_evidence_hashes"] = dict(
            manifest_sha256=prerequisites["manifest_sha256"],
            manifest_raw_sha256=prerequisites["manifest_raw_sha256"],
            sections=prerequisites["sections"], sources=prerequisites["sources"],
            inherited=prerequisites["inherited"],
            mathematical_reviews=prerequisites["mathematical_reviews"])
        audit(state, prerequisites, scientific, args.primary.resolve(), args.independent.resolve())
        receipt["input_evidence_hashes"]["consumed"] = jsonable(state["hashes"])
        receipt["checks"] = {name: bool(value) for name, value in state["checks"].items()}
        receipt["failed_checks"] = jsonable(sorted(name for name, value in state["checks"].items()
                                                   if value is not True))
        receipt["numerical_errors"] = jsonable(state["errors"])
        receipt["rows"] = jsonable(state["rows"])
        receipt["transfer"] = jsonable(state["transfer"])
        if not state["numeric_pass"]:
            verdict = VERDICT_INCONCLUSIVE
        elif state["transfer"]["both_methods_above_floor"]:
            verdict = VERDICT_SUPPORTS
        else:
            verdict = VERDICT_NO_TRANSFER
        receipt["verdict"] = verdict
        receipt["numeric_pass"] = bool(state["numeric_pass"])
    except GuardError as exc:
        guard_failure = True
        receipt.update(verdict=VERDICT_INCONCLUSIVE, numeric_pass=False, rows=[], checks={},
                       failed_checks=[], numerical_errors={}, transfer={},
                       error=f"{type(exc).__name__}: {exc}")
    except Exception as exc:
        # A scientific failure keeps the attempted rows, checks, bounds and arrays.
        receipt["checks"] = {name: bool(value) for name, value in state["checks"].items()}
        receipt["failed_checks"] = jsonable(sorted(name for name, value in state["checks"].items()
                                                   if value is not True))
        receipt["numerical_errors"] = jsonable(state["errors"])
        receipt["rows"] = jsonable(state["rows"])
        receipt["input_evidence_hashes"]["consumed"] = jsonable(state["hashes"])
        receipt["transfer"] = jsonable(dict(fine_coupled_peak_gain=state["transfer"].get("fine_coupled_peak_gain", {}),
                                           floor=TRANSFER_FLOOR, both_methods_above_floor=False))
        receipt["verdict"] = VERDICT_INCONCLUSIVE
        receipt["numeric_pass"] = False
        receipt["error"] = f"{type(exc).__name__}: {exc}"
    json.dumps(jsonable(receipt), allow_nan=False)
    arrays = {} if guard_failure else state["arrays"]
    if arrays:
        path = args.output / "audit.npz"
        np.savez_compressed(path, **arrays)
        receipt["arrays"] = {"audit.npz": hashlib.sha256(path.read_bytes()).hexdigest()}
    (args.output / "result.json").write_text(json.dumps(jsonable(receipt), indent=2, allow_nan=False) + "\n",
                                             encoding="utf-8")
    print(json.dumps({name: receipt.get(name) for name in
                      ("verdict", "numeric_pass", "error", "complete_physical_matter_formation")}, allow_nan=False))
    return 0 if receipt["numeric_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
