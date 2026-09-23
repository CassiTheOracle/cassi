"""Field-owned invention over the complete target-independent trajectory environment."""
from __future__ import annotations

import copy
import functools
import hashlib
import itertools
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from scipy.spatial import cKDTree

import cassi_field_operator_invention as typed
from cassi_field_operator_invention import ArmData, OperatorInventionError
from cassi_research_residency import open_research_residency

SCHEMA = "cassifi.full-observable-operator.v1"
VERIFICATION_SCHEMA = "cassifi.full-observable-operator-verification.v1"
CAMPAIGN_KIND = "full-observable-operator-20260919"
FIT_FRACTION = 0.60
TRACER_MODULUS = 16
NEIGHBOR_COUNT = 16
GRADIENT_RIDGE = 1e-9
MINIMUM_RADIUS = 1e-9
VALUE_BOUND = 1e6

ATOMS = (
    "one", "q", "radial_speed", "speed", "transverse_speed",
    "time", "mass_ratio", "softening_ratio", "cell_ratio",
    "cluster_radius_ratio", "cluster_separation_ratio", "field_live",
    "enclosed_mass", "enclosed_density", "neighbor_radius", "local_density",
    "density_contrast", "potential", "field_energy", "orbital_frequency",
    "virial_ratio", "angular_momentum", "velocity_dispersion",
    "velocity_coherence", "local_radial_flow", "divergence", "shear",
    "vorticity", "radial_strain", "density_gradient", "coherence_gradient",
)
FRAMES = (
    "radial", "flow", "transverse", "normal",
    "density_gradient", "coherence_gradient",
)
UNARY_OPS = typed.UNARY_OPS
MUTATION_COMPANIONS = (
    "q", "speed", "enclosed_mass", "local_density", "density_contrast",
    "field_energy", "velocity_dispersion", "velocity_coherence",
    "divergence", "shear", "coherence_gradient",
)

# The proven typed interpreter is reused without changing its frozen source.
# Its atom/frame registries are process-local runtime parameters here.
typed.ATOMS = ATOMS
typed.FRAMES = FRAMES
typed.VALUE_BOUND = VALUE_BOUND

_DEVELOPMENT_ROOTS = tuple(
    [
        f"CassiCosmos/_diag/matter_formation/energy_gaussian_s{seed}_v{speed}"
        for seed in (20260910, 20260911)
        for speed in ("0p0", "0p5", "1p0", "2p0")
    ]
    + [
        f"CassiCosmos/_diag/matter_formation/attractor_ic{index}"
        for index in (2, 5, 6, 7, 10)
    ]
    + [
        f"CassiCosmos/_diag/matter_formation/attractor_scene_calibrated/{name}"
        for name in ("G3", "G6", "GC2", "GL3")
    ]
)
_PREVIOUS_RECEIPT = "CassiFI/_diag/alien-equation-discovery/receipt.json"
_TRAJECTORY_FILES = ("receipt.json", "analysis.json", "sample_steps.bin", "history_pos.bin", "history_vel.bin")


@dataclass(frozen=True, slots=True)
class CampaignSpec:
    kind: str
    preregistration: str
    development_roots: tuple[str, ...]
    hidden_holdout: tuple[str, ...]


_CAMPAIGNS = {
    "full-observable-operator-20260919": CampaignSpec(
        kind="full-observable-operator-20260919",
        preregistration="CassiCosmos/research/equation_discovery/full_observable_operator_prereg.md",
        development_roots=_DEVELOPMENT_ROOTS,
        hidden_holdout=tuple(
            f"CassiCosmos/_diag/matter_formation/regime_holdout_20260919/{name}"
            for name in ("RH3", "RH6", "RHC1", "RHL3")
        ),
    ),
    "full-observable-operator-v2-20260919": CampaignSpec(
        kind="full-observable-operator-v2-20260919",
        preregistration="CassiCosmos/research/equation_discovery/full_observable_operator_v2_prereg.md",
        development_roots=_DEVELOPMENT_ROOTS,
        hidden_holdout=tuple(
            f"CassiCosmos/_diag/matter_formation/full_observable_v2_20260919/{name}"
            for name in ("BH3", "BH6", "BHC3", "BHL3")
        ),
    ),
    "full-observable-operator-v3-20260919": CampaignSpec(
        kind="full-observable-operator-v3-20260919",
        preregistration="CassiCosmos/research/equation_discovery/full_observable_operator_v3_prereg.md",
        development_roots=_DEVELOPMENT_ROOTS,
        hidden_holdout=tuple(
            f"CassiCosmos/_diag/matter_formation/full_observable_v3_20260919/{name}"
            for name in ("CH3", "CH6", "CHC3", "CHL3")
        ),
    ),
    "full-observable-operator-v4-20260919": CampaignSpec(
        kind="full-observable-operator-v4-20260919",
        preregistration="CassiCosmos/research/equation_discovery/full_observable_operator_v4_prereg.md",
        development_roots=tuple(root for root in _DEVELOPMENT_ROOTS if not root.endswith("/GL3")),
        hidden_holdout=tuple(
            f"CassiCosmos/_diag/matter_formation/full_observable_v4_20260919/{name}"
            for name in ("DH3", "DH6", "DHC3", "DHL3")
        ),
    ),
}
DEFAULT_CAMPAIGN_KIND = "full-observable-operator-20260919"


def _campaign_spec(kind: str) -> CampaignSpec:
    try:
        return _CAMPAIGNS[kind]
    except KeyError as exc:
        raise OperatorInventionError(f"unknown full-observable campaign: {kind}") from exc


@dataclass(slots=True)
class FeatureBundle:
    arm_id: str
    atoms: dict[str, np.ndarray]
    frames: dict[str, np.ndarray]
    target: np.ndarray
    middle_index: np.ndarray
    scales: dict[str, float]
    source_summary: dict[str, Any]


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _protocol_contract(campaign: CampaignSpec) -> dict[str, Any]:
    return {
        "campaign_kind": campaign.kind,
        "fit_fraction": FIT_FRACTION,
        "tracer_modulus": TRACER_MODULUS,
        "neighbor_count": NEIGHBOR_COUNT,
        "gradient_ridge": GRADIENT_RIDGE,
        "minimum_radius": MINIMUM_RADIUS,
        "value_bound": VALUE_BOUND,
        "atoms": list(ATOMS),
        "frames": list(FRAMES),
        "unary_ops": list(UNARY_OPS),
        "mutation_companions": list(MUTATION_COMPANIONS),
        "development": list(campaign.development_roots),
        "hidden_holdout": list(campaign.hidden_holdout),
        "classification": {
            "semantic_cosine": 0.999,
            "minimum_relative_improvement": 0.05,
            "maximum_per_arm_relative_regression": 0.10,
            "unsupported_nrmse": 0.85,
        },
    }


def _expected_source_paths(campaign: CampaignSpec) -> list[str]:
    paths = [campaign.preregistration, _PREVIOUS_RECEIPT]
    for root in (*campaign.development_roots, *campaign.hidden_holdout):
        paths.extend(f"{root}/{name}" for name in _TRAJECTORY_FILES)
    return sorted(paths)


def _source_manifest(workspace: Path, campaign: CampaignSpec) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for relative in _expected_source_paths(campaign):
        path = workspace / relative
        if not path.is_file():
            raise OperatorInventionError(f"required full-observable evidence is absent: {relative}")
        rows.append({"path": relative, "bytes": path.stat().st_size, "sha256": _file_sha256(path)})
    return rows


def _qualifying_metadata(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        receipt = json.loads((root / "receipt.json").read_text(encoding="utf-8"))
        analysis = json.loads((root / "analysis.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OperatorInventionError(f"trajectory metadata is unreadable: {root}") from exc
    if receipt.get("schema") != "cassi.trajectory-probe.v1":
        raise OperatorInventionError(f"trajectory schema is unsupported: {root}")
    if analysis.get("status") != "OK" or analysis.get("domain_status") != "BOUNDED":
        raise OperatorInventionError(f"trajectory is not a bounded qualifying arm: {root}")
    if int(receipt.get("event_overflow", -1)) != 0 or int(receipt.get("sample_overflow", -1)) != 0:
        raise OperatorInventionError(f"trajectory recorder overflowed: {root}")
    if abs(float(analysis.get("relative_mass_error", math.inf))) > 1e-9:
        raise OperatorInventionError(f"trajectory mass drift exceeded the bound: {root}")
    return receipt, analysis


def _unit(vectors: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    norm = np.linalg.norm(vectors, axis=1)
    result = np.zeros_like(vectors)
    valid = norm > 1e-12
    result[valid] = vectors[valid] / norm[valid, None]
    return result, norm


def _feature_digest(atoms: Mapping[str, np.ndarray], frames: Mapping[str, np.ndarray]) -> str:
    digest = hashlib.sha256()
    for family, values in (("atom", atoms), ("frame", frames)):
        for name in sorted(values):
            array = np.ascontiguousarray(values[name], dtype="<f8")
            digest.update(family.encode())
            digest.update(name.encode())
            digest.update(np.asarray(array.shape, dtype="<u8").tobytes())
            digest.update(array.tobytes())
    return digest.hexdigest()


def _snapshot_features(
    position: np.ndarray,
    velocity: np.ndarray,
    mass: np.ndarray,
    *,
    radius_scale: float,
    mass_scale: float,
    velocity_scale: float,
    clock_value: float,
    initial_mean_mass: float,
    softening: float,
    cell_width: float,
    cluster_radius: float,
    cluster_separation: float,
    field_live: float,
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    radius = np.linalg.norm(position, axis=1)
    if len(position) < NEIGHBOR_COUNT or np.any(radius <= MINIMUM_RADIUS):
        raise OperatorInventionError("observable snapshot lacks a valid neighborhood")
    radial = position / radius[:, None]
    u = velocity / velocity_scale
    radial_speed = np.einsum("ni,ni->n", u, radial)
    transverse = u - radial_speed[:, None] * radial
    transverse_frame, transverse_speed = _unit(transverse)
    flow_frame, speed = _unit(u)
    normal_frame, _ = _unit(np.cross(radial, transverse))
    q = radius / radius_scale
    eps = max(float(softening) / radius_scale, 1e-12)

    tree = cKDTree(position)
    distance, neighbors = tree.query(position, k=NEIGHBOR_COUNT, workers=1)
    if distance.ndim != 2 or not np.isfinite(distance).all():
        raise OperatorInventionError("nearest-neighbor construction failed")
    neighbor_radius = distance[:, -1] / radius_scale
    if np.any(neighbor_radius <= 0.0):
        raise OperatorInventionError("nearest-neighbor radius is degenerate")
    neighbor_mass = mass[neighbors]
    total_mass = float(np.sum(mass))
    local_mass_fraction = np.sum(neighbor_mass, axis=1) / total_mass
    local_density = local_mass_fraction / ((4.0 * math.pi / 3.0) * neighbor_radius**3)

    order = np.argsort(radius, kind="stable")
    cumulative = np.cumsum(mass[order]) / total_mass
    enclosed_mass = np.empty_like(cumulative)
    enclosed_mass[order] = cumulative
    enclosed_density = enclosed_mass / ((4.0 * math.pi / 3.0) * np.maximum(q, eps) ** 3)
    density_contrast = local_density / np.maximum(enclosed_density, 1e-12)

    neighbor_u = u[neighbors]
    mean_u = np.mean(neighbor_u, axis=1)
    velocity_dispersion = np.sqrt(np.mean(np.sum((neighbor_u - mean_u[:, None, :]) ** 2, axis=2), axis=1))
    rms_speed = np.sqrt(np.mean(np.sum(neighbor_u**2, axis=2), axis=1))
    velocity_coherence = np.linalg.norm(mean_u, axis=1) / np.maximum(rms_speed, 1e-12)
    local_radial_flow = np.einsum("ni,ni->n", mean_u, radial)

    dx = (position[neighbors] - position[:, None, :]) / radius_scale
    du = neighbor_u - u[:, None, :]
    gram = np.einsum("nki,nkj->nij", dx, dx)
    gram += GRADIENT_RIDGE * np.eye(3, dtype=np.float64)[None, :, :]
    rhs = np.einsum("nki,nkj->nij", dx, du)
    gradient = np.linalg.solve(gram, rhs)
    divergence = np.trace(gradient, axis1=1, axis2=2)
    symmetric = 0.5 * (gradient + np.swapaxes(gradient, 1, 2))
    traceless = symmetric - divergence[:, None, None] * np.eye(3)[None, :, :] / 3.0
    shear = np.sqrt(np.einsum("nij,nij->n", traceless, traceless))
    curl = np.stack(
        (
            gradient[:, 1, 2] - gradient[:, 2, 1],
            gradient[:, 2, 0] - gradient[:, 0, 2],
            gradient[:, 0, 1] - gradient[:, 1, 0],
        ),
        axis=1,
    )
    vorticity = np.linalg.norm(curl, axis=1)
    radial_strain = np.einsum("ni,nij,nj->n", radial, symmetric, radial)

    def scalar_gradient(value: np.ndarray) -> np.ndarray:
        delta = value[neighbors] - value[:, None]
        vector = np.einsum("nki,nk->ni", dx, delta)
        return np.linalg.solve(gram, vector[..., None])[..., 0]

    log_density = np.log(np.maximum(local_density, 1e-15))
    density_gradient_vector = scalar_gradient(log_density)
    coherence_gradient_vector = scalar_gradient(velocity_coherence)
    density_gradient_frame, density_gradient = _unit(-density_gradient_vector)
    coherence_gradient_frame, coherence_gradient = _unit(coherence_gradient_vector)

    potential = enclosed_mass / np.sqrt(q * q + eps * eps)
    field_energy = 0.5 * speed * speed - potential
    orbital_frequency = np.sqrt(enclosed_mass / (q**3 + eps**3))
    virial_ratio = speed * speed * q / (enclosed_mass + eps)
    angular_momentum = q * transverse_speed

    atoms = {
        "one": np.ones(len(position)),
        "q": q,
        "radial_speed": radial_speed,
        "speed": speed,
        "transverse_speed": transverse_speed,
        "time": np.full(len(position), clock_value * velocity_scale / radius_scale),
        "mass_ratio": mass / initial_mean_mass,
        "softening_ratio": np.full(len(position), eps),
        "cell_ratio": np.full(len(position), cell_width / radius_scale),
        "cluster_radius_ratio": np.full(len(position), cluster_radius / radius_scale),
        "cluster_separation_ratio": np.full(len(position), cluster_separation / radius_scale),
        "field_live": np.full(len(position), field_live),
        "enclosed_mass": enclosed_mass,
        "enclosed_density": enclosed_density,
        "neighbor_radius": neighbor_radius,
        "local_density": local_density,
        "density_contrast": density_contrast,
        "potential": potential,
        "field_energy": field_energy,
        "orbital_frequency": orbital_frequency,
        "virial_ratio": virial_ratio,
        "angular_momentum": angular_momentum,
        "velocity_dispersion": velocity_dispersion,
        "velocity_coherence": velocity_coherence,
        "local_radial_flow": local_radial_flow,
        "divergence": divergence,
        "shear": shear,
        "vorticity": vorticity,
        "radial_strain": radial_strain,
        "density_gradient": density_gradient,
        "coherence_gradient": coherence_gradient,
    }
    frames = {
        "radial": radial,
        "flow": flow_frame,
        "transverse": transverse_frame,
        "normal": normal_frame,
        "density_gradient": density_gradient_frame,
        "coherence_gradient": coherence_gradient_frame,
    }
    if set(atoms) != set(ATOMS) or set(frames) != set(FRAMES):
        raise OperatorInventionError("observable alphabet construction drifted")
    if not all(np.isfinite(value).all() for value in (*atoms.values(), *frames.values())):
        raise OperatorInventionError("observable construction produced nonfinite values")
    return atoms, frames


@functools.lru_cache(maxsize=32)
def _load_bundle(root_text: str) -> FeatureBundle:
    root = Path(root_text)
    receipt, analysis = _qualifying_metadata(root)
    slots = int(receipt["sample_slots"])
    tracers = int(receipt["tracer_count"])
    expected_history = slots * tracers * 4 * np.dtype("<f4").itemsize
    for name in ("history_pos.bin", "history_vel.bin"):
        if (root / name).stat().st_size != expected_history:
            raise OperatorInventionError(f"trajectory history size mismatch: {root / name}")
    position = np.fromfile(root / "history_pos.bin", dtype="<f4").reshape(slots, tracers, 4)
    velocity = np.fromfile(root / "history_vel.bin", dtype="<f4").reshape(slots, tracers, 4)
    steps = np.fromfile(root / "sample_steps.bin", dtype="<u4").astype(np.float64)
    if not np.isfinite(position).all() or not np.isfinite(velocity).all() or not np.all(np.diff(steps) > 0):
        raise OperatorInventionError(f"trajectory arrays are invalid: {root}")
    clock = steps * float(receipt["dt"])
    center = np.asarray(receipt["engine"]["window_center"], dtype=np.float64)
    initial = position[0, :, :3].astype(np.float64) - center
    initial_radius = np.linalg.norm(initial, axis=1)
    initial_live = position[0, :, 3] > 0.0
    radius_scale = float(np.median(initial_radius[initial_live]))
    mass_scale = float(receipt["initial_total_mass"])
    velocity_scale = math.sqrt(mass_scale / radius_scale)
    acceleration_scale = mass_scale / (radius_scale * radius_scale)
    initial_mean_mass = mass_scale / float(receipt["initial_live_count"])
    extents = np.asarray(receipt["extents"], dtype=np.float64)
    engine = receipt["engine"]
    cell_width = 2.0 * float(np.min(extents)) / float(receipt["grid_N"])

    atom_rows = {name: [] for name in ATOMS}
    frame_rows = {name: [] for name in FRAMES}
    target_rows: list[np.ndarray] = []
    middle_rows: list[np.ndarray] = []
    tracer_index = np.arange(tracers)
    for slot in range(1, slots - 1):
        raw_position = position[slot, :, :3].astype(np.float64) - center
        raw_velocity = velocity[slot, :, :3].astype(np.float64)
        mass = position[slot, :, 3].astype(np.float64)
        radius = np.linalg.norm(raw_position, axis=1)
        live = (mass > 0.0) & (radius > MINIMUM_RADIUS)
        live_indices = np.flatnonzero(live)
        snapshot_atoms, snapshot_frames = _snapshot_features(
            raw_position[live], raw_velocity[live], mass[live],
            radius_scale=radius_scale,
            mass_scale=mass_scale,
            velocity_scale=velocity_scale,
            clock_value=float(clock[slot]),
            initial_mean_mass=initial_mean_mass,
            softening=float(engine["softening"]),
            cell_width=cell_width,
            cluster_radius=float(engine["cluster_radius"]),
            cluster_separation=float(engine["cluster_separation"]),
            field_live=0.0 if bool(receipt["field_control"]["freeze_field"]) else 1.0,
        )
        selected_live = np.flatnonzero((live_indices % TRACER_MODULUS) == 0)
        selected_global = live_indices[selected_live]
        for name in ATOMS:
            atom_rows[name].append(snapshot_atoms[name][selected_live])
        for name in FRAMES:
            frame_rows[name].append(snapshot_frames[name][selected_live])
        acceleration = (
            velocity[slot + 1, selected_global, :3].astype(np.float64)
            - velocity[slot - 1, selected_global, :3].astype(np.float64)
        ) / (clock[slot + 1] - clock[slot - 1])
        target_rows.append(acceleration / acceleration_scale)
        middle_rows.append(np.full(len(selected_global), slot - 1, dtype=np.int32))
    atoms = {name: np.concatenate(rows) for name, rows in atom_rows.items()}
    frames = {name: np.concatenate(rows, axis=0) for name, rows in frame_rows.items()}
    target = np.concatenate(target_rows, axis=0)
    middle_index = np.concatenate(middle_rows)
    if not np.isfinite(target).all():
        raise OperatorInventionError(f"trajectory target contains nonfinite values: {root}")
    return FeatureBundle(
        arm_id=root.name,
        atoms=atoms,
        frames=frames,
        target=target,
        middle_index=middle_index,
        scales={"radius": radius_scale, "mass": mass_scale, "velocity": velocity_scale, "acceleration": acceleration_scale},
        source_summary={
            "seed": int(receipt["seed"]),
            "initial_condition": analysis.get("ic_name", receipt.get("geometry", {}).get("initial_condition")),
            "field_frozen": bool(receipt["field_control"]["freeze_field"]),
            "sample_slots": slots,
            "tracer_count": tracers,
            "domain_status": analysis["domain_status"],
            "relative_mass_error": float(analysis["relative_mass_error"]),
        },
    )


def _load_arm(root: Path, segment: str) -> ArmData:
    bundle = _load_bundle(str(root.resolve()))
    count = int(bundle.middle_index.max()) + 1
    cutoff = int(FIT_FRACTION * count)
    if segment == "early":
        mask = bundle.middle_index < cutoff
    elif segment == "late":
        mask = bundle.middle_index >= cutoff
    elif segment == "all":
        mask = np.ones(len(bundle.middle_index), dtype=bool)
    else:
        raise OperatorInventionError(f"unknown trajectory segment: {segment}")
    atoms = {name: value[mask] for name, value in bundle.atoms.items()}
    frames = {name: value[mask] for name, value in bundle.frames.items()}
    summary = dict(bundle.source_summary)
    summary["sample_count"] = int(np.count_nonzero(mask))
    summary["feature_sha256"] = _feature_digest(atoms, frames)
    return ArmData(
        arm_id=bundle.arm_id,
        segment=segment,
        atoms=atoms,
        frames=frames,
        target=bundle.target[mask],
        scales=dict(bundle.scales),
        source_summary=summary,
    )


def _load_development(workspace: Path, campaign: CampaignSpec) -> tuple[list[ArmData], list[ArmData]]:
    return (
        [_load_arm(workspace / relative, "early") for relative in campaign.development_roots],
        [_load_arm(workspace / relative, "late") for relative in campaign.development_roots],
    )

def _load_holdout(workspace: Path, campaign: CampaignSpec) -> list[ArmData]:
    return [_load_arm(workspace / relative, "all") for relative in campaign.hidden_holdout]


def _seed_scalars() -> list[dict[str, Any]]:
    return [typed._atom(name) for name in ATOMS]


def _mutations(parent: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [typed._canonical_program(parent)]
    rows.extend({"op": op, "arg": parent} for op in UNARY_OPS)
    rows.extend({"op": "multiply", "args": [parent, typed._atom(name)]} for name in MUTATION_COMPANIONS)
    rows.extend(
        {"op": "divide_one_plus_abs", "numerator": parent, "denominator": typed._atom(name)}
        for name in MUTATION_COMPANIONS
    )
    canonical = {_digest(typed._canonical_program(row)): typed._canonical_program(row) for row in rows}
    result = [canonical[key] for key in sorted(canonical)]
    if not 2 <= len(result) <= 32:
        raise OperatorInventionError("full-observable mutation family exceeds field selection bound")
    return result


def _single_term_equations(frame: str, scalars: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [typed._canonical_equation([{"frame": frame, "scalar": scalar}], kind="field-constructed") for scalar in scalars]


def _run_construction(organism: Any, *, campaign_id: str, fit_arms: Sequence[ArmData], validation_arms: Sequence[ArmData]) -> dict[str, Any]:
    seeds_by_frame: dict[str, Any] = {}
    mutations_by_frame: dict[str, Any] = {}
    evolved_terms: dict[str, Any] = {}
    selection_records: list[dict[str, Any]] = []
    for frame in FRAMES:
        seeds = typed._evaluate_candidates(_single_term_equations(frame, _seed_scalars()), fit_arms, validation_arms)
        seed_selection = typed._field_select(organism, campaign_id=campaign_id, laboratory_id=f"full-seed-{frame}", candidates=seeds)
        selection_records.append(seed_selection)
        selected_seed = seeds[str(seed_selection["candidate_id"])]
        parent = selected_seed["equation"]["terms"][0]
        mutations = typed._evaluate_candidates(_single_term_equations(frame, _mutations(parent["scalar"])), fit_arms, validation_arms)
        mutation_selection = typed._field_select(organism, campaign_id=campaign_id, laboratory_id=f"full-mutation-{frame}", candidates=mutations)
        selection_records.append(mutation_selection)
        selected_mutation = mutations[str(mutation_selection["candidate_id"])]
        evolved_terms[frame] = selected_mutation["equation"]["terms"][0]
        seeds_by_frame[frame] = {"candidate_results": seeds, "selection": seed_selection, "selected_term": parent}
        mutations_by_frame[frame] = {"parent_candidate": seed_selection["candidate_id"], "parent_term": parent, "candidate_results": mutations, "selection": mutation_selection, "selected_term": evolved_terms[frame]}
    equations = [typed._canonical_equation([term], kind="field-constructed") for term in evolved_terms.values()]
    equations.extend(
        typed._canonical_equation([evolved_terms[left], evolved_terms[right]], kind="field-constructed")
        for left, right in itertools.combinations(FRAMES, 2)
    )
    equations.extend(typed._human_equations().values())
    synthesis = typed._evaluate_candidates(equations, fit_arms, validation_arms)
    final_selection = typed._field_select(organism, campaign_id=campaign_id, laboratory_id="full-observable-synthesis", candidates=synthesis)
    selection_records.append(final_selection)
    return {
        "seed_phase": seeds_by_frame,
        "mutation_phase": mutations_by_frame,
        "evolved_terms": evolved_terms,
        "synthesis_candidates": synthesis,
        "final_selection": final_selection,
        "selection_records": selection_records,
    }


def _arm_summary(arms: Sequence[ArmData]) -> list[dict[str, Any]]:
    return [{"arm_id": arm.arm_id, "segment": arm.segment, "scales": arm.scales, "source_summary": arm.source_summary} for arm in arms]


def _classify(
    selected: Mapping[str, Any],
    synthesis: Mapping[str, Mapping[str, Any]],
    holdout_arms: Sequence[ArmData],
    campaign: CampaignSpec,
) -> dict[str, Any]:
    selected_metrics = typed._holdout_metrics(selected, holdout_arms)
    controls = {
        name: next(candidate for candidate in synthesis.values() if candidate["equation"]["kind"] == equation["kind"])
        for name, equation in typed._human_equations().items()
    }
    control_metrics = {name: {**typed._holdout_metrics(candidate, holdout_arms), "candidate_id": candidate["candidate_id"]} for name, candidate in controls.items()}
    cosines = {name: typed._prediction_cosine(selected, candidate, holdout_arms) for name, candidate in controls.items()}
    threshold = _protocol_contract(campaign)["classification"]
    best_mean = min(metric["mean_nrmse"] for metric in control_metrics.values())
    relative_improvement = 1.0 - selected_metrics["mean_nrmse"] / best_mean
    per_arm_ok = all(
        selected_metrics["nrmse_by_arm"][arm.arm_id]
        <= (1.0 + threshold["maximum_per_arm_relative_regression"])
        * min(metric["nrmse_by_arm"][arm.arm_id] for metric in control_metrics.values())
        for arm in holdout_arms
    )
    human_equivalent = selected["equation"]["kind"].startswith("human-") or max(cosines.values()) >= threshold["semantic_cosine"]
    if human_equivalent:
        classification = "HUMAN_EQUIVALENT"
    elif selected_metrics["mean_nrmse"] >= threshold["unsupported_nrmse"]:
        classification = "UNSUPPORTED_REGIME_MODEL"
    elif relative_improvement >= threshold["minimum_relative_improvement"] and per_arm_ok:
        classification = "FULL_OBSERVABLE_LAW"
    else:
        classification = "REGIME_CONDITIONED_DESCRIPTION"
    return {
        "classification": classification,
        "selected": selected_metrics,
        "human_comparators": control_metrics,
        "prediction_cosine_to_human_comparators": cosines,
        "relative_improvement_over_best_human": relative_improvement,
        "per_arm_regression_gate": per_arm_ok,
        "scope": "dimensionless regime-aware collective law; not a microscopic-force replacement",
    }


def _scalar_text(program: Mapping[str, Any]) -> str:
    program = typed._canonical_program(program)
    op = program["op"]
    if op == "atom":
        return str(program["name"])
    if op == "control_power":
        return f"q^({program['power']:g})"
    if op in UNARY_OPS:
        return f"{op}({_scalar_text(program['arg'])})"
    if op == "multiply":
        return "*".join(f"({_scalar_text(arg)})" for arg in program["args"])
    if op == "divide_one_plus_abs":
        return f"({_scalar_text(program['numerator'])})/(1+abs({_scalar_text(program['denominator'])}))"
    raise OperatorInventionError(f"cannot render scalar operation: {op}")


def _render(candidate: Mapping[str, Any]) -> str:
    frame_text = {
        "radial": "r_hat", "flow": "u_hat", "transverse": "u_perp_hat",
        "normal": "L_hat", "density_gradient": "-grad_log_rho_hat",
        "coherence_gradient": "grad_coherence_hat",
    }
    terms = [f"{coefficient:+.12g}*{frame_text[term['frame']]}*({_scalar_text(term['scalar'])})" for coefficient, term in zip(candidate["coefficients"], candidate["equation"]["terms"], strict=True)]
    return "a/A0 = " + " ".join(terms).lstrip("+")


def _synthetic_arm(*, arm_id: str, target_term: Mapping[str, Any]) -> ArmData:
    index = np.arange(1, 258, dtype=np.float64)
    atoms = {name: 0.2 + ((position + 1) * 0.013 * index) % (0.9 + 0.01 * position) for position, name in enumerate(ATOMS)}
    atoms["one"] = np.ones(len(index))
    angle = index * 0.173
    radial = np.stack((np.cos(angle), np.sin(angle), 0.2 * np.sin(index * 0.11)), axis=1)
    radial /= np.linalg.norm(radial, axis=1, keepdims=True)
    tangent = np.stack((-np.sin(angle), np.cos(angle), 0.15 * np.cos(index * 0.07)), axis=1)
    tangent /= np.linalg.norm(tangent, axis=1, keepdims=True)
    normal = np.cross(radial, tangent); normal /= np.linalg.norm(normal, axis=1, keepdims=True)
    density = np.stack((np.cos(index * 0.09), np.sin(index * 0.09), np.ones(len(index))), axis=1); density /= np.linalg.norm(density, axis=1, keepdims=True)
    coherence = np.stack((np.ones(len(index)), np.cos(index * 0.05), np.sin(index * 0.05)), axis=1); coherence /= np.linalg.norm(coherence, axis=1, keepdims=True)
    frames = {"radial": radial, "flow": tangent, "transverse": np.cross(normal, tangent), "normal": normal, "density_gradient": density, "coherence_gradient": coherence}
    shell = ArmData(arm_id=arm_id, segment="synthetic", atoms=atoms, frames=frames, target=np.zeros((len(index), 3)), scales={"radius": 1.0, "mass": 1.0, "velocity": 1.0, "acceleration": 1.0}, source_summary={"kind": "synthetic"})
    shell.target = 1.375 * typed._term_value(target_term, shell)
    return shell


def calibration_controls() -> dict[str, Any]:
    supports = {
        "enclosed-mass": {"frame": "radial", "scalar": typed._atom("enclosed_mass")},
        "field-energy": {"frame": "flow", "scalar": typed._atom("field_energy")},
        "divergence": {"frame": "transverse", "scalar": typed._atom("divergence")},
        "strain": {"frame": "normal", "scalar": typed._atom("shear")},
        "density-gradient": {"frame": "density_gradient", "scalar": typed._atom("density_gradient")},
        "coherence-gradient": {"frame": "coherence_gradient", "scalar": typed._atom("coherence_gradient")},
    }
    controls: dict[str, Any] = {}
    for name, term in supports.items():
        arm = _synthetic_arm(arm_id=f"synthetic-{name}", target_term=term)
        equation = typed._canonical_equation([term], kind=f"synthetic-{name}")
        result = typed._evaluate_candidate(equation, [arm], [arm])
        controls[name] = {"status": "PASS" if result["validation_mean_nrmse"] <= 1e-10 else "FAIL", "validation_nrmse": result["validation_mean_nrmse"], "candidate_id": result["candidate_id"]}
    replay = _synthetic_arm(arm_id="synthetic-replay", target_term=supports["field-energy"])
    first = _feature_digest(replay.atoms, replay.frames)
    second = _feature_digest(copy.deepcopy(replay.atoms), copy.deepcopy(replay.frames))
    controls["deterministic-feature-replay"] = {"status": "PASS" if first == second else "FAIL", "feature_sha256": first}
    original_target = replay.target.copy()
    replay.target = replay.target + 17.0
    target_independent = first == _feature_digest(replay.atoms, replay.frames)
    replay.target = original_target
    controls["target-independence"] = {"status": "PASS" if target_independent else "FAIL"}
    controls["alphabet"] = {"status": "PASS" if len(ATOMS) == 31 and len(FRAMES) == 6 else "FAIL", "atom_count": len(ATOMS), "frame_count": len(FRAMES)}
    if any(control["status"] != "PASS" for control in controls.values()):
        raise OperatorInventionError("full-observable calibration failed")
    return controls


def _with_digest(body: Mapping[str, Any]) -> dict[str, Any]:
    plain = copy.deepcopy(dict(body))
    plain["result_sha256"] = _digest(plain)
    return plain


def _build_receipt(*, organism: Any, workspace: Path, campaign: CampaignSpec, source_manifest: list[dict[str, Any]], campaign_id: str, fit_arms: Sequence[ArmData], validation_arms: Sequence[ArmData], construction: Mapping[str, Any], selected: Mapping[str, Any], holdout_arms: Sequence[ArmData], holdout: Mapping[str, Any], outcome: Mapping[str, Any], controls: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "campaign_id": campaign_id,
        "workspace": str(workspace),
        "organism_home": str(organism.home.resolve()),
        "protocol": _protocol_contract(campaign),
        "preregistration": {"path": campaign.preregistration, "sha256": next(row["sha256"] for row in source_manifest if row["path"] == campaign.preregistration)},
        "previous_operator_receipt": {"path": _PREVIOUS_RECEIPT, "sha256": next(row["sha256"] for row in source_manifest if row["path"] == _PREVIOUS_RECEIPT)},
        "implementation_sha256": _file_sha256(Path(__file__)),
        "source_manifest": source_manifest,
        "measurement_identity_sha256": _digest({"schema": SCHEMA, "protocol": _protocol_contract(campaign), "sources": source_manifest, "implementation_sha256": _file_sha256(Path(__file__))}),
        "calibration_controls": dict(controls),
        "development": {"fit_arms": _arm_summary(fit_arms), "validation_arms": _arm_summary(validation_arms)},
        "construction": dict(construction),
        "selected_equation": {"candidate_id": selected["candidate_id"], "equation": selected["equation"], "coefficients": selected["coefficients"], "rendered": _render(selected), "validation_mean_nrmse": selected["validation_mean_nrmse"]},
        "hidden_holdout": {"arms": _arm_summary(holdout_arms), **dict(holdout)},
        "field_outcome": dict(outcome),
        "model_calls": 0,
    }


def _verify_field_records(receipt: Mapping[str, Any]) -> int:
    home = Path(str(receipt["organism_home"]))
    count = 0
    with open_research_residency(home / "root") as residency:
        for selection in receipt["construction"]["selection_records"]:
            record = residency._record(selection["selection_record_id"])
            if record is None:
                raise OperatorInventionError("full-observable selection record is missing")
            payload = record.get("payload", {})
            if payload.get("campaign_id") != receipt["campaign_id"] or payload.get("candidate_id") != selection["candidate_id"] or payload.get("holdout_visible_during_selection") is not False:
                raise OperatorInventionError("full-observable selection record changed")
            count += 1
        outcome = receipt["field_outcome"]
        record = residency._record(outcome["record_id"])
        if record is None:
            raise OperatorInventionError("full-observable outcome record is missing")
        payload = record.get("payload", {})
        if payload.get("campaign_id") != receipt["campaign_id"] or payload.get("selected_result_sha256") != outcome["selected_result_sha256"] or payload.get("holdout_revealed_after_selection") is not True:
            raise OperatorInventionError("full-observable outcome record changed")
        count += 1
    return count


def _rebuild_construction(receipt: Mapping[str, Any], fit_arms: Sequence[ArmData], validation_arms: Sequence[ArmData]) -> dict[str, Any]:
    recorded = receipt["construction"]
    evolved_terms: dict[str, Any] = {}
    seed_results: dict[str, Any] = {}
    mutation_results: dict[str, Any] = {}
    selections: list[dict[str, Any]] = []
    for frame in FRAMES:
        seeds = typed._evaluate_candidates(_single_term_equations(frame, _seed_scalars()), fit_arms, validation_arms)
        seed_selection = recorded["seed_phase"][frame]["selection"]
        if seed_selection["candidate_id"] != typed._metric_winner(seeds):
            raise OperatorInventionError("recorded full-observable seed is not the metric winner")
        selected_seed = seeds[str(seed_selection["candidate_id"])]
        parent = selected_seed["equation"]["terms"][0]
        mutations = typed._evaluate_candidates(_single_term_equations(frame, _mutations(parent["scalar"])), fit_arms, validation_arms)
        mutation_selection = recorded["mutation_phase"][frame]["selection"]
        if mutation_selection["candidate_id"] != typed._metric_winner(mutations):
            raise OperatorInventionError("recorded full-observable mutation is not the metric winner")
        evolved_terms[frame] = mutations[str(mutation_selection["candidate_id"])]["equation"]["terms"][0]
        seed_results[frame] = {"candidate_results": seeds, "selection": seed_selection, "selected_term": parent}
        mutation_results[frame] = {"parent_candidate": seed_selection["candidate_id"], "parent_term": parent, "candidate_results": mutations, "selection": mutation_selection, "selected_term": evolved_terms[frame]}
        selections.extend((seed_selection, mutation_selection))
    equations = [typed._canonical_equation([term], kind="field-constructed") for term in evolved_terms.values()]
    equations.extend(typed._canonical_equation([evolved_terms[left], evolved_terms[right]], kind="field-constructed") for left, right in itertools.combinations(FRAMES, 2))
    equations.extend(typed._human_equations().values())
    synthesis = typed._evaluate_candidates(equations, fit_arms, validation_arms)
    final_selection = recorded["final_selection"]
    if final_selection["candidate_id"] != typed._metric_winner(synthesis):
        raise OperatorInventionError("recorded full-observable synthesis is not the metric winner")
    selections.append(final_selection)
    return {"seed_phase": seed_results, "mutation_phase": mutation_results, "evolved_terms": evolved_terms, "synthesis_candidates": synthesis, "final_selection": final_selection, "selection_records": selections}


def _verify_sources(receipt: Mapping[str, Any]) -> tuple[Path, CampaignSpec]:
    workspace = Path(str(receipt["workspace"])).resolve(strict=True)
    protocol = receipt.get("protocol")
    if not isinstance(protocol, Mapping):
        raise OperatorInventionError("full-observable protocol is missing")
    campaign = _campaign_spec(str(protocol.get("campaign_kind", "")))
    manifest = receipt.get("source_manifest")
    if not isinstance(manifest, list) or sorted(row.get("path") for row in manifest) != _expected_source_paths(campaign):
        raise OperatorInventionError("full-observable source manifest changed")
    for row in manifest:
        path = workspace / str(row["path"])
        if not path.is_file() or path.stat().st_size != int(row["bytes"]) or _file_sha256(path) != row["sha256"]:
            raise OperatorInventionError(f"full-observable source changed: {path}")
    if receipt.get("protocol") != _protocol_contract(campaign) or receipt.get("implementation_sha256") != _file_sha256(Path(__file__)):
        raise OperatorInventionError("full-observable implementation contract changed")
    identity = _digest({"schema": SCHEMA, "protocol": _protocol_contract(campaign), "sources": manifest, "implementation_sha256": receipt["implementation_sha256"]})
    if receipt.get("measurement_identity_sha256") != identity or receipt.get("campaign_id") != identity[:24]:
        raise OperatorInventionError("full-observable measurement identity changed")
    return workspace, campaign


def _exercise_mutations(receipt: Mapping[str, Any]) -> dict[str, str]:
    mutations: dict[str, dict[str, Any]] = {}
    source = copy.deepcopy(dict(receipt)); source["source_manifest"][0]["sha256"] = "0" * 64; mutations["source-hash"] = source
    split = copy.deepcopy(dict(receipt)); split["protocol"]["fit_fraction"] = 0.61; mutations["split"] = split
    atom = copy.deepcopy(dict(receipt)); atom["protocol"]["atoms"][1] = "mutated-q"; mutations["atom"] = atom
    frame = copy.deepcopy(dict(receipt)); frame["selected_equation"]["equation"]["terms"][0]["frame"] = next(name for name in FRAMES if name != frame["selected_equation"]["equation"]["terms"][0]["frame"]); mutations["frame"] = frame
    neighbor = copy.deepcopy(dict(receipt)); neighbor["protocol"]["neighbor_count"] = 15; mutations["neighbor-count"] = neighbor
    ridge = copy.deepcopy(dict(receipt)); ridge["protocol"]["gradient_ridge"] = 1e-8; mutations["gradient-ridge"] = ridge
    coefficient = copy.deepcopy(dict(receipt)); coefficient["selected_equation"]["coefficients"][0] += 0.125; mutations["coefficient"] = coefficient
    lineage = copy.deepcopy(dict(receipt)); lineage["construction"]["selection_records"] = lineage["construction"]["selection_records"][1:]; mutations["lineage"] = lineage
    classification = copy.deepcopy(dict(receipt)); classification["hidden_holdout"]["classification"] = "HUMAN_EQUIVALENT" if classification["hidden_holdout"]["classification"] != "HUMAN_EQUIVALENT" else "UNSUPPORTED_REGIME_MODEL"; mutations["classification"] = classification
    results: dict[str, str] = {}
    for name, mutated in mutations.items():
        mutated.pop("result_sha256", None)
        mutated = _with_digest(mutated)
        try:
            verify_full_observable_receipt(mutated, check_mutation_controls=False)
        except (AssertionError, KeyError, OSError, ValueError, OperatorInventionError):
            results[name] = "PASS"
        else:
            results[name] = "FAIL"
    return results


def run_full_observable_invention(
    organism: Any,
    *,
    workspace: Path,
    campaign_kind: str = DEFAULT_CAMPAIGN_KIND,
) -> dict[str, Any]:
    workspace = Path(workspace).resolve(strict=True)
    campaign = _campaign_spec(campaign_kind)
    source_manifest = _source_manifest(workspace, campaign)
    controls = calibration_controls()
    fit_arms, validation_arms = _load_development(workspace, campaign)
    implementation = _file_sha256(Path(__file__))
    identity = _digest({"schema": SCHEMA, "protocol": _protocol_contract(campaign), "sources": source_manifest, "implementation_sha256": implementation})
    campaign_id = identity[:24]
    construction = _run_construction(organism, campaign_id=campaign_id, fit_arms=fit_arms, validation_arms=validation_arms)
    selected_id = str(construction["final_selection"]["candidate_id"])
    selected = construction["synthesis_candidates"][selected_id]
    holdout_arms = _load_holdout(workspace, campaign)
    holdout = _classify(selected, construction["synthesis_candidates"], holdout_arms, campaign)
    selected_result = {"selected_equation": {"candidate_id": selected_id, "equation": selected["equation"], "coefficients": selected["coefficients"], "rendered": _render(selected)}, "hidden_holdout": holdout}
    outcome = organism.admit_laboratory_outcome(campaign_id=campaign_id, laboratory_id="full-observable-discovery", candidate_id=selected_id, selected_result=selected_result)
    body = _build_receipt(organism=organism, workspace=workspace, campaign=campaign, source_manifest=source_manifest, campaign_id=campaign_id, fit_arms=fit_arms, validation_arms=validation_arms, construction=construction, selected=selected, holdout_arms=holdout_arms, holdout=holdout, outcome=outcome, controls=controls)
    core = _with_digest(body)
    mutations = _exercise_mutations(core)
    if any(value != "PASS" for value in mutations.values()):
        raise OperatorInventionError("full-observable verifier mutation control failed")
    body["mutation_controls"] = mutations
    return _with_digest(body)


def verify_full_observable_receipt(receipt: Mapping[str, Any], *, check_mutation_controls: bool = True) -> dict[str, Any]:
    body = copy.deepcopy(dict(receipt))
    claimed = body.pop("result_sha256", None)
    if not isinstance(claimed, str) or claimed != _digest(body):
        raise OperatorInventionError("full-observable receipt digest mismatch")
    if receipt.get("schema") != SCHEMA or receipt.get("model_calls") != 0:
        raise OperatorInventionError("full-observable receipt contract changed")
    workspace, campaign = _verify_sources(receipt)
    field_records = _verify_field_records(receipt)
    controls = calibration_controls()
    if receipt.get("calibration_controls") != controls:
        raise OperatorInventionError("full-observable calibration reconstruction mismatch")
    fit_arms, validation_arms = _load_development(workspace, campaign)
    if receipt["development"]["fit_arms"] != _arm_summary(fit_arms) or receipt["development"]["validation_arms"] != _arm_summary(validation_arms):
        raise OperatorInventionError("full-observable development split changed")
    construction = _rebuild_construction(receipt, fit_arms, validation_arms)
    if receipt.get("construction") != construction:
        raise OperatorInventionError("full-observable construction reconstruction mismatch")
    selected_id = str(construction["final_selection"]["candidate_id"])
    selected = construction["synthesis_candidates"][selected_id]
    expected_selected = {"candidate_id": selected_id, "equation": selected["equation"], "coefficients": selected["coefficients"], "rendered": _render(selected), "validation_mean_nrmse": selected["validation_mean_nrmse"]}
    if receipt.get("selected_equation") != expected_selected:
        raise OperatorInventionError("full-observable selected equation changed")
    holdout_arms = _load_holdout(workspace, campaign)
    expected_holdout = {"arms": _arm_summary(holdout_arms), **_classify(selected, construction["synthesis_candidates"], holdout_arms, campaign)}
    if receipt.get("hidden_holdout") != expected_holdout:
        raise OperatorInventionError("full-observable holdout reconstruction mismatch")
    recorded_mutations = receipt.get("mutation_controls", {})
    if check_mutation_controls:
        core = copy.deepcopy(dict(receipt)); core.pop("mutation_controls", None); core.pop("result_sha256", None)
        rebuilt = _exercise_mutations(_with_digest(core))
        if recorded_mutations != rebuilt or any(value != "PASS" for value in rebuilt.values()):
            raise OperatorInventionError("full-observable mutation controls failed reconstruction")
    return {
        "schema": VERIFICATION_SCHEMA,
        "status": "PASS",
        "result_sha256": claimed,
        "classification": expected_holdout["classification"],
        "selected_candidate": selected_id,
        "selection_records_verified": field_records,
        "source_hashes_verified": len(receipt["source_manifest"]),
        "feature_atoms_verified": len(ATOMS),
        "vector_frames_verified": len(FRAMES),
        "mutation_controls_verified": len(recorded_mutations) if check_mutation_controls else 0,
        "model_calls": 0,
    }


__all__ = [
    "ATOMS", "FRAMES", "SCHEMA", "VERIFICATION_SCHEMA", "OperatorInventionError",
    "calibration_controls", "run_full_observable_invention", "verify_full_observable_receipt",
]
