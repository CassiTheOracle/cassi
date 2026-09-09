#!/usr/bin/env python3
"""Right-endpoint preparation bound for working-notebook section 72.

Independent coordinate construction: the dilation generator D = -i(x d/dx + 1/2)
in the dimensionless coordinate x = sqrt(m) S is assembled from normalized
Hermite integrals over even occupation levels 0..160. Gauss-Hermite weights
multiply the Gaussian-stripped polynomial factors only, so the e^{-x^2} weight
is applied exactly once. The discarded row, its single support and its norm are
derived from those integrals, never declared. The Taylor bound is evaluated
from each interval's right endpoint (samples u[1:]) with the fourth-derivative
remainder. No Hamiltonian trajectory is generated. Physical matter formation
remains unresolved.

Run: python computations/verify_matter_formation_quantum_preparation.py --manifest PATH --output FRESH_DIR
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
REPORT = "computations/matter-formation-continuum-report.md"
HEADING = "## 72. Working notes: higher-order preparation error on retained quantum states"
SOURCE_PATHS = {
    "source_primary": "computations/matter_formation_quantum_preparation.py",
    "source_preparation": "computations/verify_matter_formation_quantum_preparation.py",
    "source_observable": "computations/verify_matter_formation_quantum_transfer_bound.py",
}
LABELS = set(SOURCE_PATHS) | {"archive_primary", "archive_coordinate", "prior_audit"}
SCHEMA = "matter-formation-quantum-preparation-v1"
MANIFEST_SCHEMA = "matter-formation-quantum-preparation-manifest-v1"
J, N = 80, 20
DELTA = math.log(math.sqrt(1.5))
NODES = 320                      # Gauss-Hermite points; exact for degree <= 639 >= 320
QUADRATURE_TOL = 1e-10           # structural gates on derived quadrature quantities
DECLARED_EDGE = math.sqrt((2 * J - 1) * (2 * J)) / 2.0


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def rooted(value: str) -> Path:
    require(isinstance(value, str) and bool(value) and not Path(value).is_absolute(),
            "expected a repository-relative path")
    path = (ROOT / value).resolve()
    path.relative_to(ROOT)
    return path


def digest(path: Path, canonical: bool = False) -> str:
    if canonical:
        return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate(path: Path) -> dict:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(manifest, dict) and set(manifest) == {"schema", "files", "section", "reviews"},
            "manifest top-level key mismatch")
    require(manifest["schema"] == MANIFEST_SCHEMA, "manifest schema mismatch")
    files = manifest["files"]
    require(isinstance(files, dict) and set(files) == LABELS, "manifest file labels mismatch")
    for label, item in files.items():
        require(isinstance(item, dict)
                and set(item) == {"path", "snapshot", "sha256", "canonical"},
                f"manifest file entry keys mismatch: {label}")
        require(type(item["canonical"]) is bool, f"invalid canonical flag: {label}")
        if label in SOURCE_PATHS:
            require(item["path"] == SOURCE_PATHS[label], f"source path mismatch: {label}")
        for name in set((item["path"], item["snapshot"])):
            require(digest(rooted(name), item["canonical"]) == item["sha256"],
                    f"file identity mismatch: {label}")
    section = manifest["section"]
    require(isinstance(section, dict)
            and set(section) == {"path", "heading", "snapshot", "sha256"},
            "manifest section keys mismatch")
    require(section["path"] == REPORT and section["heading"] == HEADING,
            "section identity mismatch")
    lines = rooted(REPORT).read_text(encoding="utf-8").splitlines()
    starts = [i for i, line in enumerate(lines) if line == HEADING]
    require(len(starts) == 1, "section heading missing or repeated")
    first = starts[0]
    last = next((i for i in range(first + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    live = ("\n".join(lines[first:last]) + "\n").encode()
    require(hashlib.sha256(live).hexdigest() == section["sha256"], "live section mismatch")
    require(digest(rooted(section["snapshot"]), True) == section["sha256"], "section snapshot mismatch")
    reviews = manifest["reviews"]
    require(isinstance(reviews, dict) and set(reviews) == {"preparation", "observable"},
            "review roles mismatch")
    for role, review in reviews.items():
        require(isinstance(review, dict) and set(review) == {"snapshot", "sha256", "accepted"},
                f"manifest review entry keys mismatch: {role}")
        require(review["accepted"] is True, f"review not accepted: {role}")
        review_path = rooted(review["snapshot"])
        require(digest(review_path, True) == review["sha256"], f"review identity mismatch: {role}")
        acceptance = [line.strip() for line in review_path.read_text(encoding="utf-8").splitlines()
                      if line.strip().startswith("accepted:")]
        require(acceptance == ["accepted: true"], f"review acceptance mismatch: {role}")
    return manifest


def coordinate_dilation() -> np.ndarray:
    """Real Gram integrals int e^{-x^2} chi_{2j} (x d/dx + 1/2) acting chi_{2k} dx,
    rows 2j = 0..160 (81), columns 2k = 0..158 (80).

    With phi_n = chi_n e^{-x^2/2} and chi_n = pi^{-1/4} (2^n n!)^{-1/2} H_n:
    (x d/dx + 1/2) phi_n = e^{-x^2/2} (x chi'_n - (x^2 - 1/2) chi_n) and
    chi'_n = sqrt(2 n) chi_{n-1}. Only the stripped polynomial factor may
    carry the Gauss-Hermite weight; summing full phi products against w would
    apply e^{-x^2} twice.
    """
    x, w = np.polynomial.hermite.hermgauss(NODES)
    top = 2 * J                                   # level 160 = discarded row
    chi = np.empty((top + 1, NODES))
    chi[0] = math.pi ** -0.25
    chi[1] = math.sqrt(2.0) * x * chi[0]
    for n in range(1, top):
        chi[n + 1] = math.sqrt(2.0 / (n + 1)) * x * chi[n] - math.sqrt(n / (n + 1.0)) * chi[n - 1]
    dchi = np.zeros_like(chi)
    for n in range(1, top + 1):
        dchi[n] = math.sqrt(2.0 * n) * chi[n - 1]
    action = x * dchi - (x * x - 0.5) * chi
    integrals = (chi[0::2] * w) @ action[0:top:2].T
    require(np.isfinite(integrals).all(), "nonfinite coordinate dilation integrals")
    return integrals


def calculate(manifest: dict, result: dict, arrays: dict) -> None:
    integrals = coordinate_dilation()
    require(integrals.shape == (J + 1, J), "coordinate dilation shape mismatch")
    arrays["coordinate_integrals"] = integrals
    raw_generator = -1j * integrals[:J]
    forbidden = np.abs(np.arange(J)[:, None] - np.arange(J)[None, :]) != 1
    discarded = -1j * integrals[J]
    edge = float(abs(discarded[J - 1]))
    result["checks"].update({
        "generator_hermitian": bool(float(np.max(np.abs(raw_generator - raw_generator.conj().T)))
                                    <= QUADRATURE_TOL),
        "generator_band_support": bool(np.max(np.abs(raw_generator[forbidden])) <= QUADRATURE_TOL),
        "discarded_row_single": bool(float(np.max(np.abs(discarded[:J - 1]))) <= QUADRATURE_TOL),
        "discarded_row_exact": bool(abs(edge - DECLARED_EDGE) <= QUADRATURE_TOL),
    })
    # Enforce the exact Hermite selection rule after measuring quadrature roundoff.
    generator = 0.5 * (raw_generator + raw_generator.conj().T)
    generator[forbidden] = 0
    eigenvalues, vectors = np.linalg.eigh(generator)
    expected_times = np.linspace(0, DELTA, 257)
    step = DELTA / 256
    factors = np.array([step ** (r + 1) / math.factorial(r + 1) for r in range(4)])
    for source in ("primary", "coordinate"):
        path = rooted(manifest["files"]["archive_" + source]["path"])
        with np.load(path, allow_pickle=False) as archive:
            ground = archive["ground"]
            states = archive["source_state"]
            times = archive["source_time"]
            stored_generator = archive["D"]
        require(ground.shape == (J * N,) and states.shape == (257, J * N)
                and times.shape == (257,) and stored_generator.shape == (J, J),
                f"preparation array shape mismatch: {source}")
        require(all(np.isfinite(value).all() for value in (ground, states, times, stored_generator)),
                f"nonfinite preparation input: {source}")
        ground = ground.reshape(J, N)
        states = states.reshape(257, J, N)
        coefficients = vectors.conj().T @ ground
        reconstructed = np.einsum(
            "ab,tbn->tan", vectors,
            np.exp(-1j * times[:, None, None] * eigenvalues[None, :, None]) * coefficients[None],
            optimize=True)
        reconstruction_errors = np.linalg.norm(states - reconstructed, axis=(1, 2))
        generator_error = float(np.linalg.norm(stored_generator - generator)
                                / max(1., np.linalg.norm(generator)))
        norms = np.empty((257, 4))
        derivative = states
        for order in range(4):
            norms[:, order] = edge * np.linalg.norm(derivative[:, -1, :], axis=1)
            if order < 3:
                derivative = np.einsum("ab,tbn->tan", generator, derivative, optimize=True)
        fourth = ground
        for _ in range(4):
            fourth = generator @ fourth
        integral_terms = norms[1:].sum(axis=0) * factors
        remainder = float(DELTA * step ** 4 / 120 * edge * np.linalg.norm(fourth))
        upper = float(integral_terms.sum() + remainder)
        checks = {
            "time_grid": np.max(np.abs(times - expected_times)) <= 1e-12,
            "ground_norm": abs(np.linalg.norm(ground) - 1) <= 1e-10,
            "source_norms": np.max(np.abs(np.linalg.norm(states, axis=(1, 2)) - 1)) <= 1e-10,
            "generator": generator_error <= 1e-11,
            "source_reconstruction": np.max(reconstruction_errors) <= 1e-10,
            "finite_outputs": np.isfinite(norms).all() and np.isfinite(reconstruction_errors).all()
                              and np.isfinite(integral_terms).all() and math.isfinite(upper),
            "preparation_bound": 0 <= upper < 1e-6,
        }
        result["checks"].update({source + ":" + name: bool(value) for name, value in checks.items()})
        result["rows"].append({"source": source, "preparation_upper": upper,
                               "derivative_integrals": integral_terms.tolist(), "remainder": remainder,
                               "source_reconstruction_error": float(np.max(reconstruction_errors)),
                               "generator_error": generator_error})
        arrays[source + "_D"] = generator
        arrays[source + "_derivative_norms"] = norms
        arrays[source + "_reconstruction_errors"] = reconstruction_errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    result = dict(schema=SCHEMA, role="preparation", verdict="INCONCLUSIVE", numeric_pass=False,
                  error=None, checks={}, rows=[], complete_physical_matter_formation=False,
                  scope="Right-endpoint Taylor inequality with fourth-derivative remainder, evaluated "
                        "in floating point on a finite variational reference; the generator, discarded "
                        "row and its norm are reconstructed from coordinate Hermite integrals; no "
                        "interval certificate or physical matter selection.")
    arrays = {}
    try:
        manifest = validate(args.manifest)
        result["manifest_sha256"] = digest(args.manifest)
        result["checks"]["guards"] = True
        calculate(manifest, result, arrays)
        result["numeric_pass"] = len(result["rows"]) == 2 and all(result["checks"].values())
        if result["numeric_pass"]:
            result["verdict"] = "SUPPORTS-conditional preparation truncation bound"
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    if arrays and all(np.isfinite(array).all() for array in arrays.values()):
        archive = args.output / "arrays.npz"
        np.savez_compressed(archive, **arrays)
        result["arrays_sha256"] = digest(archive)
    (args.output / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("role", "verdict", "numeric_pass", "error", "rows")}, allow_nan=False))
    return 0 if result["numeric_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
