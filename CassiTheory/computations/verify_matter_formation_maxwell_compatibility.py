#!/usr/bin/env python3
"""Independent component-energy qualification of the section 56 massless-vector compatibility schedule.

Run from the repository root after sealing the source manifest:
python computations/verify_matter_formation_maxwell_compatibility.py --manifest PATH --output FRESH_DIR

This is the independent numerical path: every 4x4 mass entry is reconstructed by the
polarization identity M_ij = [E(e_i+e_j) - E(e_i-e_j)]/2 from the declared component
energy E(A,B) = a/2*|(g*A.T + h*B*I)Psi|^2 + d/2*|g*A cross Phi|^2. No analytic mass
entry, determinant, or Schur-complement expression is evaluated anywhere in this path;
the zero-density control is handled by the component energy alone, so the polarization
formula for s is never used at rho = 0. Generalized spectra solve M*modes = K*modes*omega2
with scipy.linalg.eigh(M, K) and sorted full eigenpairs whose columns are K-orthonormal.
Negative eigenvalues in the excluded negative-adjoint control are retained, not clipped.
The primary source is read only to verify its hash; its code and results are not used.
It supports no physical particle-mass, mediator, formation, SU(2)_L, or auxiliary SU(2)_Q claim beyond
the conditional compatibility constraint registered in section 56.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import scipy.linalg

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
REPORT = "computations/matter-formation-continuum-report.md"
HEADING = "## 56. Working notes: massless-vector compatibility of the matter vacuum"
MANIFEST_SCHEMA = "matter-formation-maxwell-compatibility-manifest-v1"
SCHEMA = "matter-formation-maxwell-compatibility-v1"
ROLE = "independent"
SOURCES = {
    "computations/matter_formation_maxwell_compatibility.py",
    "computations/verify_matter_formation_maxwell_compatibility.py",
    "foundations/particle-stationary-action-closure.md",
    "foundations/nonabelian-magnetic-core-boundary.md",
    "standard-model/su2-gauge-extension.md",
}
TOLERANCE = 1e-10
ZERO_THRESHOLD = 1e-10
WITNESS = {"a": 0.83, "d": 1.25, "rho": 1.2, "v": 0.9, "g": 0.71, "h": 0.41}
PHI = (1.0 + math.sqrt(5.0)) / 2.0
PHI_MINUS_CUBED = PHI ** -3
C_VALUES = [-1.0, -0.7, 0.0, PHI_MINUS_CUBED, 0.8, 1.0]
DELTA_VALUES = [0.0, math.pi / 3.0, math.pi / 2.0]
CASE_COUNT = 27
PARAMETER_ORDER = ("rho", "a", "d", "v", "g", "h", "c", "delta")
KINETIC = np.diag([0.6, 0.6, 0.6, 1.1])
PROBES = np.array([[1.0, 0.0, 0.0, 0.0],
                   [0.0, 0.0, 0.0, 1.0],
                   [1.0, 2.0, -1.0, 0.5],
                   [-0.3, 0.7, 0.2, -0.4]])
AXIS = np.array([1.0, 2.0, 3.0]) / math.sqrt(14.0)

PAULI_X = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=complex)
PAULI_Y = np.array([[0.0, -1.0j], [1.0j, 0.0]], dtype=complex)
PAULI_Z = np.array([[1.0, 0.0], [0.0, -1.0]], dtype=complex)
PAULI = (PAULI_X, PAULI_Y, PAULI_Z)
GENERATORS = tuple(0.5 * p for p in PAULI)
IDENTITY2 = np.eye(2, dtype=complex)


def canonical_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def sha(path: Path) -> str:
    return hashlib.sha256(canonical_bytes(path)).hexdigest()


def section_bytes(path: Path) -> bytes:
    lines = canonical_bytes(path).decode("utf-8").splitlines(keepends=True)
    matches = [i for i, line in enumerate(lines) if line.rstrip() == HEADING]
    if len(matches) != 1:
        raise ValueError("section 56 must occur exactly once")
    first = matches[0]
    last = next((i for i in range(first + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return ("".join(lines[first:last]).rstrip() + "\n").encode("utf-8")


def validate_manifest(path: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValueError("unexpected manifest schema")
    record = manifest["section"]
    if record["path"] != REPORT or record["heading"] != HEADING:
        raise ValueError("unexpected notebook section")
    frozen = canonical_bytes(path.parent / record["snapshot"])
    if hashlib.sha256(frozen).hexdigest() != record["sha256"] or section_bytes(ROOT / REPORT) != frozen:
        raise ValueError("frozen or current section mismatch")
    sources = manifest["sources"]
    if len(sources) != len(SOURCES) or {item["path"] for item in sources} != SOURCES:
        raise ValueError("incomplete source bindings")
    for item in sources:
        if sha(ROOT / item["path"]) != item["sha256"] or sha(path.parent / item["snapshot"]) != item["sha256"]:
            raise ValueError(f"source mismatch: {item['path']}")
    review = manifest["mathematical_review"]
    if review.get("accepted") is not True or sha(path.parent / review["snapshot"]) != review["sha256"]:
        raise ValueError("mathematical review is not qualified")
    return manifest


def schedule() -> list[tuple[str, dict[str, float]]]:
    rows: list[tuple[str, dict[str, float]]] = []
    for c_index, c_value in enumerate(C_VALUES):
        for phase_index, delta in enumerate(DELTA_VALUES):
            rows.append((f"vacuum_c{c_index}_phase{phase_index}",
                         {**WITNESS, "c": c_value, "delta": delta}))
    for phase_index, delta in enumerate(DELTA_VALUES):
        rows.append((f"no_adjoint_phase{phase_index}",
                     {**WITNESS, "c": PHI_MINUS_CUBED, "delta": delta, "d": 0.0}))
    for phase_index, delta in enumerate(DELTA_VALUES):
        rows.append((f"uncharged_doublet_phase{phase_index}",
                     {**WITNESS, "c": PHI_MINUS_CUBED, "delta": delta, "h": 0.0}))
    rows.append(("zero_density", {**WITNESS, "c": PHI_MINUS_CUBED, "delta": 0.0, "rho": 0.0}))
    rows.append(("zero_su2_coupling", {**WITNESS, "c": PHI_MINUS_CUBED, "delta": 0.0, "g": 0.0}))
    rows.append(("negative_adjoint", {**WITNESS, "c": 0.0, "delta": 0.0, "d": -1.25}))
    if len(rows) != CASE_COUNT:
        raise ValueError("schedule length defect")
    return rows


def gauge_frame() -> tuple[np.ndarray, np.ndarray]:
    axis_generators = AXIS[0] * PAULI_X + AXIS[1] * PAULI_Y + AXIS[2] * PAULI_Z
    unitary = (IDENTITY2 + 1.0j * axis_generators) / math.sqrt(2.0)
    rotation = np.empty((3, 3))
    for a in range(3):
        for b in range(3):
            rotation[a, b] = 0.5 * np.trace(PAULI[a] @ unitary @ PAULI[b]
                                            @ unitary.conjugate().T).real
    lifted = np.eye(4)
    lifted[:3, :3] = rotation
    return unitary, lifted


def vacuum_state(parameters: dict[str, float]) -> tuple[np.ndarray, np.ndarray]:
    rho = parameters["rho"]
    c = parameters["c"]
    delta = parameters["delta"]
    spinor = math.sqrt(rho) * np.array(
        [math.sqrt((1.0 + c) / 2.0),
         np.exp(1.0j * delta) * math.sqrt((1.0 - c) / 2.0)], dtype=complex)
    condensate = np.array([0.0, 0.0, parameters["v"]])
    return spinor, condensate


def component_energy(spinor: np.ndarray, condensate: np.ndarray,
                     parameters: dict[str, float], coordinates: np.ndarray) -> float:
    adjoint = coordinates[:3]
    singlet = coordinates[3]
    operator = (parameters["g"] * (adjoint[0] * GENERATORS[0] + adjoint[1] * GENERATORS[1]
                                   + adjoint[2] * GENERATORS[2])
                + (parameters["h"] * singlet) * IDENTITY2)
    covariant = operator @ spinor
    doublet = 0.5 * parameters["a"] * float(np.vdot(covariant, covariant).real)
    crossed = np.cross(parameters["g"] * adjoint, condensate)
    singlet_part = 0.5 * parameters["d"] * float(crossed @ crossed)
    return doublet + singlet_part


def polarized_mass(spinor: np.ndarray, condensate: np.ndarray,
                   parameters: dict[str, float]) -> np.ndarray:
    mass = np.zeros((4, 4))
    for i in range(4):
        first = np.zeros(4)
        first[i] = 1.0
        for j in range(4):
            second = np.zeros(4)
            second[j] = 1.0
            plus = component_energy(spinor, condensate, parameters, first + second)
            minus = component_energy(spinor, condensate, parameters, first - second)
            mass[i, j] = 0.5 * (plus - minus)
    return mass


def expected_inertia(parameters: dict[str, float]) -> list[int]:
    if parameters["g"] == 0.0:
        return [0, 3, 1]
    if parameters["rho"] == 0.0:
        return [0, 2, 2]
    if parameters["d"] < 0.0:
        return [2, 0, 2]
    if (parameters["d"] == 0.0 or parameters["h"] == 0.0
            or abs(abs(parameters["c"]) - 1.0) == 0.0):
        return [0, 1, 3]
    return [0, 0, 4]


def inertia_counts(values: np.ndarray) -> list[int]:
    negative = int(np.count_nonzero(values < -ZERO_THRESHOLD))
    zero = int(np.count_nonzero(np.abs(values) <= ZERO_THRESHOLD))
    positive = int(np.count_nonzero(values > ZERO_THRESHOLD))
    return [negative, zero, positive]


def normalized_error(actual: np.ndarray, reference: np.ndarray) -> float:
    scale = max(1.0, float(np.linalg.norm(reference)))
    return float(np.linalg.norm(actual - reference)) / scale


def probe_quadratic(mass: np.ndarray, coordinates: np.ndarray) -> np.ndarray:
    return 0.5 * np.einsum("pi,ij,pj->p", coordinates, mass, coordinates)


def solve(mass: np.ndarray) -> tuple[np.ndarray, np.ndarray, float, float]:
    values, vectors = scipy.linalg.eigh(mass, KINETIC)
    residual = normalized_error(mass @ vectors, KINETIC @ vectors * values)
    orthonormality = normalized_error(vectors.T @ KINETIC @ vectors, np.eye(4))
    return values, vectors, residual, orthonormality


def calculate() -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    unitary, rotation = gauge_frame()
    rows: list[dict[str, Any]] = []
    masses = np.zeros((CASE_COUNT, 4, 4))
    masses_rotated = np.zeros((CASE_COUNT, 4, 4))
    omega2 = np.zeros((CASE_COUNT, 4))
    omega2_rotated = np.zeros((CASE_COUNT, 4))
    modes = np.zeros((CASE_COUNT, 4, 4))
    modes_rotated = np.zeros((CASE_COUNT, 4, 4))
    probe_energies = np.zeros((CASE_COUNT, 4))
    probe_energies_rotated = np.zeros((CASE_COUNT, 4))
    for case, (label, parameters) in enumerate(schedule()):
        spinor, condensate = vacuum_state(parameters)
        mass = polarized_mass(spinor, condensate, parameters)
        rotated_spinor = unitary @ spinor
        rotated_condensate = rotation[:3, :3] @ condensate
        mass_rotated = polarized_mass(rotated_spinor, rotated_condensate, parameters)
        rotated_probes = PROBES @ rotation.T
        energies = np.array([component_energy(spinor, condensate, parameters, x)
                             for x in PROBES])
        rotated_energies = np.array(
            [component_energy(rotated_spinor, rotated_condensate, parameters, x)
             for x in rotated_probes])
        values, vectors, residual, orthonormality = solve(mass)
        rotated_values, rotated_vectors, rotated_residual, rotated_orthonormality = \
            solve(mass_rotated)
        errors = {
            "gauge_covariance": normalized_error(rotation.T @ mass_rotated @ rotation,
                                                 mass),
            "probe_energy_rotation_invariance": normalized_error(rotated_energies, energies),
            "probe_quadratic_energy": normalized_error(probe_quadratic(mass, PROBES), energies),
            "rotated_probe_quadratic_energy": normalized_error(
                probe_quadratic(mass_rotated, rotated_probes), rotated_energies),
            "eigen_residual": residual,
            "rotated_eigen_residual": rotated_residual,
            "k_orthonormality": orthonormality,
            "rotated_k_orthonormality": rotated_orthonormality,
            "frame_spectrum_difference": normalized_error(rotated_values, values),
        }
        inertia = inertia_counts(values)
        rotated_inertia = inertia_counts(rotated_values)
        target = expected_inertia(parameters)
        errors["inertia_schedule_mismatch"] = 0.0 if (inertia == target
                                                      and rotated_inertia == target) else 1.0
        within_tolerance = all(errors[name] <= TOLERANCE for name in errors
                               if name != "inertia_schedule_mismatch") and \
            errors["inertia_schedule_mismatch"] == 0.0
        rows.append({"case": case, "label": label,
                     "parameters": {name: float(parameters[name]) for name in PARAMETER_ORDER},
                     "inertia": inertia, "rotated_inertia": rotated_inertia,
                     "errors": errors, "within_tolerance": bool(within_tolerance)})
        masses[case] = mass
        masses_rotated[case] = mass_rotated
        omega2[case] = values
        omega2_rotated[case] = rotated_values
        modes[case] = vectors
        modes_rotated[case] = rotated_vectors
        probe_energies[case] = energies
        probe_energies_rotated[case] = rotated_energies
    arrays = {"mass": masses, "mass_rotated": masses_rotated, "kinetic": KINETIC,
              "omega2": omega2, "modes": modes, "omega2_rotated": omega2_rotated,
              "modes_rotated": modes_rotated, "probe_energies": probe_energies,
              "probe_energies_rotated": probe_energies_rotated, "probes": PROBES,
              "gauge_rotation": rotation}
    finite = all(array.dtype == np.float64 and np.isfinite(array).all()
                 for array in arrays.values())

    def worst(name: str) -> float:
        return max(float(row["errors"][name]) for row in rows)

    checks = {
        "schedule_exact_rows": bool(len(rows) == CASE_COUNT),
        "kinetic_positive_definite": bool(np.all(np.linalg.eigvalsh(KINETIC) > 0.0)),
        "raw_arrays_finite_float64": bool(finite),
        "gauge_covariance_within_tolerance": worst("gauge_covariance") <= TOLERANCE,
        "probe_energy_rotation_invariance_within_tolerance":
            worst("probe_energy_rotation_invariance") <= TOLERANCE,
        "probe_quadratic_energy_within_tolerance":
            worst("probe_quadratic_energy") <= TOLERANCE,
        "rotated_probe_quadratic_energy_within_tolerance":
            worst("rotated_probe_quadratic_energy") <= TOLERANCE,
        "eigen_residual_within_tolerance": worst("eigen_residual") <= TOLERANCE,
        "rotated_eigen_residual_within_tolerance": worst("rotated_eigen_residual") <= TOLERANCE,
        "k_orthonormality_within_tolerance": worst("k_orthonormality") <= TOLERANCE,
        "rotated_k_orthonormality_within_tolerance":
            worst("rotated_k_orthonormality") <= TOLERANCE,
        "frame_spectrum_agreement_within_tolerance":
            worst("frame_spectrum_difference") <= TOLERANCE,
        "inertia_schedule_exact": worst("inertia_schedule_mismatch") == 0.0,
        "rows_within_tolerance": all(row["within_tolerance"] for row in rows),
    }
    checks = {name: bool(value) for name, value in checks.items()}
    passed = all(checks.values())
    result = {"schema": SCHEMA, "role": ROLE,
              "verdict": "SUPPORTS-conditional massless-vector compatibility constraint"
              if passed else "INCONCLUSIVE",
              "numeric_pass": passed, "checks": checks, "rows": rows,
              "scope": "Conditional quadratic-form compatibility audit of the section 56 "
                       "massless-vector schedule on the declared homogeneous component-energy "
                       "witness family: full-rank positive mass interior, one exact zero mode in "
                       "the aligned, no-adjoint, and uncharged controls, and the indefinite "
                       "negative-adjoint control excluded without clipping. No physical particle "
                       "mass, mediator, experimental bound, microscopic stabilizer or global "
                       "quotient, SU(2)_L or auxiliary SU(2)_Q identification, stationary state, "
                       "or formation result follows; the complete matter-formation objective "
                       "remains open.",
              "complete_physical_matter_formation": False}
    return result, arrays


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    binding = {"manifest_sha256": None, "source_sha256": sha(SELF), "arrays_sha256": None}
    failure = {"schema": SCHEMA, "role": ROLE, "numeric_pass": False,
               "verdict": "INCONCLUSIVE", "checks": {}, "rows": [],
               "scope": "Conditional one-Abelian-factor transverse-vector compatibility; "
                        "no physical mass normalization, quantum sector or formation result.",
               "complete_physical_matter_formation": False}
    created = False
    try:
        output.mkdir(parents=True, exist_ok=False)
        created = True
        binding["manifest_sha256"] = sha(args.manifest)
        validate_manifest(args.manifest)
        result, arrays = calculate()
        if not result["checks"]["raw_arrays_finite_float64"]:
            raise ValueError("nonfinite or non-float64 scientific arrays")
        handle = io.BytesIO()
        np.savez_compressed(handle, **arrays)
        payload = handle.getvalue()
        with (output / "arrays.npz").open("xb") as stream:
            stream.write(payload)
        binding["arrays_sha256"] = hashlib.sha256(payload).hexdigest()
        result.update(binding)
    except Exception as exc:
        result = {**failure, **binding, "error": f"{type(exc).__name__}: {exc}"}
    try:
        receipt_text = json.dumps(result, indent=2, allow_nan=False) + "\n"
    except (TypeError, ValueError) as exc:
        result = {**failure, **binding, "error": f"receipt {type(exc).__name__}: {exc}"}
        receipt_text = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if created:
        try:
            with (output / "result.json").open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(receipt_text)
        except OSError as exc:
            result = {**failure, **binding, "error": f"receipt {type(exc).__name__}: {exc}"}
    print(json.dumps({"verdict": result["verdict"], "numeric_pass": result["numeric_pass"],
                      "role": ROLE, "checks": len(result["checks"]),
                      "rows": len(result["rows"]), "errors": result.get("error"),
                      "complete_physical_matter_formation": False}, allow_nan=False), flush=True)
    return 0 if result["numeric_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
