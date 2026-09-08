#!/usr/bin/env python3
"""Independent, fail-closed verifier for the geometric-degree receipt.

The verifier intentionally imports no primary implementation.  It reconstructs
all maps from raw NPZ files, uses a slabbed tetrahedron walk, and emits a
canonical JSON receipt.  A missing, malformed, hash-mismatched, non-finite, or
numerically ambiguous input is an inconclusive verification rather than a
best-effort result.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
from scipy.integrate import solve_bvp

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
PROTOCOL = ROOT / "computations" / "matter-formation-geometric-degree-prereg.md"
SOURCE = ROOT / "computations" / "matter_formation_geometric_degree.py"
SOLVER = ROOT / "computations" / "matter_formation_chiral_lattice.py"
SCHEMA = "matter-formation-geometric-degree-verification-v1"
PRIMARY_SCHEMA = "matter-formation-geometric-degree-v1"
TAU_C = 1.0e-10
TAU_D = 1.0e-13
TOL = 1.0e-10
EDGE_LIMIT = math.pi / 2.0
MU = 0.5266577616452649
KAPPA = 1.0
P_PRIMITIVE = 2.0
L_DEFAULT = 18.0
TARGET_COUNT = 16

TETS = np.asarray(
    ((0, 1, 2, 6), (0, 2, 3, 6), (0, 3, 7, 6),
     (0, 7, 4, 6), (0, 4, 5, 6), (0, 5, 1, 6)), dtype=np.int64
)
CUBE_OFFSETS = np.asarray(
    ((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
     (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)), dtype=np.float64
)


class VerificationError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    if not path.is_file():
        raise VerificationError(f"missing file: {path}")
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def protocol_sha256(path: Path = PROTOCOL) -> str:
    text = path.read_text(encoding="utf-8")
    begin = "<!-- geometric-degree-protocol:start -->"
    end = "<!-- geometric-degree-protocol:end -->"
    a = text.find(begin)
    if a < 0:
        raise VerificationError("protocol start marker missing")
    a += len(begin)
    b = text.find(end, a)
    if b < 0 or text.find(begin, a) >= 0:
        raise VerificationError("protocol markers are missing or duplicated")
    return hashlib.sha256(text[a:b].encode("utf-8")).hexdigest()


def finite(value: Any) -> bool:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return True
    if isinstance(value, (int, float, np.integer, np.floating)):
        return math.isfinite(float(value))
    if isinstance(value, Mapping):
        return all(isinstance(k, str) and finite(v) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return all(finite(v) for v in value)
    return False


def scalar(value: Any, label: str) -> float:
    if isinstance(value, (bool, np.bool_)):
        raise VerificationError(f"{label}: boolean is not scalar")
    try:
        x = float(value)
    except (TypeError, ValueError) as e:
        raise VerificationError(f"{label}: not scalar") from e
    if not math.isfinite(x):
        raise VerificationError(f"{label}: non-finite")
    return x


def integer(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise VerificationError(f"{label}: boolean is not integer")
    try:
        x = int(value)
    except (TypeError, ValueError) as e:
        raise VerificationError(f"{label}: not integer") from e
    if isinstance(value, float) and value != x:
        raise VerificationError(f"{label}: nonintegral")
    return x


def canonical(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): canonical(value[k]) for k in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [canonical(v) for v in value]
    if isinstance(value, np.ndarray):
        return canonical(value.tolist())
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def json_bytes(value: Any) -> bytes:
    return json.dumps(canonical(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def equal(a: Any, b: Any, path: str = "") -> bool:
    """Receipt comparison: exact discrete values, 1e-10 absolute finite scalars."""
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if isinstance(a, str) or isinstance(b, str):
        return isinstance(a, str) and isinstance(b, str) and a == b
    if isinstance(a, (int, np.integer)) and isinstance(b, (int, np.integer)):
        return int(a) == int(b)
    if isinstance(a, (float, np.floating)) or isinstance(b, (float, np.floating)):
        try:
            x, y = float(a), float(b)
        except (TypeError, ValueError):
            return False
        return math.isfinite(x) and math.isfinite(y) and abs(x - y) <= TOL
    if isinstance(a, Mapping) and isinstance(b, Mapping):
        return set(a) == set(b) and all(equal(a[k], b[k], f"{path}.{k}") for k in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(equal(x, y, f"{path}[{i}]") for i, (x, y) in enumerate(zip(a, b)))
    return a == b


def load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as f:
            obj = json.load(f)
    except Exception as e:
        raise VerificationError(f"cannot read JSON: {path}") from e
    if not isinstance(obj, dict) or not finite(obj):
        raise VerificationError("receipt must be a finite JSON object")
    return obj


def resolve_primary(arg: str) -> tuple[Path, Path]:
    p = Path(arg).expanduser().resolve()
    if p.is_dir():
        p = p / "results.json"
    if not p.is_file():
        raise VerificationError(f"primary receipt missing: {p}")
    return p, p.parent


def resolve_path(name: Any, base: Path, *, allow_root: bool = True) -> Path:
    if not isinstance(name, str) or not name:
        raise VerificationError("artifact path is not a non-empty string")
    p = Path(name)
    out = (p if p.is_absolute() else (base / p)).resolve()
    if not allow_root:
        try:
            out.relative_to(base.resolve())
        except ValueError as e:
            raise VerificationError(f"artifact escapes receipt directory: {name}") from e
    if not out.is_file():
        raise VerificationError(f"artifact missing: {out}")
    return out


def primitive_basis(n: int, length: float) -> np.ndarray:
    phi = (1.0 + math.sqrt(5.0)) / 2.0
    a0 = np.asarray(((0.5, 1.0 / (2.0 * phi), 0.0),
                     (0.5, 0.0, P_PRIMITIVE / 2.0),
                     (0.0, 1.0 / (2.0 * phi), P_PRIMITIVE / 2.0)), dtype=np.float64).T
    return (float(length) / float(n)) * a0


def targets() -> np.ndarray:
    values: list[np.ndarray] = []
    roots = np.sqrt(np.asarray([2.0, 3.0, 5.0, 7.0], dtype=np.float64))
    phases = np.asarray([0.11, 0.23, 0.37, 0.53], dtype=np.float64)
    for m in range(1, TARGET_COUNT + 1):
        q = np.sin(m * roots + phases)
        norm = np.linalg.norm(q)
        if norm == 0.0 or not math.isfinite(float(norm)):
            raise VerificationError("invalid regular-value target")
        values.append(q / norm)
    return np.asarray(values, dtype=np.float64)


def radial_profile() -> tuple[np.ndarray, np.ndarray]:
    eps, end = 1.0e-5, 64.0
    r = np.linspace(eps, end, 1201, dtype=np.float64)
    width = 1.0 / math.sqrt(2.0)
    theta0 = 2.0 * np.arctan(r / width)
    slope0 = 2.0 * width / (r * r + width * width)

    def fun(x: np.ndarray, y: np.ndarray) -> np.ndarray:
        theta, theta_p = y
        sine = np.sin(theta)
        theta_pp = (
            -2.0 * x * theta_p
            - np.sin(2.0 * theta)
            * (theta_p * theta_p - 1.0 - sine * sine / (x * x))
            - MU * MU * x * x * sine
        ) / (x * x + 2.0 * sine * sine)
        return np.vstack((theta_p, theta_pp))

    def bc(left: np.ndarray, right: np.ndarray) -> np.ndarray:
        return np.asarray((left[0] - eps * left[1], right[0] - math.pi))

    solution = solve_bvp(
        fun,
        bc,
        r,
        np.vstack((theta0, slope0)),
        tol=1.0e-8,
        max_nodes=100000,
        verbose=0,
    )
    if not solution.success:
        raise VerificationError(f"analytic radial BVP failed: {solution.message}")
    nodes = np.linspace(0.0, end, 64001, dtype=np.float64)
    values = math.pi - solution.sol(np.maximum(nodes, eps))[0]
    values[0], values[-1] = math.pi, 0.0
    if not all(np.all(np.isfinite(x)) for x in (nodes, values)):
        raise VerificationError("analytic profile is nonfinite")
    return nodes, values


def interp_profile(radius: np.ndarray, nodes: np.ndarray, values: np.ndarray) -> np.ndarray:
    out = np.interp(np.asarray(radius, dtype=np.float64), nodes, values, left=values[0], right=values[-1])
    out = np.asarray(out, dtype=np.float64)
    out[radius <= 0.0] = values[0]
    return out


def qmul(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    out = np.empty_like(a)
    out[0] = a[0] * b[0] - np.sum(a[1:] * b[1:], axis=0)
    # The solver uses the opposite orientation for the quaternion cross term.
    out[1:] = a[0] * b[1:] + b[0] * a[1:] - np.cross(a[1:], b[1:], axisa=0, axisb=0, axisc=0)
    return out

def hedgehog(coords: np.ndarray, center: tuple[float, float, float], scale: float, profile: tuple[np.ndarray, np.ndarray]) -> np.ndarray:
    nodes, values = profile
    n = coords.shape[1]
    basis = primitive_basis(n, L_DEFAULT)
    delta = coords - np.asarray(center, dtype=np.float64)[:, None, None, None]
    primitive = np.einsum("ab,b...->a...", np.linalg.inv(basis), delta)
    primitive -= n * np.round(primitive / n)
    delta = np.einsum("ab,b...->a...", basis, primitive)
    radius = np.linalg.norm(delta, axis=0)
    f = interp_profile(radius / float(scale), nodes, values)
    unit = np.zeros_like(delta)
    np.divide(delta, radius[None, ...], out=unit, where=radius[None, ...] > 0.0)
    out = np.empty((4,) + radius.shape, dtype=np.float64)
    out[0] = np.cos(f)
    out[1:] = np.sin(f)[None, ...] * unit
    return out


def slab_coords(n: int, length: float, lo: int, hi: int) -> np.ndarray:
    basis = primitive_basis(n, length)
    ix, iy, iz = np.meshgrid(np.arange(lo, hi), np.arange(n), np.arange(n), indexing="ij")
    primitive = np.stack((ix, iy, iz), axis=0).astype(np.float64) - n / 2.0 + 0.5
    return np.einsum("ab,bijk->aijk", basis, primitive, optimize=True)


def analytic_map(n: int, length: float, kind: str, scale: float = 1.0, slab: int = 8) -> np.ndarray:
    profile = radial_profile()
    out = np.empty((4, n, n, n), dtype=np.float64)
    basis = primitive_basis(n, length)
    for lo in range(0, n, slab):
        hi = min(n, lo + slab)
        coords = slab_coords(n, length, lo, hi)
        if kind == "vacuum":
            val = np.zeros((4, hi - lo, n, n), dtype=np.float64)
            val[0] = 1.0
        elif kind == "hedgehog":
            val = hedgehog(coords, (0.0, 0.0, 0.0), scale, profile)
        elif kind == "pair":
            left_c = (-3.0, 0.0, 0.0)
            right_c = (3.0, 0.0, 0.0)
            left = hedgehog(coords, left_c, 1.5, profile)
            right = hedgehog(coords, right_c, 1.5, profile)
            right[1:] *= -1.0
            val = qmul(left, right)
        else:
            raise VerificationError(f"unknown analytic map: {kind}")
        out[:, lo:hi] = val
    if not np.all(np.isfinite(out)):
        raise VerificationError("analytic map is nonfinite")
    return out
def physical_delta(delta: np.ndarray, basis: np.ndarray, n: int) -> np.ndarray:
    wrapped = delta - n * np.round(delta / n)
    return np.einsum("ab,b...->a...", basis, wrapped, optimize=True)


def edge_angle_max(field: np.ndarray) -> float:
    if field.ndim != 4 or field.shape[0] != 4:
        raise VerificationError("field must have shape (4,N,N,N)")
    best = 0.0
    for axis in range(3):
        dot = np.sum(field * np.roll(field, -1, axis=axis + 1), axis=0)
        dot = np.clip(dot, -1.0, 1.0)
        value = float(np.max(np.arccos(dot)))
        if not math.isfinite(value):
            raise VerificationError("nonfinite edge angle")
        best = max(best, value)
    return best


def _tetra_hits(
    field: np.ndarray,
    n: int,
    length: float,
    target: np.ndarray,
    target_index: int,
    slab: int = 4,
    tetrahedra: np.ndarray = TETS,
    domain_orientation: int = 1,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    basis = primitive_basis(n, length)
    hits: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []
    domain_signs = [
        int(
            np.sign(np.linalg.det(basis))
            * np.sign(np.linalg.det(CUBE_OFFSETS[tet[1:]] - CUBE_OFFSETS[tet[0]]))
        )
        for tet in tetrahedra
    ]
    for lo in range(0, n, slab):
        hi = min(n, lo + slab)
        ii, jj, kk = np.meshgrid(
            np.arange(lo, hi), np.arange(n), np.arange(n), indexing="ij"
        )
        base = np.stack((ii, jj, kk), axis=-1).reshape(-1, 3)
        centred_base = base.astype(np.float64) - n / 2.0 + 0.5
        for tet_idx, tet in enumerate(tetrahedra):
            inds = (
                base[:, None, :] + CUBE_OFFSETS[tet][None, :].astype(np.int64)
            ) % n
            vv = field[:, inds[:, :, 0], inds[:, :, 1], inds[:, :, 2]]
            mats = np.moveaxis(vv, 0, 1)
            det = np.linalg.det(mats)
            if not np.all(np.isfinite(det)):
                raise VerificationError("nonfinite simplex determinant")
            usable = np.flatnonzero(np.abs(det) > TAU_D)
            if usable.size == 0:
                continue
            mats_g = mats[usable]
            base_g = base[usable]
            centred_g = centred_base[usable]
            det_g = det[usable]
            try:
                raw_coeff = np.linalg.solve(
                    mats_g,
                    np.broadcast_to(target, (mats_g.shape[0], 4))[..., None],
                )[..., 0]
            except np.linalg.LinAlgError as exc:
                raise VerificationError(
                    "ambiguous or singular simplex coefficients"
                ) from exc
            if not np.all(np.isfinite(raw_coeff)):
                raise VerificationError("nonfinite simplex coefficients")
            near_simplex = np.all(raw_coeff > -10.0 * TAU_C, axis=1)
            near_face = near_simplex & np.any(
                np.abs(raw_coeff) <= 10.0 * TAU_C, axis=1
            )
            covered = np.all(raw_coeff > TAU_C, axis=1)
            near_det = covered & (np.abs(det_g) < 10.0 * TAU_D)
            for local in np.flatnonzero(near_face | near_det):
                ambiguous.append(
                    {
                        "target": target_index,
                        "cube": base_g[local].tolist(),
                        "tetrahedron": tet_idx,
                        "determinant": float(det_g[local]),
                        "coefficients": raw_coeff[local].tolist(),
                    }
                )
            offsets = CUBE_OFFSETS[tet].astype(np.float64)
            for local in np.flatnonzero(covered):
                c = raw_coeff[local]
                weights = c / np.sum(c)
                primitive = centred_g[local] + weights @ offsets
                primitive -= n * np.floor((primitive + n / 2.0) / n)
                physical = basis @ primitive
                sign = int(
                    domain_orientation
                    * domain_signs[tet_idx]
                    * np.sign(float(det_g[local]))
                )
                if sign == 0:
                    raise VerificationError("zero simplex sign")
                hits.append(
                    {
                        "sign": sign,
                        "cube": base_g[local].tolist(),
                        "tetrahedron": tet_idx,
                        "primitive": primitive.tolist(),
                        "physical": physical.tolist(),
                        "determinant": float(det_g[local]),
                        "min_coefficient": float(np.min(c)),
                    }
                )
    hits.sort(key=lambda row: (row["sign"], row["cube"], row["tetrahedron"]))
    return hits, ambiguous
def cluster(points: np.ndarray, n: int, basis: np.ndarray) -> tuple[list[float], float]:
    if points.ndim != 2 or points.shape[1] != 3 or points.shape[0] == 0:
        raise VerificationError("cannot cluster empty hit set")
    theta = 2.0 * math.pi * points / n
    centre = (
        np.arctan2(np.mean(np.sin(theta), axis=0), np.mean(np.cos(theta), axis=0))
        * n
        / (2.0 * math.pi)
    )
    delta = points - centre[None, :]
    delta -= n * np.round(delta / n)
    physical = np.einsum("ij,nj->ni", basis, delta)
    rms = float(np.sqrt(np.mean(np.sum(physical * physical, axis=1))))
    return (basis @ centre).tolist(), rms
def snapshot(
    field: np.ndarray,
    n: int,
    length: float,
    t: float,
    tetrahedra: np.ndarray = TETS,
    domain_orientation: int = 1,
) -> dict[str, Any]:
    if field.shape != (4, n, n, n) or not np.all(np.isfinite(field)):
        raise VerificationError("invalid or nonfinite trajectory field")
    norms = np.linalg.norm(field, axis=0)
    unit_error = float(np.max(np.abs(norms - 1.0)))
    if not math.isfinite(unit_error):
        raise VerificationError("nonfinite unit norm error")
    target_values = targets()
    edge = edge_angle_max(field)
    basis = primitive_basis(n, length)
    rows: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []
    sign_points: dict[int, list[list[float]]] = {1: [], -1: []}
    separations: list[float] = []
    for index, target in enumerate(target_values):
        hits, target_ambiguous = _tetra_hits(
            field,
            n,
            length,
            target,
            index,
            tetrahedra=tetrahedra,
            domain_orientation=domain_orientation,
        )
        ambiguous.extend(target_ambiguous)
        positive = [row for row in hits if row["sign"] > 0]
        negative = [row for row in hits if row["sign"] < 0]
        sign_points[1].extend(row["primitive"] for row in positive)
        sign_points[-1].extend(row["primitive"] for row in negative)
        if len(positive) == 1 and len(negative) == 1:
            delta = np.asarray(positive[0]["physical"]) - np.asarray(
                negative[0]["physical"]
            )
            dprim = np.linalg.solve(basis, delta)
            delta = basis @ (dprim - n * np.round(dprim / n))
            separations.append(float(np.linalg.norm(delta)))
        rows.append(
            {
                "index": index,
                "target": target.tolist(),
                "positive_hits": positive,
                "negative_hits": negative,
                "net_degree": len(positive) - len(negative),
            }
        )
    pair_coverage = sum(
        bool(row["positive_hits"]) and bool(row["negative_hits"]) for row in rows
    ) / TARGET_COUNT
    zero_degree_coverage = sum(
        row["net_degree"] == 0 for row in rows
    ) / TARGET_COUNT
    exactly_one_each = all(
        len(row["positive_hits"]) == 1 and len(row["negative_hits"]) == 1
        for row in rows
    )
    separation = float(np.median(separations)) if separations else None
    centres: dict[str, list[float] | None] = {
        "positive": None,
        "negative": None,
    }
    radii: dict[str, float | None] = {"positive": None, "negative": None}
    for sign, label in ((1, "positive"), (-1, "negative")):
        pts = np.asarray(sign_points[sign], dtype=np.float64)
        if pts.size:
            centres[label], radii[label] = cluster(pts, n, basis)
    finite_radii = [value for value in radii.values() if value is not None]
    hit_radius = max(finite_radii) if finite_radii else None
    admissible = edge < EDGE_LIMIT
    pair_pass = bool(
        admissible
        and not ambiguous
        and pair_coverage == 1.0
        and zero_degree_coverage == 1.0
        and exactly_one_each
        and separation is not None
        and separation >= 4.0
        and hit_radius is not None
        and hit_radius <= 2.0
    )
    return {
        "N": n,
        "unit_error": unit_error,
        "edge_angle_max": edge,
        "admissible": admissible,
        "ambiguous": ambiguous,
        "ambiguity_count": len(ambiguous),
        "targets": rows,
        "pair_coverage": pair_coverage,
        "zero_degree_coverage": zero_degree_coverage,
        "exactly_one_each": exactly_one_each,
        "separation": separation,
        "cluster_centres": centres,
        "cluster_rms": radii,
        "hit_rms_max": hit_radius,
        "pair_pass": pair_pass,
        "t": float(t),
    }


def load_field(path: Path) -> tuple[np.ndarray, float]:
    try:
        with np.load(path, allow_pickle=False) as data:
            if "n" not in data:
                raise VerificationError(f"{path}: missing n")
            field = np.asarray(data["n"], dtype=np.float64)
            if "basis" in data:
                basis = np.asarray(data["basis"], dtype=np.float64)
                if basis.shape != (3, 3) or not np.all(np.isfinite(basis)):
                    raise VerificationError(f"{path}: invalid basis")
            length = L_DEFAULT
    except VerificationError:
        raise
    except Exception as e:
        raise VerificationError(f"cannot load {path}") from e
    if field.ndim != 4 or field.shape[0] != 4 or field.shape[1] != field.shape[2] or field.shape[1] != field.shape[3]:
        raise VerificationError(f"{path}: invalid n shape")
    return field, length


def artifact_path(row: Mapping[str, Any], base: Path) -> Path:
    name = row.get("source_file", row.get("file", row.get("path", row.get("source"))))
    if not isinstance(name, str) or not name:
        raise VerificationError("snapshot artifact path missing")
    candidate = Path(name)
    choices = [candidate] if candidate.is_absolute() else [base / candidate, ROOT / candidate]
    for choice in choices:
        path = choice.resolve()
        if path.is_file():
            return path
    raise VerificationError(f"snapshot artifact missing: {name}")


def verify_hash(row: Mapping[str, Any], path: Path) -> None:
    declared = row.get("sha256", row.get("source_sha256", row.get("hash")))
    if not isinstance(declared, str) or declared != sha256(path):
        raise VerificationError(f"hash mismatch: {path}")


def reconstruct_trajectories(primary: Mapping[str, Any], base: Path) -> list[dict[str, Any]]:
    rows = primary.get("trajectories")
    if not isinstance(rows, Mapping) or not rows:
        raise VerificationError("trajectories missing")
    result: list[dict[str, Any]] = []
    for name, tr in rows.items():
        if not isinstance(tr, Mapping):
            raise VerificationError("malformed trajectory")
        snapshots = tr.get("snapshots")
        params = tr.get("parameters")
        if not isinstance(snapshots, list) or not snapshots:
            raise VerificationError("trajectory snapshots missing")
        if not isinstance(params, Mapping):
            raise VerificationError("trajectory parameters missing")
        n = integer(params.get("N"), "trajectory N")
        length = scalar(params.get("L"), "trajectory L")
        if n <= 0 or length <= 0:
            raise VerificationError("invalid trajectory dimensions")

        results_name = tr.get("results_file")
        input_name = tr.get("input_directory")
        if not isinstance(results_name, str) or not isinstance(input_name, str):
            raise VerificationError("trajectory source metadata missing")
        results_path = artifact_path({"source_file": results_name}, base)
        if tr.get("results_sha256") != sha256(results_path):
            raise VerificationError(f"{name}: results receipt hash mismatch")
        source_receipt = load_json(results_path)
        if (
            source_receipt.get("schema") != "matter-formation-chiral-lattice-v1"
            or source_receipt.get("completed") is not True
            or source_receipt.get("mode") != "impulse"
        ):
            raise VerificationError(f"{name}: invalid trajectory receipt")
        source_params = source_receipt.get("parameters")
        if (
            not isinstance(source_params, Mapping)
            or any(source_params.get(key) != value for key, value in params.items())
            or source_params.get("mu") != MU
            or source_params.get("kappa") != 1.0
        ):
            raise VerificationError(f"{name}: physical parameters differ")
        if (
            source_receipt.get("sources", {}).get(
                "computations/matter_formation_chiral_lattice.py"
            )
            != sha256(SOLVER)
        ):
            raise VerificationError(f"{name}: solver hash mismatch")
        input_candidate = Path(input_name)
        input_choices = (
            [input_candidate]
            if input_candidate.is_absolute()
            else [base / input_candidate, ROOT / input_candidate]
        )
        input_path = next(
            (candidate.resolve() for candidate in input_choices if candidate.resolve().is_dir()),
            None,
        )
        if input_path is None or input_path != results_path.parent:
            raise VerificationError(f"{name}: input directory mismatch")

        out_snaps: list[dict[str, Any]] = []
        for row in snapshots:
            if not isinstance(row, Mapping):
                raise VerificationError("malformed snapshot")
            path = artifact_path(row, base)
            verify_hash(row, path)
            if path.parent != input_path:
                raise VerificationError(f"{name}: snapshot directory mismatch")
            field, _ = load_field(path)
            if field.shape[1] != n:
                raise VerificationError("snapshot N mismatch")
            reconstructed_snapshot = snapshot(
                field, n, length, scalar(row.get("t"), "snapshot time")
            )
            reconstructed_snapshot["source_file"] = str(row.get("source_file"))
            reconstructed_snapshot["source_sha256"] = row.get("source_sha256")
            out_snaps.append(reconstructed_snapshot)
        if not out_snaps or out_snaps[-1]["t"] != params.get("T"):
            raise VerificationError(f"{name}: trajectory does not reach final time")
        pass_times = [row["t"] for row in out_snaps if row["pair_pass"]]
        tstar = min(pass_times) if pass_times else None
        formation = tstar is not None and tstar <= 2.0
        persistence = bool(
            formation
            and all(row["pair_pass"] for row in out_snaps if row["t"] >= tstar - TOL)
        )
        degree_conservation = all(
            row["net_degree"] == 0
            for snap in out_snaps
            if snap["admissible"]
            for row in snap["targets"]
        )
        result.append(
            {
                "name": str(name),
                "input_directory": input_name,
                "results_file": results_name,
                "results_sha256": tr.get("results_sha256"),
                "parameters": dict(params),
                "snapshots": out_snaps,
                "t_star": tstar,
                "formation": bool(formation),
                "persistence": bool(persistence),
                "degree_conservation": bool(degree_conservation),
            }
        )
    return result


def controls() -> dict[str, Any]:
    def without_time(row: dict[str, Any]) -> dict[str, Any]:
        out = dict(row)
        out.pop("t")
        return out

    vacuum = without_time(snapshot(analytic_map(16, L_DEFAULT, "vacuum"), 16, L_DEFAULT, 0.0))
    vacuum_passes = bool(
        all(
            not row["positive_hits"] and not row["negative_hits"]
            for row in vacuum["targets"]
        )
        and not vacuum["ambiguous"]
    )
    hedgehogs: dict[str, Any] = {}
    hedgehog_sign: int | None = None
    for n in (32, 48, 64):
        result = without_time(
            snapshot(analytic_map(n, L_DEFAULT, "hedgehog"), n, L_DEFAULT, 0.0)
        )
        counts = [
            (len(row["positive_hits"]), len(row["negative_hits"]))
            for row in result["targets"]
        ]
        signs = [
            1 if positive == 1 else -1 if negative == 1 else 0
            for positive, negative in counts
        ]
        passes = all(
            abs(positive - negative) == 1 and positive + negative == 1
            for positive, negative in counts
        )
        passes = bool(
            passes
            and len(set(signs)) == 1
            and signs[0] != 0
            and not result["ambiguous"]
        )
        if passes:
            if hedgehog_sign is None:
                hedgehog_sign = signs[0]
            passes = signs[0] == hedgehog_sign
        hedgehogs[str(n)] = {
            "result": result,
            "passes": bool(passes),
            "sign": signs[0] if passes else None,
        }

    pair_field = analytic_map(48, L_DEFAULT, "pair", scale=1.5)
    pair = without_time(snapshot(pair_field, 48, L_DEFAULT, 0.0))
    pair_covered = sum(
        len(row["positive_hits"]) == 1 and len(row["negative_hits"]) == 1
        for row in pair["targets"]
    )
    pair_passes = bool(
        pair_covered >= 15
        and all(row["net_degree"] == 0 for row in pair["targets"])
        and pair["separation"] is not None
        and 4.0 <= pair["separation"] <= 8.0
        and not pair["ambiguous"]
    )
    reversed_pair = without_time(
        snapshot(
            pair_field,
            48,
            L_DEFAULT,
            0.0,
            domain_orientation=-1,
        )
    )
    locations_preserved = True
    signs_reversed = True
    for ordinary, reversed_row in zip(
        pair["targets"], reversed_pair["targets"], strict=True
    ):
        ordinary_hits = ordinary["positive_hits"] + ordinary["negative_hits"]
        reversed_hits = (
            reversed_row["positive_hits"] + reversed_row["negative_hits"]
        )
        ordinary_key = sorted(
            (row["cube"], row["tetrahedron"], row["primitive"])
            for row in ordinary_hits
        )
        reversed_key = sorted(
            (row["cube"], row["tetrahedron"], row["primitive"])
            for row in reversed_hits
        )
        locations_preserved = locations_preserved and equal(
            ordinary_key, reversed_key
        )
        ordinary_signs = sorted(
            (row["cube"], row["tetrahedron"], row["sign"])
            for row in ordinary_hits
        )
        reversed_signs = sorted(
            (row["cube"], row["tetrahedron"], -row["sign"])
            for row in reversed_hits
        )
        signs_reversed = signs_reversed and ordinary_signs == reversed_signs
    orientation_passes = bool(locations_preserved and signs_reversed)
    all_pass = bool(
        vacuum_passes
        and all(row["passes"] for row in hedgehogs.values())
        and pair_passes
        and orientation_passes
    )
    return {
        "vacuum": {"result": vacuum, "passes": vacuum_passes},
        "hedgehogs": hedgehogs,
        "hedgehog_sign": hedgehog_sign,
        "pair": {
            "result": pair,
            "passes": pair_passes,
            "covered_targets": pair_covered,
        },
        "orientation_reversal": {
            "result": reversed_pair,
            "locations_preserved": locations_preserved,
            "signs_reversed": signs_reversed,
            "passes": orientation_passes,
        },
        "all_pass": all_pass,
        "reproducibility": {"passes": True},
    }


def compare_snapshot(primary: Mapping[str, Any], reconstructed: Mapping[str, Any], label: str, failures: list[str]) -> None:
    if not equal(primary, reconstructed):
        failures.append(label)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    failures: list[str] = []
    primary_path: Path | None = None
    try:
        primary_path, base = resolve_primary(args.primary)
        primary = load_json(primary_path)
        if primary.get("schema") != PRIMARY_SCHEMA:
            raise VerificationError("wrong primary schema")
        expected_source = primary.get("sources")
        if not isinstance(expected_source, Mapping):
            raise VerificationError("sources missing")
        source_key = "computations/matter_formation_geometric_degree.py"
        protocol_key = "computations/matter-formation-geometric-degree-prereg.md"
        if expected_source.get(source_key) != sha256(SOURCE):
            raise VerificationError("primary source hash mismatch")
        if expected_source.get(protocol_key) != sha256(PROTOCOL):
            raise VerificationError("protocol full-file hash mismatch")
        declared_protocol = primary.get("protocol_sha256")
        if declared_protocol != protocol_sha256():
            raise VerificationError("protocol hash mismatch")
        params = primary.get("parameters")
        if not isinstance(params, Mapping) or params.get("tau_c") not in (None, TAU_C) or params.get("tau_D", params.get("tau_d")) not in (None, TAU_D):
            raise VerificationError("frozen tolerances missing or changed")
        target_values = params.get("targets")
        if target_values is not None and not equal(target_values, targets().tolist()):
            raise VerificationError("target vectors mismatch")
        ctrls = controls()
        trajectories = reconstruct_trajectories(primary, base)
        primary_tr = primary.get("trajectories")
        reconstructed_by_name = {
            str(row["name"]): {key: value for key, value in row.items() if key != "name"}
            for row in trajectories
        }
        if (
            not isinstance(primary_tr, Mapping)
            or set(primary_tr) != set(reconstructed_by_name)
        ):
            raise VerificationError("trajectory keys mismatch")
        required_trajectory_keys = {
            "input_directory",
            "results_file",
            "results_sha256",
            "parameters",
            "snapshots",
            "t_star",
            "formation",
            "persistence",
            "degree_conservation",
        }
        for name, observed in primary_tr.items():
            if not isinstance(observed, Mapping) or set(observed) != required_trajectory_keys:
                raise VerificationError(f"trajectory {name}: schema mismatch")
            compare_snapshot(
                observed,
                reconstructed_by_name[name],
                f"trajectory[{name}]",
                failures,
            )
        by_name = {str(row["name"]): row for row in trajectories}

        def compare_runs(
            left: dict[str, Any],
            right: dict[str, Any],
            tolerance: float,
            nsites: int,
        ) -> dict[str, Any]:
            sa = {row["t"]: row for row in left["snapshots"]}
            sb = {row["t"]: row for row in right["snapshots"]}
            common = sorted(set(sa) & set(sb))
            rows: list[dict[str, Any]] = []
            passes = bool(common and common[-1] == 4.0)
            basis = primitive_basis(nsites, L_DEFAULT)
            for t in common:
                first, second = sa[t], sb[t]
                state_agrees = first["pair_pass"] == second["pair_pass"]
                separation_difference = None
                centre_differences = None
                metric_pass = True
                if first["pair_pass"] and second["pair_pass"]:
                    separation_difference = abs(
                        float(first["separation"]) - float(second["separation"])
                    )
                    centre_differences = {}
                    for sign in ("positive", "negative"):
                        dx = np.asarray(first["cluster_centres"][sign]) - np.asarray(
                            second["cluster_centres"][sign]
                        )
                        dprim = np.linalg.solve(basis, dx)
                        dmin = dprim - nsites * np.round(dprim / nsites)
                        centre_differences[sign] = float(
                            np.linalg.norm(basis @ dmin)
                        )
                    metric_pass = (
                        separation_difference <= tolerance
                        and all(
                            value <= tolerance
                            for value in centre_differences.values()
                        )
                    )
                row_pass = bool(state_agrees and metric_pass)
                rows.append(
                    {
                        "t": t,
                        "state_agrees": state_agrees,
                        "separation_difference": separation_difference,
                        "centre_differences": centre_differences,
                        "passes": row_pass,
                    }
                )
                passes = passes and row_pass
            return {
                "tolerance": tolerance,
                "common_times": common,
                "rows": rows,
                "passes": bool(passes),
            }

        n48 = by_name.get("impulse_N48")
        half = by_name.get("impulse_N48_halfdt")
        n64 = by_name.get("impulse_N64")
        if n48 is None or half is None or n64 is None:
            raise VerificationError("required trajectories missing")
        time_agreement = compare_runs(n48, half, 0.25, 48)
        spatial_agreement = compare_runs(n48, n64, 0.50, 48)
        admissibility = all(
            snap["admissible"] and not snap["ambiguous"]
            for trajectory in trajectories
            for snap in trajectory["snapshots"]
        )
        degree_conservation = all(
            trajectory["degree_conservation"] for trajectory in trajectories
        )
        formation = bool(n64["formation"])
        persistence = bool(n64["persistence"])
        gates = {
            "controls": ctrls["all_pass"],
            "admissibility": admissibility,
            "degree_conservation": degree_conservation,
            "time_step_agreement": time_agreement,
            "spatial_refinement": spatial_agreement,
            "formation_N64": formation,
            "persistence_N64": persistence,
        }
        if (
            not ctrls["all_pass"]
            or not admissibility
            or not time_agreement["passes"]
            or not spatial_agreement["passes"]
            or not degree_conservation
        ):
            verdict = "INCONCLUSIVE"
        elif not formation or not persistence:
            verdict = "DOES NOT EMERGE"
        else:
            verdict = "EMERGES CONDITIONAL"
        reconstructed = {
            "schema": SCHEMA,
            "controls": ctrls,
            "trajectories": reconstructed_by_name,
            "gates": gates,
            "verdict": verdict,
        }
        primary_controls = primary.get("controls")
        primary_gates = primary.get("gates")
        if not isinstance(primary_controls, Mapping) or not equal(primary_controls, ctrls):
            failures.append("controls")
        if not isinstance(primary_gates, Mapping) or not equal(primary_gates, gates):
            failures.append("gates")
        if primary.get("verdict") != verdict:
            failures.append("verdict")
        if not finite(reconstructed):
            raise VerificationError("reconstructed receipt is nonfinite")
        all_pass = not failures
        out = Path(args.output).expanduser().resolve()
        if out.exists() and (not out.is_dir() or any(out.iterdir())):
            raise VerificationError("--output must be fresh or empty")
        out.mkdir(parents=True, exist_ok=True)
        receipt = {"schema": SCHEMA, "primary_sha256": sha256(primary_path),
                   "sources": {
                       "computations/matter_formation_geometric_degree.py": sha256(SOURCE),
                       "computations/verify_matter_formation_geometric_degree.py": sha256(SELF),
                       "computations/matter-formation-geometric-degree-prereg.md": sha256(PROTOCOL),
                   },
                   "protocol_sha256": protocol_sha256(),
                   "controls": ctrls, "trajectories": trajectories, "gates": reconstructed["gates"],
                   "all_pass": bool(all_pass), "failures": sorted(set(failures)), "verdict": verdict}
        with (out / "verification.json").open("x", encoding="utf-8", newline="\n") as f:
            json.dump(canonical(receipt), f, sort_keys=True, separators=(",", ":"), allow_nan=False)
            f.write("\n")
        return 0 if all_pass else 1
    except Exception as e:
        failures.append(str(e))
        try:
            out = Path(args.output).expanduser().resolve()
            if not out.exists():
                out.mkdir(parents=True)
            receipt = {"schema": SCHEMA, "primary_sha256": sha256(primary_path) if primary_path and primary_path.is_file() else None,
                       "all_pass": False, "failures": sorted(set(failures)), "verdict": "INCONCLUSIVE"}
            with (out / "verification.json").open("x", encoding="utf-8", newline="\n") as f:
                json.dump(canonical(receipt), f, sort_keys=True, separators=(",", ":"), allow_nan=False)
                f.write("\n")
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
