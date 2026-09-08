#!/usr/bin/env python3
"""Geometric regular-value degree analysis of retained chiral-lattice fields.

Run from the CassiTheory root after the three frozen trajectories complete. The
protocol is frozen in matter-formation-geometric-degree-prereg.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from scipy.integrate import solve_bvp

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations" / "matter-formation-geometric-degree-prereg.md"
SOLVER = ROOT / "computations" / "matter_formation_chiral_lattice.py"
SCHEMA = "matter-formation-geometric-degree-v1"
MU = 0.5266577616452649
PHI = (1.0 + math.sqrt(5.0)) / 2.0
TAU_COEFFICIENT = 1.0e-10
TAU_DETERMINANT = 1.0e-13
EDGE_LIMIT = math.pi / 2.0
CHUNK_CUBES = 32768
TETRAHEDRA = (
    ((0, 0, 0), (1, 0, 0), (1, 1, 0), (1, 1, 1)),
    ((0, 0, 0), (1, 1, 0), (0, 1, 0), (1, 1, 1)),
    ((0, 0, 0), (0, 1, 0), (0, 1, 1), (1, 1, 1)),
    ((0, 0, 0), (0, 1, 1), (0, 0, 1), (1, 1, 1)),
    ((0, 0, 0), (0, 0, 1), (1, 0, 1), (1, 1, 1)),
    ((0, 0, 0), (1, 0, 1), (1, 0, 0), (1, 1, 1)),
)
TRAJECTORY_DIRS = {
    "impulse_N48": ROOT / "runs" / "20260907_matter_formation_chiral_lattice" / "execution_recovery1" / "impulse_N48",
    "impulse_N64": ROOT / "runs" / "20260907_matter_formation_chiral_lattice" / "execution_cpu1" / "impulse_N64",
    "impulse_N48_halfdt": ROOT / "runs" / "20260907_matter_formation_chiral_lattice" / "execution_cpu1" / "impulse_N48_halfdt",
}
EXPECTED = {
    "impulse_N48": {"N": 48, "L": 18.0, "dt": 0.002, "T": 4.0},
    "impulse_N64": {"N": 64, "L": 18.0, "dt": 0.002, "T": 4.0},
    "impulse_N48_halfdt": {"N": 48, "L": 18.0, "dt": 0.001, "T": 4.0},
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def protocol_sha256() -> str:
    text = PROTOCOL.read_text(encoding="utf-8")
    frozen = text.split("<!-- geometric-degree-protocol:start -->", 1)[1].split(
        "<!-- geometric-degree-protocol:end -->", 1
    )[0]
    return hashlib.sha256(frozen.encode("utf-8")).hexdigest()


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def targets() -> np.ndarray:
    values = []
    roots = np.sqrt(np.array([2.0, 3.0, 5.0, 7.0]))
    phases = np.array([0.11, 0.23, 0.37, 0.53])
    for m in range(1, 17):
        q = np.sin(m * roots + phases)
        values.append(q / np.linalg.norm(q))
    return np.asarray(values, dtype=np.float64)


def basis_matrix(nsites: int, length: float) -> np.ndarray:
    primitive = np.array(
        [[0.5, 0.5, 0.0], [0.5 / PHI, 0.0, 0.5 / PHI], [0.0, 1.0, 1.0]],
        dtype=np.float64,
    )
    return (length / nsites) * primitive


def coordinate_grid(nsites: int, basis: np.ndarray) -> np.ndarray:
    index = np.arange(nsites, dtype=np.float64) - nsites / 2.0 + 0.5
    grid = np.stack(np.meshgrid(index, index, index, indexing="ij"))
    return np.einsum("ai,ixyz->axyz", basis, grid)


def radial_profile() -> tuple[np.ndarray, np.ndarray]:
    r = np.linspace(1.0e-5, 64.0, 1201)
    radius = 1.0 / math.sqrt(2.0)
    guess = 2.0 * np.arctan(r / radius)
    guess_p = 2.0 * radius / (r * r + radius * radius)

    def rhs(x: np.ndarray, y: np.ndarray) -> np.ndarray:
        theta, theta_p = y
        sine = np.sin(theta)
        theta_pp = (
            -2.0 * x * theta_p
            - np.sin(2.0 * theta) * (theta_p * theta_p - 1.0 - sine * sine / (x * x))
            - MU * MU * x * x * sine
        ) / (x * x + 2.0 * sine * sine)
        return np.vstack((theta_p, theta_pp))

    def boundary(left: np.ndarray, right: np.ndarray) -> np.ndarray:
        return np.array([left[0] - r[0] * left[1], right[0] - math.pi])

    solution = solve_bvp(rhs, boundary, r, np.vstack((guess, guess_p)), tol=1.0e-8, max_nodes=100000)
    if not solution.success:
        raise RuntimeError(f"Massive radial profile failed: {solution.message}")
    sample = np.linspace(0.0, 64.0, 64001)
    profile = math.pi - solution.sol(np.maximum(sample, r[0]))[0]
    profile[0], profile[-1] = math.pi, 0.0
    return sample, profile


def minimum_image(displacement: np.ndarray, basis: np.ndarray, nsites: int) -> np.ndarray:
    inverse = np.linalg.inv(basis)
    primitive = np.einsum("ij,j...->i...", inverse, displacement)
    primitive -= nsites * np.round(primitive / nsites)
    return np.einsum("ij,j...->i...", basis, primitive)


def hedgehog(
    coordinates: np.ndarray,
    basis: np.ndarray,
    nsites: int,
    radial: tuple[np.ndarray, np.ndarray],
    scale: float,
    centre: np.ndarray | None = None,
) -> np.ndarray:
    displacement = coordinates if centre is None else minimum_image(
        coordinates - np.asarray(centre, dtype=np.float64)[:, None, None, None], basis, nsites
    )
    radius = np.linalg.norm(displacement, axis=0)
    knots, values = radial
    f = np.interp(radius / scale, knots, values)
    unit = displacement / np.maximum(radius, 1.0e-30)[None]
    return np.concatenate((np.cos(f)[None], np.sin(f)[None] * unit), axis=0)


def multiply(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    scalar = a[:1] * b[:1] - np.sum(a[1:] * b[1:], axis=0, keepdims=True)
    vector = (
        a[:1] * b[1:]
        + b[:1] * a[1:]
        - np.cross(a[1:], b[1:], axisa=0, axisb=0, axisc=0)
    )
    return np.concatenate((scalar, vector), axis=0)


def max_edge_angle(field: np.ndarray) -> float:
    maximum = 0.0
    for axis in range(3):
        dot = np.sum(field * np.roll(field, -1, axis=axis + 1), axis=0)
        maximum = max(maximum, float(np.max(np.arccos(np.clip(dot, -1.0, 1.0)))))
    return maximum


def periodic_cluster(points: list[list[float]], basis: np.ndarray, nsites: int) -> tuple[list[float], float]:
    primitive = np.asarray(points, dtype=np.float64)
    angles = 2.0 * math.pi * primitive / nsites
    mean_angle = np.arctan2(np.mean(np.sin(angles), axis=0), np.mean(np.cos(angles), axis=0))
    centre_primitive = mean_angle * nsites / (2.0 * math.pi)
    delta = primitive - centre_primitive[None]
    delta -= nsites * np.round(delta / nsites)
    physical_delta = np.einsum("ij,nj->ni", basis, delta)
    rms = float(np.sqrt(np.mean(np.sum(physical_delta * physical_delta, axis=1))))
    centre_physical = basis @ centre_primitive
    return centre_physical.tolist(), rms


def _domain_orientation(basis: np.ndarray, tetrahedron: tuple[tuple[int, int, int], ...]) -> float:
    x = np.asarray(tetrahedron, dtype=np.float64)
    physical = np.einsum("ij,nj->ni", basis, x)
    determinant = np.linalg.det(np.stack((physical[1] - physical[0], physical[2] - physical[0], physical[3] - physical[0]), axis=1))
    if abs(determinant) <= 1.0e-30:
        raise RuntimeError("Degenerate domain tetrahedron")
    return float(np.sign(determinant))


def geometric_snapshot(
    field: np.ndarray,
    basis: np.ndarray,
    target_values: np.ndarray,
    *,
    reverse_orientation: bool = False,
) -> dict[str, Any]:
    if field.ndim != 4 or field.shape[0] != 4 or len(set(field.shape[1:])) != 1:
        raise ValueError(f"Expected (4,N,N,N) field, received {field.shape}")
    if not np.all(np.isfinite(field)) or not np.all(np.isfinite(basis)):
        raise ValueError("Nonfinite field or basis")
    norms = np.linalg.norm(field, axis=0)
    unit_error = float(np.max(np.abs(norms - 1.0)))
    if unit_error > 1.0e-8:
        raise ValueError(f"Field is not unit normalized: {unit_error}")
    nsites = field.shape[1]
    edge_angle = max_edge_angle(field)
    hits: list[list[dict[str, Any]]] = [[] for _ in range(len(target_values))]
    ambiguous: list[dict[str, Any]] = []
    total_cubes = nsites**3
    orientation_multiplier = -1.0 if reverse_orientation else 1.0

    for start in range(0, total_cubes, CHUNK_CUBES):
        flat = np.arange(start, min(start + CHUNK_CUBES, total_cubes), dtype=np.int64)
        ii = flat // (nsites * nsites)
        jj = (flat // nsites) % nsites
        kk = flat % nsites
        bases = np.stack((ii, jj, kk), axis=1)
        centred_bases = bases.astype(np.float64) - nsites / 2.0 + 0.5
        for tetra_index, tetrahedron in enumerate(TETRAHEDRA):
            columns = []
            for offset in tetrahedron:
                index = (bases + np.asarray(offset, dtype=np.int64)[None]) % nsites
                columns.append(field[:, index[:, 0], index[:, 1], index[:, 2]].T)
            matrices = np.stack(columns, axis=2)
            determinants = np.linalg.det(matrices)
            usable = np.flatnonzero(np.abs(determinants) > TAU_DETERMINANT)
            if usable.size == 0:
                continue
            selected = matrices[usable]
            inverse = np.linalg.inv(selected)
            coefficients = np.einsum("nij,kj->nik", inverse, target_values)
            det_selected = determinants[usable]
            domain_sign = _domain_orientation(basis, tetrahedron) * orientation_multiplier
            offsets = np.asarray(tetrahedron, dtype=np.float64)
            for target_index in range(len(target_values)):
                c = coefficients[:, :, target_index]
                near_simplex = np.all(c > -10.0 * TAU_COEFFICIENT, axis=1)
                near_face = near_simplex & np.any(np.abs(c) <= 10.0 * TAU_COEFFICIENT, axis=1)
                covered = np.all(c > TAU_COEFFICIENT, axis=1)
                near_det = covered & (np.abs(det_selected) < 10.0 * TAU_DETERMINANT)
                for local in np.flatnonzero(near_face | near_det):
                    original = int(usable[local])
                    ambiguous.append(
                        {
                            "target": target_index,
                            "cube": bases[original].tolist(),
                            "tetrahedron": tetra_index,
                            "determinant": float(determinants[original]),
                            "coefficients": c[local].tolist(),
                        }
                    )
                for local in np.flatnonzero(covered):
                    original = int(usable[local])
                    weights = c[local] / np.sum(c[local])
                    primitive = centred_bases[original] + weights @ offsets
                    primitive -= nsites * np.floor((primitive + nsites / 2.0) / nsites)
                    physical = basis @ primitive
                    sign = int(np.sign(det_selected[local] * domain_sign))
                    hits[target_index].append(
                        {
                            "sign": sign,
                            "cube": bases[original].tolist(),
                            "tetrahedron": tetra_index,
                            "primitive": primitive.tolist(),
                            "physical": physical.tolist(),
                            "determinant": float(det_selected[local]),
                            "min_coefficient": float(np.min(c[local])),
                        }
                    )

    summaries = []
    separations = []
    sign_points: dict[int, list[list[float]]] = {1: [], -1: []}
    for target_index, target_hits in enumerate(hits):
        target_hits.sort(key=lambda row: (row["sign"], row["cube"], row["tetrahedron"]))
        positive = [row for row in target_hits if row["sign"] > 0]
        negative = [row for row in target_hits if row["sign"] < 0]
        for row in positive:
            sign_points[1].append(row["primitive"])
        for row in negative:
            sign_points[-1].append(row["primitive"])
        if len(positive) == 1 and len(negative) == 1:
            delta = np.asarray(positive[0]["physical"]) - np.asarray(negative[0]["physical"])
            delta = minimum_image(delta, basis, nsites)
            separations.append(float(np.linalg.norm(delta)))
        summaries.append(
            {
                "index": target_index,
                "target": target_values[target_index].tolist(),
                "positive_hits": positive,
                "negative_hits": negative,
                "net_degree": len(positive) - len(negative),
            }
        )

    pair_coverage = sum(bool(row["positive_hits"]) and bool(row["negative_hits"]) for row in summaries) / len(summaries)
    zero_degree_coverage = sum(row["net_degree"] == 0 for row in summaries) / len(summaries)
    exactly_one_each = all(len(row["positive_hits"]) == 1 and len(row["negative_hits"]) == 1 for row in summaries)
    separation = float(np.median(separations)) if separations else None
    centres: dict[str, list[float] | None] = {"positive": None, "negative": None}
    radii: dict[str, float | None] = {"positive": None, "negative": None}
    for sign, label in ((1, "positive"), (-1, "negative")):
        if sign_points[sign]:
            centres[label], radii[label] = periodic_cluster(sign_points[sign], basis, nsites)
    finite_radii = [value for value in radii.values() if value is not None]
    hit_rms = max(finite_radii) if finite_radii else None
    admissible = edge_angle < EDGE_LIMIT
    pair_pass = bool(
        admissible
        and not ambiguous
        and pair_coverage == 1.0
        and zero_degree_coverage == 1.0
        and exactly_one_each
        and separation is not None
        and separation >= 4.0
        and hit_rms is not None
        and hit_rms <= 2.0
    )
    return {
        "N": nsites,
        "unit_error": unit_error,
        "edge_angle_max": edge_angle,
        "admissible": admissible,
        "ambiguous": ambiguous,
        "ambiguity_count": len(ambiguous),
        "targets": summaries,
        "pair_coverage": pair_coverage,
        "zero_degree_coverage": zero_degree_coverage,
        "exactly_one_each": exactly_one_each,
        "separation": separation,
        "cluster_centres": centres,
        "cluster_rms": radii,
        "hit_rms_max": hit_rms,
        "pair_pass": pair_pass,
    }


def strip_reversal_details(receipt: dict[str, Any]) -> dict[str, Any]:
    copy = json.loads(canonical(receipt))
    for target in copy["targets"]:
        for hit in target["positive_hits"] + target["negative_hits"]:
            hit.pop("sign", None)
    return copy


def control_suite(target_values: np.ndarray, radial: tuple[np.ndarray, np.ndarray]) -> dict[str, Any]:
    vacuum_basis = basis_matrix(16, 18.0)
    vacuum = np.zeros((4, 16, 16, 16), dtype=np.float64)
    vacuum[0] = 1.0
    vacuum_result = geometric_snapshot(vacuum, vacuum_basis, target_values)

    hedgehogs: dict[str, Any] = {}
    hedgehog_sign: int | None = None
    for nsites in (32, 48, 64):
        basis = basis_matrix(nsites, 18.0)
        field = hedgehog(coordinate_grid(nsites, basis), basis, nsites, radial, 1.0)
        result = geometric_snapshot(field, basis, target_values)
        counts = [(len(row["positive_hits"]), len(row["negative_hits"])) for row in result["targets"]]
        signs = [1 if positive == 1 else -1 if negative == 1 else 0 for positive, negative in counts]
        passes = all(abs(positive - negative) == 1 and positive + negative == 1 for positive, negative in counts)
        passes = passes and len(set(signs)) == 1 and signs[0] != 0 and not result["ambiguous"]
        if passes:
            if hedgehog_sign is None:
                hedgehog_sign = signs[0]
            passes = signs[0] == hedgehog_sign
        hedgehogs[str(nsites)] = {"result": result, "passes": bool(passes), "sign": signs[0] if passes else None}

    pair_basis = basis_matrix(48, 18.0)
    coordinates = coordinate_grid(48, pair_basis)
    left = hedgehog(coordinates, pair_basis, 48, radial, 1.5, np.array([-3.0, 0.0, 0.0]))
    right = hedgehog(coordinates, pair_basis, 48, radial, 1.5, np.array([3.0, 0.0, 0.0]))
    right_inverse = right.copy()
    right_inverse[1:] *= -1.0
    pair_field = multiply(left, right_inverse)
    pair_field /= np.linalg.norm(pair_field, axis=0, keepdims=True)
    pair = geometric_snapshot(pair_field, pair_basis, target_values)
    pair_targets = pair["targets"]
    pair_covered = sum(len(row["positive_hits"]) == 1 and len(row["negative_hits"]) == 1 for row in pair_targets)
    pair_passes = bool(
        pair_covered >= 15
        and all(row["net_degree"] == 0 for row in pair_targets)
        and pair["separation"] is not None
        and 4.0 <= pair["separation"] <= 8.0
        and not pair["ambiguous"]
    )

    reversed_pair = geometric_snapshot(pair_field, pair_basis, target_values, reverse_orientation=True)
    locations_preserved = True
    signs_reversed = True
    for ordinary, reversed_row in zip(pair["targets"], reversed_pair["targets"], strict=True):
        ordinary_hits = ordinary["positive_hits"] + ordinary["negative_hits"]
        reversed_hits = reversed_row["positive_hits"] + reversed_row["negative_hits"]
        ordinary_key = sorted((row["cube"], row["tetrahedron"], row["primitive"]) for row in ordinary_hits)
        reversed_key = sorted((row["cube"], row["tetrahedron"], row["primitive"]) for row in reversed_hits)
        locations_preserved = locations_preserved and canonical(ordinary_key) == canonical(reversed_key)
        ordinary_signs = sorted((row["cube"], row["tetrahedron"], row["sign"]) for row in ordinary_hits)
        reversed_signs = sorted((row["cube"], row["tetrahedron"], -row["sign"]) for row in reversed_hits)
        signs_reversed = signs_reversed and ordinary_signs == reversed_signs
    orientation_passes = bool(locations_preserved and signs_reversed)
    vacuum_passes = bool(
        all(not row["positive_hits"] and not row["negative_hits"] for row in vacuum_result["targets"])
        and not vacuum_result["ambiguous"]
    )
    all_pass = bool(
        vacuum_passes
        and all(row["passes"] for row in hedgehogs.values())
        and pair_passes
        and orientation_passes
    )
    return {
        "vacuum": {"result": vacuum_result, "passes": vacuum_passes},
        "hedgehogs": hedgehogs,
        "hedgehog_sign": hedgehog_sign,
        "pair": {"result": pair, "passes": pair_passes, "covered_targets": pair_covered},
        "orientation_reversal": {
            "result": reversed_pair,
            "locations_preserved": locations_preserved,
            "signs_reversed": signs_reversed,
            "passes": orientation_passes,
        },
        "all_pass": all_pass,
    }


def load_trajectory(name: str, directory: Path, target_values: np.ndarray) -> dict[str, Any]:
    result_path = directory / "results.json"
    if not result_path.is_file():
        raise FileNotFoundError(f"Missing trajectory receipt: {result_path}")
    source = json.loads(result_path.read_text(encoding="utf-8"))
    if source.get("schema") != "matter-formation-chiral-lattice-v1" or source.get("completed") is not True:
        raise ValueError(f"Incomplete or wrong-schema trajectory: {name}")
    expected = EXPECTED[name]
    parameters = source.get("parameters", {})
    for key, value in expected.items():
        if parameters.get(key) != value:
            raise ValueError(f"{name} parameter {key} differs: {parameters.get(key)} != {value}")
    if parameters.get("mu") != MU or parameters.get("kappa") != 1.0 or source.get("mode") != "impulse":
        raise ValueError(f"{name} physical parameters differ from protocol")
    source_hash = source.get("sources", {}).get("computations/matter_formation_chiral_lattice.py")
    if source_hash != sha256(SOLVER):
        raise ValueError(f"{name} solver hash differs from current frozen source")

    snapshots = []
    for artifact in source.get("snapshots", []):
        snapshot_path = directory / artifact["file"]
        if not snapshot_path.is_file() or sha256(snapshot_path) != artifact.get("sha256"):
            raise ValueError(f"{name} snapshot identity failure: {snapshot_path}")
        with np.load(snapshot_path, allow_pickle=False) as data:
            field = np.asarray(data["n"], dtype=np.float64)
            basis = np.asarray(data["basis"], dtype=np.float64)
        if not np.array_equal(basis, basis_matrix(expected["N"], expected["L"])):
            raise ValueError(f"{name} basis differs from protocol")
        reconstructed = geometric_snapshot(field, basis, target_values)
        reconstructed.update(
            {
                "t": float(artifact["t"]),
                "source_file": relative(snapshot_path),
                "source_sha256": artifact["sha256"],
            }
        )
        snapshots.append(reconstructed)
    if not snapshots or snapshots[-1]["t"] != expected["T"]:
        raise ValueError(f"{name} snapshots do not reach T={expected['T']}")
    snapshots.sort(key=lambda row: row["t"])
    first = next((row["t"] for row in snapshots if row["pair_pass"]), None)
    formation = first is not None and first <= 2.0
    persistence = bool(
        formation and all(row["pair_pass"] for row in snapshots if row["t"] >= float(first))
    )
    degree_conservation = all(
        row["targets"][target]["net_degree"] == 0
        for row in snapshots
        if row["admissible"]
        for target in range(len(target_values))
    )
    return {
        "input_directory": relative(directory),
        "results_file": relative(result_path),
        "results_sha256": sha256(result_path),
        "parameters": expected,
        "snapshots": snapshots,
        "t_star": first,
        "formation": bool(formation),
        "persistence": persistence,
        "degree_conservation": bool(degree_conservation),
    }


def physical_distance(a: Iterable[float], b: Iterable[float], basis: np.ndarray, nsites: int) -> float:
    return float(np.linalg.norm(minimum_image(np.asarray(a) - np.asarray(b), basis, nsites)))


def compare_trajectories(
    left: dict[str, Any],
    right: dict[str, Any],
    *,
    tolerance: float,
    nsites: int,
    basis: np.ndarray,
) -> dict[str, Any]:
    left_rows = {row["t"]: row for row in left["snapshots"]}
    right_rows = {row["t"]: row for row in right["snapshots"]}
    common = sorted(set(left_rows) & set(right_rows))
    rows = []
    all_pass = bool(common and common[-1] == 4.0)
    for time in common:
        first, second = left_rows[time], right_rows[time]
        state_agrees = first["pair_pass"] == second["pair_pass"]
        separation_difference = None
        centre_differences = None
        metric_pass = True
        if first["pair_pass"] and second["pair_pass"]:
            separation_difference = abs(float(first["separation"]) - float(second["separation"]))
            centre_differences = {
                label: physical_distance(
                    first["cluster_centres"][label], second["cluster_centres"][label], basis, nsites
                )
                for label in ("positive", "negative")
            }
            metric_pass = separation_difference <= tolerance and all(
                value <= tolerance for value in centre_differences.values()
            )
        row_pass = bool(state_agrees and metric_pass)
        rows.append(
            {
                "t": time,
                "state_agrees": state_agrees,
                "separation_difference": separation_difference,
                "centre_differences": centre_differences,
                "passes": row_pass,
            }
        )
        all_pass = all_pass and row_pass
    return {"tolerance": tolerance, "common_times": common, "rows": rows, "passes": bool(all_pass)}


def run(output: Path) -> dict[str, Any]:
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError(f"--output must be absent or empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    target_values = targets()
    radial = radial_profile()
    first_controls = control_suite(target_values, radial)
    second_controls = control_suite(target_values, radial)
    reproducible = canonical(first_controls) == canonical(second_controls)
    first_controls["reproducibility"] = {"passes": reproducible}
    first_controls["all_pass"] = bool(first_controls["all_pass"] and reproducible)

    trajectories = {
        name: load_trajectory(name, directory, target_values)
        for name, directory in TRAJECTORY_DIRS.items()
    }
    timestep = compare_trajectories(
        trajectories["impulse_N48"],
        trajectories["impulse_N48_halfdt"],
        tolerance=0.25,
        nsites=48,
        basis=basis_matrix(48, 18.0),
    )
    refinement = compare_trajectories(
        trajectories["impulse_N48"],
        trajectories["impulse_N64"],
        tolerance=0.50,
        nsites=48,
        basis=basis_matrix(48, 18.0),
    )
    # The cluster centres are physical coordinates, so only the common physical
    # periodic cell matters; using the N=48 primitive basis gives that cell.
    admissibility = all(
        row["admissible"] and not row["ambiguous"]
        for trajectory in trajectories.values()
        for row in trajectory["snapshots"]
    )
    degree_conservation = all(row["degree_conservation"] for row in trajectories.values())
    formation = trajectories["impulse_N64"]["formation"]
    persistence = trajectories["impulse_N64"]["persistence"]
    gates = {
        "controls": first_controls["all_pass"],
        "admissibility": admissibility,
        "degree_conservation": degree_conservation,
        "time_step_agreement": timestep,
        "spatial_refinement": refinement,
        "formation_N64": formation,
        "persistence_N64": persistence,
    }
    if not first_controls["all_pass"] or not admissibility:
        verdict = "INCONCLUSIVE"
    elif not timestep["passes"] or not refinement["passes"] or not degree_conservation:
        verdict = "INCONCLUSIVE"
    elif not formation or not persistence:
        verdict = "DOES NOT EMERGE"
    else:
        verdict = "EMERGES CONDITIONAL"

    source_paths = [Path(__file__).resolve(), PROTOCOL, SOLVER]
    payload = {
        "schema": SCHEMA,
        "sources": {relative(path): sha256(path) for path in source_paths},
        "protocol_file": relative(PROTOCOL),
        "protocol_sha256": protocol_sha256(),
        "parameters": {
            "mu": MU,
            "coefficient_tolerance": TAU_COEFFICIENT,
            "determinant_tolerance": TAU_DETERMINANT,
            "edge_angle_limit": EDGE_LIMIT,
            "targets": target_values.tolist(),
            "tetrahedra": TETRAHEDRA,
            "trajectory_directories": {name: relative(path) for name, path in TRAJECTORY_DIRS.items()},
        },
        "controls": first_controls,
        "trajectories": trajectories,
        "gates": gates,
        "verdict": verdict,
        "scientific_scope": (
            "This geometric qualification concerns only pair formation and persistence in the supplied "
            "massive chiral action. It does not select a canonical Cassi action, quantum state, "
            "renormalization prescription, fermionic statistics or particle identity."
        ),
    }
    receipt = output / "results.json"
    receipt.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "runs" / "20260907_matter_formation_geometric_degree" / "primary",
    )
    args = parser.parse_args()
    payload = run(args.output.resolve())
    print(json.dumps({"verdict": payload["verdict"], "gates": payload["gates"]}, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
