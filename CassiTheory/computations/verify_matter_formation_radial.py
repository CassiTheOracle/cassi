#!/usr/bin/env python3
"""Independent verifier for the preregistered continuum matter-formation campaign.

This module deliberately does not import or execute the primary radial driver.  It
reconstructs the finite-volume action from the preregistration and solves the
continuum equations with scipy's collocation BVP solver.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from scipy.integrate import quad
from scipy.integrate import cumulative_trapezoid
from scipy.integrate import solve_bvp

ROOT = Path(__file__).resolve().parents[1]
PREREG_PATH = ROOT / "computations" / "matter-formation-continuum-prereg.md"
PRIMARY_PATH = ROOT / "computations" / "matter_formation_radial.py"
DEFAULT_INPUT_DIR = ROOT / "runs" / "20260906_matter_formation_radial"

COEFFICIENTS = {
    "u_rho": 4.0,
    "u_phi": 4.0,
    "u_H": 4.0,
    "gamma_x": 1.0,
    "k_Cx": 1.0,
    "u_C": 1.0,
    "e_C": 0.75,
    "h_C": 2.9598260763447164,
}
TARGETS = (4.0, 16.0, 64.0, 256.0)
R12 = (192, 384, 768)
REQUIRED_NPZ = ("r", "volumes", "f", "c", "R", "q")
REQUIRED_DIAGNOSTICS = (
    "energy",
    "charge",
    "omega",
    "carrier_radius",
    "outer_fraction",
    "residual_f",
    "residual_c",
    "qualified",
    "bound",
)
SEEDS = {"w1", "w2", "w4", "diffuse", "refine"}
SCHEMA_PREFIX = "matter-formation-radial"
NUM_TOL = 2.0e-8
FV_GEOMETRY_TOL = 2.0e-10
QUAL_RESIDUAL_TOL = 1.0e-4
QUAL_CHARGE_TOL = 1.0e-10
BINDING_MARGIN = 1.0e-3
OUTER_TOL = 1.0e-3
COMPARE_ENERGY_TOL = 5.0e-3
COMPARE_RADIUS_TOL = 5.0e-3
COMPARE_OMEGA_TOL = 1.0e-3
BVP_TOL = 1.0e-7
BVP_MAX_NODES = 20_000


def json_safe(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_safe(v) for v in value]
    return value


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(json_safe(dict(payload)), indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def mismatch(rows: list[dict[str, Any]], path: str, expected: Any, actual: Any, reason: str) -> None:
    rows.append({"path": path, "expected": json_safe(expected), "actual": json_safe(actual), "reason": reason})


def canonical_sha256(path: Path) -> str:
    """Hash source text after the preregistered CRLF-to-LF normalization."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        data = handle.read()
    digest.update(data.replace(b"\r\n", b"\n"))
    return digest.hexdigest()


def byte_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float, np.number)) and not isinstance(value, bool) and math.isfinite(float(value))


def close(actual: Any, expected: float, tol: float = NUM_TOL) -> bool:
    return finite_number(actual) and abs(float(actual) - expected) <= tol * max(1.0, abs(expected))


def relative_difference(a: float, b: float) -> float:
    return abs(float(a) - float(b)) / max(abs(float(a)), abs(float(b)), 1.0e-300)


def safe_artifact_path(artifact: Any) -> Path | None:
    if not isinstance(artifact, str) or not artifact or Path(artifact).is_absolute():
        return None
    candidate = (ROOT / Path(artifact)).resolve()
    try:
        candidate.relative_to(ROOT.resolve())
    except ValueError:
        return None
    return candidate


def expected_grid(R: float, n: int) -> tuple[np.ndarray, np.ndarray]:
    dr = R / n
    faces = np.arange(n + 1, dtype=np.float64) * dr
    centers = (np.arange(n, dtype=np.float64) + 0.5) * dr
    volumes = (4.0 * math.pi / 3.0) * (faces[1:] ** 3 - faces[:-1] ** 3)
    return centers, volumes


def finite_volume(
    r: np.ndarray,
    volumes: np.ndarray,
    f: np.ndarray,
    c: np.ndarray,
    R: float,
    q_target: float,
) -> dict[str, float | bool]:
    n = len(r)
    dr = R / n
    conductance = 4.0 * math.pi * (np.arange(1, n, dtype=np.float64) * dr) ** 2 / dr
    outer_conductance = 8.0 * math.pi * R * R / dr
    ef = 0.5 * float(np.sum(conductance * np.diff(f) ** 2))
    ec = 0.5 * float(np.sum(conductance * np.diff(c) ** 2))
    ef += 0.5 * outer_conductance * float((1.0 - f[-1]) ** 2)
    ec += 0.5 * outer_conductance * float(c[-1] ** 2)
    potential_density = (
        COEFFICIENTS["u_rho"] / 4.0 * (f * f - 1.0) ** 2
        + (COEFFICIENTS["e_C"] - COEFFICIENTS["h_C"] * (1.0 - f * f)) * c * c
        + COEFFICIENTS["u_C"] / 2.0 * c**4
    )
    energy = ef + ec + float(np.dot(volumes, potential_density))
    charge = float(np.dot(volumes, c * c))
    radius = math.sqrt(max(0.0, float(np.dot(volumes, r * r * c * c)) / charge)) if charge > 0 else math.inf
    outer = float(np.dot(volumes[r > R / 2.0], c[r > R / 2.0] ** 2) / charge) if charge > 0 else math.inf

    grad_f = np.zeros(n, dtype=np.float64)
    grad_c = np.zeros(n, dtype=np.float64)
    if n > 1:
        flux_f = conductance * np.diff(f)
        flux_c = conductance * np.diff(c)
        grad_f[:-1] -= flux_f
        grad_f[1:] += flux_f
        grad_c[:-1] -= flux_c
        grad_c[1:] += flux_c
    grad_f[-1] += outer_conductance * (f[-1] - 1.0)
    grad_c[-1] += outer_conductance * c[-1]
    grad_f += volumes * (COEFFICIENTS["u_rho"] * (f * f - 1.0) * f + 2.0 * COEFFICIENTS["h_C"] * c * c * f)
    grad_c += volumes * (
        2.0 * (COEFFICIENTS["e_C"] - COEFFICIENTS["h_C"] * (1.0 - f * f)) * c
        + 2.0 * COEFFICIENTS["u_C"] * c**3
    )
    omega = float(np.dot(c, grad_c) / (2.0 * charge)) if charge > 0 else math.nan
    residual_f = grad_f / volumes
    residual_c = grad_c / (2.0 * volumes) - omega * c
    f_scale = math.sqrt(float(np.dot(volumes, (1.0 - f) ** 2)))
    rf_norm = math.sqrt(float(np.dot(volumes, residual_f**2))) / max(1.0, f_scale)
    rc_norm = math.sqrt(float(np.dot(volumes, residual_c**2))) / math.sqrt(charge) if charge > 0 else math.inf
    charge_relative_error = abs(charge - q_target) / max(abs(q_target), 1.0)
    values = (energy, charge, omega, radius, outer, rf_norm, rc_norm, charge_relative_error)
    finite_and_charge = all(math.isfinite(value) for value in values) and charge_relative_error < QUAL_CHARGE_TOL
    stationary = finite_and_charge and rf_norm < QUAL_RESIDUAL_TOL and rc_norm < QUAL_RESIDUAL_TOL
    return {
        "energy": energy,
        "charge": charge,
        "charge_relative_error": charge_relative_error,
        "omega": omega,
        "carrier_radius": radius,
        "outer_fraction": outer,
        "residual_f": rf_norm,
        "residual_c": rc_norm,
        "qualified": bool(stationary),
        "bound": bool(
            stationary
            and energy < COEFFICIENTS["e_C"] * q_target - BINDING_MARGIN
            and omega < COEFFICIENTS["e_C"] - BINDING_MARGIN
            and outer < OUTER_TOL
        ),
    }


def _validate_npz(
    path: Path, row: Mapping[str, Any], failures: list[dict[str, Any]], label: str
) -> tuple[dict[str, np.ndarray], dict[str, float | bool]] | None:
    try:
        with np.load(path, allow_pickle=False) as loaded:
            missing = [key for key in REQUIRED_NPZ if key not in loaded]
            if missing:
                mismatch(failures, f"{label}.npz.keys", "required keys", missing, "schema")
                return None
            arrays = {key: np.asarray(loaded[key]) for key in REQUIRED_NPZ}
    except Exception as exc:  # infrastructure/corrupt artifact
        mismatch(failures, f"{label}.artifact", "readable NPZ", repr(exc), "infrastructure")
        return None
    n = row["n"]
    for key in ("r", "volumes", "f", "c"):
        if arrays[key].ndim != 1 or len(arrays[key]) != n or not np.issubdtype(arrays[key].dtype, np.number):
            mismatch(failures, f"{label}.npz.{key}", f"finite length-{n} numeric vector", arrays[key].shape, "schema")
            return None
        if not np.all(np.isfinite(arrays[key])):
            mismatch(failures, f"{label}.npz.{key}", "all finite", "nonfinite", "numeric")
            return None
    if arrays["R"].ndim != 0 or arrays["q"].ndim != 0 or not np.isfinite(arrays["R"]) or not np.isfinite(arrays["q"]):
        mismatch(failures, f"{label}.npz.scalars", "finite scalar R,q", "invalid", "schema")
        return None
    R = float(arrays["R"])
    q = float(arrays["q"])
    if not close(R, float(row["R"])) or not close(q, float(row["q"])):
        mismatch(
            failures,
            f"{label}.npz.identity",
            {"R": row["R"], "q": row["q"]},
            {"R": R, "q": q},
            "identity",
        )
    if np.any(arrays["c"] < -1.0e-12):
        mismatch(failures, f"{label}.npz.c", "nonnegative carrier representative", "negative values", "physical schema")
        return None
    if np.any(arrays["f"] < -1.0e-10) or np.any(arrays["f"] > 1.0 + 1.0e-10):
        mismatch(failures, f"{label}.npz.f", "0 <= f <= 1 clipping representative", "out of range", "physical schema")
        return None
    expected_r, expected_v = expected_grid(float(row["R"]), n)
    if not np.allclose(arrays["r"], expected_r, rtol=FV_GEOMETRY_TOL, atol=FV_GEOMETRY_TOL):
        mismatch(failures, f"{label}.r", "cell-centred R/n grid", "different", "geometry")
    if not np.allclose(arrays["volumes"], expected_v, rtol=FV_GEOMETRY_TOL, atol=FV_GEOMETRY_TOL):
        mismatch(failures, f"{label}.volumes", "spherical cell volumes", "different", "geometry")
    if np.any(np.diff(arrays["r"]) <= 0) or np.any(arrays["volumes"] <= 0):
        mismatch(failures, f"{label}.grid", "increasing r and positive volumes", "invalid", "geometry")
    diagnostics = finite_volume(
        arrays["r"], arrays["volumes"], arrays["f"], arrays["c"], float(row["R"]), float(row["q"])
    )
    return arrays, diagnostics
def _validate_row(
    row: Any, index: int, input_dir: Path, failures: list[dict[str, Any]]
) -> tuple[str, dict[str, Any], dict[str, np.ndarray], dict[str, float | bool]] | None:
    label = f"arms[{index}]"
    if not isinstance(row, dict):
        mismatch(failures, label, "object", row, "schema")
        return None
    needed = ("id", "q", "R", "n", "seed", "artifact", "artifact_sha256", "diagnostics")
    missing = [key for key in needed if key not in row]
    if missing:
        mismatch(failures, label, needed, missing, "schema")
        return None
    if not finite_number(row["q"]) or float(row["q"]) not in TARGETS or not finite_number(row["R"]):
        mismatch(failures, f"{label}.identity", "registered finite q and R", row, "identity")
        return None
    if not isinstance(row["n"], int) or isinstance(row["n"], bool) or row["n"] <= 0:
        mismatch(failures, f"{label}.n", "positive integer", row["n"], "schema")
        return None
    if row["seed"] not in SEEDS or not isinstance(row["id"], str):
        mismatch(failures, f"{label}.id", "registered seed and string id", row.get("id"), "identity")
        return None
    expected_id = f"q{row['q']:g}_R{row['R']:g}_n{row['n']}_{row['seed']}"
    if row["id"] != expected_id:
        mismatch(failures, f"{label}.id", expected_id, row["id"], "identity")
    if row["R"] not in (12, 24):
        mismatch(failures, f"{label}.R", "12 or 24", row["R"], "identity")
    if row["R"] == 12 and row["n"] not in R12 or row["R"] == 24 and row["n"] != 768:
        mismatch(failures, f"{label}.grid", "registered (R,n) grid", {"R": row["R"], "n": row["n"]}, "identity")
    if row["seed"] == "refine" and row["n"] == 192:
        mismatch(failures, f"{label}.seed", "coarse basin seed for n=192", row["seed"], "identity")
    if row["seed"] != "refine" and row["n"] != 192:
        mismatch(failures, f"{label}.seed", "refine seed for refined grid", row["seed"], "identity")
    artifact = safe_artifact_path(row["artifact"])
    if artifact is None:
        mismatch(failures, f"{label}.artifact", "repo-relative path", row["artifact"], "schema")
        return None
    if not artifact.exists():
        mismatch(failures, f"{label}.artifact", "existing NPZ", str(artifact), "infrastructure")
        return None
    if not isinstance(row["artifact_sha256"], str) or byte_sha256(artifact) != row["artifact_sha256"]:
        mismatch(failures, f"{label}.artifact_sha256", byte_sha256(artifact), row["artifact_sha256"], "hash")
        return None
    loaded = _validate_npz(artifact, row, failures, label)
    if loaded is None:
        return None
    arrays, diagnostics = loaded
    reported = row.get("diagnostics")
    if not isinstance(reported, dict):
        mismatch(failures, f"{label}.diagnostics", "object", reported, "schema")
    else:
        for key in REQUIRED_DIAGNOSTICS:
            if key not in reported:
                mismatch(failures, f"{label}.diagnostics.{key}", "present", "missing", "schema")
            elif key in ("qualified", "bound"):
                if reported[key] is not diagnostics[key]:
                    mismatch(failures, f"{label}.diagnostics.{key}", diagnostics[key], reported[key], "recompute")
            elif not close(reported[key], float(diagnostics[key])):
                mismatch(failures, f"{label}.diagnostics.{key}", diagnostics[key], reported[key], "recompute")
    result = dict(row)
    result["artifact_path"] = artifact
    result["diagnostics"] = diagnostics
    return row["id"], result, arrays, diagnostics


def _interpolate_initial(arrays: Mapping[str, np.ndarray], R: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    r = arrays["r"]
    f = arrays["f"]
    c = arrays["c"]
    x = np.linspace(0.0, R, min(max(256, len(r) * 2), 4097), dtype=np.float64)
    xp = np.concatenate(([0.0], r, [R]))
    fp = np.concatenate(([f[0]], f, [1.0]))
    cp = np.concatenate(([c[0]], c, [0.0]))
    fi = np.interp(x, xp, fp)
    ci = np.interp(x, xp, cp)
    p = np.gradient(fi, x, edge_order=2)
    v = np.gradient(ci, x, edge_order=2)
    p[0] = 0.0
    v[0] = 0.0
    s = cumulative_trapezoid(4.0 * math.pi * x * x * ci * ci, x, initial=0.0)
    return x, np.vstack((fi, p, ci, v, s)), np.array([0.0], dtype=np.float64)


def solve_continuum(arrays: Mapping[str, np.ndarray], R: float, q: float) -> dict[str, Any]:
    x, y0, omega0 = _interpolate_initial(arrays, R)
    # solve_bvp removes S*y/(x-a) from fun and applies it consistently at the
    # singular endpoint.  The two -2 entries encode the radial Laplacian.
    singular = np.zeros((5, 5), dtype=np.float64)
    singular[1, 1] = -2.0
    singular[3, 3] = -2.0
    omega0[0] = float(
        finite_volume(arrays["r"], arrays["volumes"], arrays["f"], arrays["c"], R, q)["omega"]
    )

    def fun(xv: np.ndarray, y: np.ndarray, parameters: np.ndarray) -> np.ndarray:
        omega = parameters[0]
        f, _p, c, _v, _s = y
        out = np.empty_like(y)
        out[0] = y[1]
        out[1] = COEFFICIENTS["u_rho"] * (f * f - 1.0) * f + 2.0 * COEFFICIENTS["h_C"] * c * c * f
        out[2] = y[3]
        out[3] = 2.0 * (COEFFICIENTS["e_C"] - COEFFICIENTS["h_C"] * (1.0 - f * f) + COEFFICIENTS["u_C"] * c * c - omega) * c
        out[4] = 4.0 * math.pi * xv * xv * c * c
        return out

    def bc(ya: np.ndarray, yb: np.ndarray, parameters: np.ndarray) -> np.ndarray:
        return np.array((ya[1], ya[3], ya[4], yb[0] - 1.0, yb[2], yb[4] - q), dtype=np.float64)

    try:
        solution = solve_bvp(
            fun,
            bc,
            x,
            y0,
            p=omega0,
            S=singular,
            tol=BVP_TOL,
            max_nodes=BVP_MAX_NODES,
            verbose=0,
        )
    except Exception as exc:
        return {"status": "exception", "success": False, "message": repr(exc), "nodes": 0}
    result: dict[str, Any] = {
        "status": int(solution.status),
        "success": bool(solution.success),
        "message": str(solution.message),
        "nodes": int(solution.x.size),
        "iterations": int(solution.niter),
    }
    if not solution.success:
        return result
    try:
        f, p, c, v, s = solution.sol(solution.x)
        charge = float(4.0 * math.pi * quad(lambda z: z * z * float(solution.sol(z)[2]) ** 2, 0.0, R, epsabs=1e-10, epsrel=1e-10, limit=1000)[0])
        radius_num = float(4.0 * math.pi * quad(lambda z: z**4 * float(solution.sol(z)[2]) ** 2, 0.0, R, epsabs=1e-10, epsrel=1e-10, limit=1000)[0])
        radius = math.sqrt(radius_num / charge)
        outer_num = float(4.0 * math.pi * quad(lambda z: z * z * float(solution.sol(z)[2]) ** 2, R / 2.0, R, epsabs=1e-10, epsrel=1e-10, limit=1000)[0])
        def energy_integrand(z: float) -> float:
            fv, pv, cv, vv, _sv = solution.sol(z)
            density = (
                0.5 * (pv * pv + vv * vv)
                + COEFFICIENTS["u_rho"] / 4.0 * (fv * fv - 1.0) ** 2
                + (COEFFICIENTS["e_C"] - COEFFICIENTS["h_C"] * (1.0 - fv * fv)) * cv * cv
                + COEFFICIENTS["u_C"] / 2.0 * cv**4
            )
            return 4.0 * math.pi * z * z * float(density)
        energy = float(quad(energy_integrand, 0.0, R, epsabs=1e-10, epsrel=1e-10, limit=1000)[0])
        result.update({
            "energy": energy,
            "charge": charge,
            "omega": float(solution.p[0]),
            "carrier_radius": radius,
            "outer_fraction": outer_num / charge,
            "boundary_residual": float(np.max(np.abs(bc(solution.y[:, 0], solution.y[:, -1], solution.p)))),
        })
        result["field"] = solution
        result["finite"] = all(math.isfinite(float(result[key])) for key in ("energy", "charge", "omega", "carrier_radius", "outer_fraction"))
    except Exception as exc:
        result.update({"success": False, "status": "quadrature_exception", "message": repr(exc)})
    return result


def _save_collocation(path: Path, result: Mapping[str, Any], R: float, q: float) -> str:
    solution = result["field"]
    x = np.asarray(solution.x, dtype=np.float64)
    y = np.asarray(solution.y, dtype=np.float64)
    np.savez_compressed(path, x=x, f=y[0], p=y[1], c=y[2], v=y[3], running_charge=y[4], R=R, q=q, omega=float(solution.p[0]))
    return byte_sha256(path)


def _campaign_decisions(arms: Mapping[str, Mapping[str, Any]], failures: list[dict[str, Any]]) -> dict[str, Any]:
    decisions: dict[str, Any] = {}
    for q in TARGETS:
        qkey = f"{q:g}"
        rows = [row for row in arms.values() if float(row["q"]) == q]
        coarse = [
            row
            for row in rows
            if float(row["R"]) == 12.0
            and int(row["n"]) == 192
            and row["seed"] in {"w1", "w2", "w4", "diffuse"}
        ]
        eligible = [row for row in coarse if row["diagnostics"]["qualified"]]
        selected = min(eligible, key=lambda row: float(row["diagnostics"]["energy"])) if eligible else None
        finest = next(
            (row for row in rows if float(row["R"]) == 12.0 and int(row["n"]) == 768 and row["seed"] == "refine"),
            None,
        )
        adjacent = next(
            (row for row in rows if float(row["R"]) == 12.0 and int(row["n"]) == 384 and row["seed"] == "refine"),
            None,
        )
        domain = next(
            (row for row in rows if float(row["R"]) == 24.0 and int(row["n"]) == 768 and row["seed"] == "refine"),
            None,
        )
        comparisons: dict[str, Any] = {}
        if selected is not None and finest is not None and finest["diagnostics"]["qualified"]:
            if adjacent is None or not adjacent["diagnostics"]["qualified"]:
                comparisons["adjacent"] = {"available": False, "pass": False}
            else:
                p, o = finest["diagnostics"], adjacent["diagnostics"]
                metrics = {
                    "energy_relative": relative_difference(p["energy"], o["energy"]),
                    "radius_relative": relative_difference(p["carrier_radius"], o["carrier_radius"]),
                    "omega_absolute": abs(float(p["omega"]) - float(o["omega"])),
                }
                comparisons["adjacent"] = {
                    "available": True,
                    "pass": bool(
                        metrics["energy_relative"] < COMPARE_ENERGY_TOL
                        and metrics["radius_relative"] < COMPARE_RADIUS_TOL
                        and metrics["omega_absolute"] < COMPARE_OMEGA_TOL
                    ),
                    "baseline": finest["id"],
                    "metrics": metrics,
                }
            # The larger-domain control has the same spacing as R12/n384;
            # compare those physical endpoints, not different resolutions.
            if adjacent is None or not adjacent["diagnostics"]["qualified"] or domain is None or not domain["diagnostics"]["qualified"]:
                comparisons["domain"] = {"available": False, "pass": False}
            else:
                p, o = adjacent["diagnostics"], domain["diagnostics"]
                metrics = {
                    "energy_relative": relative_difference(p["energy"], o["energy"]),
                    "radius_relative": relative_difference(p["carrier_radius"], o["carrier_radius"]),
                    "omega_absolute": abs(float(p["omega"]) - float(o["omega"])),
                }
                comparisons["domain"] = {
                    "available": True,
                    "pass": bool(
                        metrics["energy_relative"] < COMPARE_ENERGY_TOL
                        and metrics["radius_relative"] < COMPARE_RADIUS_TOL
                        and metrics["omega_absolute"] < COMPARE_OMEGA_TOL
                    ),
                    "baseline": adjacent["id"],
                    "metrics": metrics,
                }
        bound = bool(
            selected is not None
            and finest is not None
            and finest["diagnostics"]["qualified"]
            and finest["diagnostics"]["bound"]
        )
        resolved = bool(
            selected is not None
            and finest is not None
            and finest["diagnostics"]["qualified"]
            and comparisons.get("adjacent", {}).get("pass")
            and comparisons.get("domain", {}).get("pass")
        )
        continuation_qualified = bool(
            selected is not None
            and finest is not None
            and adjacent is not None
            and domain is not None
            and finest["diagnostics"]["qualified"]
            and adjacent["diagnostics"]["qualified"]
            and domain["diagnostics"]["qualified"]
        )
        decisions[qkey] = {
            "coarse_candidates": [row["id"] for row in coarse],
            "coarse_qualified": [row["id"] for row in eligible],
            "selected_for_refinement": selected["id"] if selected else None,
            "finest": finest["id"] if finest else None,
            "adjacent": adjacent["id"] if adjacent else None,
            "domain_control": domain["id"] if domain else None,
            "comparisons": comparisons,
            "qualified": continuation_qualified,
            "bound": bound,
            "resolved": resolved,
            "verdict": "EMERGES" if bound and resolved else (
                "DOES NOT EMERGE"
                if continuation_qualified and not bound
                else "INCONCLUSIVE"
            ),
        }
    return decisions


def _verdict_category(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.upper()
    if "INCONCLUSIVE" in text:
        return "INCONCLUSIVE"
    if "DOES NOT EMERGE" in text:
        return "DOES NOT EMERGE"
    if "EMERGES" in text:
        return "EMERGES"
    return None


def _find_charge_verdict(value: Any, qkey: str) -> str | None:
    if not isinstance(value, dict):
        return None
    for key in (qkey, f"q{qkey}", f"charge_{qkey}", f"Q{qkey}"):
        if key not in value:
            continue
        category = _verdict_category(value[key])
        if category is not None:
            return category
        nested_value = value[key]
        if isinstance(nested_value, dict):
            for field in ("verdict", "classification", "status"):
                category = _verdict_category(nested_value.get(field))
                if category is not None:
                    return category
        nested = _find_charge_verdict(nested_value, qkey)
        if nested is not None:
            return nested
    for key in ("charges", "charge_results", "by_charge"):
        nested = value.get(key)
        if isinstance(nested, dict):
            found = _find_charge_verdict(nested, qkey)
            if found is not None:
                return found
    return None


def verify(input_dir: Path, output_dir: Path) -> tuple[dict[str, Any], int]:
    failures: list[dict[str, Any]] = []
    results_path = input_dir / "results.json"
    report: dict[str, Any] = {"schema": "matter-formation-radial-verification-v1", "input_dir": str(input_dir), "failures": failures}
    if not results_path.exists():
        mismatch(failures, "results.json", "existing primary receipt", str(results_path), "infrastructure")
        write_json(output_dir / "verification.json", report)
        return report, 1
    try:
        source = json.loads(results_path.read_text(encoding="utf-8"))
    except Exception as exc:
        mismatch(failures, "results.json", "valid JSON object", repr(exc), "infrastructure")
        write_json(output_dir / "verification.json", report)
        return report, 1
    if not isinstance(source, dict):
        mismatch(failures, "results", "object", source, "schema")
        write_json(output_dir / "verification.json", report)
        return report, 1
    if not isinstance(source.get("schema"), str) or not source["schema"].startswith(SCHEMA_PREFIX):
        mismatch(failures, "schema", f"string starting {SCHEMA_PREFIX}", source.get("schema"), "schema")
    if not PREREG_PATH.exists() or not PRIMARY_PATH.exists():
        mismatch(failures, "source", "prereg and primary source files", "missing", "infrastructure")
    else:
        expected_prereg = canonical_sha256(PREREG_PATH)
        expected_source = canonical_sha256(PRIMARY_PATH)
        if source.get("prereg_sha256") != expected_prereg:
            mismatch(failures, "prereg_sha256", expected_prereg, source.get("prereg_sha256"), "hash")
        if source.get("source_sha256") != expected_source:
            mismatch(failures, "source_sha256", expected_source, source.get("source_sha256"), "hash")
    coefficients = source.get("coefficients")
    if not isinstance(coefficients, dict):
        mismatch(failures, "coefficients", "object", coefficients, "schema")
    else:
        for key, expected in COEFFICIENTS.items():
            if not close(coefficients.get(key), expected):
                mismatch(failures, f"coefficients.{key}", expected, coefficients.get(key), "frozen coefficient")
    if not isinstance(source.get("verdicts"), dict):
        mismatch(failures, "verdicts", "object", source.get("verdicts"), "schema")
    rows = source.get("arms")
    if not isinstance(rows, list):
        mismatch(failures, "arms", "list", rows, "schema")
        rows = []
    arms: dict[str, dict[str, Any]] = {}
    array_cache: dict[str, np.ndarray] = {}
    for index, row in enumerate(rows):
        validated = _validate_row(row, index, input_dir, failures)
        if validated is None:
            continue
        key, normalized, arrays, _diagnostics = validated
        if key in arms:
            mismatch(failures, f"arms[{index}].id", "unique id", key, "identity")
            continue
        arms[key] = normalized
        array_cache[key] = arrays
    for q in TARGETS:
        qkey = f"{q:g}"
        present = {
            row["seed"]
            for row in arms.values()
            if float(row["q"]) == q and float(row["R"]) == 12.0 and int(row["n"]) == 192
        }
        for seed in ("w1", "w2", "w4", "diffuse"):
            if seed not in present:
                mismatch(
                    failures,
                    f"arms.q{qkey}.coarse.{seed}",
                    "present",
                    "missing",
                    "incomplete primary basin evidence",
                )
    decisions = _campaign_decisions(arms, failures)
    reported_verdicts = source.get("verdicts") if isinstance(source.get("verdicts"), dict) else {}
    for qkey, decision in decisions.items():
        receipt_category = _find_charge_verdict(reported_verdicts, qkey)
        decision["receipt_verdict"] = receipt_category
        if receipt_category is None:
            mismatch(
                failures,
                f"verdicts.{qkey}",
                "charge-specific recognized verdict",
                "missing or unrecognized",
                "schema",
            )
        elif receipt_category != decision["verdict"]:
            mismatch(
                failures,
                f"verdicts.{qkey}",
                decision["verdict"],
                receipt_category,
                "independent decision mismatch",
            )
    collocations: dict[str, Any] = {}
    collocation_dir = output_dir / "collocation"
    for qkey, decision in decisions.items():
        finest_id = decision.get("finest")
        if not finest_id or not decision.get("bound"):
            continue
        row = arms[finest_id]
        result = solve_continuum(array_cache[finest_id], float(row["R"]), float(row["q"]))
        clean = {key: value for key, value in result.items() if key not in {"field"}}
        if result.get("success") and result.get("finite"):
            p = row["diagnostics"]
            metrics = {
                "energy_relative": relative_difference(result["energy"], p["energy"]),
                "radius_relative": relative_difference(result["carrier_radius"], p["carrier_radius"]),
                "omega_absolute": abs(float(result["omega"]) - float(p["omega"])),
            }
            clean["comparison"] = metrics
            clean["pass"] = bool(metrics["energy_relative"] < COMPARE_ENERGY_TOL and metrics["radius_relative"] < COMPARE_RADIUS_TOL and metrics["omega_absolute"] < COMPARE_OMEGA_TOL)
            collocation_dir.mkdir(parents=True, exist_ok=True)
            artifact = collocation_dir / f"collocation_q{qkey}_R{int(row['R'])}_n{int(row['n'])}.npz"
            clean["artifact"] = str(artifact.relative_to(ROOT))
            clean["artifact_sha256"] = _save_collocation(artifact, result, float(row["R"]), float(row["q"]))
            if not clean["pass"]:
                mismatch(failures, f"collocation.{qkey}", "continuum comparison thresholds", metrics, "independent mismatch")
        else:
            clean["pass"] = False
            mismatch(failures, f"collocation.{qkey}", "successful finite continuum solve", clean, "continuum failure")
        collocations[qkey] = clean
    write_json(output_dir / "collocation.json", {"schema": "matter-formation-radial-collocation-v1", "rows": collocations})
    for qkey, decision in decisions.items():
        if decision["bound"] and not collocations.get(qkey, {}).get("pass", False):
            decision["verdict"] = "INCONCLUSIVE"
    report.update({
        "source_receipt": str(results_path.relative_to(ROOT)) if results_path.is_relative_to(ROOT) else str(results_path),
        "independent": {"arms": {key: value["diagnostics"] for key, value in arms.items()}, "charges": decisions, "collocation": collocations},
        "pass": not failures,
        "verdict": "INCONCLUSIVE" if failures or any(row["verdict"] == "INCONCLUSIVE" for row in decisions.values()) else ("EMERGES" if any(row["verdict"] == "EMERGES" for row in decisions.values()) else "DOES NOT EMERGE"),
    })
    write_json(output_dir / "verification.json", report)
    return report, 1 if failures or report["verdict"] == "INCONCLUSIVE" else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    input_dir = args.input_dir if args.input_dir.is_absolute() else ROOT / args.input_dir
    explicit_output = args.output_dir is not None
    output_dir = args.output_dir if explicit_output else input_dir
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    input_dir = input_dir.resolve()
    output_dir = output_dir.resolve()
    if (output_dir / "verification.json").exists() or (output_dir / "collocation.json").exists():
        parser.error("refusing to replace existing verifier receipts; use a distinct --output-dir")
    if output_dir == input_dir and explicit_output:
        parser.error("--output-dir must be separate from --input-dir")
    return verify(input_dir, output_dir)[1]


if __name__ == "__main__":
    raise SystemExit(main())
