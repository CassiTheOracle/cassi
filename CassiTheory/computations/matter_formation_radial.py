#!/usr/bin/env python3
"""Preregistered continuum-consistent radial matter-formation campaign.

The optimization variables are the cell-centred scalar field ``f`` and a
nonnegative carrier shape.  The latter is normalized to the registered charge
inside every objective evaluation; consequently the L-BFGS-B gradient is the
exact pullback of the fixed-charge finite-volume action, rather than a penalty
or a softplus reparameterization.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

import numpy as np
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN_DIR = ROOT / "runs" / "20260906_matter_formation_radial"
PREREG_PATH = ROOT / "computations" / "matter-formation-continuum-prereg.md"
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
Q_VALUES = (4.0, 16.0, 64.0, 256.0)
SEEDS = ("w1", "w2", "w4", "diffuse")
PRIMARY_GRID = (12.0, 192)
REFINEMENT_GRIDS = ((12.0, 384), (12.0, 768), (24.0, 768))
MAX_ITER = 50_000
MAX_EVAL = 200_000
FTOL = 1.0e-15
GTOL = 1.0e-10
MAXCOR = 50
SCHEMA = "matter-formation-radial-v1"


class OptimizationFailure(RuntimeError):
    def __init__(self, message: str, calls: int, callbacks: int):
        super().__init__(message)
        self.calls = int(calls)
        self.callbacks = int(callbacks)


@dataclass(frozen=True)
class Grid:
    R: float
    n: int
    dr: float
    r: np.ndarray
    faces: np.ndarray
    volumes: np.ndarray
    conductance: np.ndarray
    outer_conductance: float

    @classmethod
    def make(cls, R: float, n: int) -> "Grid":
        dr = float(R) / int(n)
        faces = np.arange(n + 1, dtype=np.float64) * dr
        r = (np.arange(n, dtype=np.float64) + 0.5) * dr
        volumes = (4.0 * math.pi / 3.0) * (faces[1:] ** 3 - faces[:-1] ** 3)
        conductance = 4.0 * math.pi * faces[1:-1] ** 2 / dr
        outer_conductance = 8.0 * math.pi * float(R) ** 2 / dr
        for array in (r, faces, volumes, conductance):
            array.setflags(write=False)
        return cls(float(R), int(n), dr, r, faces, volumes, conductance, outer_conductance)


def canonical_sha256(path: Path) -> str:
    """Hash source/preregistration bytes after the declared CRLF normalization."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        data = handle.read()
    digest.update(data.replace(b"\r\n", b"\n"))
    return digest.hexdigest()


def raw_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    os.replace(temporary, path)

def relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return os.path.relpath(path.resolve(), ROOT).replace("\\", "/")


def normalize_carrier(shape: np.ndarray, grid: Grid, q: float) -> np.ndarray:
    shape = np.asarray(shape, dtype=np.float64)
    norm2 = float(np.dot(grid.volumes, shape * shape))
    if not math.isfinite(norm2) or norm2 <= 0.0:
        raise ValueError("carrier shape has no positive fixed-charge norm")
    return shape * math.sqrt(float(q) / norm2)


def _fields_from_raw(raw: np.ndarray, grid: Grid, q: float) -> tuple[np.ndarray, np.ndarray]:
    n = grid.n
    f = np.asarray(raw[:n], dtype=np.float64)
    # L-BFGS-B enforces this bound; no softplus or post-objective clipping is used.
    shape = np.asarray(raw[n:], dtype=np.float64)
    c = normalize_carrier(shape, grid, q)
    return f, c


def finite_volume_energy_gradient(
    f: np.ndarray, c: np.ndarray, grid: Grid
) -> tuple[float, np.ndarray, np.ndarray]:
    """Return exact action energy and cell derivatives for already-normalized fields."""
    f = np.asarray(f, dtype=np.float64)
    c = np.asarray(c, dtype=np.float64)
    if f.shape != (grid.n,) or c.shape != (grid.n,):
        raise ValueError("radial fields must have one value per cell")
    vf = f[-1] - 1.0
    vc = c[-1]
    df = np.diff(f)
    dc = np.diff(c)
    gradient = 0.5 * float(np.dot(grid.conductance, df * df + dc * dc))
    gradient += 0.5 * grid.outer_conductance * (vf * vf + vc * vc)
    rho = f * f - 1.0
    A = COEFFICIENTS["e_C"] - COEFFICIENTS["h_C"] * (1.0 - f * f)
    potential_density = (
        COEFFICIENTS["u_rho"] / 4.0 * rho * rho
        + A * c * c
        + COEFFICIENTS["u_C"] / 2.0 * c**4
    )
    energy = gradient + float(np.dot(grid.volumes, potential_density))

    gf = np.empty(grid.n, dtype=np.float64)
    gc = np.empty(grid.n, dtype=np.float64)
    gf.fill(0.0)
    gc.fill(0.0)
    if grid.n > 1:
        gf[:-1] += grid.conductance * (f[:-1] - f[1:])
        gf[1:] += grid.conductance * (f[1:] - f[:-1])
        gc[:-1] += grid.conductance * (c[:-1] - c[1:])
        gc[1:] += grid.conductance * (c[1:] - c[:-1])
    gf[-1] += grid.outer_conductance * vf
    gc[-1] += grid.outer_conductance * vc
    gf += grid.volumes * (
        COEFFICIENTS["u_rho"] * f * rho + 2.0 * COEFFICIENTS["h_C"] * f * c * c
    )
    gc += grid.volumes * (2.0 * A * c + 2.0 * COEFFICIENTS["u_C"] * c**3)
    return float(energy), gf, gc


def evaluate_fixed_charge(raw: np.ndarray, grid: Grid, q: float) -> tuple[float, np.ndarray]:
    """Objective and analytic raw-coordinate gradient used by scipy."""
    f, c = _fields_from_raw(raw, grid, q)
    energy, gf, gc = finite_volume_energy_gradient(f, c, grid)
    shape = np.asarray(raw[grid.n:], dtype=np.float64)
    norm2 = float(np.dot(grid.volumes, shape * shape))
    alpha = math.sqrt(float(q) / norm2)
    # Pull back through dc/dshape = alpha [I - shape (V shape)^T / norm2].
    projection = float(np.dot(shape, gc)) / norm2
    gc_raw = alpha * (gc - grid.volumes * shape * projection)
    return energy, np.concatenate((gf, gc_raw))


def stationary_diagnostics(f: np.ndarray, c: np.ndarray, grid: Grid, q: float) -> dict[str, Any]:
    energy, gf, gc = finite_volume_energy_gradient(f, c, grid)
    charge = float(np.dot(grid.volumes, c * c))
    omega = float(np.dot(c, gc) / (2.0 * charge))
    rf = gf / grid.volumes
    rc = gc / (2.0 * grid.volumes) - omega * c
    f_scale = max(1.0, math.sqrt(float(np.dot(grid.volumes, (1.0 - f) ** 2))))
    outer = grid.r > 0.5 * grid.R
    residual_f = math.sqrt(float(np.dot(grid.volumes, rf * rf))) / f_scale
    residual_c = math.sqrt(float(np.dot(grid.volumes, rc * rc))) / math.sqrt(q)
    charge_error = abs(charge - q) / q
    outer_fraction = float(np.dot(grid.volumes[outer], c[outer] * c[outer]) / charge)
    qualified = bool(
        np.all(np.isfinite(f)) and np.all(np.isfinite(c))
        and all(math.isfinite(x) for x in (energy, omega, residual_f, residual_c))
        and charge_error < 1.0e-10 and residual_f < 1.0e-4 and residual_c < 1.0e-4
    )
    return {
        "energy": float(energy),
        "charge": charge,
        "charge_relative_error": charge_error,
        "omega": omega,
        "carrier_radius": math.sqrt(float(np.dot(grid.volumes, grid.r * grid.r * c * c)) / charge),
        "outer_fraction": outer_fraction,
        "residual_f": residual_f,
        "residual_c": residual_c,
        "qualified": qualified,
        "bound": bool(
            qualified and energy < COEFFICIENTS["e_C"] * q - 1.0e-3
            and omega < COEFFICIENTS["e_C"] - 1.0e-3 and outer_fraction < 1.0e-3
        ),
    }


def save_npz(path: Path, f: np.ndarray, c: np.ndarray, grid: Grid, q: float) -> str:
    """Atomically write the raw artifact schema and return its byte hash."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp.npz")
    np.savez(
        temporary,
        r=np.asarray(grid.r, dtype=np.float64),
        volumes=np.asarray(grid.volumes, dtype=np.float64),
        f=np.asarray(f, dtype=np.float64),
        c=np.asarray(c, dtype=np.float64),
        R=np.asarray(float(grid.R), dtype=np.float64),
        q=np.asarray(float(q), dtype=np.float64),
    )
    os.replace(temporary, path)
    return raw_sha256(path)


def seed_fields(grid: Grid, q: float, seed: str) -> tuple[np.ndarray, np.ndarray]:
    if seed == "diffuse":
        f = np.ones(grid.n, dtype=np.float64)
        shape = np.cos(math.pi * grid.r / (2.0 * grid.R))
    else:
        width = {"w1": 1.0, "w2": 2.0, "w4": 4.0}[seed]
        gaussian = np.exp(-grid.r * grid.r / (2.0 * width * width))
        f = 1.0 - 0.9 * gaussian
        shape = gaussian
    shape = np.maximum(shape, 0.0)
    shape = normalize_carrier(shape, grid, q)
    return f, shape


def interpolate_fields(
    f: np.ndarray, c: np.ndarray, old_grid: Grid, new_grid: Grid
) -> tuple[np.ndarray, np.ndarray]:
    """Interpolate in physical radius, including the declared outer values."""
    radius = np.concatenate((old_grid.r, np.asarray([old_grid.R], dtype=np.float64)))
    f_extended = np.concatenate((f, np.asarray([1.0], dtype=np.float64)))
    c_extended = np.concatenate((c, np.asarray([0.0], dtype=np.float64)))
    return (
        np.interp(new_grid.r, radius, f_extended, left=f[0], right=1.0),
        np.interp(new_grid.r, radius, c_extended, left=c[0], right=0.0),
    )


def _optimizer_dict(result: Any, calls: int, callback_count: int) -> dict[str, Any]:
    jac = np.asarray(getattr(result, "jac", np.array([], dtype=np.float64)), dtype=np.float64)
    return {
        "success": bool(result.success),
        "status": int(result.status),
        "message": str(result.message),
        "nit": int(getattr(result, "nit", 0)),
        "nfev": int(getattr(result, "nfev", calls)),
        "njev": int(getattr(result, "njev", calls)),
        "objective_calls": int(calls),
        "callback_calls": int(callback_count),
        "final_objective": float(result.fun),
        "final_reduced_gradient_inf": float(np.max(np.abs(jac))) if jac.size else None,
    }


def optimize_endpoint(
    f0: np.ndarray,
    c0: np.ndarray,
    grid: Grid,
    q: float,
    artifact: Path,
    checkpoint: Callable[[np.ndarray, int], None] | None = None,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    raw0 = np.concatenate((np.asarray(f0, dtype=np.float64), np.asarray(c0, dtype=np.float64)))
    calls = 0
    callbacks = 0

    def objective(raw: np.ndarray) -> tuple[float, np.ndarray]:
        nonlocal calls
        calls += 1
        return evaluate_fixed_charge(raw, grid, q)

    def callback_fn(raw: np.ndarray) -> None:
        nonlocal callbacks
        callbacks += 1
        if checkpoint is not None and callbacks % 20 == 0:
            checkpoint(np.asarray(raw, dtype=np.float64), callbacks)

    bounds = [(0.0, 1.0)] * grid.n + [(0.0, None)] * grid.n
    try:
        result = minimize(
            objective,
            raw0,
            method="L-BFGS-B",
            jac=True,
            bounds=bounds,
            callback=callback_fn,
            options={
                "maxiter": MAX_ITER,
                "maxfun": MAX_EVAL,
                "ftol": FTOL,
                "gtol": GTOL,
                "maxcor": MAXCOR,
            },
        )
        f, c = _fields_from_raw(np.asarray(result.x), grid, q)
        return f, c, _optimizer_dict(result, calls, callbacks)
    except KeyboardInterrupt:
        raise
    except Exception as error:
        raise OptimizationFailure(
            f"optimizer failed after {calls} objective calls: {error}", calls, callbacks
        ) from error


def _arm_id(q: float, R: float, n: int, seed: str) -> str:
    q_string = str(int(q)) if q.is_integer() else str(q).replace(".", "p")
    r_string = str(int(R)) if R.is_integer() else str(R).replace(".", "p")
    return f"q{q_string}_R{r_string}_n{n}_{seed}"


def _comparison(a: Mapping[str, Any], b: Mapping[str, Any]) -> dict[str, Any]:
    def rel(x: float, y: float) -> float:
        return abs(float(x) - float(y)) / max(1.0e-300, abs(float(x)), abs(float(y)))

    energy = rel(a["energy"], b["energy"])
    radius = rel(a["carrier_radius"], b["carrier_radius"])
    frequency = abs(float(a["omega"]) - float(b["omega"]))
    return {
        "energy_relative_difference": energy,
        "carrier_radius_relative_difference": radius,
        "frequency_absolute_difference": frequency,
        "pass": bool(energy < 5.0e-3 and radius < 5.0e-3 and frequency < 1.0e-3),
    }


def _charge_verdict(q: float, arms: list[dict[str, Any]]) -> dict[str, Any]:
    q_arms = [a for a in arms if float(a.get("q", -1.0)) == q]
    primary = [a for a in q_arms if a.get("R") == 12.0 and a.get("n") == 192]
    qualified_primary = [
        a for a in primary if (a.get("diagnostics") or {}).get("qualified") is True
    ]
    if not qualified_primary:
        return {"q": q, "verdict": "INCONCLUSIVE", "reason": "no qualified primary endpoint"}
    refined = [a for a in q_arms if a.get("seed") == "refine"]
    qualified_refined = [
        a for a in refined if (a.get("diagnostics") or {}).get("qualified") is True
    ]
    if len(qualified_refined) < 3:
        return {
            "q": q,
            "verdict": "INCONCLUSIVE",
            "reason": "continuation endpoint failed qualification",
        }
    by_grid = {(float(a["R"]), int(a["n"])): a for a in qualified_refined}
    required = [(12.0, 384), (12.0, 768), (24.0, 768)]
    if any(key not in by_grid for key in required):
        return {"q": q, "verdict": "INCONCLUSIVE", "reason": "missing continuation grid"}
    a384, a768, domain = (by_grid[key] for key in required)
    comparisons = {
        "R12_n384_vs_R12_n768": _comparison(a384["diagnostics"], a768["diagnostics"]),
        # R24/n768 has dr=R12/n384: the preregistered same-spacing control.
        "R12_n384_vs_R24_n768_same_spacing": _comparison(
            a384["diagnostics"], domain["diagnostics"]
        ),
    }
    bound = a768["diagnostics"].get("bound") is True
    resolved = all(value["pass"] for value in comparisons.values())
    if bound and resolved:
        verdict = "EMERGES"
        reason = "qualified bound branch passes finite-grid and domain comparisons"
    elif not bound:
        verdict = "DOES NOT EMERGE"
        reason = "qualified tested branch is not bound"
    else:
        verdict = "INCONCLUSIVE"
        reason = "bound finite-domain endpoint fails spatial or domain resolution"
    return {"q": q, "verdict": verdict, "reason": reason, "comparisons": comparisons}




def run_campaign(output_dir: Path = DEFAULT_RUN_DIR) -> dict[str, Any]:
    if output_dir == DEFAULT_RUN_DIR and (output_dir / "results.json").exists():
        raise FileExistsError(f"refusing existing default result destination: {output_dir / 'results.json'}")
    if (output_dir / "results.json").exists():
        raise FileExistsError(f"refusing existing result destination: {output_dir / 'results.json'}")
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "results.json"
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "coefficients": dict(COEFFICIENTS),
        "prereg_sha256": canonical_sha256(PREREG_PATH),
        "source_sha256": canonical_sha256(Path(__file__).resolve()),
        "arms": [],
        "verdicts": {},
    }
    write_json(result_path, receipt)
    completed: dict[str, dict[str, Any]] = {}

    def persist() -> None:
        receipt["verdicts"] = {f"{q:g}": _charge_verdict(q, list(completed.values())) for q in Q_VALUES}
        write_json(result_path, receipt)

    def set_arm(arm: dict[str, Any]) -> None:
        completed[arm["id"]] = arm
        receipt["arms"] = list(completed.values())
        persist()

    def execute(
        q: float, grid: Grid, seed: str, f0: np.ndarray, c0: np.ndarray, continuation: str | None = None
    ) -> dict[str, Any]:
        arm_id = _arm_id(q, grid.R, grid.n, seed)
        artifact = output_dir / f"{arm_id}.npz"
        arm: dict[str, Any] = {
            "id": arm_id,
            "q": q,
            "R": grid.R,
            "n": grid.n,
            "seed": seed,
            "artifact": relative_path(artifact),
            "artifact_sha256": None,
            "diagnostics": None,
            "optimizer": {"status": "running", "continuation": continuation},
        }
        set_arm(arm)

        def checkpoint(raw: np.ndarray, callback_count: int) -> None:
            ff, cc = _fields_from_raw(raw, grid, q)
            arm["artifact_sha256"] = save_npz(artifact, ff, cc, grid, q)
            arm["diagnostics"] = stationary_diagnostics(ff, cc, grid, q)
            arm["optimizer"] = {"status": "running", "callback_calls": callback_count}
            set_arm(arm)

        # Initial arrays are retained even if the optimizer is interrupted.
        arm["artifact_sha256"] = save_npz(artifact, f0, c0, grid, q)
        arm["diagnostics"] = stationary_diagnostics(f0, c0, grid, q)
        set_arm(arm)
        try:
            ff, cc, optimizer = optimize_endpoint(f0, c0, grid, q, artifact, checkpoint)
            arm["artifact_sha256"] = save_npz(artifact, ff, cc, grid, q)
            arm["diagnostics"] = stationary_diagnostics(ff, cc, grid, q)
            arm["optimizer"] = dict(optimizer, continuation=continuation)
            arm["status"] = "complete"
        except BaseException as error:
            arm["status"] = "failed"
            arm["optimizer"] = {
                "status": "interrupted" if isinstance(error, KeyboardInterrupt) else "exception",
                "continuation": continuation,
                "error": f"{type(error).__name__}: {error}",
                "objective_calls": int(getattr(error, "calls", 0)),
                "callback_calls": int(getattr(error, "callbacks", 0)),
            }
            set_arm(arm)
            if isinstance(error, KeyboardInterrupt):
                raise
        set_arm(arm)
        return arm
    for q in Q_VALUES:
        coarse_grid = Grid.make(*PRIMARY_GRID)
        coarse: list[dict[str, Any]] = []
        for seed in SEEDS:
            f0, c0 = seed_fields(coarse_grid, q, seed)
            try:
                coarse.append(execute(q, coarse_grid, seed, f0, c0))
            except KeyboardInterrupt:
                raise
            except Exception:
                # The failed arm and its last checkpoint are already in the receipt.
                arm_id = _arm_id(q, coarse_grid.R, coarse_grid.n, seed)
                coarse.append(completed[arm_id])
        eligible = [
            a
            for a in coarse
            if a.get("status") == "complete"
            and (a.get("diagnostics") or {}).get("qualified") is True
        ]
        if not eligible:
            continue
        selected = min(eligible, key=lambda a: float(a["diagnostics"]["energy"]))
        old_grid = coarse_grid
        old_f, old_c = _load_artifact(ROOT / selected["artifact"])
        same_spacing_base: tuple[Grid, np.ndarray, np.ndarray, dict[str, Any]] | None = None
        for R, n in REFINEMENT_GRIDS:
            new_grid = Grid.make(R, n)
            if R == 24.0 and n == 768 and same_spacing_base is not None:
                base_grid, base_f, base_c, base_arm = same_spacing_base
                f0, c0 = interpolate_fields(base_f, base_c, base_grid, new_grid)
                continuation = (
                    f"{base_arm['id']} physical-radius interpolation (same-spacing domain control)"
                )
            else:
                f0, c0 = interpolate_fields(old_f, old_c, old_grid, new_grid)
                continuation = f"{selected['id']} physical-radius interpolation"
            c0 = normalize_carrier(c0, new_grid, q)
            try:
                refined = execute(q, new_grid, "refine", f0, c0, continuation)
            except KeyboardInterrupt:
                raise
            except Exception:
                break
            if (
                refined.get("status") != "complete"
                or (refined.get("diagnostics") or {}).get("qualified") is not True
            ):
                break
            if R == 12.0 and n == 384:
                same_spacing_base = (new_grid, *_load_artifact(ROOT / refined["artifact"]), refined)
            old_grid, old_f, old_c, selected = (
                new_grid,
                *_load_artifact(ROOT / refined["artifact"]),
                refined,
            )
    persist()
    return receipt


def _load_artifact(path: Path) -> tuple[np.ndarray, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        return np.array(archive["f"], dtype=np.float64), np.array(archive["c"], dtype=np.float64)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_RUN_DIR)
    args = parser.parse_args(argv)
    try:
        receipt = run_campaign(args.output_dir.resolve())
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        print(json.dumps({"schema": SCHEMA, "verdict": "INCONCLUSIVE", "error": f"{type(error).__name__}: {error}"}, sort_keys=True), file=sys.stderr)
        return 1
    print(json.dumps({"schema": receipt["schema"], "output_dir": relative_path(args.output_dir), "verdicts": receipt["verdicts"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
