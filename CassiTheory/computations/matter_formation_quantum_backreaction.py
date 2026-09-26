#!/usr/bin/env python3
"""Full scalar finite-mode quantum transfer for working notebook section 70.

python computations/matter_formation_quantum_backreaction.py --manifest PATH --output FRESH_DIR
The spatial mode, bosonic quantization and normalization are supplied inputs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from scipy.linalg import eigh
from scipy.sparse import csr_matrix, diags, eye, kron

ROOT = Path(__file__).resolve().parents[1]
REPORT = "computations/matter-formation-continuum-report.md"
HEADINGS = {
    "## 25. Autonomous mediator oscillation in the scalar parent",
    "## 64. Working notes: matching quantum conversion to the scalar action",
    "## 70. Working notes: autonomous quantum transfer with the full scalar interaction",
}
SOURCES = {
    "computations/matter_formation_quantum_backreaction.py",
    "computations/verify_matter_formation_quantum_backreaction.py",
    "computations/verify_matter_formation_quantum_residuals.py",
    "foundations/particle-stationary-action-closure.md",
}
INHERITED = {
    "runs/20260907_matter_formation_autonomous_pump/results.json":
        "cad33ef760404c79807570be1269390dfb790574dc13bfe60d61d67c5b1bc9c5",
    "runs/20260907_matter_formation_autonomous_pump_verification/results.json":
        "a54c07d1a973f9a915355e26b7c23e7caa7ee75a468f09fda53e13a272959758",
}
SCHEMA = "matter-formation-quantum-backreaction-v1"
MANIFEST_SCHEMA = "matter-formation-quantum-backreaction-manifest-v1"
H_INHERITED = 2.9598260763447164
K_INHERITED = 2.675336705149658


def canonical(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def relative_path(value: str) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ValueError("expected a nonempty root-relative path")
    target = (ROOT / value).resolve()
    if not target.is_relative_to(ROOT.resolve()):
        raise ValueError("path escapes the repository")
    return target


def entries(manifest: dict, key: str, field: str, required: set) -> list[dict]:
    rows = manifest[key]
    if not isinstance(rows, list) or len(rows) != len(required):
        raise ValueError(f"incomplete {key} coverage")
    if {row[field] for row in rows} != required:
        raise ValueError(f"duplicate or unexpected {key} binding")
    return rows


def validate_manifest(path: Path) -> dict:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValueError("unexpected manifest schema")
    lines = canonical(ROOT / REPORT).decode("utf-8").splitlines(keepends=True)
    for item in entries(manifest, "sections", "heading", HEADINGS):
        if item["path"] != REPORT:
            raise ValueError("unexpected section path")
        starts = [index for index, line in enumerate(lines) if line.rstrip() == item["heading"]]
        if len(starts) != 1:
            raise ValueError("section heading must occur exactly once")
        start = starts[0]
        stop = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
        data = ("".join(lines[start:stop]).rstrip() + "\n").encode("utf-8")
        if sha(data) != item["sha256"] or canonical(relative_path(item["snapshot"])) != data:
            raise ValueError("live or frozen section mismatch")
    for item in entries(manifest, "sources", "path", SOURCES):
        if (sha(canonical(relative_path(item["path"]))) != item["sha256"]
                or sha(canonical(relative_path(item["snapshot"]))) != item["sha256"]):
            raise ValueError("source mismatch: " + item["path"])
    inherited = {}
    for item in entries(manifest, "inherited", "path", set(INHERITED)):
        data = relative_path(item["path"]).read_bytes()
        if (item["sha256"] != INHERITED[item["path"]] or sha(data) != item["sha256"]
                or relative_path(item["snapshot"]).read_bytes() != data):
            raise ValueError("inherited evidence mismatch")
        receipt = json.loads(data)
        if (receipt.get("passed") is not True or receipt.get("qualified") is not True
                or receipt.get("verdict") != "SUPPORTS—neutral linear parametric amplification in the supplied temporal parent"):
            raise ValueError("inherited calculation is not qualified")
        if "_verification/" in item["path"] and receipt.get("mismatches") != []:
            raise ValueError("independent inherited calculation has mismatches")
        inherited[item["path"]] = receipt
    for item in entries(manifest, "mathematical_reviews", "role", {"coordinate", "residuals"}):
        data = canonical(relative_path(item["snapshot"]))
        flags = [line.strip() for line in data.decode("utf-8").splitlines()
                 if line.strip().startswith("accepted:")]
        if item.get("accepted") is not True or flags != ["accepted: true"] or sha(data) != item["sha256"]:
            raise ValueError("unaccepted mathematical review: " + item["role"])
    primary = inherited["runs/20260907_matter_formation_autonomous_pump/results.json"]
    witness = [row for row in primary["witnesses"] if row["j"] == 3]
    if len(witness) != 1 or witness[0]["k"] != K_INHERITED or witness[0].get("unstable") is not True:
        raise ValueError("inherited carrier mode differs from the fixed input")
    return manifest


def parameters() -> dict[str, float]:
    a, cpsi, urho, uc, kcx, ec, action_norm = 1 / 16, 1 / 8, 4., 1., 1., .75, 4.
    volume = (2 * math.pi / K_INHERITED) ** 3
    eta = action_norm * volume
    b = ec + 1 / (4 * a)
    return {"a": a, "cPsi": cpsi, "uRho": urho, "uC": uc, "kCx": kcx,
            "eC": ec, "Naction": action_norm, "k": K_INHERITED, "B": b, "Hc": H_INHERITED,
            "V": volume, "eta": eta, "v2": eta * cpsi,
            "m": math.sqrt(2 * urho / cpsi),
            "w": math.sqrt((b + kcx * K_INHERITED ** 2 / 2) / a),
            "F": math.sqrt(1.5), "delta": math.log(math.sqrt(1.5))}


def oscillator_matrices(j_count: int, n_count: int, m: float, w: float) -> dict:
    # Extra indices retain the full intermediate images in coordinate fourth powers.
    j = np.arange(j_count + 2, dtype=float)
    q_off = np.sqrt((2 * j[:-1] + 1) * (2 * j[:-1] + 2)) / (2 * m)
    q2 = diags((q_off, (2 * j + .5) / m, q_off), (-1, 0, 1), format="csr")
    p2 = diags((-m * m * q_off, m * (2 * j + .5), -m * m * q_off),
               (-1, 0, 1), format="csr")
    n = np.arange(n_count + 2, dtype=float)
    r_off = (n[:-1] + 1) / w
    r2 = diags((r_off, (2 * n + 1) / w, r_off), (-1, 0, 1), format="csr")
    raising = .5j * np.sqrt((2 * j[:j_count - 1] + 1) * (2 * j[:j_count - 1] + 2))
    dilation = diags((raising, -raising), (-1, 1), shape=(j_count, j_count), format="csr")
    return {"S2": q2[:j_count, :j_count], "S4": (q2 @ q2)[:j_count, :j_count],
            "PS2": p2[:j_count, :j_count], "R2": r2[:n_count, :n_count],
            "R4": (r2 @ r2)[:n_count, :n_count], "D": dilation}


def operators(j_count: int, n_count: int, h: float, p: dict) -> dict:
    je, ne = j_count + 2, n_count + 2
    factors = oscillator_matrices(je, ne, p["m"], p["w"])
    iq, ir = eye(je, format="csr"), eye(ne, format="csr")
    hf = factors["PS2"] / 2 + p["m"] ** 2 / (8 * p["v2"]) * (
        factors["S4"] - 2 * p["v2"] * factors["S2"] + p["v2"] ** 2 * iq)
    carrier0 = diags(p["w"] * (2 * np.arange(ne) + 1), format="csr")
    parts = [kron(hf, ir, format="csr"), kron(iq, carrier0, format="csr"),
             p["uC"] / (8 * p["eta"] * p["a"] ** 2) * kron(iq, factors["R4"], format="csr"),
             h / (2 * p["a"]) * kron(factors["S2"] / p["v2"] - iq, factors["R2"], format="csr")]
    extended = sum(parts).tocsr()
    inner = (np.arange(j_count)[:, None] * ne + np.arange(n_count)[None, :]).ravel()
    mask = np.ones(je * ne, dtype=bool)
    mask[inner] = False
    outer = np.flatnonzero(mask)
    result = {"H": extended[inner][:, inner].tocsr(), "R": extended[outer][:, inner].tocsr(),
              "parts": [part[inner][:, inner].tocsr() for part in parts],
              "inner_indices": inner, "outer_indices": outer}
    for name, matrix in factors.items():
        size = n_count if name.startswith("R") else j_count
        result[name] = matrix[:size, :size].tocsr()
    for name in ("H", "R"):
        result[name].eliminate_zeros()
        result[name].sort_indices()
    return result


def csr_fields(prefix: str, matrix: csr_matrix) -> dict[str, np.ndarray]:
    return {prefix + "_data": matrix.data, prefix + "_indices": matrix.indices,
            prefix + "_indptr": matrix.indptr, prefix + "_shape": np.array(matrix.shape, dtype=np.int64)}


def expectations(states: np.ndarray, ops: dict, j_count: int, n_count: int, p: dict) -> dict:
    conjugate = states.conj()
    weights = np.abs(states.reshape(-1, j_count, n_count)) ** 2
    energies = np.column_stack([
        np.einsum("ti,it->t", conjugate, part @ states.T).real for part in ops["parts"]])
    shaped = states.reshape(-1, j_count, n_count)
    f2 = np.einsum("tjn,jk,tkn->t", shaped.conj(), ops["S2"].toarray(), shaped,
                   optimize=True).real / p["v2"]
    return {"norm": weights.sum(axis=(1, 2)), "energy_terms": energies, "f2": f2,
            "pairs": np.einsum("tjn,n->t", weights, np.arange(n_count)),
            "pair_probability": weights[:, :, 1:].sum(axis=(1, 2))}


def trajectory(key: str, j_count: int, n_count: int, h: float, delta: float,
               p: dict, output: Path, cache: dict) -> tuple[dict, dict]:
    cache_key = (j_count, n_count, h)
    if cache_key not in cache:
        ops = operators(j_count, n_count, h, p)
        values, vectors = eigh(ops["H"].toarray(), driver="evd")
        if vectors[0, 0] < 0:
            vectors[:, 0] *= -1
        dvalues, dvectors = eigh(ops["D"].toarray())
        cache[cache_key] = (ops, values, vectors, dvalues, dvectors)
    ops, values, vectors, dvalues, dvectors = cache[cache_key]
    ground = vectors[:, 0]
    eg = float(values[0])
    times = np.linspace(0, 16, 513)
    source_times = np.linspace(0, delta, 257)
    source_coefficients = dvectors.conj().T @ ground.reshape(j_count, n_count)
    if delta == 0:
        source_states = np.broadcast_to(ground, (257, ground.size)).astype(complex, copy=True)
        states = np.broadcast_to(ground, (513, ground.size)).astype(complex, copy=True)
    else:
        source_states = np.einsum(
            "ij,tjn->tin", dvectors,
            np.exp(-1j * source_times[:, None, None] * dvalues[None, :, None])
            * source_coefficients[None, :, :], optimize=True).reshape(257, -1)
        coefficients = vectors.T @ source_states[-1]
        phases = np.exp(-1j * times[:, None] * (values[None, :] - eg)) * coefficients[None, :]
        states = phases @ vectors.T
    prepared = source_states[-1]
    observables = expectations(states, ops, j_count, n_count, p)
    ground_probability = float((np.abs(ground.reshape(j_count, n_count)[:, 1:]) ** 2).sum())
    initial_energy = float(observables["energy_terms"][0].sum())
    ground_residual = math.sqrt(float(np.linalg.norm(ops["H"] @ ground - eg * ground) ** 2
                                     + np.linalg.norm(ops["R"] @ ground) ** 2))
    arrays = {"time": times, "state": states, "ground": ground, "prepared": prepared,
              "source_time": source_times, "source_state": source_states,
              "ground_energy": np.array(eg), "eigenvalues": values, "eigenvectors": vectors,
              "source_eigenvalues": dvalues, "source_eigenvectors": dvectors,
              "inner_indices": ops["inner_indices"], "outer_indices": ops["outer_indices"],
              **observables, **csr_fields("H", ops["H"]), **csr_fields("R", ops["R"])}
    arrays.update({name: ops[name].toarray().astype(np.complex128)
                   for name in ("S2", "S4", "PS2", "R2", "R4", "D")})
    if not all(np.isfinite(value).all() for value in arrays.values()):
        raise ArithmeticError("nonfinite scientific array")
    archive = output / (key + ".npz")
    with archive.open("xb") as stream:
        np.savez_compressed(stream, **arrays)
    norm_error = float(np.max(np.abs(observables["norm"] - 1)))
    energy_error = float(np.max(np.abs(observables["energy_terms"].sum(axis=1) - initial_energy))
                         / max(1., abs(initial_energy)))
    gain = float(np.max(observables["pair_probability"] - ground_probability))
    row = {"key": key, "J": j_count, "N": n_count, "h": h, "delta": delta,
           "archive": archive.name, "archive_sha256": sha(archive.read_bytes()),
           "ground_energy": eg, "ground_pair_probability": ground_probability,
           "initial_energy": initial_energy, "preparation_work": initial_energy - eg,
           "peak_pair_probability_gain": gain, "norm_error": norm_error,
           "energy_error": energy_error, "ground_full_residual": ground_residual}
    checks = {key + ".norm": norm_error <= 1e-10,
              key + ".energy": energy_error <= 1e-9,
              key + ".source_preserves_carrier_state": bool(np.linalg.norm(
                  prepared.reshape(j_count, n_count).conj().T @ prepared.reshape(j_count, n_count)
                  - ground.reshape(j_count, n_count).T @ ground.reshape(j_count, n_count)) <= 1e-10)}
    if key.startswith(("zero_pump", "uncoupled")):
        checks[key + ".zero_transfer"] = bool(np.max(np.abs(
            observables["pair_probability"] - ground_probability)) <= 1e-8)
    print(json.dumps({"row": key, "peak_pair_probability_gain": gain,
                      "norm_error": norm_error, "energy_error": energy_error,
                      "ground_full_residual": ground_residual}), flush=True)
    return row, checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    result = {"schema": SCHEMA, "role": "primary", "numeric_pass": False,
              "verdict": "INCONCLUSIVE", "error": None, "checks": {}, "parameters": {},
              "rows": [], "complete_physical_matter_formation": False}
    try:
        validate_manifest(args.manifest)
        p = parameters()
        result["parameters"] = p
        schedule = [(f"coupled_{j}_{n}", j, n, H_INHERITED, p["delta"])
                    for j, n in ((48, 12), (64, 16), (80, 20))]
        schedule += [("zero_pump_80_20", 80, 20, H_INHERITED, 0.),
                     ("uncoupled_80_20", 80, 20, 0., p["delta"])]
        cache = {}
        for specification in schedule:
            row, checks = trajectory(*specification, p, args.output, cache)
            result["rows"].append(row)
            result["checks"].update(checks)
        result["numeric_pass"] = all(result["checks"].values())
        if result["numeric_pass"]:
            result["verdict"] = "INCONCLUSIVE-awaiting joint quantum transfer qualification"
        else:
            result["error"] = "one or more numerical qualifications failed"
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    (args.output / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("role", "numeric_pass", "verdict", "error",
                                                "complete_physical_matter_formation")}), flush=True)
    return 0 if result["numeric_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
