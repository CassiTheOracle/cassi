#!/usr/bin/env python3
"""Independent verifier for §§74-75: stationary pool profiles and pool dispersal.

This program imports no numerical implementation from
``matter_formation_pool_profiles.py``, ``matter_formation_pool_dispersal.py``,
``matter_formation_neutral_packets.py``, ``matter_formation_radial.py`` or
``matter_formation_radial_cloud.py``.  Every discrete operator below - the
spherical finite-volume pool energy, the §74.2 stationarity residuals, the
axisymmetric finite-volume Laplacian and Hamiltonian assembled as face-flux
divergences, the compact cutoff energy, the axial momentum and the classical
RK4 advance - is re-derived from the §74.2 / §75.1-75.3 continuum formulas and
assembled independently in float64.

Modes
  --profiles-only  reconstruct all twelve stationary profiles and every profile
                   prerequisite, write the receipt and exit without evolution.
  full             additionally run the ten prescribed axisymmetric evolutions
                   with RK4 and reconcile them against the primary evidence and
                   the profile archive given by --input / --profiles.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import math
import platform
import time
from pathlib import Path
from typing import Any

import numpy as np
from scipy.interpolate import PchipInterpolator

try:  # The frozen-source gate must be able to hash this file on a host without
    import torch  # the GPU stack; the evolution schedule reports its own refusal.
except ImportError:  # pragma: no cover
    torch = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
REPORT = "computations/matter-formation-continuum-report.md"

MANIFEST_SCHEMA = "matter-formation-pool-dispersal-manifest-v1"
PROFILES_SCHEMA = "matter-formation-pool-profiles-v1"
PRIMARY_SCHEMA = "matter-formation-pool-dispersal-primary-v1"
SCHEMA = "matter-formation-pool-dispersal-verification-v1"
HEADING_74 = "## 74. Working notes: dispersal of a self-bound field pool"
HEADING_75 = "## 75. Working notes: controlled pool-dispersal experiment"
HEADINGS = (HEADING_74, HEADING_75)

# Frozen coefficients (§74.1).
A = 1.0 / 16.0
CPSI = 1.0 / 8.0
URHO = 4.0
UC = 1.0
K = 1.0
EC = 0.75
HC = 2.9598260763447164
# §74.2's B is exactly e_C + 1/(4a) for these kept coefficients.  Adding N/(4a)
# to the §74.3 spatial core (which carries (e_C - h_C + h_C f^2)c^2) therefore
# promotes it to the boxed (B - h_C + h_C f^2)c^2.  Both readings of the pool
# functional are computed below and required to agree, rather than being typed
# in by hand.
B = EC + 1.0 / (4.0 * A)
OMEGA_INF = math.sqrt(B / A)
SPEED2 = 8.0
Q_PARENT = 512.0
Q_DAUGHTER = 256.0
N0 = math.sqrt(URHO / (2.0 * UC))
OMEGA_0 = math.sqrt((B - HC + math.sqrt(URHO * UC / 2.0)) / A)
assert B == 4.75 and SPEED2 == 1.0 / CPSI == K / (2.0 * A)

CORE_RADIUS = 8.0
CUT_INNER = 8.0
CUT_WIDTH = 4.0
CUT_OUTER = 12.0
CORE_RADIUS2 = CORE_RADIUS * CORE_RADIUS

# §74.3 stationary-profile registries.
PROFILE_GRIDS = {"S0": (24.0, 0.125), "S1": (24.0, 0.0625), "S2": (48.0, 0.0625)}
PROFILE_SEEDS = {"s0": 0.8, "s1": 1.2}
PROFILE_CHARGES = (Q_DAUGHTER, Q_PARENT)
PROFILE_KEYS = tuple(f"q{int(q)}_{gid}_{sid}"
                     for q in PROFILE_CHARGES for gid in PROFILE_GRIDS for sid in PROFILE_SEEDS)
PROFILE_ARRAYS = ("r", "volume", "f", "c", "Q", "omega", "energy", "R", "spacing")
PROFILE_SCALARS = ("Q", "R", "spacing", "omega", "energy", "population", "rms",
                   "outer_fraction", "residual_f", "residual_c", "charge_error")
PROFILE_ROW_FIELDS = ("key", "Q", "grid", "seed", "R", "spacing", "omega", "energy", "population",
                      "rms", "outer_fraction", "residual_f", "residual_c", "charge_error",
                      "archive", "archive_sha256", "qualified", "optimizer")
SELECTED = {"Q256": "q256_S1_s0", "Q512": "q512_S1_s0"}

# §75.3 frozen evolution schedule: ten rows per method.
HOLD, WEAK, STRONG, UNCOUPLED = "hold", "weak", "strong", "uncoupled"
ARMS = {HOLD: (0.0, HC), WEAK: (0.5, HC), STRONG: (1.5, HC), UNCOUPLED: (1.5, 0.0)}
GRIDS = {"G0": (112, 0.25, 1.0 / 256.0), "G1": (112, 0.125, 1.0 / 256.0),
         "G2": (160, 0.25, 1.0 / 256.0), "T1": (112, 0.125, 1.0 / 512.0)}
SCHEDULE = (("G0", (HOLD, WEAK, STRONG, UNCOUPLED)),
            ("G1", (HOLD, WEAK, STRONG, UNCOUPLED)),
            ("G2", (STRONG,)),
            ("T1", (STRONG,)))
ROW_KEYS = tuple(f"{grid}_{arm}" for grid, arms in SCHEDULE for arm in arms)
T_FINAL = 32.0
SAMPLE_DT = 0.125
SNAPSHOT_TIMES = (0.0, 24.0, 32.0)
LATE_START = 24.0
SAMPLE_COUNT = int(round(T_FINAL / SAMPLE_DT)) + 1
TRACE_TIMES = np.arange(SAMPLE_COUNT, dtype=np.float64) * SAMPLE_DT

HALF_NAMES = ("positive_charge", "center", "core_fraction", "core_rms", "core_f2",
              "cut_charge", "cut_energy", "cut_momentum", "cut_radicand",
              "binding_ratio", "clearance")
TRACE_NAMES = ("energy", "charge", "charge_l1", "rms", "reflection") + tuple(
    f"{side}_{name}" for side in ("right", "left") for name in HALF_NAMES)
COLUMN_COUNT = len(TRACE_NAMES)
INDEX = {name: position for position, name in enumerate(TRACE_NAMES)}
RIGHT_OFFSET = INDEX["right_positive_charge"]
LEFT_OFFSET = INDEX["left_positive_charge"]

# Declared fixed units (§75.3).
ENERGY_LIKE = (INDEX["energy"], INDEX["right_cut_energy"], INDEX["left_cut_energy"])
CHARGE_LIKE = tuple(position for position, name in enumerate(TRACE_NAMES) if "charge" in name)
LENGTH_LIKE = (INDEX["rms"], INDEX["right_center"], INDEX["right_core_rms"], INDEX["right_clearance"],
               INDEX["left_center"], INDEX["left_core_rms"], INDEX["left_clearance"])
MOMENTUM_LIKE = (INDEX["right_cut_momentum"], INDEX["left_cut_momentum"])
RADICAND_LIKE = (INDEX["right_cut_radicand"], INDEX["left_cut_radicand"])
_CLASSIFIED = set(ENERGY_LIKE) | set(LENGTH_LIKE) | set(CHARGE_LIKE) | set(MOMENTUM_LIKE) | set(RADICAND_LIKE)
DIMENSIONLESS = tuple(position for position in range(COLUMN_COUNT) if position not in _CLASSIFIED)
assert len(_CLASSIFIED) + len(DIMENSIONLESS) == COLUMN_COUNT
assert not (_CLASSIFIED & set(DIMENSIONLESS))
assert INDEX["right_core_f2"] in DIMENSIONLESS and INDEX["left_core_f2"] in DIMENSIONLESS
assert INDEX["right_cut_energy"] == RIGHT_OFFSET + 6 and INDEX["left_cut_energy"] == LEFT_OFFSET + 6
assert INDEX["right_cut_radicand"] == RIGHT_OFFSET + 8 and INDEX["left_cut_radicand"] == LEFT_OFFSET + 8

# Declared tolerances.  Nothing here is tunable at run time.
TOL_RECONSTRUCTION = 1.0e-9
TOL_CHARGE_RECONSTRUCTION = 1.0e-10
TOL_PROFILE_RESIDUAL = 1.0e-5
TOL_PROFILE_OUTER = 1.0e-6
PROFILE_BINDING_FRACTION = 0.999
TOL_SEED = 1.0e-5
TOL_REFINEMENT = 2.0e-3
TOL_DOMAIN = 1.0e-5
TOL_ENERGY_DRIFT = 2.0e-4
TOL_CHARGE_DRIFT = 2.0e-5
TOL_REFLECTION = 1.0e-10
TOL_HOLD_RMS = 2.0e-2
TOL_UNCOUPLED_MASS = 1.0e-8
TOL_DIAGNOSTIC_MEAN = 0.05
TOL_STATE_SNAPSHOT = 1.0e-2
FORMATION_LATE_SAMPLES = 65
FORMATION_CHARGE = 128.0
FORMATION_FRACTION = 0.6
FORMATION_RMS = 6.0
FORMATION_F2 = 0.5
FORMATION_BINDING = 0.98
FORMATION_CENTER = 12.0
FORMATION_CLEARANCE = 16.0

VERDICT_EMERGES = "EMERGES—conditional smaller pools from one dispersed pool"
VERDICT_NO_EMERGE = "DOES NOT EMERGE in the specified pool-dispersal calculation"
VERDICT_INCONCLUSIVE = "INCONCLUSIVE"
PROFILES_SUCCESS = "SUPPORTS-conditional stationary pool references"
VERDICT_PROFILES_ONLY = "PROFILES-" + PROFILES_SUCCESS


class ContractError(RuntimeError):
    """Frozen input, schema or provenance rejection."""


def no_grad() -> Any:
    return torch.no_grad() if torch is not None else contextlib.nullcontext()


def grid_name(key: str) -> str:
    return key.split("_", 1)[0]


# --------------------------------------------------------------------------- #
# provenance
# --------------------------------------------------------------------------- #
def raw_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_bytes(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def canonical_section(text: str, heading: str) -> bytes:
    """Heading through the next H2, CRLF/CR normalised, trailing whitespace
    stripped once, exactly one terminating newline."""
    normalized = canonical_bytes(text.encode("utf-8")).decode("utf-8")
    lines = normalized.splitlines(keepends=True)
    marks = [position for position, line in enumerate(lines) if line.rstrip() == heading]
    if len(marks) != 1:
        raise ContractError(f"section heading must occur exactly once: {heading}")
    following = [position for position in range(marks[0] + 1, len(lines))
                 if lines[position].startswith("## ")]
    end = following[0] if following else len(lines)
    return (''.join(lines[marks[0]:end]).rstrip() + "\n").encode("utf-8")


def safe_relative(root: Path, value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ContractError(f"{label} must be a non-empty string")
    candidate = Path(value)
    if candidate.is_absolute():
        raise ContractError(f"{label} must be repository-relative: {value}")
    resolved = (root / candidate).resolve()
    if root not in resolved.parents:
        raise ContractError(f"{label} escapes the repository: {value}")
    return resolved


def strict_json(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ContractError(f"missing JSON receipt: {path.name}") from exc

    def pairs_hook(items: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in items:
            if key in out:
                raise ContractError(f"duplicate JSON key {key} in {path.name}")
            out[key] = value
        return out

    value = json.loads(text, object_pairs_hook=pairs_hook)
    if not isinstance(value, dict):
        raise ContractError(f"{path.name} must be a JSON object")
    return value


def finite(value: Any) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return True
    if isinstance(value, (int, float, np.integer, np.floating)):
        return math.isfinite(float(value))
    if isinstance(value, np.ndarray):
        if value.dtype.kind in "fci":
            return bool(np.all(np.isfinite(value)))
        return all(finite(item) for item in value.tolist())
    if isinstance(value, (list, tuple)):
        return all(finite(item) for item in value)
    if isinstance(value, dict):
        return all(finite(item) for item in value.values())
    if value is None or isinstance(value, str):
        return True
    raise ContractError(f"unsupported JSON leaf {type(value).__name__}")


def jsonable(value: Any) -> Any:
    if isinstance(value, (bool, np.bool_)) or value is None or isinstance(value, str):
        return value
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        number = float(value)
        if not math.isfinite(number):
            raise ContractError("non-finite JSON number")
        return number
    if isinstance(value, np.ndarray):
        return jsonable(value.tolist())
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    raise ContractError(f"unsupported JSON value {type(value).__name__}")


def write_json(path: Path, value: dict[str, Any]) -> None:
    if not finite(value):
        raise ContractError(f"non-finite JSON payload at {path.name}")
    payload = (json.dumps(jsonable(value), ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode("utf-8")
    with path.open("xb") as stream:
        stream.write(payload)


def save_npz(path: Path, **arrays: np.ndarray) -> dict[str, Any]:
    for name, value in arrays.items():
        raw = np.asarray(value)
        if raw.dtype.kind in "fci" and not bool(np.all(np.isfinite(raw))):
            raise FloatingPointError(f"nonfinite saved array: {name}")
    with path.open("xb") as stream:
        np.savez_compressed(stream, **arrays)
    return {"path": path.name, "sha256": raw_sha256(path)}


def require(condition: bool, message: str, failures: list[str]) -> bool:
    if not condition:
        failures.append(message)
    return bool(condition)


def normalized_error(mine: float, theirs: float, scale: float) -> float:
    if not (math.isfinite(mine) and math.isfinite(theirs)):
        return math.inf
    return abs(mine - theirs) / max(1.0, abs(scale))


def number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, np.integer, np.floating)):
        raise ContractError(f"numeric receipt field required, got {value!r}")
    return float(value)


def diagnostic_scales(initial_energy: float) -> np.ndarray:
    """Declared fixed units: energy -> max(1,E0), charge -> 512, lengths -> 12,
    momentum -> E0/sqrt(8), radicand -> E0^2, all else -> 1."""
    energy_scale = max(1.0, abs(initial_energy))
    scales = np.ones(COLUMN_COUNT, dtype=np.float64)
    scales[list(ENERGY_LIKE)] = energy_scale
    scales[list(CHARGE_LIKE)] = Q_PARENT
    scales[list(LENGTH_LIKE)] = CUT_OUTER
    scales[list(MOMENTUM_LIKE)] = energy_scale / math.sqrt(SPEED2)
    scales[list(RADICAND_LIKE)] = energy_scale ** 2
    return scales


def verify_manifest(path: Path) -> tuple[dict[str, Any], str]:
    manifest = strict_json(path)
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise ContractError("manifest schema mismatch")
    sections = manifest.get("sections")
    if not isinstance(sections, list) or len(sections) != len(HEADINGS):
        raise ContractError("manifest must seal §74 and §75 exactly")
    live_text = (ROOT / REPORT).read_text(encoding="utf-8")
    seen: list[str] = []
    for record in sections:
        if not isinstance(record, dict):
            raise ContractError("malformed manifest section record")
        heading = record.get("heading")
        if heading not in HEADINGS:
            raise ContractError(f"unexpected manifest heading: {heading!r}")
        seen.append(heading)
        expected = record.get("sha256")
        source = safe_relative(ROOT, record.get("path"), "manifest section path")
        if source != (ROOT / REPORT).resolve():
            raise ContractError("manifest section path must be the continuum report")
        live = canonical_section(live_text, heading)
        if hashlib.sha256(live).hexdigest() != expected:
            raise ContractError(f"live section differs from the manifest hash: {heading}")
        snapshot = safe_relative(ROOT, record.get("snapshot"), "manifest section snapshot")
        frozen = snapshot.read_bytes()
        if raw_sha256(snapshot) != expected or canonical_bytes(frozen) != live:
            raise ContractError(f"frozen section differs from the live section: {heading}")
    if sorted(seen) != sorted(HEADINGS):
        raise ContractError("manifest must seal both §74 and §75 exactly once")
    sources = manifest.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ContractError("manifest source inventory missing")
    own = str(SELF.resolve().relative_to(ROOT)).replace("\\", "/")
    listed: list[str] = []
    for record in sources:
        if not isinstance(record, dict):
            raise ContractError("malformed manifest source record")
        entry = safe_relative(ROOT, record.get("path"), "manifest source path")
        if raw_sha256(entry) != record.get("sha256"):
            raise ContractError(f"source identity mismatch: {record.get('path')}")
        listed.append(str(entry.relative_to(ROOT)).replace("\\", "/"))
    required = {
        "computations/matter_formation_pool_profiles.py",
        "computations/matter_formation_pool_dispersal.py",
        "computations/verify_matter_formation_pool_dispersal.py",
        "computations/matter_formation_radial.py",
        "computations/matter_formation_radial_cloud.py",
        "computations/matter_formation_neutral_packets.py",
    }
    if own not in listed or len(listed) != len(set(listed)) or not required.issubset(listed):
        raise ContractError("source inventory incomplete or duplicated")
    return manifest, raw_sha256(path)


# --------------------------------------------------------------------------- #
# §74.2/§74.3 independent spherical finite volume
# --------------------------------------------------------------------------- #
class SphericalPool:
    """Cell-centred spherical finite volume with exact shell volumes and the
    Dirichlet exterior values f(R)=1, c(R)=0 held half a spacing beyond the last
    centre, so every face contributes area/distance."""

    def __init__(self, radius: float, spacing: float) -> None:
        self.R = float(radius)
        self.dr = float(spacing)
        self.n = int(round(self.R / self.dr))
        if self.n < 2 or abs(self.n * self.dr - self.R) > 1.0e-12 * self.R:
            raise ContractError("profile grid does not tile its radius")
        self.faces = np.arange(self.n + 1, dtype=np.float64) * self.dr
        self.r = (np.arange(self.n, dtype=np.float64) + 0.5) * self.dr
        self.volume = (4.0 * math.pi / 3.0) * (self.faces[1:] ** 3 - self.faces[:-1] ** 3)
        self.face_area = 4.0 * math.pi * self.faces[1:-1] ** 2
        self.conductance = self.face_area / self.dr
        self.boundary_conductance = 4.0 * math.pi * self.R ** 2 / (self.dr / 2.0)

    def laplacian(self, u: np.ndarray) -> np.ndarray:
        out = np.zeros_like(u)
        flux = self.conductance * (u[1:] - u[:-1])
        out[:-1] += flux
        out[1:] -= flux
        out[-1] -= self.boundary_conductance * u[-1]
        return out / self.volume

    def gradient_energy(self, u: np.ndarray, weight: float) -> float:
        difference = u[1:] - u[:-1]
        return 0.5 * weight * float(np.dot(self.conductance, difference * difference)
                                    + self.boundary_conductance * u[-1] * u[-1])

    def population(self, c: np.ndarray) -> float:
        return float(np.dot(self.volume, c * c))

    def spatial_energy(self, f: np.ndarray, c: np.ndarray, carrier_core: float) -> float:
        """Gradient plus potential part of §74.2, where carrier_core is B for
        the boxed functional or e_C for the §74.3 staged spatial core."""
        density = (URHO / 4.0 * (f * f - 1.0) ** 2
                   + (carrier_core - HC + HC * f * f) * c * c
                   + UC / 2.0 * c ** 4)
        return (self.gradient_energy(f - 1.0, 1.0) + self.gradient_energy(c, K)
                + float(np.dot(self.volume, density)))

    def temporal_energy(self, population: float, charge: float) -> float:
        if population <= 0.0:
            raise ContractError("carrier population vanished")
        return population / (4.0 * A) + charge * charge / (4.0 * A * population)

    def energies(self, f: np.ndarray, c: np.ndarray, charge: float) -> dict[str, float]:
        population = self.population(c)
        if population <= 0.0:
            raise ContractError(f"carrier population vanished: {charge}")
        boxed = self.spatial_energy(f, c, B) + charge * charge / (4.0 * A * population)
        staged = self.spatial_energy(f, c, EC) + self.temporal_energy(population, charge)
        return {"energy": boxed, "energy_staged_form": staged, "population": population}

    def residuals(self, f: np.ndarray, c: np.ndarray, frequency: float) -> tuple[float, float]:
        """Mass-weighted §74.2 stationary equations, each divided by
        max(1, weighted field norm)."""
        residual_f = -self.laplacian(f - 1.0) + URHO * (f * f - 1.0) * f + 2.0 * HC * f * c * c
        residual_c = (-0.5 * K * self.laplacian(c)
                      + (B - HC + HC * f * f + UC * c * c - A * frequency * frequency) * c)
        norm_f = max(1.0, math.sqrt(float(np.dot(self.volume, (f - 1.0) ** 2))))
        norm_c = max(1.0, math.sqrt(float(np.dot(self.volume, c * c))))
        return (math.sqrt(float(np.dot(self.volume, residual_f * residual_f))) / norm_f,
                math.sqrt(float(np.dot(self.volume, residual_c * residual_c))) / norm_c)

    def moments(self, c: np.ndarray, population: float) -> tuple[float, float]:
        outer = self.r > 0.5 * self.R
        rms = math.sqrt(max(0.0, float(np.dot(self.volume, c * c * self.r * self.r)) / population))
        fraction = float(np.dot(self.volume[outer], c[outer] * c[outer]) / population)
        return rms, fraction

    def eigenvalue_frequency(self, f: np.ndarray, c: np.ndarray) -> float:
        """Rayleigh quotient of the linearised carrier equation; recorded only
        as reconciliation evidence, never used as a criterion."""
        population = self.population(c)
        interior = float(np.dot(self.volume, (B - HC + HC * f * f + UC * c * c) * c * c))
        value = (self.gradient_energy(c, K) + interior) / (A * population)
        return math.sqrt(value) if value > 0.0 else 0.0


def scalar_array(archive: dict[str, np.ndarray], name: str) -> float:
    array = np.asarray(archive[name])
    if array.shape != ():
        raise ContractError(f"profile scalar {name} must be a 0-dimensional array")
    return float(array.item())


def reconstruct_profile(pool: SphericalPool, archive: dict[str, np.ndarray], row: dict[str, Any],
                        failures: list[str]) -> dict[str, Any]:
    key = str(row["key"])
    charge = scalar_array(archive, "Q")
    radius = scalar_array(archive, "R")
    spacing = scalar_array(archive, "spacing")
    f = np.asarray(archive["f"], dtype=np.float64)
    c = np.asarray(archive["c"], dtype=np.float64)
    r = np.asarray(archive["r"], dtype=np.float64)
    volume = np.asarray(archive["volume"], dtype=np.float64)
    for name, array in (("f", f), ("c", c), ("r", r), ("volume", volume)):
        if not bool(np.all(np.isfinite(array))):
            raise ContractError(f"nonfinite raw profile array {name} in {key}")
    if f.shape != (pool.n,) or c.shape != (pool.n,):
        raise ContractError(f"profile field length mismatch for {key}")
    require(charge == number(row["Q"]), f"profile charge mismatch:{key}", failures)
    require(charge in PROFILE_CHARGES, f"profile charge registry:{key}", failures)
    require(radius == pool.R and spacing == pool.dr, f"profile grid scalar mismatch:{key}", failures)
    require(float(row["R"]) == pool.R and float(row["spacing"]) == pool.dr,
            f"profile grid registry:{key}", failures)
    for name, mine, theirs in (("r", pool.r, r), ("volume", pool.volume, volume)):
        error = float(np.max(np.abs(mine - theirs) / np.maximum(1.0, np.abs(mine))))
        require(error < TOL_RECONSTRUCTION, f"profile {name} raw mismatch:{key}:{error:.3e}", failures)
    stored_omega = scalar_array(archive, "omega")
    stored_energy = scalar_array(archive, "energy")
    energies = pool.energies(f, c, charge)
    energy = energies["energy"]
    population = energies["population"]
    omega = charge / (2.0 * A * population)
    reconstructed_charge = 2.0 * A * stored_omega * population
    rms, outer_fraction = pool.moments(c, population)
    residual_f, residual_c = pool.residuals(f, c, stored_omega)
    charge_error = abs(reconstructed_charge - charge) / abs(charge)
    discrepancies = {
        "energy": normalized_error(energy, stored_energy, abs(stored_energy)),
        "energy_forms": normalized_error(energy, energies["energy_staged_form"], abs(stored_energy)),
        "omega": normalized_error(omega, stored_omega, abs(stored_omega)),
        "rms": normalized_error(rms, number(row["rms"]), CUT_OUTER),
        "population": normalized_error(population, number(row["population"]), abs(charge)),
        "outer_fraction": normalized_error(outer_fraction, number(row["outer_fraction"]), 1.0),
        "residual_f": normalized_error(residual_f, number(row["residual_f"]), 1.0),
        "residual_c": normalized_error(residual_c, number(row["residual_c"]), 1.0),
        "charge_error": normalized_error(charge_error, number(row["charge_error"]), 1.0),
    }
    for name, error in discrepancies.items():
        require(error < TOL_RECONSTRUCTION, f"profile reconstruction:{key}:{name}:{error:.3e}", failures)
    require(charge_error < TOL_CHARGE_RECONSTRUCTION,
            f"profile charge reconstruction:{key}:{charge_error:.3e}", failures)
    physical = {
        "finite": True,
        "residual_f": residual_f < TOL_PROFILE_RESIDUAL,
        "residual_c": residual_c < TOL_PROFILE_RESIDUAL,
        "outer_fraction": outer_fraction < TOL_PROFILE_OUTER,
        "bound_energy": energy < PROFILE_BINDING_FRACTION * OMEGA_INF * charge,
        "bound_frequency": omega < PROFILE_BINDING_FRACTION * OMEGA_INF,
        "charge_error": charge_error < TOL_CHARGE_RECONSTRUCTION,
    }
    qualified = all(physical.values())
    require(qualified == bool(row["qualified"]), f"profile qualification mismatch:{key}:{physical}", failures)
    return {
        "key": key, "Q": charge, "grid": str(row["grid"]), "seed": number(row["seed"]),
        "R": radius, "spacing": spacing, "cells": pool.n, "archive": str(row["archive"]),
        "energy": energy, "energy_staged_form": energies["energy_staged_form"],
        "population": population, "omega": omega, "omega_stored": stored_omega,
        "omega_eigenvalue_form": pool.eigenvalue_frequency(f, c),
        "rms": rms, "outer_fraction": outer_fraction,
        "residual_f": residual_f, "residual_c": residual_c,
        "charge_reconstructed": reconstructed_charge, "charge_error": charge_error,
        "discrepancies": discrepancies, "physical": physical, "qualified": qualified,
        "stored": {name: row[name] for name in PROFILE_ROW_FIELDS},
        "optimizer": row.get("optimizer"),
    }


# --------------------------------------------------------------------------- #
# §75 independent axisymmetric finite volume
# --------------------------------------------------------------------------- #
def pick_device() -> str:
    if torch is None:
        raise ContractError("torch is unavailable; the evolution schedule cannot run")
    return "cuda" if torch.cuda.is_available() else "cpu"


class CylindricalPool:
    """Axisymmetric cell-centred finite volume for d^3x -> 2*pi*r dr dzeta.

    An interior radial face is a cylindrical band of area 2*pi*r_face*h whose
    neighbouring centres are h apart, so its conductance is 2*pi*r_face.  An
    axial face is an annulus of area volume/h and contributes volume/h^2.  The
    axis face has zero area, so regularity is automatic.  Every Dirichlet outer
    value sits half a spacing beyond the last centre, hence 2*area/spacing:
    4*pi*R for the cylindrical boundary and 2*volume/h^2 for the end annuli."""

    def __init__(self, radius: int, spacing: float, device: str) -> None:
        if torch is None:
            raise ContractError("torch is required")
        self.R = float(radius)
        self.h = float(spacing)
        self.nr = int(round(self.R / self.h))
        if self.nr * self.h != self.R:
            raise ContractError("evolution grid does not tile its radius")
        self.nz = 2 * self.nr
        self.mid = self.nz // 2
        self.device = device
        dtype = torch.float64
        index_r = torch.arange(self.nr, dtype=dtype, device=device)
        index_z = torch.arange(self.nz, dtype=dtype, device=device)
        self.r = (index_r + 0.5) * self.h
        self.axial = (index_z - self.nr + 0.5) * self.h
        faces = torch.arange(self.nr + 1, dtype=dtype, device=device) * self.h
        self.volume = (math.pi * (faces[1:] ** 2 - faces[:-1] ** 2) * self.h)[:, None]
        self.radial_face = (2.0 * math.pi * faces[1:-1])[None, :, None]
        self.axial_face = self.volume / self.h ** 2
        self.outer_radial = 4.0 * math.pi * self.R
        self.outer_axial = 2.0 * self.volume / self.h ** 2
        component = torch.tensor([1.0, K, K], dtype=dtype, device=device)
        self.component = component[:, None, None]
        self.component2 = component[:, None]
        self.r2 = self.r[:, None] ** 2
        self.distance2 = self.r2 + self.axial[None, :] ** 2
        self.right = (self.axial[None, :] > 0.0).to(dtype)
        self.left = (self.axial[None, :] < 0.0).to(dtype)
        self.shape = (3, self.nr, self.nz)

    def laplacian(self, q: Any) -> Any:
        out = torch.zeros_like(q)
        radial = self.radial_face * (q[:, 1:, :] - q[:, :-1, :])
        out[:, :-1, :] += radial
        out[:, 1:, :] -= radial
        out[:, -1, :] -= self.outer_radial * q[:, -1, :]
        axial = self.axial_face * (q[:, :, 1:] - q[:, :, :-1])
        out[:, :, :-1] += axial
        out[:, :, 1:] -= axial
        out[:, :, 0] -= self.outer_axial[:, 0][None, :] * q[:, :, 0]
        out[:, :, -1] -= self.outer_axial[:, 0][None, :] * q[:, :, -1]
        return out / self.volume

    def acceleration(self, q: Any, coupling: float) -> Any:
        laplacian = self.laplacian(q)
        f = q[0] + 1.0
        density = q[1] * q[1] + q[2] * q[2]
        coefficient = B - coupling + coupling * f * f + UC * density
        out = torch.empty_like(q)
        out[0] = (laplacian[0] - URHO * (f * f - 1.0) * f - 2.0 * coupling * f * density) / CPSI
        out[1] = (0.5 * K * laplacian[1] - coefficient * q[1]) / A
        out[2] = (0.5 * K * laplacian[2] - coefficient * q[2]) / A
        return out

    def gradient_energy(self, q: Any) -> Any:
        radial = q[:, 1:, :] - q[:, :-1, :]
        axial = q[:, :, 1:] - q[:, :, :-1]
        total = (self.component * self.radial_face * radial * radial).sum()
        total = total + (self.component * self.axial_face * axial * axial).sum()
        total = total + self.outer_radial * (self.component2 * q[:, -1, :] * q[:, -1, :]).sum()
        ends = self.outer_axial[:, 0] * (q[:, :, 0] * q[:, :, 0] + q[:, :, -1] * q[:, :, -1])
        total = total + (self.component2 * ends).sum()
        return 0.5 * total

    def energy(self, q: Any, v: Any, coupling: float) -> Any:
        f = q[0] + 1.0
        density = q[1] * q[1] + q[2] * q[2]
        potential = (URHO / 4.0 * (f * f - 1.0) ** 2
                     + (B - coupling + coupling * f * f) * density
                     + UC / 2.0 * density * density)
        kinetic = CPSI / 2.0 * v[0] * v[0] + A * (v[1] * v[1] + v[2] * v[2])
        return ((potential + kinetic) * self.volume).sum() + self.gradient_energy(q)

    def norm(self, q: Any, v: Any) -> Any:
        scaled = v / OMEGA_INF
        return torch.sqrt(((q * q + scaled * scaled) * self.volume).sum())

    def axial_derivative(self, q: Any) -> Any:
        out = torch.empty_like(q)
        step = 2.0 * self.h
        out[:, :, 1:-1] = (q[:, :, 2:] - q[:, :, :-2]) / step
        out[:, :, 0] = (q[:, :, 1] + q[:, :, 0]) / step
        out[:, :, -1] = -(q[:, :, -1] + q[:, :, -2]) / step
        return out

    def cutoff(self, center: Any) -> Any:
        distance = torch.sqrt(self.r2 + (self.axial[None, :] - center) ** 2)
        soft = torch.clamp((distance - CUT_INNER) / CUT_WIDTH, 0.0, 1.0)
        return 1.0 - 3.0 * soft * soft + 2.0 * soft * soft * soft

    def momentum(self, q: Any, v: Any) -> Any:
        derivative = self.axial_derivative(q)
        integrand = (CPSI * v[0] * derivative[0]
                     + 2.0 * A * (v[1] * derivative[1] + v[2] * derivative[2]))
        return -(self.volume * integrand).sum()

    def diagnostics(self, q: Any, v: Any, coupling: float) -> np.ndarray:
        density = -2.0 * A * (q[1] * v[2] - q[2] * v[1])
        weighted = self.volume * density
        positive = torch.clamp_min(density, 0.0)
        total_positive = (self.volume * positive).sum()
        energy = float(self.energy(q, v, coupling))
        charge = float(weighted.sum())
        charge_l1 = float(weighted.abs().sum())
        if total_positive > 0.0:
            rms = float(torch.sqrt(torch.clamp_min(
                (self.volume * positive * self.distance2).sum() / total_positive, 0.0)))
        else:
            rms = 0.0
        reflection = float(self.norm(q - q.flip(-1), v - v.flip(-1))
                           / max(1.0, float(self.norm(q, v))))
        values = [energy, charge, charge_l1, rms, reflection]
        zero = torch.zeros((), dtype=torch.float64, device=q.device)
        for mask in (self.right, self.left):
            charged = positive * mask
            mass = (self.volume * charged).sum()
            center = ((self.volume * charged * self.axial[None, :]).sum() / mass
                      if mass > 0.0 else zero)
            distance2 = self.r2 + (self.axial[None, :] - center) ** 2
            core = (distance2 < CORE_RADIUS2) & (charged > 0.0)
            core_density = charged * core
            core_mass = (self.volume * core_density).sum()
            if mass > 0.0 and core_mass > 0.0:
                fraction = core_mass / mass
                core_rms = torch.sqrt(torch.clamp_min(
                    (self.volume * core_density * distance2).sum() / core_mass, 0.0))
                core_f2 = (self.volume * core_density * (q[0] + 1.0) ** 2).sum() / core_mass
            else:
                fraction = core_rms = core_f2 = zero
            theta = self.cutoff(center)
            masked_q = theta * q
            masked_v = theta * v
            cut_energy = float(self.energy(masked_q, masked_v, coupling))
            cut_charge = float((weighted * theta * theta).sum())
            cut_momentum = float(self.momentum(masked_q, masked_v))
            radicand = cut_energy * cut_energy - SPEED2 * cut_momentum * cut_momentum
            numeric_center = float(center)
            binding = (math.sqrt(radicand) / (OMEGA_INF * cut_charge)
                       if cut_charge > 0.0 and radicand >= 0.0 else 0.0)
            clearance = min(self.R - CUT_OUTER, self.R - abs(numeric_center) - CUT_OUTER)
            values.extend([float(mass), numeric_center, float(fraction), float(core_rms),
                           float(core_f2), cut_charge, cut_energy, cut_momentum, radicand,
                           binding, clearance])
        array = np.asarray(values, dtype=np.float64)
        if array.shape != (COLUMN_COUNT,):
            raise ContractError("diagnostic column count mismatch")
        if not bool(np.all(np.isfinite(array))):
            raise FloatingPointError("nonfinite diagnostic vector")
        return array


# --------------------------------------------------------------------------- #
# §75.1 preparation
# --------------------------------------------------------------------------- #
def load_selected_profile(profile_dir: Path, rows: list[dict[str, Any]], key: str,
                          failures: list[str]) -> dict[str, np.ndarray]:
    row = next((item for item in rows if item.get("key") == key), None)
    if row is None:
        raise ContractError(f"selected profile row {key} is missing")
    if not row.get("archive") or not row.get("archive_sha256"):
        raise ContractError(f"selected profile row {key} has no raw archive")
    path = profile_dir / str(row["archive"])
    if raw_sha256(path) != str(row["archive_sha256"]):
        raise ContractError(f"selected profile archive hash mismatch: {row['archive']}")
    with np.load(path, allow_pickle=False) as data:
        arrays = {name: np.asarray(data[name], dtype=np.float64) for name in PROFILE_ARRAYS}
    for name, array in arrays.items():
        if not bool(np.all(np.isfinite(array))):
            raise ContractError(f"nonfinite selected profile array {name}")
    require(float(arrays["Q"]) == Q_PARENT, "selected profile charge is not the Q=512 parent", failures)
    require(float(arrays["R"]) == 24.0, "selected profile domain is not R=24", failures)
    require(bool(row["qualified"]), "selected parent profile is not qualified", failures)
    return arrays


def prepare_base(grid: CylindricalPool, profile: dict[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray, float]:
    """Even origin reflection plus shape-preserving cubic interpolation of the
    stationary parent onto the axisymmetric grid, with the vacuum exterior."""
    r = np.asarray(profile["r"], dtype=np.float64)
    f = np.asarray(profile["f"], dtype=np.float64)
    c = np.asarray(profile["c"], dtype=np.float64)
    radius = float(np.asarray(profile["R"]).item())
    knots_r = np.concatenate(([-radius], -r[::-1], r, [radius]))
    knots_f = np.concatenate(([1.0], f[::-1], f, [1.0]))
    knots_c = np.concatenate(([0.0], c[::-1], c, [0.0]))
    if np.any(np.diff(knots_r) <= 0.0):
        raise ContractError("mirrored profile knots are not strictly increasing")
    interpolant_f = PchipInterpolator(knots_r, knots_f)
    interpolant_c = PchipInterpolator(knots_r, knots_c)
    radial = grid.r.cpu().numpy()[:, None]
    axial = grid.axial.cpu().numpy()[None, :]
    distance = np.sqrt(radial * radial + axial * axial)
    inside = distance <= radius
    clipped = np.clip(distance, 0.0, radius)
    values_f = np.where(inside, np.asarray(interpolant_f(clipped), dtype=np.float64), 1.0)
    values_c = np.where(inside, np.asarray(interpolant_c(clipped), dtype=np.float64), 0.0)
    if not (bool(np.all(np.isfinite(values_f))) and bool(np.all(np.isfinite(values_c)))):
        raise FloatingPointError("nonfinite prepared profile")
    return values_f, values_c, float(np.asarray(profile["omega"]).item())


def prepared_state(grid: CylindricalPool, base: tuple[np.ndarray, np.ndarray, float],
                   impulse: float) -> tuple[Any, Any, float]:
    """Carrier rescaled once so that 2*a*Omega*sum(V c^2) = 512; mediator and
    frequency are left fixed, and there is no normalisation during evolution."""
    frequency = base[2]
    carrier = np.asarray(base[1], dtype=np.float64)
    weights = grid.volume.cpu().numpy()[:, 0]
    population = float(np.sum(weights[:, None] * carrier * carrier))
    if population <= 0.0 or frequency <= 0.0:
        raise ContractError("prepared carrier has no positive charge norm")
    factor = math.sqrt(Q_PARENT / (2.0 * A * frequency * population))
    scaled = torch.as_tensor(carrier * factor, dtype=torch.float64, device=grid.device)[None, :, :]
    mediator = torch.as_tensor(np.asarray(base[0], dtype=np.float64) - 1.0,
                              dtype=torch.float64, device=grid.device)[None, :, :]
    axial = grid.axial[None, None, :]
    phase = impulse * (torch.sqrt(axial * axial + 4.0) - 2.0)
    q = torch.cat((mediator, scaled * torch.cos(phase), scaled * torch.sin(phase)), dim=0)
    v = torch.stack((torch.zeros_like(q[0]), frequency * q[2], -frequency * q[1]), dim=0)
    return q, v, factor


# --------------------------------------------------------------------------- #
# RK4
# --------------------------------------------------------------------------- #
class Workspace:
    def __init__(self, shape: tuple[int, int, int], device: str) -> None:
        blank = lambda: torch.empty(shape, dtype=torch.float64, device=device)  # noqa: E731
        self.kq1, self.kv1 = blank(), blank()
        self.kq2, self.kv2 = blank(), blank()
        self.kq3, self.kv3 = blank(), blank()
        self.kq4, self.kv4 = blank(), blank()
        self.qi, self.vi = blank(), blank()


def rk4_step(grid: CylindricalPool, q: Any, v: Any, dt: float, coupling: float, work: Workspace) -> None:
    def slope(qi: Any, vi: Any, out_q: Any, out_v: Any) -> None:
        out_q.copy_(vi)
        out_v.copy_(grid.acceleration(qi, coupling))

    slope(q, v, work.kq1, work.kv1)
    torch.add(q, work.kq1, alpha=0.5 * dt, out=work.qi)
    torch.add(v, work.kv1, alpha=0.5 * dt, out=work.vi)
    slope(work.qi, work.vi, work.kq2, work.kv2)
    torch.add(q, work.kq2, alpha=0.5 * dt, out=work.qi)
    torch.add(v, work.kv2, alpha=0.5 * dt, out=work.vi)
    slope(work.qi, work.vi, work.kq3, work.kv3)
    torch.add(q, work.kq3, alpha=dt, out=work.qi)
    torch.add(v, work.kv3, alpha=dt, out=work.vi)
    slope(work.qi, work.vi, work.kq4, work.kv4)
    q.add_(work.kq1 + 2.0 * work.kq2 + 2.0 * work.kq3 + work.kq4, alpha=dt / 6.0)
    v.add_(work.kv1 + 2.0 * work.kv2 + 2.0 * work.kv3 + work.kv4, alpha=dt / 6.0)


def state_arrays(grid: CylindricalPool, q: Any, v: Any, moment: float) -> dict[str, np.ndarray]:
    return {"fields": np.asarray(q.detach().cpu().numpy(), dtype=np.float64),
            "velocities": np.asarray(v.detach().cpu().numpy(), dtype=np.float64),
            "r": np.asarray(grid.r.cpu().numpy(), dtype=np.float64),
            "axial": np.asarray(grid.axial.cpu().numpy(), dtype=np.float64),
            "volume": np.asarray(grid.volume.cpu().numpy(), dtype=np.float64),
            "time": np.asarray(moment, dtype=np.float64)}


def save_state(grid: CylindricalPool, output: Path, key: str, moment: float,
               q: Any, v: Any) -> dict[str, Any]:
    entry = save_npz(output / f"{key}_t{int(moment):03d}.npz", **state_arrays(grid, q, v, moment))
    return {**entry, "time": moment}


def write_trace(path: Path, times: np.ndarray, trace: np.ndarray) -> dict[str, Any]:
    return save_npz(path, time=times, diagnostics=trace, names=np.asarray(TRACE_NAMES, dtype="U32"))


def load_trace(path: Path) -> tuple[np.ndarray, np.ndarray]:
    with np.load(path, allow_pickle=False) as data:
        times = np.asarray(data["time"], dtype=np.float64)
        trace = np.asarray(data["diagnostics"], dtype=np.float64)
        names = tuple(str(item) for item in np.asarray(data["names"]).tolist())
    if names != TRACE_NAMES:
        raise ContractError(f"trace column names mismatch: {path.name}")
    if trace.ndim != 2 or trace.shape[1] != COLUMN_COUNT or trace.shape[0] != times.shape[0]:
        raise ContractError(f"trace shape mismatch: {path.name}")
    if not bool(np.all(np.isfinite(times))) or not bool(np.all(np.isfinite(trace))):
        raise ContractError(f"nonfinite trace payload: {path.name}")
    return times, trace


def load_state(path: Path, grid: CylindricalPool, moment: float) -> tuple[Any, Any]:
    with np.load(path, allow_pickle=False) as data:
        fields = np.asarray(data["fields"], dtype=np.float64)
        velocities = np.asarray(data["velocities"], dtype=np.float64)
        r = np.asarray(data["r"], dtype=np.float64)
        axial = np.asarray(data["axial"], dtype=np.float64)
        volume = np.asarray(data["volume"], dtype=np.float64)
        saved = float(np.asarray(data["time"]).item())
    if fields.shape != grid.shape or velocities.shape != fields.shape:
        raise ContractError(f"state shape mismatch: {path.name}")
    if not (bool(np.all(np.isfinite(fields))) and bool(np.all(np.isfinite(velocities)))):
        raise ContractError(f"nonfinite state: {path.name}")
    if saved != moment:
        raise ContractError(f"state time mismatch: {path.name}")
    if not np.array_equal(r, grid.r.cpu().numpy()):
        raise ContractError(f"state radial coordinates mismatch: {path.name}")
    if not np.array_equal(axial, grid.axial.cpu().numpy()):
        raise ContractError(f"state axial coordinates mismatch: {path.name}")
    if not np.array_equal(volume, grid.volume.cpu().numpy()):
        raise ContractError(f"state volume mismatch: {path.name}")
    device = grid.device
    return (torch.as_tensor(fields, dtype=torch.float64, device=device),
            torch.as_tensor(velocities, dtype=torch.float64, device=device))


# --------------------------------------------------------------------------- #
# §75.3 qualification
# --------------------------------------------------------------------------- #
def qualify_row(times: np.ndarray, trace: np.ndarray, arm: str, failures: list[str]) -> dict[str, float]:
    require(bool(times.shape == (SAMPLE_COUNT,)) and bool(np.array_equal(times, TRACE_TIMES)),
            "sample schedule incomplete", failures)
    require(bool(trace.shape == (SAMPLE_COUNT, COLUMN_COUNT)), "trace shape incomplete", failures)
    energy0 = float(trace[0, 0])
    charge0 = float(trace[0, 1])
    summary = {
        "energy_drift": float(np.max(np.abs(trace[:, 0] - energy0)) / max(1.0, abs(energy0))),
        "charge_drift": float(np.max(np.abs(trace[:, 1] - charge0)) / Q_PARENT),
        "charge_offset": abs(charge0 - Q_PARENT) / Q_PARENT,
        "reflection": float(np.max(np.abs(trace[:, 4]))),
    }
    require(summary["energy_drift"] < TOL_ENERGY_DRIFT, f"energy drift:{summary['energy_drift']:.3e}", failures)
    require(summary["charge_drift"] < TOL_CHARGE_DRIFT, f"signed charge drift:{summary['charge_drift']:.3e}", failures)
    require(summary["charge_offset"] < TOL_CHARGE_RECONSTRUCTION,
            f"charge preparation offset:{summary['charge_offset']:.3e}", failures)
    require(summary["reflection"] < TOL_REFLECTION, f"reflection error:{summary['reflection']:.3e}", failures)
    if arm == HOLD:
        rms0 = float(trace[0, 3])
        require(rms0 > 0.0, "unperturbed rms radius vanished", failures)
        drift = float(np.max(np.abs(trace[:, 3] / rms0 - 1.0))) if rms0 > 0.0 else math.inf
        summary["rms_drift"] = drift
        require(drift < TOL_HOLD_RMS, f"unperturbed parent radius survival:{drift:.3e}", failures)
    for offset, side in ((RIGHT_OFFSET, "right"), (LEFT_OFFSET, "left")):
        charge = trace[:, offset + 5]
        radicand = trace[:, offset + 8]
        require(not bool(np.any(radicand < 0.0)), f"negative compact radicand:{side}", failures)
        if arm == UNCOUPLED:
            positive = charge > 0.0
            if bool(np.any(positive)):
                bound = (1.0 - TOL_UNCOUPLED_MASS) * OMEGA_INF * charge[positive]
                count = int(np.count_nonzero(trace[positive, offset + 9] * OMEGA_INF * charge[positive] < bound))
                require(count == 0, f"disabled-coupling free-charge bound:{side}:{count}", failures)
    return summary


def formation_row(times: np.ndarray, trace: np.ndarray) -> bool:
    """§75.2 two-pool condition on both half-space candidates at every sampled
    time with 24 <= t <= 32."""
    late = times >= LATE_START
    if int(np.count_nonzero(late)) != FORMATION_LATE_SAMPLES:
        return False
    block = trace[late]
    for offset in (RIGHT_OFFSET, LEFT_OFFSET):
        charge = block[:, offset + 5]
        center = np.abs(block[:, offset + 1])
        fraction = block[:, offset + 2]
        core_rms = block[:, offset + 3]
        core_f2 = block[:, offset + 4]
        radicand = block[:, offset + 8]
        binding = block[:, offset + 9]
        clearance = block[:, offset + 10]
        good = ((charge >= FORMATION_CHARGE) & (fraction >= FORMATION_FRACTION)
                & (core_rms < FORMATION_RMS) & (core_f2 <= FORMATION_F2)
                & (radicand > 0.0) & (binding > 0.0) & (binding < FORMATION_BINDING)
                & (center > FORMATION_CENTER) & (clearance > FORMATION_CLEARANCE))
        if not bool(np.all(good)):
            return False
    return True


def reconstruct_saved_states(grid: CylindricalPool, states: list[dict[str, Any]], coupling: float,
                            times: np.ndarray, trace: np.ndarray, directory: Path,
                            label: str, failures: list[str]) -> float:
    """Recompute every declared diagnostic from the saved raw state arrays and
    compare against the stored trace column in the fixed §75.3 units."""
    scales = diagnostic_scales(float(trace[0, 0]))
    worst = 0.0
    for record in states:
        name = str(record["path"])
        moment = float(record["time"])
        path = directory / name
        if not path.is_file():
            failures.append(f"{label} snapshot missing:{name}")
            continue
        if raw_sha256(path) != str(record["sha256"]):
            failures.append(f"{label} snapshot hash mismatch:{name}")
            continue
        index = int(round(moment / SAMPLE_DT))
        if index >= times.size or times[index] != moment:
            failures.append(f"{label} snapshot has no matching trace time:{name}")
            continue
        try:
            q, v = load_state(path, grid, moment)
        except ContractError as exc:
            failures.append(f"{label} snapshot:{name}:{exc}")
            continue
        reconstructed = grid.diagnostics(q, v, coupling)
        error = float(np.max(np.abs(reconstructed - trace[index]) / scales))
        worst = max(worst, error)
        if error >= TOL_RECONSTRUCTION:
            failures.append(f"{label} raw diagnostic reconstruction:{name}:{error:.3e}")
    return worst


# --------------------------------------------------------------------------- #
# independent evolution
# --------------------------------------------------------------------------- #
def run_independent_row(grid: CylindricalPool, key: str, dt: float,
                        base: tuple[np.ndarray, np.ndarray, float], parent_key: str,
                        output: Path, manifest_sha: str) -> dict[str, Any]:
    arm = key.split("_", 1)[1]
    impulse, coupling = ARMS[arm]
    started = time.perf_counter()
    failures: list[str] = []
    row: dict[str, Any] = {
        "key": key, "grid": grid_name(key), "arm": arm, "p": impulse, "coupling": coupling,
        "R": grid.R, "spacing": grid.h, "dt": dt, "method": "independent_rk4_float64",
        "device": grid.device, "dtype": "float64", "initial_energy": None,
        "trace": "", "trace_sha256": "", "states": [], "qualified": False, "formation": False,
        "failures": failures, "energy_drift": None, "charge_drift": None,
        "raw_reconstruction_error": None, "late_means": [],
        "parent_profile": parent_key, "manifest_sha256": manifest_sha,
        "complete_physical_matter_formation": False,
    }
    sample_stride = int(round(SAMPLE_DT / dt))
    total_steps = int(round(T_FINAL / dt))
    snapshots = {int(round(moment / dt)): moment for moment in SNAPSHOT_TIMES}
    trace = np.full((SAMPLE_COUNT, COLUMN_COUNT), np.nan, dtype=np.float64)
    q, v, carrier_scale = prepared_state(grid, base, impulse)
    row["carrier_rescaling"] = carrier_scale
    work = Workspace(grid.shape, grid.device)
    record_index = 0
    completed_samples = 0
    completed = False
    progress = int(round(8.0 / dt))
    try:
        with no_grad():
            trace[0] = grid.diagnostics(q, v, coupling)
            completed_samples = 1
            row["states"].append(save_state(grid, output, key, snapshots[0], q, v))
            for step in range(1, total_steps + 1):
                rk4_step(grid, q, v, dt, coupling, work)
                if step % sample_stride == 0:
                    record_index += 1
                    trace[record_index] = grid.diagnostics(q, v, coupling)
                    completed_samples = record_index + 1
                    moment = step * dt
                    if step in snapshots:
                        row["states"].append(save_state(grid, output, key, snapshots[step], q, v))
                if step % progress == 0:
                    print(json.dumps({"row": key, "time": step * dt,
                                      "elapsed_seconds": time.perf_counter() - started}), flush=True)
        completed = completed_samples == SAMPLE_COUNT
    except Exception as exc:
        failures.append(f"{type(exc).__name__}: {exc}")
    name = f"{key}_trace.npz" if completed else f"{key}_partial_trace.npz"
    if not (output / name).exists():
        saved = write_trace(output / name, TRACE_TIMES[:completed_samples], trace[:completed_samples])
        row["trace"] = saved["path"]
        row["trace_sha256"] = saved["sha256"]
    require(completed, "trajectory incomplete", failures)
    require(len(row["states"]) == len(SNAPSHOT_TIMES), "snapshot schedule incomplete", failures)
    if not bool(np.all(np.isfinite(trace[:completed_samples]))):
        failures.append("nonfinite trace column")
    if not completed or failures:
        row["qualified"] = False
        row["elapsed_seconds"] = time.perf_counter() - started
        write_json(output / f"{key}.json", row)
        print(json.dumps({"failed": key, "failures": failures}), flush=True)
        return row
    times = TRACE_TIMES
    row["initial_energy"] = float(trace[0, 0])
    row.update(qualify_row(times, trace, arm, failures))
    row["formation"] = formation_row(times, trace)
    row["late_means"] = [float(value) for value in np.mean(trace[times >= LATE_START], axis=0)]
    row["raw_reconstruction_error"] = reconstruct_saved_states(
        grid, row["states"], coupling, times, trace, output, "independent", failures)
    row["qualified"] = not failures
    row["elapsed_seconds"] = time.perf_counter() - started
    write_json(output / f"{key}.json", row)
    print(json.dumps({"completed": key, "qualified": row["qualified"], "formation": row["formation"],
                      "failures": failures, "elapsed_seconds": row["elapsed_seconds"]}), flush=True)
    return dict(row, times=times, trace=trace)


# --------------------------------------------------------------------------- #
# primary evidence
# --------------------------------------------------------------------------- #
def bind_primary(primary_dir: Path, manifest_sha: str, failures: list[str]) -> dict[str, Any]:
    receipt = strict_json(primary_dir / "result.json")
    require(receipt.get("schema") == PRIMARY_SCHEMA, "primary schema mismatch", failures)
    require(receipt.get("manifest_sha256") == manifest_sha, "primary manifest identity mismatch", failures)
    require(receipt.get("complete_physical_matter_formation") is False, "primary completion flag", failures)
    rows = receipt.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ContractError("primary rows missing")
    by_key: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or "key" not in row:
            raise ContractError("malformed primary row")
        key = str(row["key"])
        if key in by_key or key not in ROW_KEYS:
            raise ContractError(f"unexpected primary row key: {key}")
        by_key[key] = row
    require(sorted(by_key) == sorted(ROW_KEYS), "primary row schedule incomplete", failures)
    return {"receipt": receipt, "rows": by_key}


def verify_primary_row(row: dict[str, Any], key: str, grid: CylindricalPool,
                       primary_dir: Path, output: Path) -> dict[str, Any]:
    local: list[str] = []
    entry: dict[str, Any] = {
        "key": key, "grid": grid_name(key), "arm": str(row.get("arm")), "p": None, "coupling": None,
        "R": row.get("R"), "spacing": row.get("spacing"), "dt": row.get("dt"),
        "method": str(row.get("method", "primary_yoshida_verlet")),
        "trace": str(row.get("trace")), "trace_sha256": str(row.get("trace_sha256")),
        "states": row.get("states") if isinstance(row.get("states"), list) else [],
        "initial_energy": None, "qualified": False, "formation": False, "failures": local,
        "energy_drift": None, "charge_drift": None, "raw_reconstruction_error": None,
        "late_means": row.get("late_means") if isinstance(row.get("late_means"), list) else [],
    }
    arm = entry["arm"]
    if arm not in ARMS:
        local.append("primary arm label is not in the frozen schedule")
        return finish_entry(entry)
    impulse, coupling = ARMS[arm]
    entry["p"] = impulse
    entry["coupling"] = coupling
    require(number(row.get("p")) == impulse, "primary impulse mismatch", local)
    require(number(row.get("coupling")) == coupling, "primary coupling mismatch", local)
    require(number(row.get("R")) == grid.R, "primary domain mismatch", local)
    require(number(row.get("spacing")) == grid.h, "primary spacing mismatch", local)
    require(number(row.get("dt")) == GRIDS[grid_name(key)][2], "primary time step mismatch", local)
    receipt_path = primary_dir / f"{key}.json"
    if receipt_path.is_file():
        receipt_row = strict_json(receipt_path)
        require(receipt_row.get("trace") == row.get("trace"), "primary row receipt trace mismatch", local)
        require(bool(receipt_row.get("qualified")) == bool(row.get("qualified")),
                "primary row receipt qualification mismatch", local)
        require([str(item.get("path")) for item in receipt_row.get("states", [])]
                == [str(item.get("path")) for item in entry["states"]],
                "primary row receipt snapshot mismatch", local)
    else:
        local.append("primary row receipt missing")
    if len(entry["states"]) != len(SNAPSHOT_TIMES):
        local.append("primary snapshot schedule incomplete")
    else:
        require([str(item.get("path")) for item in entry["states"]]
                == [f"{key}_t{int(moment):03d}.npz" for moment in SNAPSHOT_TIMES],
                "primary snapshot names mismatch", local)
        require([number(item.get("time")) for item in entry["states"]] == list(SNAPSHOT_TIMES),
                "primary snapshot times mismatch", local)
    trace_path = primary_dir / entry["trace"]
    if not trace_path.is_file():
        local.append("primary trace missing")
        return finish_entry(entry)
    require(entry["trace_sha256"] == raw_sha256(trace_path), "primary trace hash mismatch", local)
    try:
        times, trace = load_trace(trace_path)
    except ContractError as exc:
        local.append(f"primary trace:{exc}")
        return finish_entry(entry)
    entry["initial_energy"] = number(row.get("initial_energy", trace[0, 0]))
    require(entry["initial_energy"] == float(trace[0, 0]), "primary initial energy mismatch", local)
    require([number(value) for value in entry["late_means"]]
            == [float(value) for value in np.mean(trace[times >= LATE_START], axis=0).tolist()]
            if entry["late_means"] and bool(np.all(np.isfinite(trace))) else True,
            "primary late means mismatch", local)
    if bool(np.all(np.isfinite(trace))):
        entry.update(qualify_row(times, trace, arm, local))
        entry["formation"] = formation_row(times, trace)
        if len(entry["states"]) == len(SNAPSHOT_TIMES):
            entry["raw_reconstruction_error"] = reconstruct_saved_states(
                grid, entry["states"], coupling, times, trace, primary_dir, "primary", local)
    else:
        local.append("primary nonfinite trace")
    entry["qualified"] = not local
    write_json(output / f"primary_{key}_reconciliation.json", strip(entry))
    return dict(entry, times=times, trace=trace)


def finish_entry(entry: dict[str, Any]) -> dict[str, Any]:
    entry["qualified"] = not entry["failures"]
    return entry


# --------------------------------------------------------------------------- #
# comparisons
# --------------------------------------------------------------------------- #
def comparison_row(row: dict[str, Any]) -> dict[str, Any]:
    if row.get("times") is None or row.get("trace") is None:
        return {"key": row["key"], "times": np.zeros((0,), dtype=np.float64),
                "trace": np.zeros((0, COLUMN_COUNT), dtype=np.float64),
                "initial_energy": 0.0, "states_count": 0}
    return {"key": row["key"], "times": row["times"], "trace": row["trace"],
            "initial_energy": float(row["initial_energy"]), "states_count": len(row["states"])}


def compare_traces(kind: str, left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    record: dict[str, Any] = {"type": kind, "left": left["key"], "right": right["key"], "pass": False}
    if left["states_count"] != len(SNAPSHOT_TIMES) or right["states_count"] != len(SNAPSHOT_TIMES):
        record["error"] = "incomplete snapshot schedule"
        return record
    if left["times"].shape != right["times"].shape or not np.array_equal(left["times"], right["times"]):
        record["error"] = "mismatched sample schedules"
        return record
    late = left["times"] >= LATE_START
    if int(np.count_nonzero(late)) != FORMATION_LATE_SAMPLES:
        record["error"] = "no complete late-time window"
        return record
    scales = np.maximum(diagnostic_scales(left["initial_energy"]), diagnostic_scales(right["initial_energy"]))
    difference = np.mean(left["trace"][late], axis=0) - np.mean(right["trace"][late], axis=0)
    errors = np.abs(difference) / scales
    record["max_error"] = float(np.max(errors))
    record["columns"] = {name: float(error) for name, error in zip(TRACE_NAMES, errors)}
    record["pass"] = bool(record["max_error"] < TOL_DIAGNOSTIC_MEAN)
    return record


def cross_comparisons(rows: dict[str, dict[str, Any]], prefix: str) -> list[dict[str, Any]]:
    pairs = ([(f"G0_{arm}", f"G1_{arm}", "space") for arm in (HOLD, WEAK, STRONG, UNCOUPLED)]
             + [("G0_strong", "G2_strong", "domain"), ("G1_strong", "T1_strong", "time")])
    return [compare_traces(f"{prefix}_{kind}", comparison_row(rows[left]), comparison_row(rows[right]))
            for left, right, kind in pairs]


def weighted_field_error(grid: CylindricalPool, left: tuple[Any, Any],
                         right: tuple[Any, Any]) -> tuple[float, float, float]:
    """§75.3 weighted norm of (f-1, z, dot f/Omega_inf, dot z/Omega_inf) with
    the raw q and v norm errors reported alongside (no phase alignment)."""
    q1, v1 = left
    q2, v2 = right
    volume = grid.volume
    difference_q = q1 - q2
    difference_v = v1 - v2
    numerator = torch.sqrt(((difference_q * difference_q
                             + difference_v * difference_v / OMEGA_INF ** 2) * volume).sum())
    scale_left = torch.sqrt((((q1 * q1 + v1 * v1 / OMEGA_INF ** 2)) * volume).sum())
    scale_right = torch.sqrt((((q2 * q2 + v2 * v2 / OMEGA_INF ** 2)) * volume).sum())
    raw_q = torch.sqrt(((difference_q * difference_q) * volume).sum())
    raw_v = torch.sqrt(((difference_v * difference_v) * volume).sum())
    denominator = torch.clamp_min(torch.maximum(scale_left, scale_right), 1.0)
    return float(numerator / denominator), float(raw_q), float(raw_v)


def snapshot_comparisons(grids: dict[str, CylindricalPool], primary_dir: Path,
                         output: Path) -> list[dict[str, Any]]:
    results = []
    for key in ROW_KEYS:
        grid = grids[grid_name(key)]
        for moment in SNAPSHOT_TIMES:
            name = f"{key}_t{int(moment):03d}.npz"
            record: dict[str, Any] = {"type": "state_snapshot", "key": key, "left": f"primary:{name}",
                                      "right": f"independent:{name}", "time": moment, "pass": False}
            try:
                left = load_state(primary_dir / name, grid, moment)
                right = load_state(output / name, grid, moment)
                error, raw_q, raw_v = weighted_field_error(grid, left, right)
                record.update({"max_error": error, "raw_q_norm_error": raw_q,
                               "raw_v_norm_error": raw_v, "pass": bool(error < TOL_STATE_SNAPSHOT)})
            except (ContractError, FileNotFoundError) as exc:
                record["error"] = f"{type(exc).__name__}: {exc}"
            results.append(record)
    return results


def emergence_candidates(rows: dict[str, dict[str, Any]], prefix: str) -> list[dict[str, Any]]:
    """§75.3: either nonzero impulse, on every applicable grid, in both methods.
    The h_C = 0 arm is the free-charge control of §75.1, whose §75.3 role is the
    M_theta >= (1-1e-8) Omega_inf Q_theta identity, so it is excluded from the
    emergence disjunction while its formation flag is still recorded."""
    results = []
    for arm in (WEAK, STRONG):
        grids = [grid for grid, arms in SCHEDULE if arm in arms]
        flags = {f"{prefix}_{grid}_{arm}": bool(rows[f"{grid}_{arm}"]["formation"]) for grid in grids}
        results.append({"impulse": ARMS[arm][0], "arm": arm, "flags": flags,
                        "pass": bool(flags) and all(flags.values())})
    return results


def merge_candidates(primary: list[dict[str, Any]], independent: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = []
    for left, right in zip(primary, independent):
        flags = dict(left["flags"])
        flags.update(right["flags"])
        merged.append({"impulse": left["impulse"], "arm": left["arm"], "flags": flags,
                       "pass": bool(left["pass"] and right["pass"])})
    return merged


def aggregate(comparisons: list[dict[str, Any]]) -> dict[str, bool]:
    groups: dict[str, list[bool]] = {}
    for record in comparisons:
        groups.setdefault(record["type"], []).append(bool(record.get("pass")))
    return {kind: all(flags) and bool(flags) for kind, flags in groups.items()}


# --------------------------------------------------------------------------- #
# §74 profiles prerequisite
# --------------------------------------------------------------------------- #
def verify_profiles(profile_dir: Path, manifest_sha: str,
                    failures: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    receipt = strict_json(profile_dir / "result.json")
    require(receipt.get("schema") == PROFILES_SCHEMA, "profiles schema mismatch", failures)
    require(receipt.get("manifest_sha256") == manifest_sha, "profiles manifest identity mismatch", failures)
    require(receipt.get("complete_physical_matter_formation") is False, "profiles completion flag", failures)
    rows = receipt.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ContractError("profiles rows missing")
    by_key: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ContractError("malformed profiles row")
        key = str(row.get("key"))
        if key not in PROFILE_KEYS or key in by_key:
            raise ContractError(f"unexpected profiles row key: {key}")
        missing = [name for name in PROFILE_ROW_FIELDS if name not in row]
        if missing:
            raise ContractError(f"profiles row {key} lacks fields {missing}")
        by_key[key] = row
    if sorted(by_key) != sorted(PROFILE_KEYS):
        raise ContractError("profiles rows must hold every charge/grid/seed row")
    blocks: dict[str, dict[str, Any]] = {}
    for key in PROFILE_KEYS:
        row = by_key[key]
        archive_name = row["archive"]
        if not isinstance(archive_name, str) or not archive_name:
            failures.append(f"profile archive unavailable:{key}")
            continue
        require(archive_name == f"{key}.npz", f"profile archive name:{key}", failures)
        path = profile_dir / archive_name
        if not path.is_file():
            failures.append(f"profile archive missing:{archive_name}")
            continue
        require(raw_sha256(path) == str(row["archive_sha256"]), f"profile archive hash:{key}", failures)
        with np.load(path, allow_pickle=False) as data:
            missing = [name for name in PROFILE_ARRAYS if name not in data]
            if missing:
                raise ContractError(f"profile archive {key} lacks arrays {missing}")
            archive = {name: np.asarray(data[name]) for name in PROFILE_ARRAYS}
        absent = [name for name in PROFILE_SCALARS if row[name] is None]
        if absent:
            failures.append(f"profile row scalars absent:{key}:{absent}")
            continue
        radius, spacing = PROFILE_GRIDS[str(row["grid"])]
        seed_token = key.rsplit("_", 1)[1]
        require(str(row["grid"]) in PROFILE_GRIDS, f"profile grid registry:{key}", failures)
        require(number(row["seed"]) == PROFILE_SEEDS[seed_token], f"profile seed registry:{key}", failures)
        try:
            blocks[key] = reconstruct_profile(SphericalPool(radius, spacing), archive, row, failures)
        except ContractError as exc:
            failures.append(f"profile reconstruction:{key}:{exc}")
    checks: dict[str, bool] = {}
    agreements: dict[str, list[dict[str, Any]]] = {}
    for label, tolerance, pairs in (
        ("seed", TOL_SEED, [(f"q{int(q)}_{gid}_s0", f"q{int(q)}_{gid}_s1")
                            for q in PROFILE_CHARGES for gid in PROFILE_GRIDS]),
        ("refinement", TOL_REFINEMENT, [(f"q{int(q)}_S0_{sid}", f"q{int(q)}_S1_{sid}")
                                        for q in PROFILE_CHARGES for sid in PROFILE_SEEDS]),
        ("domain", TOL_DOMAIN, [(f"q{int(q)}_S1_{sid}", f"q{int(q)}_S2_{sid}")
                                for q in PROFILE_CHARGES for sid in PROFILE_SEEDS]),
    ):
        entries = []
        for left_key, right_key in pairs:
            if left_key not in blocks or right_key not in blocks:
                entries.append({"left": left_key, "right": right_key, "tolerance": tolerance,
                                "errors": {}, "pass": False})
                failures.append(f"profile {label} agreement unavailable:{left_key}~{right_key}")
                continue
            left, right = blocks[left_key], blocks[right_key]
            errors = {field: abs(left[field] - right[field])
                      / max(1.0, abs(left[field]), abs(right[field]))
                      for field in ("energy", "omega", "rms")}
            entries.append({"left": left_key, "right": right_key, "tolerance": tolerance,
                            "errors": errors, "pass": all(value < tolerance for value in errors.values())})
        agreements[label] = entries
        checks[f"profile_{label}_agreement"] = all(entry["pass"] for entry in entries)
    checks["profile_rows_complete"] = len(blocks) == len(PROFILE_KEYS)
    checks["profile_thresholds"] = bool(blocks) and all(block["qualified"] for block in blocks.values()) \
        and checks["profile_rows_complete"]
    checks["profile_reconstruction"] = bool(blocks) and all(
        all(error < TOL_RECONSTRUCTION for error in block["discrepancies"].values())
        for block in blocks.values()) and checks["profile_rows_complete"]
    checks["profile_charge_reconstruction"] = bool(blocks) and all(
        block["charge_error"] < TOL_CHARGE_RECONSTRUCTION for block in blocks.values()) \
        and checks["profile_rows_complete"]
    selection = receipt.get("selected")
    checks["profile_selection"] = bool(isinstance(selection, dict)
                                       and all(selection.get(name) == key for name, key in SELECTED.items()))
    if not checks["profile_selection"]:
        failures.append("profile selection registry mismatch")
    reference: float | None = None
    stored_reference: Any = receipt.get("reference_fission_energy")
    checks["profile_selected_present"] = bool(all(key in blocks for key in SELECTED.values()))
    if not checks["profile_selected_present"]:
        failures.append("selected parent or daughter raw evidence is unavailable")
        checks["profile_selected_qualified"] = False
        checks["profile_reference_fission"] = False
    else:
        parent = blocks[SELECTED["Q512"]]
        daughter = blocks[SELECTED["Q256"]]
        checks["profile_selected_qualified"] = bool(parent["qualified"] and daughter["qualified"])
        if not checks["profile_selected_qualified"]:
            failures.append("selected parent and daughter references are not qualified")
        reference = 2.0 * daughter["energy"] - parent["energy"]
        checks["profile_reference_fission"] = bool(
            isinstance(stored_reference, (int, float)) and not isinstance(stored_reference, bool)
            and normalized_error(reference, float(stored_reference), abs(float(stored_reference)))
            < TOL_RECONSTRUCTION)
        if not checks["profile_reference_fission"]:
            failures.append(f"reference fission energy mismatch:{stored_reference!r} vs {reference!r}")
    checks["receipt_passes"] = bool(receipt.get("numeric_pass") is True
                                    and isinstance(receipt.get("checks"), dict)
                                    and receipt["checks"]
                                    and all(value is True for value in receipt["checks"].values()))
    if not checks["receipt_passes"]:
        failures.append("profiles receipt does not declare every prerequisite check passed")
    checks["profile_evidence_valid"] = not failures
    checks["profiles_numeric_pass"] = all(checks.values())
    payload = {
        "rows": [blocks[key] for key in PROFILE_KEYS if key in blocks],
        "agreement": agreements, "checks": checks,
        "numeric_pass": bool(checks["profiles_numeric_pass"]),
        "verdict": (VERDICT_PROFILES_ONLY if checks["profiles_numeric_pass"] else VERDICT_INCONCLUSIVE),
        "reference_fission_energy": reference,
        "reference_fission_energy_stored": stored_reference,
        "selected": SELECTED, "selection_stored": selection,
        "receipt_verdict": receipt.get("verdict"), "receipt_numeric_pass": receipt.get("numeric_pass"),
        "receipt_checks": receipt.get("checks"),
        "constants": {"a": A, "c_psi": CPSI, "u_rho": URHO, "u_C": UC, "k_Cx": K, "e_C": EC,
                      "h_C": HC, "B": B, "omega_inf": OMEGA_INF, "speed2": SPEED2,
                      "n0": N0, "omega_0": OMEGA_0},
    }
    return payload, receipt


# --------------------------------------------------------------------------- #
# driver
# --------------------------------------------------------------------------- #
def environment(device: str | None = None) -> dict[str, Any]:
    import scipy
    payload = {"python": platform.python_version(), "numpy": np.__version__,
               "scipy": scipy.__version__, "torch": None, "device": device, "dtype": "float64"}
    if torch is not None:
        payload["torch"] = torch.__version__
    return payload


def failure_payload(manifest_sha: str, error: str, mode: str | None) -> dict[str, Any]:
    return {"schema": SCHEMA, "manifest_sha256": manifest_sha, "mode": mode,
            "sections": [{"heading": heading, "sha256": None} for heading in HEADINGS],
            "sources": [], "sources_verified": 0, "profiles": None, "rows": [], "primary_rows": [],
            "comparisons": [], "formation_candidates": [],
            "checks": {"provenance": False}, "numeric_pass": False,
            "verdict": VERDICT_INCONCLUSIVE, "error": error,
            "complete_physical_matter_formation": False, "environment": environment(),
            "scope": {"asymptotic_stability_established": False, "particle_species_identified": False,
                      "infinite_time_survival_established": False,
                      "nonaxisymmetric_stability_established": False}}


def run(manifest_path: Path, output: Path, profile_dir: Path, primary_dir: Path | None,
        profiles_only: bool) -> dict[str, Any]:
    manifest, manifest_sha = verify_manifest(manifest_path)
    failures: list[str] = []
    profiles, profile_receipt = verify_profiles(profile_dir, manifest_sha, failures)
    payload: dict[str, Any] = {
        "schema": SCHEMA, "manifest_sha256": manifest_sha,
        "mode": "profiles-only" if profiles_only else "full",
        "sections": [{"heading": record["heading"], "path": record["path"],
                      "snapshot": record["snapshot"], "sha256": record["sha256"]}
                     for record in manifest["sections"]],
        "sources": manifest["sources"], "sources_verified": len(manifest["sources"]),
        "profiles": profiles, "rows": [], "primary_rows": [], "comparisons": [],
        "formation_candidates": [],
        "checks": {"provenance": True, "profiles_numeric_pass": bool(profiles["numeric_pass"])},
        "complete_physical_matter_formation": False, "environment": environment(),
        "scope": {"asymptotic_stability_established": False, "particle_species_identified": False,
                  "infinite_time_survival_established": False,
                  "nonaxisymmetric_stability_established": False,
                  "note": "the supplied scalar parent is not identified with a physical particle"},
    }
    if profiles_only:
        payload["failures"] = failures
        payload["numeric_pass"] = bool(profiles["numeric_pass"])
        payload["verdict"] = profiles["verdict"]
        return payload
    if not profiles["numeric_pass"]:
        failures.append("stationary-profile prerequisite failed; the dispersal calculation is stopped")
        payload["failures"] = failures
        payload["numeric_pass"] = False
        payload["verdict"] = VERDICT_INCONCLUSIVE
        return payload
    if primary_dir is None:
        raise ContractError("full verification requires --input PRIMARY_DIR")
    device = pick_device()
    payload["environment"] = environment(device)
    grids = {name: CylindricalPool(radius, spacing, device)
             for name, (radius, spacing, _dt) in GRIDS.items()
             if any(key.startswith(f"{name}_") for key in ROW_KEYS)}
    selected_key = str(profile_receipt["selected"]["Q512"])
    parent = load_selected_profile(profile_dir, profile_receipt["rows"], selected_key, failures)
    payload["parent_profile"] = {"key": selected_key, "archive": str(parent["archive"])
                                 if "archive" in parent else SELECTED["Q512"]}
    bases: dict[str, tuple[np.ndarray, np.ndarray, float]] = {}
    independent: dict[str, dict[str, Any]] = {}
    primary: dict[str, dict[str, Any]] = {}
    binding = bind_primary(primary_dir, manifest_sha, failures)
    for key in ROW_KEYS:
        name = grid_name(key)
        grid = grids[name]
        if name not in bases:
            bases[name] = prepare_base(grid, parent)
            payload.setdefault("prepared_domains", []).append({
                "grid": name, "R": grid.R, "spacing": grid.h,
                "cells": [grid.nr, grid.nz], "parent_key": selected_key})
        independent[key] = run_independent_row(grid, key, GRIDS[name][2], bases[name],
                                              selected_key, output, manifest_sha)
    for key in ROW_KEYS:
        if key not in binding["rows"]:
            failures.append(f"primary row missing:{key}")
            primary[key] = {"key": key, "grid": grid_name(key), "qualified": False, "formation": False,
                            "failures": [f"primary row missing:{key}"], "states": [], "late_means": [],
                            "raw_reconstruction_error": None, "initial_energy": None}
            continue
        primary[key] = verify_primary_row(binding["rows"][key], key, grids[grid_name(key)],
                                          primary_dir, output)
    comparisons = [compare_traces("same_row", comparison_row(primary[key]), comparison_row(independent[key]))
                   for key in ROW_KEYS]
    comparisons.extend(cross_comparisons(primary, "primary"))
    comparisons.extend(cross_comparisons(independent, "independent"))
    comparisons.extend(snapshot_comparisons(grids, primary_dir, output))
    payload["comparisons"] = comparisons
    payload["rows"] = [strip(independent[key]) for key in ROW_KEYS]
    payload["primary_rows"] = [strip(primary[key]) for key in ROW_KEYS]
    payload["formation_candidates"] = merge_candidates(
        emergence_candidates(primary, "primary"), emergence_candidates(independent, "independent"))
    rows_ok = all(independent[key]["qualified"] for key in ROW_KEYS)
    primary_ok = all(primary[key]["qualified"] for key in ROW_KEYS)
    groups = aggregate(comparisons)
    reconstruction_ok = all(
        primary[key].get("raw_reconstruction_error") is not None
        and float(primary[key]["raw_reconstruction_error"]) < TOL_RECONSTRUCTION
        and independent[key].get("raw_reconstruction_error") is not None
        and float(independent[key]["raw_reconstruction_error"]) < TOL_RECONSTRUCTION
        for key in ROW_KEYS)
    payload["checks"].update({
        "independent_rows": bool(rows_ok),
        "primary_rows": bool(primary_ok),
        "evolution_rows_twenty": bool(rows_ok and primary_ok),
        "same_row_diagnostics": bool(groups.get("same_row", False)),
        "state_snapshots": bool(groups.get("state_snapshot", False)),
        "cross_space": bool(groups.get("primary_space", False) and groups.get("independent_space", False)),
        "cross_domain": bool(groups.get("primary_domain", False) and groups.get("independent_domain", False)),
        "cross_time": bool(groups.get("primary_time", False) and groups.get("independent_time", False)),
        "raw_reconstruction": bool(reconstruction_ok),
        "no_uncaptured_failures": not failures,
    })
    payload["comparison_groups"] = groups
    numeric_pass = bool(all(payload["checks"].values()))
    payload["failures"] = failures
    payload["numeric_pass"] = numeric_pass
    if not numeric_pass:
        payload["verdict"] = VERDICT_INCONCLUSIVE
    elif any(item["pass"] for item in payload["formation_candidates"]):
        payload["verdict"] = VERDICT_EMERGES
    else:
        payload["verdict"] = VERDICT_NO_EMERGE
    return payload


def strip(row: dict[str, Any]) -> dict[str, Any]:
    return {name: value for name, value in row.items() if name not in ("times", "trace")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--profiles", required=True, type=Path)
    parser.add_argument("--input", type=Path, default=None)
    parser.add_argument("--profiles-only", action="store_true",
                        help="verify the §74 profiles and exit without any evolution")
    args = parser.parse_args(argv)
    output = args.output.resolve()
    if output.exists():
        print(json.dumps({"schema": SCHEMA, "verdict": VERDICT_INCONCLUSIVE, "numeric_pass": False,
                          "error": f"refusing existing output directory: {output}",
                          "complete_physical_matter_formation": False}), flush=True)
        return 2
    output.mkdir(parents=False, exist_ok=False)
    manifest_path = args.manifest.resolve()
    profile_dir = args.profiles.resolve()
    primary_dir = args.input.resolve() if args.input is not None else None
    mode = "profiles-only" if args.profiles_only else "full"
    try:
        payload = run(manifest_path, output, profile_dir, primary_dir, args.profiles_only)
    except Exception as exc:
        manifest_sha = ""
        try:
            _, manifest_sha = verify_manifest(manifest_path)
        except Exception:
            manifest_sha = raw_sha256(manifest_path) if manifest_path.is_file() else ""
        payload = failure_payload(manifest_sha, f"{type(exc).__name__}: {exc}", mode)
        print(json.dumps({"schema": SCHEMA, "verdict": VERDICT_INCONCLUSIVE, "numeric_pass": False,
                          "error": payload["error"], "complete_physical_matter_formation": False},
                         ensure_ascii=False), flush=True)
        write_json(output / "result.json", payload)
        return 1
    write_json(output / "result.json", payload)
    print(json.dumps({"schema": SCHEMA, "verdict": payload["verdict"],
                      "numeric_pass": payload["numeric_pass"], "mode": payload["mode"],
                      "complete_physical_matter_formation": False}, ensure_ascii=False), flush=True)
    return 0 if payload["numeric_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
