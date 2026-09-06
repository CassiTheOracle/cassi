#!/usr/bin/env python3
"""Run the fixed extended-domain calculation in the working research record.

python computations/matter_formation_spatial_domain.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.linalg import eig_banded, eigh_tridiagonal, solve_banded
from scipy.sparse.linalg import LinearOperator, eigsh

from matter_formation_radial import (
    COEFFICIENTS, Grid, finite_volume_energy_gradient, interpolate_fields,
    normalize_carrier, stationary_diagnostics,
)
from matter_formation_parent_spatial import derivative
from verify_matter_formation_charged_stability import (
    banded_mv, banded_operator, source_metrics,
)

ROOT = Path(__file__).resolve().parents[1]
NOTE = ROOT / "computations/matter-formation-continuum-report.md"
HEADING = "### 11.5 Extended-domain calculation: pre-execution criteria\n"
SOURCE = ROOT / "runs/20260906_matter_formation_radial/q256_R24_n768_refine.npz"
SOURCE_HASH = "7f839b59fa3a0a4c9ca6897ec3962aec2b7f62d20a1751968482349a22742b66"
SPATIAL_DIR = ROOT / "runs/20260906_matter_formation_parent_spatial"
EVIDENCE_HASHES = {
    "results.json": "9445ff33b33b664bf15e09b499bb185f18bfeb9f8a9393c388afef7c7affa79c",
    "verification.json": "2994e44ee2566ecc4e7ce660dc5d0510a088b694e0224086792eda2854f148dd",
}
SCHEDULE = ((24.0, 768), (48.0, 1536), (48.0, 3072), (96.0, 3072))
A_DENOMINATORS = (64, 32, 16)
N = 256.0
DEFAULT_OUTPUT = ROOT / "runs/20260906_matter_formation_spatial_domain"


def sha(path: Path, canonical: bool = False) -> str:
    data = path.read_bytes()
    return hashlib.sha256(data.replace(b"\r\n", b"\n") if canonical else data).hexdigest()


def write_json(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def save_arrays(path: Path, arrays: dict) -> dict:
    with path.open("xb") as stream:
        np.savez_compressed(stream, **arrays)
    return {"path": path.name, "sha256": sha(path)}


def freeze_inputs(output: Path) -> dict:
    text = NOTE.read_text(encoding="utf-8").replace("\r\n", "\n")
    start = text.index(HEADING)
    end = text.index("\n##", start + len(HEADING))
    section = text[start:end] + "\n"
    with (output / "protocol.txt").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(section)
    inputs = {
        "protocol": {"path": NOTE.relative_to(ROOT).as_posix(), "heading": HEADING.strip(),
                     "sha256": hashlib.sha256(section.encode()).hexdigest()},
        "source": {"path": SOURCE.relative_to(ROOT).as_posix(), "sha256": sha(SOURCE)},
        "programs": {}, "evidence": {},
    }
    if inputs["source"]["sha256"] != SOURCE_HASH:
        raise ValueError("source field hash mismatch")
    for name in (Path(__file__).name, "matter_formation_radial.py",
                 "matter_formation_parent_spatial.py", "verify_matter_formation_charged_stability.py"):
        path = ROOT / "computations" / name
        inputs["programs"][path.relative_to(ROOT).as_posix()] = sha(path, canonical=True)
    for name, expected in EVIDENCE_HASHES.items():
        path = SPATIAL_DIR / name
        actual = sha(path)
        if actual != expected:
            raise ValueError(f"retained {name} hash mismatch")
        receipt = json.loads(path.read_text(encoding="utf-8"))
        if receipt["numerical_pass"] is not True or receipt["failures"]:
            raise ValueError(f"retained {name} is numerically unqualified")
        inputs["evidence"][path.relative_to(ROOT).as_posix()] = actual
    primary = json.loads((SPATIAL_DIR / "results.json").read_text(encoding="utf-8"))
    for identity in primary["identities"].values():
        if sha(ROOT / identity["path"], canonical=True) != identity["sha256"]:
            raise ValueError("retained spatial computational identity mismatch")
    if any(COEFFICIENTS[k] != v for k, v in
           {"u_rho": 4.0, "u_C": 1.0, "k_Cx": 1.0, "e_C": 0.75, "h_C": 2.9598260763447164}.items()):
        raise ValueError("fixed coefficient mismatch")
    write_json(output / "inputs.json", inputs)
    return inputs


def residual(f: np.ndarray, c: np.ndarray, omega: float, grid: Grid) -> tuple[np.ndarray, float, float]:
    _, gf, gc = finite_volume_energy_gradient(f, c, grid)
    root_v = np.sqrt(grid.volumes)
    force = np.empty(2 * grid.n)
    force[0::2] = gf / root_v
    force[1::2] = gc / root_v - 2 * omega * root_v * c
    population = float(np.dot(grid.volumes, c * c))
    score = max(float(np.linalg.norm(force[0::2])) / max(1.0, float(np.linalg.norm(root_v * (1 - f)))),
                float(np.linalg.norm(force[1::2])) / (2 * np.sqrt(N)), abs(population - N) / N)
    return force, population, score


def stationary_band(f: np.ndarray, c: np.ndarray, omega: float, grid: Grid) -> tuple[np.ndarray, np.ndarray]:
    band, g, _ = banded_operator({"f": f, "c": c, "V": grid.volumes, "R": grid.R, "omega_C": omega})
    return band, g


def continue_stationary(state: dict, grid: Grid) -> None:
    root_v = np.sqrt(grid.volumes)
    for iteration in range(21):
        f, c, omega = state["f"], state["c"], state["omega"]
        force, population, score = residual(f, c, omega, grid)
        state["trace"].append({"iteration": iteration, "residual": score, "population": population})
        if score < 1e-9 and abs(population - N) / N < 1e-13:
            return
        if iteration == 20:
            raise RuntimeError("stationary Newton iteration limit")
        band, g = stationary_band(f, c, omega, grid)
        solved = solve_banded((2, 2), band, np.column_stack((-force, g)), check_finite=True)
        response = float(np.dot(g, solved[:, 1]))
        if not np.isfinite(response) or response == 0:
            raise RuntimeError("singular population-constrained Newton response")
        dw = (N - population - float(np.dot(g, solved[:, 0]))) / response
        delta = solved[:, 0] + dw * solved[:, 1]
        for halving in range(24):
            step = 2.0 ** -halving
            nf = f + step * delta[0::2] / root_v
            nc = c + step * delta[1::2] / root_v
            nw = omega + step * dw
            _, _, trial_score = residual(nf, nc, nw, grid)
            if np.isfinite(trial_score) and trial_score < score:
                state.update(f=nf, c=nc, omega=nw)
                state["trace"][-1]["step"] = step
                break
        else:
            raise RuntimeError("stationary Newton line search failed")


def kinetic(vector: np.ndarray, grid: Grid) -> np.ndarray:
    root_v = np.sqrt(grid.volumes)
    physical = vector / root_v
    flux = grid.conductance * np.diff(physical)
    result = np.zeros(grid.n)
    result[:-1] -= flux
    result[1:] += flux
    result[-1] += grid.outer_conductance * physical[-1]
    return result / root_v


def direct_action(vector: np.ndarray, f: np.ndarray, c: np.ndarray, omega: float,
                  grid: Grid, ell: int, phase: bool = False) -> np.ndarray:
    angular = ell * (ell + 1) * 4 * np.pi * grid.dr / grid.volumes
    h = COEFFICIENTS["h_C"]
    carrier = 2 * (COEFFICIENTS["e_C"] - h * (1 - f * f) - omega)
    if phase:
        return kinetic(vector, grid) + (angular + carrier + 2 * c * c) * vector
    u, v = vector[0::2], vector[1::2]
    result = np.empty_like(vector)
    mixed = 4 * h * f * c
    result[0::2] = kinetic(u, grid) + (angular + 4 * (3 * f * f - 1) + 2 * h * c * c) * u + mixed * v
    result[1::2] = kinetic(v, grid) + (angular + carrier + 6 * c * c) * v + mixed * u
    return result


def eigen_diagnostics(values: np.ndarray, vectors: np.ndarray, apply) -> dict:
    residuals = [float(np.linalg.norm(apply(vectors[:, j]) - value * vectors[:, j])) / max(1.0, abs(float(value)))
                 for j, value in enumerate(values)]
    orthogonality = float(np.max(np.abs(vectors.T @ vectors - np.eye(len(values)))))
    if max(residuals) >= 1e-8 or orthogonality >= 1e-8:
        raise RuntimeError(f"eigenpair qualification failed: {max(residuals)}, {orthogonality}")
    return {"eigenvalues": values.tolist(), "direct_residuals": residuals, "orthonormality_error": orthogonality}


def symmetry(values: np.ndarray, vectors: np.ndarray, candidate: np.ndarray, apply) -> dict:
    candidate = candidate / np.linalg.norm(candidate)
    overlaps = np.abs(vectors.T @ candidate)
    index = int(np.argmax(overlaps))
    return {"index": index, "overlap": float(overlaps[index]), "eigenvalue": float(values[index]),
            "operator_residual": float(np.linalg.norm(apply(candidate)))}


def spatial_spectra(f: np.ndarray, c: np.ndarray, omega: float, grid: Grid,
                    band: np.ndarray, eta: float) -> tuple[dict, dict]:
    operators, arrays = {}, {}
    angular = 4 * np.pi * grid.dr / grid.volumes
    for name, ell, phase in (("amp1", 1, False), ("amp2", 2, False),
                             ("phase0", 0, True), ("phase1", 1, True)):
        if phase:
            diagonal = band[2, 1::2] - 4 * c * c + ell * (ell + 1) * angular
            off = band[0, 3::2]
            values, vectors = eigh_tridiagonal(diagonal, off, select="i", select_range=(0, 5))
        else:
            lower = band[2:].copy()
            lower[0] += np.repeat(ell * (ell + 1) * angular, 2)
            values, vectors = eig_banded(lower, lower=True, select="i", select_range=(0, 5))
        apply = lambda v, l=ell, p=phase: direct_action(v, f, c, omega, grid, l, p)
        operators[name] = eigen_diagnostics(values, vectors, apply)
        arrays[name + "_values"], arrays[name + "_vectors"] = values, vectors
    root_v = np.sqrt(grid.volumes)
    translation = np.empty(2 * grid.n)
    translation[0::2] = root_v * derivative(f, grid.dr)
    translation[1::2] = root_v * derivative(c, grid.dr)
    symmetries = {
        "translation": symmetry(arrays["amp1_values"], arrays["amp1_vectors"], translation,
                                 lambda v: direct_action(v, f, c, omega, grid, 1)),
        "phase": symmetry(arrays["phase0_values"], arrays["phase0_vectors"], root_v * c,
                           lambda v: direct_action(v, f, c, omega, grid, 0, True)),
    }
    ti, pi = symmetries["translation"]["index"], symmetries["phase"]["index"]
    nonsymmetry = [j for j in range(6) if j != ti]
    gap_index = min(nonsymmetry, key=lambda j: arrays["amp1_values"][j])
    metrics = {
        "amp1_gap": float(arrays["amp1_values"][gap_index]),
        "amp2_minimum": float(arrays["amp2_values"][0]),
        "phase0_gap": float(np.min(np.delete(arrays["phase0_values"], pi))),
        "phase1_minimum": float(arrays["phase1_values"][0]),
    }
    dipole = arrays["amp1_vectors"][:, gap_index]
    weight = dipole[0::2] ** 2 + dipole[1::2] ** 2
    excess = metrics["amp1_gap"] - 2 * (COEFFICIENTS["e_C"] - omega)
    mode = {
        "index": gap_index, "carrier_fraction": float(np.dot(dipole[1::2], dipole[1::2])),
        "outside_radius_6": float(np.sum(weight[grid.r > 6])),
        "outside_half_domain": float(np.sum(weight[grid.r > grid.R / 2])),
        "rms_radius": float(np.sqrt(np.dot(weight, grid.r * grid.r))),
        "excess_over_exterior_threshold": excess, "radius_squared_excess": grid.R ** 2 * excess,
    }
    negative = any(op["eigenvalues"][0] < -eta for op in operators.values())
    support = all(s["overlap"] > 0.99 and abs(s["eigenvalue"]) <= eta for s in symmetries.values())
    support = support and all(value > eta for value in metrics.values())
    verdict = "CONTRADICTS" if negative else "SUPPORTS" if support else "INCONCLUSIVE"
    return {"operators": operators, "symmetries": symmetries, "metrics": metrics,
            "dipole_mode": mode, "angular_phase_verdict": verdict}, arrays


def radial_spectra(f: np.ndarray, c: np.ndarray, omega: float, grid: Grid,
                   band: np.ndarray, g: np.ndarray, eta: float) -> tuple[list, dict]:
    base_values = eig_banded(band[2:], lower=True, select="i", select_range=(0, 5), eigvals_only=True)
    if base_values[-1] <= eta:
        raise RuntimeError("six base eigenvalues do not determine shifted radial inertia")
    shifted = band.copy()
    shifted[2] -= eta
    shifted_response = solve_banded((2, 2), shifted, g)
    response_residual = float(np.linalg.norm(banded_mv(shifted, shifted_response) - g) / max(1.0, np.linalg.norm(g)))
    if response_residual >= 1e-8:
        raise RuntimeError("shifted radial response residual")
    zero_response = solve_banded((2, 2), band, g)
    rows, arrays = [], {"radial_base_values": base_values}
    for denominator in A_DENOMINATORS:
        a = 1.0 / denominator
        gamma = (1 + 4 * a * omega) / (2 * a * N)
        factor = float(1 + gamma * np.dot(g, shifted_response))
        if gamma <= 0 or not np.isfinite(factor) or factor == 0:
            raise RuntimeError("radial rank-one inertia is undefined")
        count = int(np.count_nonzero(base_values < eta) - int(factor < 0))
        if count != 0:
            raise RuntimeError(f"radial positivity at eta is unestablished: {count} eigenvalues below eta")
        factor_zero = float(1 + gamma * np.dot(g, zero_response))
        if factor_zero == 0:
            raise RuntimeError("zero-shift radial inverse is singular")
        def apply(v):
            return banded_mv(band, v) + gamma * g * np.dot(g, v)
        def inverse(v):
            z = solve_banded((2, 2), band, v)
            return z - gamma * zero_response * np.dot(g, z) / factor_zero
        size = 2 * grid.n
        operator = LinearOperator((size, size), matvec=apply, dtype=np.float64)
        opinv = LinearOperator((size, size), matvec=inverse, dtype=np.float64)
        values, vectors = eigsh(operator, k=1, sigma=0, which="LM", OPinv=opinv,
                               v0=np.cos(np.arange(size) * 0.37), tol=1e-11, maxiter=4000)
        direct = lambda v: direct_action(v, f, c, omega, grid, 0) + gamma * g * np.dot(g, v)
        diagnostics = eigen_diagnostics(values, vectors, direct)
        if values[0] <= eta:
            raise RuntimeError("radial minimum disagrees with positive inertia")
        rows.append({"a": a, "denominator": denominator, "gamma": gamma,
                     "minimum": float(values[0]), "shift": eta, "secular_factor": factor,
                     "eigenvalues_below_shift": count, "response_residual": response_residual,
                     "eigenpair": diagnostics, "verdict": "SUPPORTS"})
        arrays[f"radial_{denominator}_values"] = values
        arrays[f"radial_{denominator}_vectors"] = vectors
    return rows, arrays


def run(output: Path) -> int:
    output.mkdir(parents=True, exist_ok=False)
    receipt = {"schema": "matter-formation-spatial-domain-v1", "rows": [], "comparisons": [],
               "numerical_pass": False, "verdict": "INCONCLUSIVE", "failures": []}
    try:
        receipt["inputs"] = freeze_inputs(output)
        with np.load(SOURCE, allow_pickle=False) as archive:
            old_f, old_c = archive["f"].copy(), archive["c"].copy()
        old_grid = Grid.make(24.0, 768)
        baseline = stationary_diagnostics(old_f, old_c, old_grid, N)
        if not baseline["qualified"]:
            raise ValueError("immutable source fails first-variation qualification")
        for radius, cells in SCHEDULE:
            identifier = f"q256_R{int(radius)}_n{cells}"
            grid = Grid.make(radius, cells)
            f, c = interpolate_fields(old_f, old_c, old_grid, grid)
            state = {"f": f, "c": normalize_carrier(c, grid, N), "omega": baseline["omega"], "trace": []}
            row = {"id": identifier, "R": radius, "n": cells}
            arrays = {}
            try:
                continue_stationary(state, grid)
                f, c, omega = state["f"], state["c"], state["omega"]
                independent = source_metrics({"r": grid.r, "volumes": grid.volumes, "f": f, "c": c}, radius, N)
                primary = stationary_diagnostics(f, c, grid, N)
                row["source"] = primary
                row["independent_source"] = {k: v for k, v in independent.items() if k not in ("r", "V", "f", "c")}
                row["sampled_profile"] = {"min_f": float(np.min(f)), "min_c": float(np.min(c)),
                                          "min_f_difference": float(np.min(np.diff(f))),
                                          "max_c_difference": float(np.max(np.diff(c)))}
                if not (np.all(f >= 0) and np.all(c >= 0) and primary["charge_relative_error"] < 1e-12
                        and independent["population_error"] < 1e-12
                        and max(primary["residual_f"], primary["residual_c"], independent["residual_f"], independent["residual_c"]) < 1e-8):
                    raise RuntimeError("continued source is unqualified")
                for p, q in ((primary["energy"], independent["energy"]), (primary["omega"], independent["omega_C"])):
                    if abs(p - q) >= 1e-10 * max(1.0, abs(p), abs(q)):
                        raise RuntimeError("independent source reconstruction disagreement")
                if (radius, cells) == SCHEDULE[0]:
                    for key in ("energy", "omega"):
                        if abs(primary[key] - baseline[key]) > 1e-4 * max(1.0, abs(primary[key]), abs(baseline[key])):
                            raise RuntimeError("continued source differs from the retained prepared branch")
                eta = max(5e-4, 10 * primary["residual_f"], 10 * primary["residual_c"])
                row["eta"] = eta
                row["exterior_carrier_threshold"] = 2 * (COEFFICIENTS["e_C"] - omega)
                band, g = stationary_band(f, c, omega, grid)
                spatial, spectra = spatial_spectra(f, c, omega, grid, band, eta)
                row.update(spatial)
                arrays.update(spectra)
                parents, radial_arrays = radial_spectra(f, c, omega, grid, band, g, eta)
                row["parents"] = parents
                arrays.update(radial_arrays)
                row["metrics"].update({f"radial_{p['denominator']}": p["minimum"] for p in parents})
                row["numerical_pass"] = True
                print(identifier, json.dumps(row["metrics"]), flush=True)
            except Exception as error:
                row["numerical_pass"] = False
                row["error"] = f"{type(error).__name__}: {error}"
                receipt["failures"].append(identifier + ": " + row["error"])
                print(identifier, row["error"], flush=True)
            row["newton_trace"] = state["trace"]
            arrays.update(r=grid.r, volumes=grid.volumes, f=state["f"], c=state["c"], R=np.asarray(radius), q=np.asarray(N))
            row["artifact"] = save_arrays(output / (identifier + ".npz"), arrays)
            receipt["rows"].append(row)
        by_id = {row["id"]: row for row in receipt["rows"]}
        left = by_id["q256_R48_n1536"]
        for label, right_id in (("resolution", "q256_R48_n3072"), ("domain", "q256_R96_n3072")):
            right = by_id[right_id]
            if not left["numerical_pass"] or not right["numerical_pass"]:
                continue
            for metric, value in left["metrics"].items():
                other = right["metrics"][metric]
                tolerance = max(0.01 * max(abs(value), abs(other)), left["eta"], right["eta"])
                receipt["comparisons"].append({"pair": label, "metric": metric, "left": left["id"],
                                                "right": right_id, "difference": abs(value - other),
                                                "tolerance": tolerance, "pass": bool(abs(value - other) <= tolerance)})
        receipt["numerical_pass"] = not receipt["failures"] and len(receipt["comparisons"]) == 14
        if receipt["numerical_pass"]:
            if any(row["angular_phase_verdict"] == "CONTRADICTS" for row in receipt["rows"]):
                receipt["verdict"] = "CONTRADICTS—extended-domain finite-grid scalar spatial energetic qualification"
            elif all(row["angular_phase_verdict"] == "SUPPORTS" for row in receipt["rows"]) and all(c["pass"] for c in receipt["comparisons"]):
                receipt["verdict"] = "SUPPORTS—extended-domain finite-grid scalar spatial energetic qualification"
    except Exception as error:
        receipt["failures"].append(f"{type(error).__name__}: {error}")
    write_json(output / "results.json", receipt)
    print(json.dumps({"numerical_pass": receipt["numerical_pass"], "verdict": receipt["verdict"],
                      "failures": receipt["failures"]}), flush=True)
    return 0 if receipt["numerical_pass"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    return run(args.output_dir.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
