#!/usr/bin/env python3
"""Notebook sections 74-75: one stationary scalar pool with a phase impulse.

Run: python computations/matter_formation_pool_dispersal.py --manifest PATH
     --profiles PROFILE_DIR --output FRESH_DIR
The finite-time scalar experiment supplies no microscopic particle identity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import time
from pathlib import Path

import numpy as np
import torch
from scipy.interpolate import PchipInterpolator

from matter_formation_neutral_packets import CylindricalGrid, YOSHIDA
from matter_formation_radial_cloud import CONSTANTS, OMEGA_INF

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
SCHEMA = "matter-formation-pool-dispersal-primary-v1"
MANIFEST_SCHEMA = "matter-formation-pool-dispersal-manifest-v1"
HEADINGS = (
    "## 74. Working notes: dispersal of a self-bound field pool",
    "## 75. Working notes: controlled pool-dispersal experiment",
)
A, CPSI, HC = CONSTANTS["a"], CONSTANTS["c_psi"], CONSTANTS["h_C"]
CHARGE, SPEED2 = 512.0, 8.0
ARMS = {"hold": (0.0, HC), "weak": (0.5, HC), "strong": (1.5, HC), "uncoupled": (1.5, 0.0)}
SCHEDULE = (
    ("G0", 112, 0.25, 1 / 256, tuple(ARMS)),
    ("G1", 112, 0.125, 1 / 256, tuple(ARMS)),
    ("G2", 160, 0.25, 1 / 256, ("strong",)),
    ("T1", 112, 0.125, 1 / 512, ("strong",)),
)
HALF_NAMES = (
    "positive_charge", "center", "core_fraction", "core_rms", "core_f2",
    "cut_charge", "cut_energy", "cut_momentum", "cut_radicand", "binding_ratio", "clearance",
)
NAMES = ("energy", "charge", "charge_l1", "rms", "reflection") + tuple(
    f"{side}_{name}" for side in ("right", "left") for name in HALF_NAMES
)
INDEX = {name: index for index, name in enumerate(NAMES)}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def section(data: bytes, heading: str) -> bytes:
    lines = canonical(data).decode("utf-8").splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.rstrip() == heading]
    if len(starts) != 1:
        raise ValueError(f"heading absent or ambiguous: {heading}")
    start = starts[0]
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return ("".join(lines[start:end]).rstrip() + "\n").encode("utf-8")


def rooted(value: str) -> Path:
    path = (ROOT / value).resolve()
    if Path(value).is_absolute() or not path.is_relative_to(ROOT):
        raise ValueError(f"manifest path escapes repository: {value}")
    return path


def validate_manifest(path: Path) -> dict:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest["schema"] != MANIFEST_SCHEMA:
        raise ValueError("manifest schema mismatch")
    entries = manifest["sources"]
    paths = [entry["path"] for entry in entries]
    required = {
        "computations/matter_formation_pool_profiles.py",
        "computations/matter_formation_pool_dispersal.py",
        "computations/verify_matter_formation_pool_dispersal.py",
        "computations/matter_formation_neutral_packets.py",
        "computations/matter_formation_radial_cloud.py",
        "computations/matter_formation_radial.py",
    }
    if len(paths) != len(set(paths)) or not required.issubset(paths):
        raise ValueError("source inventory incomplete or duplicated")
    for entry in entries:
        if sha(rooted(entry["path"])) != entry["sha256"]:
            raise ValueError(f"source identity mismatch: {entry['path']}")
    if sorted(entry["heading"] for entry in manifest["sections"]) != sorted(HEADINGS):
        raise ValueError("section inventory mismatch")
    for entry in manifest["sections"]:
        live = section(rooted(entry["path"]).read_bytes(), entry["heading"])
        snapshot = section(rooted(entry["snapshot"]).read_bytes(), entry["heading"])
        if live != snapshot or hashlib.sha256(live).hexdigest() != entry["sha256"]:
            raise ValueError(f"section identity mismatch: {entry['heading']}")
    return manifest


def write_json(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def save_npz(path: Path, **arrays: np.ndarray) -> dict:
    for name, value in arrays.items():
        if np.asarray(value).dtype.kind in "fc" and not np.isfinite(value).all():
            raise FloatingPointError(f"nonfinite archive array: {name}")
    with path.open("xb") as stream:
        np.savez_compressed(stream, **arrays)
    return {"path": path.name, "sha256": sha(path)}


def load_parent(directory: Path, manifest_hash: str) -> tuple[dict, dict[str, np.ndarray]]:
    receipt = json.loads((directory / "result.json").read_text(encoding="utf-8"))
    if (receipt["schema"] != "matter-formation-pool-profiles-v1"
            or receipt["manifest_sha256"] != manifest_hash
            or receipt["numeric_pass"] is not True
            or len(receipt["rows"]) != 12
            or not receipt["checks"] or not all(value is True for value in receipt["checks"].values())):
        raise ValueError("stationary profiles are not qualified under this manifest")
    for row in receipt["rows"]:
        path = directory / row["archive"]
        if path.resolve().parent != directory.resolve() or sha(path) != row["archive_sha256"]:
            raise ValueError("profile archive identity mismatch")
    if receipt["selected"] != {"Q256": "q256_S1_s0", "Q512": "q512_S1_s0"}:
        raise ValueError("stationary reference selection changed")
    rows = [row for row in receipt["rows"] if row["key"] == receipt["selected"]["Q512"]]
    if len(rows) != 1 or rows[0]["qualified"] is not True:
        raise ValueError("selected parent missing or unqualified")
    with np.load(directory / rows[0]["archive"], allow_pickle=False) as data:
        profile = {name: data[name].copy() for name in data.files}
    return rows[0], profile


def initial_state(grid: CylindricalGrid, profile: dict[str, np.ndarray], p: float) -> tuple[torch.Tensor, torch.Tensor]:
    radial = np.append(profile["r"], float(profile["R"]))
    fvalues, cvalues = np.append(profile["f"], 1.0), np.append(profile["c"], 0.0)
    knots = np.concatenate((-radial[::-1], radial))
    distance = torch.sqrt(grid.r2 + grid.axial[None, :].square()).cpu().numpy()
    interior = distance <= float(profile["R"])
    f = np.ones_like(distance)
    c = np.zeros_like(distance)
    f[interior] = PchipInterpolator(knots, np.concatenate((fvalues[::-1], fvalues)))(distance[interior])
    c[interior] = PchipInterpolator(knots, np.concatenate((cvalues[::-1], cvalues)))(distance[interior])
    mediator = torch.as_tensor(f - 1.0, dtype=torch.float64, device="cuda")
    carrier = torch.as_tensor(c, dtype=torch.float64, device="cuda")
    omega = float(profile["omega"])
    carrier *= math.sqrt(CHARGE / (2.0 * A * omega * float((grid.volume * carrier.square()).sum())))
    theta = p * (torch.sqrt(grid.axial.square() + 4.0) - 2.0)
    q = torch.stack((mediator, carrier * torch.cos(theta), carrier * torch.sin(theta)))
    v = torch.zeros_like(q)
    v[1], v[2] = omega * q[2], -omega * q[1]
    return q, v


def axial_derivative(q: torch.Tensor, h: float) -> torch.Tensor:
    derivative = torch.empty_like(q)
    derivative[..., 1:-1] = (q[..., 2:] - q[..., :-2]) / (2.0 * h)
    derivative[..., 0] = (q[..., 1] + q[..., 0]) / (2.0 * h)
    derivative[..., -1] = (-q[..., -1] - q[..., -2]) / (2.0 * h)
    return derivative


def diagnostics(grid: CylindricalGrid, q: torch.Tensor, v: torch.Tensor, coupling: float) -> np.ndarray:
    density = -2.0 * A * (q[1] * v[2] - q[2] * v[1])
    weighted = grid.volume * density
    positive = torch.clamp(density, min=0.0)
    mass = float((grid.volume * positive).sum())
    rms = math.sqrt(float((grid.volume * positive * (grid.r2 + grid.axial[None, :].square())).sum()) / mass) if mass > 0.0 else 0.0
    reflection = float(grid.norm(q - q.flip(-1), v - v.flip(-1))) / max(1.0, float(grid.norm(q, v)))
    values = [float(grid.energy(q, v, coupling)), float(weighted.sum()), float(weighted.abs().sum()), rms, reflection]
    for half in (grid.axial[None, :] > 0.0, grid.axial[None, :] < 0.0):
        half_density = positive * half
        half_charge = float((grid.volume * half_density).sum())
        center = float((grid.volume * half_density * grid.axial[None, :]).sum()) / half_charge if half_charge > 0.0 else 0.0
        d2 = grid.r2 + (grid.axial[None, :] - center).square()
        core = half_density * (d2 < 64.0)
        core_charge = float((grid.volume * core).sum())
        fraction = core_charge / half_charge if half_charge > 0.0 else 0.0
        core_rms = math.sqrt(float((grid.volume * core * d2).sum()) / core_charge) if core_charge > 0.0 else 0.0
        core_f2 = float((grid.volume * core * (q[0] + 1.0).square()).sum()) / core_charge if core_charge > 0.0 else 0.0
        s = torch.clamp((torch.sqrt(d2) - 8.0) / 4.0, 0.0, 1.0)
        theta = 1.0 - 3.0 * s.square() + 2.0 * s.pow(3)
        cut_q, cut_v = q * theta, v * theta
        energy = float(grid.energy(cut_q, cut_v, coupling))
        charge = float((weighted * theta.square()).sum())
        dz = axial_derivative(cut_q, grid.h)
        momentum = -float((grid.volume * (CPSI * cut_v[0] * dz[0] + 2.0 * A * (cut_v[1] * dz[1] + cut_v[2] * dz[2]))).sum())
        radicand = energy * energy - SPEED2 * momentum * momentum
        if radicand < 0.0:
            raise FloatingPointError(f"negative compact energy-momentum radicand: {radicand}")
        ratio = math.sqrt(radicand) / (OMEGA_INF * charge) if charge > 0.0 else 0.0
        clearance = min(grid.R - 12.0, grid.R - abs(center) - 12.0)
        values.extend((half_charge, center, fraction, core_rms, core_f2, charge, energy, momentum, radicand, ratio, clearance))
    result = np.asarray(values, dtype=np.float64)
    if result.shape != (len(NAMES),) or not np.isfinite(result).all():
        raise FloatingPointError("invalid pool diagnostics")
    return result


def diagnostic_scales(energy: float) -> np.ndarray:
    scales = []
    energy = max(1.0, energy)
    for name in NAMES:
        if name.endswith("radicand"):
            scales.append(energy * energy)
        elif name.endswith("momentum"):
            scales.append(energy / math.sqrt(SPEED2))
        elif name.endswith("energy"):
            scales.append(energy)
        elif "charge" in name:
            scales.append(CHARGE)
        elif name == "rms" or name.endswith(("center", "rms", "clearance")):
            scales.append(12.0)
        else:
            scales.append(1.0)
    return np.asarray(scales)


def two_pools(trace: np.ndarray, times: np.ndarray) -> bool:
    late = trace[times >= 24.0]
    if len(late) != 65:
        return False
    for side in ("right", "left"):
        col = lambda name: late[:, INDEX[f"{side}_{name}"]]
        if not (np.all(col("cut_charge") >= 128.0)
                and np.all(col("core_fraction") >= 0.6)
                and np.all(col("core_rms") < 6.0)
                and np.all(col("core_f2") <= 0.5)
                and np.all(col("binding_ratio") > 0.0)
                and np.all(col("binding_ratio") < 0.98)
                and np.all(np.abs(col("center")) > 12.0)
                and np.all(col("clearance") > 16.0)):
            return False
    return True


def save_state(output: Path, key: str, time_value: float, grid: CylindricalGrid, q: torch.Tensor, v: torch.Tensor) -> dict:
    entry = save_npz(output / f"{key}_t{int(time_value):03d}.npz", fields=q.cpu().numpy(),
                     velocities=v.cpu().numpy(), r=grid.r.cpu().numpy(), axial=grid.axial.cpu().numpy(),
                     volume=grid.volume.cpu().numpy(), time=np.asarray(time_value))
    return {**entry, "time": time_value}


def run_row(output: Path, tag: str, grid: CylindricalGrid, dt: float, arm: str, profile: dict[str, np.ndarray]) -> dict:
    key = f"{tag}_{arm}"
    p, coupling = ARMS[arm]
    q, v = initial_state(grid, profile, p)
    acceleration = grid.acceleration(q, coupling)
    times = np.arange(257, dtype=np.float64) / 8.0
    trace = np.empty((len(times), len(NAMES)), dtype=np.float64)
    trace[0] = diagnostics(grid, q, v, coupling)
    initial_energy = float(trace[0, 0])
    states = [save_state(output, key, 0.0, grid, q, v)]
    sample_step = round(0.125 / dt)
    sample = 0
    completed_samples = 1
    started = time.perf_counter()
    try:
        for step in range(1, round(32.0 / dt) + 1):
            for factor in YOSHIDA:
                h = factor * dt
                v.add_(acceleration, alpha=h / 2.0)
                q.add_(v, alpha=h)
                acceleration = grid.acceleration(q, coupling)
                v.add_(acceleration, alpha=h / 2.0)
            if step % sample_step == 0:
                sample += 1
                trace[sample] = diagnostics(grid, q, v, coupling)
                completed_samples = sample + 1
                current_time = float(times[sample])
                if current_time in (24.0, 32.0):
                    states.append(save_state(output, key, current_time, grid, q, v))
                if current_time % 8.0 == 0.0:
                    print(json.dumps({"row": key, "time": current_time, "elapsed_seconds": time.perf_counter() - started}), flush=True)
    except Exception:
        save_npz(output / f"{key}_partial_trace.npz", time=times[:completed_samples], diagnostics=trace[:completed_samples], names=np.asarray(NAMES))
        raise
    artifact = save_npz(output / f"{key}_trace.npz", time=times, diagnostics=trace, names=np.asarray(NAMES))
    energy_drift = float(np.max(np.abs(trace[:, 0] - initial_energy))) / max(1.0, initial_energy)
    charge_drift = float(np.max(np.abs(trace[:, 1] - trace[0, 1]))) / CHARGE
    failures = []
    if energy_drift >= 2e-4:
        failures.append("energy_drift")
    if charge_drift >= 2e-5:
        failures.append("charge_drift")
    if float(trace[:, 4].max()) >= 1e-10:
        failures.append("reflection")
    if arm == "hold" and float(np.max(np.abs(trace[:, 3] / trace[0, 3] - 1.0))) > 0.02:
        failures.append("parent_radius_survival")
    if arm == "uncoupled":
        for side in ("right", "left"):
            charged = trace[:, INDEX[f"{side}_cut_charge"]] > 0.0
            if np.any(trace[charged, INDEX[f"{side}_binding_ratio"]] < 1.0 - 1e-8):
                failures.append(f"{side}_uncoupled_binding_bound")
    row = {"key": key, "grid": tag, "arm": arm, "p": p, "coupling": coupling, "R": grid.R,
           "spacing": grid.h, "dt": dt, "initial_energy": initial_energy,
           "trace": artifact["path"], "trace_sha256": artifact["sha256"], "states": states,
           "qualified": not failures, "formation": two_pools(trace, times), "failures": failures,
           "complete_physical_matter_formation": False,
           "energy_drift": energy_drift, "charge_drift": charge_drift,
           "late_means": trace[times >= 24.0].mean(axis=0).tolist(), "elapsed_seconds": time.perf_counter() - started}
    write_json(output / f"{key}.json", row)
    print(json.dumps({"completed": key, "qualified": row["qualified"], "formation": row["formation"], "failures": failures}), flush=True)
    return row


def comparisons(rows: list[dict]) -> list[dict]:
    indexed = {row["key"]: row for row in rows}
    pairs = [(f"G0_{arm}", f"G1_{arm}") for arm in ARMS]
    pairs.extend((("G0_strong", "G2_strong"), ("G1_strong", "T1_strong")))
    result = []
    for left, right in pairs:
        if left not in indexed or right not in indexed:
            result.append({"left": left, "right": right, "pass": False, "error": "missing row"})
            continue
        a, b = indexed[left], indexed[right]
        error = np.abs(np.asarray(a["late_means"]) - np.asarray(b["late_means"])) / diagnostic_scales(max(a["initial_energy"], b["initial_energy"]))
        result.append({"left": left, "right": right, "errors": dict(zip(NAMES, error.tolist())),
                       "max_error": float(error.max()), "pass": bool(np.all(error < 0.05))})
    return result


@torch.no_grad()
def run(args: argparse.Namespace) -> int:
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    output.mkdir(parents=True)
    result = {"schema": SCHEMA, "rows": [], "comparisons": [], "numeric_pass": False,
              "verdict": "INCONCLUSIVE", "complete_physical_matter_formation": False}
    try:
        validate_manifest(args.manifest)
        result["manifest_sha256"] = sha(args.manifest)
        _, profile = load_parent(args.profiles.resolve(), result["manifest_sha256"])
        result["profile_receipt_sha256"] = sha(args.profiles / "result.json")
        if not torch.cuda.is_available():
            raise RuntimeError("the fixed float64 GPU calculation needs the ROCm device")
        torch.set_num_threads(1)
        result["environment"] = {"python": platform.python_version(), "numpy": np.__version__,
                                 "torch": torch.__version__, "hip": torch.version.hip, "device": torch.cuda.get_device_name(0)}
        for tag, radius, spacing, dt, arms in SCHEDULE:
            grid = CylindricalGrid(radius, spacing)
            for arm in arms:
                result["rows"].append(run_row(output, tag, grid, dt, arm, profile))
            del grid
        result["comparisons"] = comparisons(result["rows"])
        result["numeric_pass"] = (len(result["rows"]) == 10
                                  and all(row["qualified"] for row in result["rows"])
                                  and all(item["pass"] for item in result["comparisons"]))
        result["verdict"] = "INCONCLUSIVE-awaiting independent pool qualification" if result["numeric_pass"] else "INCONCLUSIVE"
    except Exception as error:
        result["error"] = f"{type(error).__name__}: {error}"
    write_json(output / "result.json", result)
    print(json.dumps({key: result.get(key) for key in ("verdict", "numeric_pass", "error", "complete_physical_matter_formation")}), flush=True)
    return 0 if result["numeric_pass"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--profiles", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        return run(args)
    except Exception as error:
        print(json.dumps({"error": f"{type(error).__name__}: {error}", "complete_physical_matter_formation": False}), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
