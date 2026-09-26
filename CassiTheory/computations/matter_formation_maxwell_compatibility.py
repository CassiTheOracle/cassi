#!/usr/bin/env python3
"""Source-bound transverse gauge-mass qualification for notebook section 56.

Run from the repository root after sealing the sources and mathematical review:
python computations/matter_formation_maxwell_compatibility.py --manifest PATH --output FRESH_DIR
The supplied Abelian gauging is a comparison. No particle or formation is selected.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
REPORT = "computations/matter-formation-continuum-report.md"
HEADING = "## 56. Working notes: massless-vector compatibility of the matter vacuum"
MANIFEST_SCHEMA = "matter-formation-maxwell-compatibility-manifest-v1"
SCHEMA = "matter-formation-maxwell-compatibility-v1"
VERDICT = "SUPPORTS-conditional massless-vector compatibility constraint"
SOURCES = {
    "computations/matter_formation_maxwell_compatibility.py",
    "computations/verify_matter_formation_maxwell_compatibility.py",
    "foundations/particle-stationary-action-closure.md",
    "foundations/nonabelian-magnetic-core-boundary.md",
    "standard-model/su2-gauge-extension.md",
}
TOL = 1e-10
SIGMA = np.array([[[0, 1], [1, 0]], [[0, -1j], [1j, 0]], [[1, 0], [0, -1]]], dtype=complex)
KINETIC = np.diag([0.6, 0.6, 0.6, 1.1])
PROBES = np.array([[1, 0, 0, 0], [0, 0, 0, 1], [1, 2, -1, 0.5], [-0.3, 0.7, 0.2, -0.4]])


def canonical(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def digest(path: Path) -> str:
    return hashlib.sha256(canonical(path)).hexdigest()


def section_bytes() -> bytes:
    lines = canonical(ROOT / REPORT).decode("utf-8").splitlines(keepends=True)
    starts = [index for index, line in enumerate(lines) if line.rstrip() == HEADING]
    if len(starts) != 1:
        raise ValueError("section 56 must occur exactly once")
    start = starts[0]
    stop = next((index for index in range(start + 1, len(lines)) if lines[index].startswith("## ")), len(lines))
    return ("".join(lines[start:stop]).rstrip() + "\n").encode("utf-8")


def validate_manifest(path: Path) -> None:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValueError("unexpected manifest schema")
    section = manifest["section"]
    if section["path"] != REPORT or section["heading"] != HEADING:
        raise ValueError("unexpected notebook section")
    frozen = canonical(path.parent / section["snapshot"])
    if hashlib.sha256(frozen).hexdigest() != section["sha256"] or frozen != section_bytes():
        raise ValueError("frozen or current section mismatch")
    sources = manifest["sources"]
    if len(sources) != len(SOURCES) or {source["path"] for source in sources} != SOURCES:
        raise ValueError("incomplete source bindings")
    for source in sources:
        if digest(ROOT / source["path"]) != source["sha256"] or digest(path.parent / source["snapshot"]) != source["sha256"]:
            raise ValueError(f"source mismatch: {source['path']}")
    review = manifest["mathematical_review"]
    if review.get("accepted") is not True or digest(path.parent / review["snapshot"]) != review["sha256"]:
        raise ValueError("mathematical review is not qualified")


def exact_algebra() -> tuple[dict[str, bool], dict[str, str]]:
    a, d, g, h = sp.symbols("a d g h", real=True)
    xr, xi, yr, yi = sp.symbols("xr xi yr yi", real=True)
    f1, f2, f3 = sp.symbols("f1 f2 f3", real=True)
    x = sp.Matrix(sp.symbols("A1 A2 A3 B", real=True))
    sigma = (sp.Matrix([[0, 1], [1, 0]]), sp.Matrix([[0, -sp.I], [sp.I, 0]]), sp.diag(1, -1))
    psi, phi = sp.Matrix([xr + sp.I * xi, yr + sp.I * yi]), sp.Matrix([f1, f2, f3])
    rho = (psi.conjugate().T * psi)[0].expand()
    spin = sp.Matrix([(psi.conjugate().T * matrix * psi)[0].expand() for matrix in sigma])
    op = sum((g * x[j] * sigma[j] / 2 for j in range(3)), h * x[3] * sp.eye(2))
    derivative = op * psi
    adjoint = g * sp.Matrix(x[:3]).cross(phi)
    energy = sp.expand(a * (derivative.conjugate().T * derivative)[0] / 2 + d * adjoint.dot(adjoint) / 2)
    component_mass = sp.hessian(energy, x)
    predicted = sp.zeros(4)
    predicted[:3, :3] = g**2 * (a * rho * sp.eye(3) / 4 + d * (phi.dot(phi) * sp.eye(3) - phi * phi.T))
    predicted[:3, 3] = a * g * h * spin / 2
    predicted[3, :3] = (a * g * h * spin / 2).T
    predicted[3, 3] = a * rho * h**2
    zero = lambda values: all(sp.factor(value) == 0 for value in values)
    checks = {
        "component_hessian_equals_full_gram_matrix": zero(component_mass - predicted),
        "pure_doublet_spin_norm_identity": sp.expand(spin.dot(spin) - rho**2) == 0,
    }
    p, r = sp.symbols("p r", positive=True)
    t = sp.symbols("t", real=True)
    c, s = (1 - t**2) / (1 + t**2), 2 * t / (1 + t**2)
    unit = sp.diag(g**2 * (p + r), g**2 * (p + r), g**2 * p, 4 * p * h**2)
    unit[0, 3] = unit[3, 0] = 2 * p * g * h * s
    unit[2, 3] = unit[3, 2] = 2 * p * g * h * c
    det_reference = 4 * g**6 * h**2 * p**2 * r * (p + r) * (1 - c**2)
    schur = unit[3, 3] - (unit[3, :3] * unit[:3, :3].inv() * unit[:3, 3])[0]
    schur_reference = 4 * p * h**2 * r * (1 - c**2) / (p + r)
    null = sp.Matrix([-2 * h * s / g, 0, -2 * h * c / g, 1])
    checks.update({
        "determinant_factorization": sp.factor(unit.det() - det_reference) == 0,
        "schur_equals_common_phase_stiffness": sp.factor(schur - schur_reference) == 0,
        "fundamental_only_null_direction": zero(unit.subs(r, 0) * null),
        "aligned_positive_null_direction": zero(unit.subs(t, 0) * null.subs(t, 0)),
        "aligned_negative_null_direction": zero(unit.applyfunc(lambda value: sp.limit(value, t, sp.oo)) * sp.Matrix([0, 0, 2 * h / g, 1])),
        "uncharged_doublet_null_direction": zero(unit.subs(h, 0) * sp.Matrix([0, 0, 0, 1])),
        "zero_density_mass_block": zero(unit.subs(p, 0) - sp.diag(g**2 * r, g**2 * r, 0, 0)),
        "zero_su2_coupling_mass_block": zero(unit.subs(g, 0) - sp.diag(0, 0, 0, 4 * p * h**2)),
    })
    return {name: bool(value) for name, value in checks.items()}, {
        "determinant": str(sp.factor(det_reference)), "schur_complement": str(sp.factor(schur_reference)),
        "coordinate": "c=(1-t^2)/(1+t^2), s=2t/(1+t^2)",
    }


def cases() -> list[tuple[str, dict[str, float], list[int]]]:
    cphi = ((1 + np.sqrt(5)) / 2)**-3
    base = dict(rho=1.2, a=0.83, d=1.25, v=0.9, g=0.71, h=0.41, c=cphi, delta=0.0)
    phases = (0.0, np.pi / 3, np.pi / 2)
    rows = []
    for i, c in enumerate((-1.0, -0.7, 0.0, cphi, 0.8, 1.0)):
        for j, delta in enumerate(phases):
            rows.append((f"vacuum_c{i}_phase{j}", {**base, "c": c, "delta": delta}, [0, 1, 3] if abs(c) == 1 else [0, 0, 4]))
    for label, key in (("no_adjoint", "d"), ("uncharged_doublet", "h")):
        for j, delta in enumerate(phases):
            rows.append((f"{label}_phase{j}", {**base, key: 0.0, "delta": delta}, [0, 1, 3]))
    rows.extend([
        ("zero_density", {**base, "rho": 0.0}, [0, 2, 2]),
        ("zero_su2_coupling", {**base, "g": 0.0}, [0, 3, 1]),
        ("negative_adjoint", {**base, "d": -1.25, "c": 0.0}, [2, 0, 2]),
    ])
    return rows


def mass_matrix(p: dict[str, float], spin: np.ndarray, phi: np.ndarray) -> np.ndarray:
    result = np.zeros((4, 4))
    result[:3, :3] = p["g"]**2 * (p["a"] * p["rho"] * np.eye(3) / 4 + p["d"] * (phi @ phi * np.eye(3) - np.outer(phi, phi)))
    result[:3, 3] = p["a"] * p["g"] * p["h"] * spin / 2
    result[3, :3] = result[:3, 3]
    result[3, 3] = p["a"] * p["rho"] * p["h"]**2
    return result


def energy(p: dict[str, float], psi: np.ndarray, phi: np.ndarray, x: np.ndarray) -> float:
    derivative = (p["g"] * np.einsum("a,aij->ij", x[:3], SIGMA) / 2 + p["h"] * x[3] * np.eye(2)) @ psi
    adjoint = p["g"] * np.cross(x[:3], phi)
    return float((p["a"] * np.vdot(derivative, derivative).real + p["d"] * (adjoint @ adjoint)) / 2)


def relative(actual: np.ndarray, reference: np.ndarray) -> float:
    return float(np.linalg.norm(actual - reference) / max(1.0, np.linalg.norm(reference)))


def inertia(values: np.ndarray) -> list[int]:
    return [int(np.count_nonzero(values < -TOL)), int(np.count_nonzero(np.abs(values) <= TOL)), int(np.count_nonzero(values > TOL))]


def numeric_calculation() -> tuple[dict[str, bool], list[dict], dict[str, np.ndarray]]:
    n = np.array([1.0, 2.0, 3.0]) / np.sqrt(14)
    cross = np.array([[0, -n[2], n[1]], [n[2], 0, -n[0]], [-n[1], n[0], 0]])
    rotation = np.outer(n, n) - cross
    transform = np.eye(4)
    transform[:3, :3] = rotation
    unitary = (np.eye(2) + 1j * np.einsum("a,aij->ij", n, SIGMA)) / np.sqrt(2)
    invroot = np.diag(1 / np.sqrt(np.diag(KINETIC)))
    fields = {name: [] for name in ("mass", "mass_rotated", "omega2", "modes", "omega2_rotated", "modes_rotated", "probe_energies", "probe_energies_rotated")}
    rows = []
    for index, (label, p, expected) in enumerate(cases()):
        c, delta = p["c"], p["delta"]
        psi = np.sqrt(p["rho"]) * np.array([np.sqrt((1 + c) / 2), np.exp(1j * delta) * np.sqrt((1 - c) / 2)])
        spin = p["rho"] * np.array([np.sqrt(1 - c*c) * np.cos(delta), np.sqrt(1 - c*c) * np.sin(delta), c])
        phi = np.array([0.0, 0.0, p["v"]])
        matrices = [mass_matrix(p, spin, phi), mass_matrix(p, rotation @ spin, rotation @ phi)]
        spectra, modes, energies = [], [], []
        errors = {}
        for frame, (matrix, frame_psi, frame_phi, probes) in enumerate(zip(matrices, (psi, unitary @ psi), (phi, rotation @ phi), (PROBES, PROBES @ transform.T))):
            eigenvalues, eigenvectors = np.linalg.eigh(invroot @ matrix @ invroot)
            eigenvectors = invroot @ eigenvectors
            direct = np.array([energy(p, frame_psi, frame_phi, probe) for probe in probes])
            quadratic = np.einsum("bi,ij,bj->b", probes, matrix, probes) / 2
            errors[f"frame{frame}_eigen_residual"] = relative(matrix @ eigenvectors, KINETIC @ eigenvectors * eigenvalues)
            errors[f"frame{frame}_kinetic_orthonormality"] = relative(eigenvectors.T @ KINETIC @ eigenvectors, np.eye(4))
            errors[f"frame{frame}_probe_energy"] = relative(quadratic, direct)
            spectra.append(eigenvalues)
            modes.append(eigenvectors)
            energies.append(direct)
        errors["gauge_covariance"] = relative(matrices[1], transform @ matrices[0] @ transform.T)
        errors["gauge_spectrum"] = relative(spectra[1], spectra[0])
        errors["gauge_probe_energy"] = relative(energies[1], energies[0])
        pp, rr = p["a"] * p["rho"] / 4, p["d"] * p["v"]**2
        determinant = 4 * p["g"]**6 * p["h"]**2 * pp**2 * rr * (pp + rr) * (1 - c*c)
        errors["determinant"] = relative(np.linalg.det(matrices[0]), determinant)
        if p["g"] != 0 and pp != 0:
            schur = matrices[0][3, 3] - matrices[0][3, :3] @ np.linalg.solve(matrices[0][:3, :3], matrices[0][:3, 3])
            errors["schur"] = relative(schur, 4 * pp * p["h"]**2 * rr * (1 - c*c) / (pp + rr))
        measured, rotated = inertia(spectra[0]), inertia(spectra[1])
        within = all(np.isfinite(value) and value <= TOL for value in errors.values()) and measured == expected and rotated == expected
        rows.append(dict(case=index, label=label, parameters=p, inertia=measured, rotated_inertia=rotated, errors=errors, within_tolerance=bool(within)))
        for key, value in zip(fields, (*matrices, spectra[0], modes[0], spectra[1], modes[1], energies[0], energies[1])):
            fields[key].append(value)
    arrays = {name: np.asarray(values, dtype=np.float64) for name, values in fields.items()}
    arrays.update(kinetic=KINETIC, probes=PROBES, gauge_rotation=transform)
    checks = {
        "schedule_complete": len(rows) == 27,
        "all_covariance_spectra_energy_and_inertia_checks": all(row["within_tolerance"] for row in rows),
        "raw_arrays_finite": all(bool(np.isfinite(value).all()) for value in arrays.values()),
    }
    return checks, rows, arrays


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    receipt = dict(schema=SCHEMA, role="primary", numeric_pass=False, verdict="INCONCLUSIVE",
                   checks={}, rows=[], manifest_sha256=None, source_sha256=digest(Path(__file__)),
                   arrays_sha256=None, complete_physical_matter_formation=False,
                   scope="Conditional one-Abelian-factor transverse-vector compatibility; no physical mass normalization, quantum sector or formation result.")
    try:
        receipt["manifest_sha256"] = digest(args.manifest)
        validate_manifest(args.manifest)
        checks, identities = exact_algebra()
        numeric, rows, arrays = numeric_calculation()
        checks.update(numeric)
        if not checks["raw_arrays_finite"]:
            raise ValueError("nonfinite scientific array")
        np.savez_compressed(args.output / "arrays.npz", **arrays)
        passed = all(checks.values())
        receipt.update(numeric_pass=passed, verdict=VERDICT if passed else "INCONCLUSIVE", checks=checks, rows=rows, identities=identities,
                       arrays_sha256=hashlib.sha256((args.output / "arrays.npz").read_bytes()).hexdigest())
        text = json.dumps(receipt, indent=2, allow_nan=False) + "\n"
    except Exception as error:
        receipt.update(numeric_pass=False, verdict="INCONCLUSIVE", error=f"{type(error).__name__}: {error}")
        text = json.dumps(receipt, indent=2, allow_nan=False) + "\n"
    (args.output / "result.json").write_text(text, encoding="utf-8", newline="\n")
    print(json.dumps({key: receipt.get(key) for key in ("verdict", "numeric_pass", "error", "complete_physical_matter_formation")}))
    return 0 if receipt["numeric_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
