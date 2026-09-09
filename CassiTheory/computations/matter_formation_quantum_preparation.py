#!/usr/bin/env python3
"""Left-endpoint preparation bound for working-notebook section 72.

Run: python computations/matter_formation_quantum_preparation.py --manifest PATH --output FRESH_DIR
No Hamiltonian trajectory is generated. Physical matter formation remains unresolved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from scipy.linalg import eigh

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
    require(manifest.get("schema") == MANIFEST_SCHEMA, "manifest schema mismatch")
    require(set(manifest["files"]) == LABELS, "manifest file labels mismatch")
    for label, item in manifest["files"].items():
        require(type(item["canonical"]) is bool, f"invalid canonical flag: {label}")
        if label in SOURCE_PATHS:
            require(item["path"] == SOURCE_PATHS[label], f"source path mismatch: {label}")
        for name in set((item["path"], item["snapshot"])):
            require(digest(rooted(name), item["canonical"]) == item["sha256"],
                    f"file identity mismatch: {label}")
    section = manifest["section"]
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
    require(set(manifest["reviews"]) == {"preparation", "observable"}, "review roles mismatch")
    for role, review in manifest["reviews"].items():
        require(review["accepted"] is True, f"review not accepted: {role}")
        review_path = rooted(review["snapshot"])
        require(digest(review_path, True) == review["sha256"], f"review identity mismatch: {role}")
        acceptance = [line.strip() for line in review_path.read_text(encoding="utf-8").splitlines()
                      if line.strip().startswith("accepted:")]
        require(acceptance == ["accepted: true"], f"review acceptance mismatch: {role}")
    return manifest


def calculate(manifest: dict, result: dict, arrays: dict) -> None:
    indices = np.arange(J - 1, dtype=float)
    raising = 0.5j * np.sqrt((2 * indices + 1) * (2 * indices + 2))
    generator = np.diag(raising, -1) + np.diag(raising.conj(), 1)
    edge = math.sqrt((2 * J - 1) * (2 * J)) / 2
    eigenvalues, vectors = eigh(generator)
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
        integral_terms = norms[:-1].sum(axis=0) * factors
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
    result = dict(schema=SCHEMA, role="primary", verdict="INCONCLUSIVE", numeric_pass=False,
                  error=None, checks={}, rows=[], complete_physical_matter_formation=False,
                  scope="Left-endpoint Taylor inequality evaluated in floating point on a finite variational reference; no interval certificate or physical matter selection.")
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
