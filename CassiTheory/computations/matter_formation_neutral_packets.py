#!/usr/bin/env python3
"""Section 50: source-bound axisymmetric neutral-packet evolution.

Run from the repository root with --manifest PATH --output FRESH_DIR.
The initial Gaussian is supplied classical field data, not a quantum vacuum.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import time

import numpy as np
import torch

from matter_formation_radial_cloud import (
    B, CONSTANTS, OMEGA_INF, canonical_bytes, write_exclusive, write_json,
)

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
SCHEMA = "matter-formation-neutral-packets-primary-v1"
MANIFEST_SCHEMA = "matter-formation-neutral-packets-manifest-v1"
HEADING = "## 50. Working notes: charge-neutral packet condensation"
M0, WIDTH = 1024.0, 8.0
A = CONSTANTS["a"]
CPSI = CONSTANTS["c_psi"]
URHO = CONSTANTS["u_rho"]
UC = CONSTANTS["u_C"]
K = CONSTANTS["k_Cx"]
HC = CONSTANTS["h_C"]
QREF = A * OMEGA_INF * M0 / 2.0
W1 = 1.0 / (2.0 - 2.0 ** (1.0 / 3.0))
YOSHIDA = (W1, 1.0 - 2.0 * W1, W1)
SCHEDULE = (
    ("G0", 192, 0.5, 1.0 / 128.0, ("coupled", "uncoupled", "common_phase", "conjugate", "vacuum")),
    ("G1", 192, 0.25, 1.0 / 128.0, ("coupled", "uncoupled")),
    ("G2", 256, 0.5, 1.0 / 128.0, ("coupled", "uncoupled")),
    ("T1", 192, 0.25, 1.0 / 256.0, ("coupled", "uncoupled")),
)
NAMES = (
    "energy", "charge", "charge_l1", "half_charge", "half_derivative", "half_current",
    "continuity_residual", "reflection_error", "right_mass", "right_center",
    "right_core_charge", "right_core_fraction", "right_core_rms", "right_core_f2",
    "right_cut_energy", "right_cut_charge", "left_mass", "left_center",
    "left_core_charge", "left_core_fraction", "left_core_rms", "left_core_f2",
    "left_cut_energy", "left_cut_charge",
)
REQUIRED_SOURCES = {
    "computations/matter_formation_neutral_packets.py",
    "computations/verify_matter_formation_neutral_packets.py",
    "computations/matter_formation_radial_cloud.py",
    "foundations/particle-stationary-action-closure.md",
}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def section_text(path: Path) -> str:
    text = canonical_bytes(path.read_bytes()).decode("utf-8")
    lines = text.splitlines(keepends=True)
    matches = [i for i, line in enumerate(lines) if line.rstrip() == HEADING]
    if len(matches) != 1:
        raise ValueError("section 50 must occur exactly once")
    first = matches[0]
    last = next((i for i in range(first + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "".join(lines[first:last]).rstrip() + "\n"


def validate_manifest(path: Path) -> dict:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ValueError("unexpected manifest schema")
    record = manifest["section"]
    if record["heading"] != HEADING:
        raise ValueError("unexpected section heading")
    frozen = (path.parent / record["snapshot"]).read_bytes()
    if hashlib.sha256(frozen).hexdigest() != record["sha256"]:
        raise ValueError("frozen section hash mismatch")
    if section_text(ROOT / record["path"]).encode("utf-8") != frozen:
        raise ValueError("live section differs from frozen section")
    records = manifest["sources"]
    if len(records) != len(REQUIRED_SOURCES) or {r["path"] for r in records} != REQUIRED_SOURCES:
        raise ValueError("incomplete source identities")
    for record in records:
        if sha(ROOT / record["path"]) != record["sha256"]:
            raise ValueError(f"live source mismatch: {record['path']}")
        if sha(path.parent / record["snapshot"]) != record["sha256"]:
            raise ValueError(f"source snapshot mismatch: {record['path']}")
    review = manifest["mathematical_review"]
    if review.get("accepted") is not True or sha(path.parent / review["snapshot"]) != review["sha256"]:
        raise ValueError("independent mathematical review is not qualified")
    return manifest


class CylindricalGrid:
    def __init__(self, radius: int, spacing: float):
        self.R, self.h = radius, spacing
        self.nr = round(radius / spacing)
        self.nz = 2 * self.nr
        self.mid = self.nz // 2
        dtype, device = torch.float64, "cuda"
        self.r = (torch.arange(self.nr, dtype=dtype, device=device) + 0.5) * spacing
        self.axial = -radius + (torch.arange(self.nz, dtype=dtype, device=device) + 0.5) * spacing
        faces = torch.arange(self.nr + 1, dtype=dtype, device=device) * spacing
        self.volume = (math.pi * (faces[1:].square() - faces[:-1].square()) * spacing)[:, None]
        self.radial_edge = (2.0 * math.pi * faces[1:-1])[:, None]
        self.axial_edge = self.volume / spacing ** 2
        self.radial_boundary = 4.0 * math.pi * radius
        self.up = ((self.r + spacing / 2.0) / (self.r * spacing ** 2))[:-1, None]
        self.down = ((self.r - spacing / 2.0) / (self.r * spacing ** 2))[1:, None]
        self.outer_lap = 2.0 * radius / (self.r[-1] * spacing ** 2)
        self.r2 = self.r[:, None].square()
        self.right = self.axial[None, :] > 0
        self.left = ~self.right
        self.parity = torch.tensor([1.0, 1.0, -1.0], dtype=dtype, device=device)[:, None, None]

    def laplacian(self, q: torch.Tensor) -> torch.Tensor:
        result = torch.zeros_like(q)
        difference = q[:, 1:, :] - q[:, :-1, :]
        result[:, :-1, :] += difference * self.up
        result[:, 1:, :] -= difference * self.down
        difference = (q[:, :, 1:] - q[:, :, :-1]) / self.h ** 2
        result[:, :, :-1] += difference
        result[:, :, 1:] -= difference
        result[:, -1, :] -= self.outer_lap * q[:, -1, :]
        result[:, :, 0] -= 2.0 / self.h ** 2 * q[:, :, 0]
        result[:, :, -1] -= 2.0 / self.h ** 2 * q[:, :, -1]
        return result

    def acceleration(self, q: torch.Tensor, coupling: float) -> torch.Tensor:
        result = self.laplacian(q)
        f = q[0] + 1.0
        population = q[1].square() + q[2].square()
        coefficient = B - coupling + coupling * f.square() + UC * population
        result[0] -= URHO * (f.square() - 1.0) * f + 2.0 * coupling * f * population
        result[0] /= CPSI
        result[1:] *= K / 2.0
        result[1:] -= coefficient * q[1:]
        result[1:] /= A
        return result

    def gradient_energy(self, q: torch.Tensor) -> torch.Tensor:
        radial = ((q[:, 1:, :] - q[:, :-1, :]).square() * self.radial_edge).sum(dim=(1, 2))
        axial = ((q[:, :, 1:] - q[:, :, :-1]).square() * self.axial_edge).sum(dim=(1, 2))
        boundary_r = self.radial_boundary * q[:, -1, :].square().sum(dim=1)
        boundary_z = (2.0 * self.axial_edge[:, 0] * (q[:, :, 0].square() + q[:, :, -1].square())).sum(dim=1)
        terms = (radial + axial + boundary_r + boundary_z) / 2.0
        return terms[0] + K * (terms[1] + terms[2])

    def energy(self, q: torch.Tensor, v: torch.Tensor, coupling: float) -> torch.Tensor:
        f2 = (q[0] + 1.0).square()
        n = q[1].square() + q[2].square()
        potential = URHO / 4.0 * (f2 - 1.0).square() + (B - coupling + coupling * f2) * n + UC / 2.0 * n.square()
        kinetic = CPSI / 2.0 * v[0].square() + A * (v[1].square() + v[2].square())
        return ((potential + kinetic) * self.volume).sum() + self.gradient_energy(q)

    def norm(self, q: torch.Tensor, v: torch.Tensor) -> torch.Tensor:
        return torch.sqrt(((q.square() + (v / OMEGA_INF).square()) * self.volume).sum())

    def diagnostics(self, q: torch.Tensor, v: torch.Tensor, acc: torch.Tensor, coupling: float, orientation: float) -> np.ndarray:
        rho = -2.0 * A * (q[1] * v[2] - q[2] * v[1])
        weighted = self.volume * rho
        derivative = -2.0 * A * (self.volume * (q[1] * acc[2] - q[2] * acc[1]))[:, self.mid:].sum()
        current = (self.volume[:, 0] / self.h * K / self.h * (
            q[1, :, self.mid - 1] * q[2, :, self.mid] - q[2, :, self.mid - 1] * q[1, :, self.mid]
        )).sum()
        derivative_f, current_f = float(derivative), float(current)
        residual = abs(derivative_f - current_f) / max(1.0, abs(derivative_f), abs(current_f))
        reflection = float(self.norm(q - self.parity * q.flip(-1), v - self.parity * v.flip(-1))) / max(math.sqrt(M0), float(self.norm(q, v)))
        result = [float(self.energy(q, v, coupling)), float(weighted.sum()), float(weighted.abs().sum()),
                  float(weighted[:, self.mid:].sum()), derivative_f, current_f, residual, reflection]
        for direction, half in ((1.0, self.right), (-1.0, self.left)):
            density = torch.clamp_min(direction * orientation * rho, 0.0) * half
            mass = float((self.volume * density).sum())
            center = float((self.volume * density * self.axial).sum()) / mass if mass > 0.0 else 0.0
            d2 = self.r2 + (self.axial[None, :] - center).square()
            core_density = density * (d2 < 64.0)
            core_mass = float((self.volume * core_density).sum())
            fraction = core_mass / mass if mass > 0.0 else 0.0
            if core_mass > 0.0:
                rms = math.sqrt(max(0.0, float((self.volume * core_density * d2).sum()) / core_mass))
                f2_mean = float((self.volume * core_density * (q[0] + 1.0).square()).sum()) / core_mass
            else:
                rms, f2_mean = 0.0, 0.0
            # This bounded diagnostic mask is never used in the evolution.
            s = torch.clamp((torch.sqrt(d2) - 8.0) / 4.0, 0.0, 1.0)
            theta = 1.0 - 3.0 * s.square() + 2.0 * s.square() * s
            cut_energy = float(self.energy(theta * q, theta * v, coupling))
            cut_charge = float((weighted * theta.square()).sum())
            result.extend((mass, center, core_mass, fraction, rms, f2_mean, cut_energy, cut_charge))
        values = np.asarray(result, dtype=np.float64)
        if not np.all(np.isfinite(values)):
            raise FloatingPointError("nonfinite scalar diagnostics")
        return values

    def initial(self, arm: str) -> tuple[torch.Tensor, torch.Tensor, float, float]:
        q = torch.zeros((3, self.nr, self.nz), dtype=torch.float64, device="cuda")
        if arm != "vacuum":
            shape = torch.exp(-(self.r2 + self.axial[None, :].square()) / (2.0 * WIDTH ** 2))
            shape *= math.sqrt(M0 / float((self.volume * shape.square()).sum()))
            wave_number = 0.0 if arm == "common_phase" else (-0.5 if arm == "conjugate" else 0.5)
            q[1] = shape * torch.cos(wave_number * self.axial)
            q[2] = shape * torch.sin(wave_number * self.axial)
        return q, torch.zeros_like(q), (0.0 if arm == "uncoupled" else HC), (-1.0 if arm == "conjugate" else 1.0)


def save_npz(path: Path, **arrays: np.ndarray) -> dict:
    for name, value in arrays.items():
        if np.asarray(value).dtype.kind in "fci" and not np.all(np.isfinite(value)):
            raise FloatingPointError(f"nonfinite saved array: {name}")
    with path.open("xb") as stream:
        np.savez_compressed(stream, **arrays)
    return {"path": path.name, "sha256": sha(path)}


def save_state(path: Path, grid: CylindricalGrid, q: torch.Tensor, v: torch.Tensor, current_time: float) -> dict:
    return save_npz(path, fields=q.cpu().numpy(), velocities=v.cpu().numpy(),
                    r=grid.r.cpu().numpy(), axial=grid.axial.cpu().numpy(), volume=grid.volume.cpu().numpy(), time=np.asarray(current_time))


def diagnostic_scales(initial_energy: float) -> np.ndarray:
    scales = np.full(len(NAMES), QREF, dtype=np.float64)
    for index in (0, 14, 22):
        scales[index] = max(1.0, abs(initial_energy))
    for index in (9, 12, 17, 20):
        scales[index] = WIDTH
    for index in (6, 7, 11, 13, 19, 21):
        scales[index] = 1.0
    return scales


def formation(trace: np.ndarray, times: np.ndarray, radius: float) -> bool:
    late = trace[times >= 32.0]
    return bool(np.all(
        (late[:, 9] > 12.0) & (late[:, 9] < radius - 12.0)
        & (late[:, 17] < -12.0) & (late[:, 17] > -radius + 12.0)
        & (late[:, 15] >= QREF / 2.0) & (late[:, 23] <= -QREF / 2.0)
        & (late[:, 11] >= 0.6) & (late[:, 19] >= 0.6)
        & (late[:, 13] <= 0.5) & (late[:, 21] <= 0.5)
        & (late[:, 14] <= 0.98 * OMEGA_INF * np.abs(late[:, 15]))
        & (late[:, 22] <= 0.98 * OMEGA_INF * np.abs(late[:, 23]))
    ))


def run_row(grid_name: str, grid: CylindricalGrid, dt: float, arm: str, output: Path) -> dict:
    started = time.perf_counter()
    prefix = f"{grid_name}_{arm}"
    q, v, coupling, orientation = grid.initial(arm)
    acc = grid.acceleration(q, coupling)
    times = np.arange(1537, dtype=np.float64) / 32.0
    trace = np.empty((times.size, len(NAMES)), dtype=np.float64)
    trace[0] = grid.diagnostics(q, v, acc, coupling, orientation)
    files = [save_state(output / f"{prefix}_t000.npz", grid, q, v, 0.0)]
    state_names = [files[-1]["path"]]
    initial_energy = float(trace[0, 0])
    sample_steps = round(1.0 / (32.0 * dt))
    steps = round(48.0 / dt)
    sample = 0
    exact_vacuum = True
    try:
        for step in range(1, steps + 1):
            for weight in YOSHIDA:
                h = weight * dt
                v.add_(acc, alpha=h / 2.0)
                q.add_(v, alpha=h)
                acc = grid.acceleration(q, coupling)
                v.add_(acc, alpha=h / 2.0)
            if step % sample_steps == 0:
                sample += 1
                trace[sample] = grid.diagnostics(q, v, acc, coupling, orientation)
                if arm == "vacuum":
                    exact_vacuum = exact_vacuum and bool(torch.count_nonzero(q) == 0) and bool(torch.count_nonzero(v) == 0)
                current_time = step * dt
                if current_time in (32.0, 40.0, 48.0):
                    files.append(save_state(output / f"{prefix}_t{int(current_time):03d}.npz", grid, q, v, current_time))
                    state_names.append(files[-1]["path"])
                if current_time % 8.0 == 0.0:
                    print(json.dumps({"grid": grid_name, "arm": arm, "time": current_time,
                                      "elapsed_seconds": time.perf_counter() - started}), flush=True)
    except Exception:
        save_npz(output / f"{prefix}_partial_trace.npz", time=times[:sample], diagnostics=trace[:sample], names=np.asarray(NAMES))
        raise
    files.append(save_npz(output / f"{prefix}_trace.npz", time=times, diagnostics=trace, names=np.asarray(NAMES)))
    energy_drift = float(np.max(np.abs(trace[:, 0] - initial_energy)) / max(1.0, abs(initial_energy)))
    charge_drift = float(np.max(np.abs(trace[:, 1])) / QREF)
    failures = []
    if energy_drift >= 2.0e-4:
        failures.append("energy_drift")
    if charge_drift >= 1.0e-8:
        failures.append("global_charge")
    if float(trace[:, 6].max()) >= 1.0e-10:
        failures.append("half_charge_continuity")
    if float(trace[:, 7].max()) >= 1.0e-10:
        failures.append("reflection")
    if arm == "common_phase" and float(trace[:, 2].max()) / QREF >= 1.0e-10:
        failures.append("common_phase_charge")
    if arm == "vacuum" and (not exact_vacuum or np.any(trace[:, :3] != 0.0)):
        failures.append("vacuum_invariance")
    if arm == "uncoupled":
        for energy_index, charge_index in ((14, 15), (22, 23)):
            if np.any(trace[:, energy_index] < OMEGA_INF * np.abs(trace[:, charge_index]) - 1.0e-10 * max(1.0, abs(initial_energy))):
                failures.append(f"uncoupled_bound_{energy_index}")
    row = {"grid": grid_name, "arm": arm, "R": grid.R, "spacing": grid.h, "dt": dt,
           "initial_energy": initial_energy, "trace": f"{prefix}_trace.npz", "states": state_names,
           "files": files, "qualified": not failures, "failures": failures,
           "energy_drift": energy_drift, "charge_drift": charge_drift,
           "late_means": trace[times >= 32.0].mean(axis=0).tolist(),
           "formation": formation(trace, times, grid.R), "elapsed_seconds": time.perf_counter() - started}
    write_json(output / f"{prefix}_row.json", row)
    print(json.dumps({"completed": prefix, "qualified": row["qualified"], "formation": row["formation"],
                      "failures": failures, "elapsed_seconds": row["elapsed_seconds"]}), flush=True)
    return row


def conjugate_checks(output: Path, rows: list[dict]) -> list[dict]:
    by_arm = {row["arm"]: row for row in rows if row["grid"] == "G0"}
    if not {"coupled", "conjugate"}.issubset(by_arm):
        return [{"kind": "conjugate", "pass": False, "error": "missing rows"}]
    results = []
    parity = np.asarray([1.0, 1.0, -1.0])[:, None, None]
    for time_index in (0, 32, 40, 48):
        with np.load(output / f"G0_coupled_t{time_index:03d}.npz", allow_pickle=False) as base, np.load(output / f"G0_conjugate_t{time_index:03d}.npz", allow_pickle=False) as conjugate:
            dq = conjugate["fields"] - parity * base["fields"]
            dv = (conjugate["velocities"] - parity * base["velocities"]) / OMEGA_INF
            volume = base["volume"]
            norm = math.sqrt(float(np.sum(volume * (base["fields"] ** 2 + (base["velocities"] / OMEGA_INF) ** 2))))
            error = math.sqrt(float(np.sum(volume * (dq ** 2 + dv ** 2)))) / max(math.sqrt(M0), norm)
            results.append({"kind": "conjugate", "time": time_index, "normalized_error": error, "pass": error < 1.0e-10})
    return results


def grid_comparisons(rows: list[dict]) -> list[dict]:
    indexed = {(r["grid"], r["arm"]): r for r in rows}
    comparisons = []
    for arm in ("coupled", "uncoupled"):
        for left, right, tolerance in (("G0", "G1", 0.05), ("G0", "G2", 0.05), ("G1", "T1", 0.01)):
            if (left, arm) not in indexed or (right, arm) not in indexed:
                comparisons.append({"kind": "grid", "left": left, "right": right, "arm": arm, "pass": False, "error": "missing rows"})
                continue
            arow, brow = indexed[left, arm], indexed[right, arm]
            errors = np.abs(np.asarray(arow["late_means"]) - np.asarray(brow["late_means"])) / diagnostic_scales(arow["initial_energy"])
            comparisons.append({"kind": "grid", "left": left, "right": right, "arm": arm,
                                "normalized_errors": errors.tolist(), "maximum_error": float(errors.max()),
                                "failed_columns": [NAMES[i] for i in np.flatnonzero(errors >= tolerance)],
                                "pass": bool(np.all(errors < tolerance))})
    return comparisons


@torch.no_grad()
def run(manifest_path: Path, output: Path) -> dict:
    manifest = validate_manifest(manifest_path)
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    output.mkdir(parents=True, exist_ok=False)
    write_exclusive(output / "manifest.json", manifest_path.read_bytes())
    rows, comparisons, errors = [], [], []
    if not torch.cuda.is_available():
        raise RuntimeError("the frozen primary requires the qualified float64 ROCm device")
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    for grid_name, radius, spacing, dt, arms in SCHEDULE:
        grid = CylindricalGrid(radius, spacing)
        for arm in arms:
            try:
                rows.append(run_row(grid_name, grid, dt, arm, output))
            except Exception as error:
                record = {"grid": grid_name, "arm": arm, "error": f"{type(error).__name__}: {error}"}
                errors.append(record)
                write_json(output / f"{grid_name}_{arm}_error.json", record)
                print(json.dumps(record), flush=True)
        del grid
    comparisons.extend(conjugate_checks(output, rows))
    comparisons.extend(grid_comparisons(rows))
    numeric_pass = len(rows) == 11 and not errors and all(row["qualified"] for row in rows) and all(item["pass"] for item in comparisons)
    result = {"schema": SCHEMA, "manifest_sha256": sha(manifest_path), "source_sha256": sha(SELF),
              "rows": rows, "comparisons": comparisons, "errors": errors, "names": list(NAMES),
              "numeric_pass": bool(numeric_pass), "verdict": "PASS" if numeric_pass else "INCONCLUSIVE",
              "environment": {"python": sys.version, "numpy": np.__version__, "torch": torch.__version__,
                              "hip": torch.version.hip, "device": torch.cuda.get_device_name(0)},
              "complete_physical_matter_formation": False}
    write_json(output / "summary.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run(args.manifest.resolve(), args.output.resolve())
        print(json.dumps({"schema": SCHEMA, "rows": len(result["rows"]), "numeric_pass": result["numeric_pass"],
                          "verdict": result["verdict"], "complete_physical_matter_formation": False}), flush=True)
        return 0 if result["numeric_pass"] else 1
    except Exception as error:
        print(json.dumps({"schema": SCHEMA, "numeric_pass": False, "verdict": "INCONCLUSIVE",
                          "error": f"{type(error).__name__}: {error}", "complete_physical_matter_formation": False}), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
