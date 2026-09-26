from __future__ import annotations

"""Continuing field-owned study of scheduled, nonlinear CassiCosmos worlds."""

import hashlib
import json
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from cassi_cosmos_adapter import (
    CassiCosmosWorldFactoryController,
    authorize_cassicosmos_seed,
)
from cassi_field_atlas import canonical_json_bytes, sha256_value
from cassi_field_input import CODEC_JSON
from cassi_field_owner import CapacityLimits, SourceInput
from cassi_reality_residency import Deposit
from cassi_research_residency import ResearchResidency, open_research_residency
from cassi_field_cognition import experiment_schedule_fingerprint


SCHEMA = "cassifi.autonomous-physics-residency-receipt.v8"
MANIFEST_SCHEMA = "cassifi.autonomous-physics-residency-manifest.v8"
WORLD_SCHEMA = "cassifi.scheduled-physics-world.v1"
GRID_N = 64
COMPOSITION_REPRESENTATION_ID = "physics:scheduled-pulse-composition"
COLLISION_REPRESENTATION_ID = "physics:spatiotemporal-dominance"
CLAMP_REPRESENTATION_ID = "physics:nonlinear-clamp-regime"
TEMPORAL_REPRESENTATION_ID = "physics:long-horizon-direction"
EXPERIMENT_CONSTRUCTOR_ID = "physics:experiment-constructor"
EXPERIMENT_LANGUAGE_GENERATION_1_ID = "physics:generated-experiment-language:g1"
EXPERIMENT_LANGUAGE_GENERATION_2_ID = "physics:generated-experiment-language:g2"
EXPERIMENT_LANGUAGE_GENERATION_3_ID = "physics:generated-experiment-language:g3"
RESEARCH_PROGRAM_ID = "physics:autonomous-research-program"
RESEARCH_STAGE_GENERATION_3_ID = "generation-3-nonmonotone-routing"
MECHANISM_EXPERIMENT_ID = "physics:phase-flow-mechanism-experiment"
DISTRIBUTED_PHASE_EXPERIMENT_ID = (
    "physics:distributed-phase-flow-experiment"
)
PHASE_CURRENT_TOPOLOGY_EXPERIMENT_ID = (
    "physics:phase-current-topology-experiment"
)
CLAMP_EPS2_THRESHOLD = 63.0
_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_RESIDENT_PROFILE = {"default_value_words": 4_096, "mode_count": 1_572_864}
_RESIDENT_OBSERVATION_PAGE_SIZE = 31
_RESIDENT_LIMITS = CapacityLimits(
    max_state_bytes=256 * 1024 * 1024,
    max_workspace_bytes=128 * 1024 * 1024,
)


def _distributed_phase_fields() -> list[str]:
    return [
        f"{prefix}_x{bin_index:02d}"
        for prefix in ("phase_abs_jx", "phase_jx", "phase_q")
        for bin_index in range(16)
    ]


def _phase_topology_fields() -> list[str]:
    return [
        f"{prefix}_b{bin_index:02d}"
        for prefix in (
            "phase_topology_jx",
            "phase_topology_jy",
            "phase_topology_jz",
            "phase_topology_q",
        )
        for bin_index in range(64)
    ]
def _phase_winding_fields() -> list[str]:
    return [
        f"{prefix}_{plane}_r{radius:02d}"
        for prefix in (
            "phase_winding",
            "phase_winding_circ",
            "phase_winding_current",
            "phase_winding_qmin",
        )
        for plane in ("xy", "xz", "yz")
        for radius in (2, 4, 8)
    ]



class AutonomousPhysicsResidencyError(RuntimeError):
    """The residency cannot preserve its physical or evidence boundary."""


@dataclass(frozen=True, slots=True)
class ScheduledSegment:
    deposits: tuple[Deposit, ...]
    steps: int

    def __post_init__(self) -> None:
        if isinstance(self.steps, bool) or not isinstance(self.steps, int) or self.steps < 1:
            raise AutonomousPhysicsResidencyError("scheduled segment steps must be positive")
        if len(self.deposits) > 64:
            raise AutonomousPhysicsResidencyError("scheduled segment has too many deposits")

    def as_dict(self) -> dict[str, Any]:
        return {
            "deposits": [deposit.as_dict() for deposit in self.deposits],
            "steps": self.steps,
        }


@dataclass(frozen=True, slots=True)
class ScheduledPhysicsWorld:
    world_id: str
    regime: str
    split: str
    segments: tuple[ScheduledSegment, ...]
    features: tuple[tuple[str, float], ...]
    source_of: str | None = None

    def __post_init__(self) -> None:
        if _RUN_ID.fullmatch(self.world_id) is None:
            raise AutonomousPhysicsResidencyError("world identity is invalid")
        if not self.regime or not self.split or not self.segments or len(self.segments) > 16:
            raise AutonomousPhysicsResidencyError("scheduled world declaration is invalid")
        if sum(segment.steps for segment in self.segments) > 100_000:
            raise AutonomousPhysicsResidencyError("scheduled world horizon is outside its bound")
        names = [name for name, _ in self.features]
        if names != sorted(set(names)):
            raise AutonomousPhysicsResidencyError("world features must be sorted and unique")
        if any(not math.isfinite(float(value)) for _, value in self.features):
            raise AutonomousPhysicsResidencyError("world features must be finite")

    @property
    def horizons(self) -> tuple[int, ...]:
        total = 0
        values = []
        for segment in self.segments:
            total += segment.steps
            values.append(total)
        return tuple(values)

    @property
    def feature_values(self) -> dict[str, float]:
        return {name: float(value) for name, value in self.features}

    def as_dict(self) -> dict[str, Any]:
        return {
            "features": self.feature_values,
            "horizons": list(self.horizons),
            "regime": self.regime,
            "segments": [segment.as_dict() for segment in self.segments],
            "source_of": self.source_of,
            "split": self.split,
            "world_id": self.world_id,
        }


@dataclass(frozen=True, slots=True)
class AutonomousPhysicsCurriculum:
    calibration: ScheduledPhysicsWorld
    composition_training: tuple[ScheduledPhysicsWorld, ...]
    composition_holdout: tuple[ScheduledPhysicsWorld, ...]
    composition_transfer: tuple[ScheduledPhysicsWorld, ...]
    collision_training: tuple[ScheduledPhysicsWorld, ...]
    collision_holdout: tuple[ScheduledPhysicsWorld, ...]
    collision_transfer: tuple[ScheduledPhysicsWorld, ...]
    collision_surprise: ScheduledPhysicsWorld
    delayed_training: tuple[ScheduledPhysicsWorld, ...]
    delayed_holdout: tuple[ScheduledPhysicsWorld, ...]
    delayed_transfer: tuple[ScheduledPhysicsWorld, ...]
    clamp_training: tuple[ScheduledPhysicsWorld, ...]
    clamp_holdout: tuple[ScheduledPhysicsWorld, ...]
    clamp_transfer: tuple[ScheduledPhysicsWorld, ...]
    repeats: tuple[ScheduledPhysicsWorld, ...]

    @property
    def groups(self) -> dict[str, tuple[ScheduledPhysicsWorld, ...]]:
        return {
            "calibration": (self.calibration,),
            "clamp_holdout": self.clamp_holdout,
            "clamp_training": self.clamp_training,
            "clamp_transfer": self.clamp_transfer,
            "collision_holdout": self.collision_holdout,
            "collision_surprise": (self.collision_surprise,),
            "collision_training": self.collision_training,
            "collision_transfer": self.collision_transfer,
            "composition_holdout": self.composition_holdout,
            "composition_training": self.composition_training,
            "composition_transfer": self.composition_transfer,
            "delayed_holdout": self.delayed_holdout,
            "delayed_training": self.delayed_training,
            "delayed_transfer": self.delayed_transfer,
            "repeats": self.repeats,
        }

    @property
    def all_worlds(self) -> tuple[ScheduledPhysicsWorld, ...]:
        return tuple(world for group in self.groups.values() for world in group)


def _deposit(x: float, cy: float, *, y: float = 0.0, z: float = 0.0) -> Deposit:
    return Deposit(x=x, y=y, z=z, cy=cy, ci=0.0, sigma=1.0)


def _features(**values: float) -> tuple[tuple[str, float], ...]:
    return tuple(sorted((name, float(value)) for name, value in values.items()))


def _composition_world(
    world_id: str,
    split: str,
    first: float,
    second: float,
    *,
    source_of: str | None = None,
) -> ScheduledPhysicsWorld:
    position = (0.17, -0.21, 0.33)
    return ScheduledPhysicsWorld(
        world_id=world_id,
        regime="scheduled-pulse-composition",
        split=split,
        segments=(
            ScheduledSegment((_deposit(position[0], first, y=position[1], z=position[2]),), 4),
            ScheduledSegment((_deposit(position[0], second, y=position[1], z=position[2]),), 4),
        ),
        features=_features(first_charge=first, second_charge=second),
        source_of=source_of,
    )


def _collision_world(
    world_id: str,
    split: str,
    left: float,
    right: float,
    *,
    source_of: str | None = None,
) -> ScheduledPhysicsWorld:
    return ScheduledPhysicsWorld(
        world_id=world_id,
        regime="simultaneous-spatial-collision",
        split=split,
        segments=(
            ScheduledSegment(
                (
                    _deposit(-0.55, left, y=0.08, z=-0.11),
                    _deposit(0.55, right, y=0.08, z=-0.11),
                ),
                8,
            ),
        ),
        features=_features(delay_steps=0.0, left_strength=left, right_strength=right),
        source_of=source_of,
    )


def _delayed_collision_world(
    world_id: str,
    split: str,
    left: float,
    right: float,
    delay: int,
    *,
    post_steps: int = 8,
) -> ScheduledPhysicsWorld:
    return ScheduledPhysicsWorld(
        world_id=world_id,
        regime="delayed-spatial-collision",
        split=split,
        segments=(
            ScheduledSegment((_deposit(-0.55, left, y=0.08, z=-0.11),), delay),
            ScheduledSegment((_deposit(0.55, right, y=0.08, z=-0.11),), post_steps),
        ),
        features=_features(
            delay_steps=float(delay),
            left_strength=left,
            right_strength=right,
        ),
    )


def _clamp_world(
    world_id: str,
    split: str,
    first: float,
    second: float,
) -> ScheduledPhysicsWorld:
    return ScheduledPhysicsWorld(
        world_id=world_id,
        regime="nonlinear-clamp-and-long-horizon",
        split=split,
        segments=(
            ScheduledSegment(
                (
                    _deposit(0.21, first, y=-0.27, z=0.14),
                    _deposit(0.21, second, y=-0.27, z=0.14),
                ),
                1,
            ),
            ScheduledSegment((), 7),
            ScheduledSegment((), 24),
            ScheduledSegment((), 96),
        ),
        features=_features(first_charge=first, second_charge=second),
    )


def build_autonomous_physics_curriculum() -> AutonomousPhysicsCurriculum:
    """Create the deterministic multi-regime world sequence."""

    composition_training = tuple(
        _composition_world(f"composition-train-{index:02d}", "training", first, second)
        for index, (first, second) in enumerate(
            ((4.0, 2.0), (2.0, 4.0), (-4.0, -2.0), (-2.0, -4.0)),
            start=1,
        )
    )
    composition_holdout = (
        _composition_world("composition-holdout-01", "holdout", 1.0, 5.0),
        _composition_world("composition-holdout-02", "holdout", -1.0, -5.0),
    )
    composition_transfer = (
        _composition_world("composition-transfer-01", "sealed-transfer", 3.0, 3.0),
        _composition_world("composition-transfer-02", "sealed-transfer", -3.0, -3.0),
    )
    collision_training = tuple(
        _collision_world(f"collision-train-{index:02d}", "training", left, right)
        for index, (left, right) in enumerate(
            ((6.0, 2.0), (2.0, 6.0), (5.0, 3.0), (3.0, 5.0)),
            start=1,
        )
    )
    collision_holdout = (
        _collision_world("collision-holdout-01", "holdout", 7.0, 1.0),
        _collision_world("collision-holdout-02", "holdout", 1.0, 7.0),
    )
    collision_transfer = (
        _collision_world("collision-transfer-01", "sealed-transfer", 4.5, 2.5),
        _collision_world("collision-transfer-02", "sealed-transfer", 2.5, 4.5),
    )
    collision_surprise = _delayed_collision_world(
        "collision-surprise-01",
        "sealed-surprise",
        64.0,
        63.0,
        120,
    )
    delayed_training = tuple(
        _delayed_collision_world(
            f"delayed-train-{index:02d}", "field-selected-training", left, right, delay
        )
        for index, (left, right, delay) in enumerate(
            ((8.0, 4.0, 8), (8.0, 7.0, 96), (4.0, 8.0, 32), (12.0, 3.0, 24)),
            start=1,
        )
    )
    delayed_holdout = (
        _delayed_collision_world("delayed-holdout-01", "field-selected-holdout", 7.0, 5.0, 64),
        _delayed_collision_world("delayed-holdout-02", "field-selected-holdout", 5.0, 9.0, 48),
    )
    delayed_transfer = (
        _delayed_collision_world("delayed-transfer-01", "sealed-transfer", 8.5, 4.5, 80),
        _delayed_collision_world("delayed-transfer-02", "sealed-transfer", 7.5, 2.5, 16),
    )
    clamp_training = tuple(
        _clamp_world(f"clamp-train-{index:02d}", "training", first, second)
        for index, (first, second) in enumerate(
            ((3.0, 1.0), (1.0, 3.0), (48.0, 16.0), (16.0, 48.0)),
            start=1,
        )
    )
    clamp_holdout = (
        _clamp_world("clamp-holdout-01", "holdout", 2.5, 1.5),
        _clamp_world("clamp-holdout-02", "holdout", 32.0, 32.0),
    )
    clamp_transfer = (
        _clamp_world("clamp-transfer-01", "sealed-transfer", 2.0, 2.0),
        _clamp_world("clamp-transfer-02", "sealed-transfer", 24.0, 40.0),
    )
    repeats = (
        _composition_world(
            "repeat-composition-transfer-01",
            "exact-repeat",
            3.0,
            3.0,
            source_of="composition-transfer-01",
        ),
        _collision_world(
            "repeat-collision-transfer-01",
            "exact-repeat",
            4.5,
            2.5,
            source_of="collision-transfer-01",
        ),
    )
    calibration = ScheduledPhysicsWorld(
        world_id="calibration-unit-source",
        regime="linear-source-calibration",
        split="calibration",
        segments=(ScheduledSegment((_deposit(0.55, 1.0, y=0.08, z=-0.11),), 8),),
        features=_features(source_strength=1.0),
    )
    curriculum = AutonomousPhysicsCurriculum(
        calibration=calibration,
        composition_training=composition_training,
        composition_holdout=composition_holdout,
        composition_transfer=composition_transfer,
        collision_training=collision_training,
        collision_holdout=collision_holdout,
        collision_transfer=collision_transfer,
        collision_surprise=collision_surprise,
        delayed_training=delayed_training,
        delayed_holdout=delayed_holdout,
        delayed_transfer=delayed_transfer,
        clamp_training=clamp_training,
        clamp_holdout=clamp_holdout,
        clamp_transfer=clamp_transfer,
        repeats=repeats,
    )
    identities = [world.world_id for world in curriculum.all_worlds]
    if len(identities) != len(set(identities)):
        raise AutonomousPhysicsResidencyError("curriculum world identities are not unique")
    return curriculum


def build_experiment_primitive_grammar() -> dict[str, Any]:
    """Declare only the bounded physical alphabet the field may compose."""

    return {
        "bounds": {
            "max_abs_charge": 36.0,
            "max_deposits": 3,
            "max_observables": 8,
            "max_segments": 8,
            "max_total_steps": 128,
        },
        "derived_operations": [
            "count-transitions",
            "final-over-maximum",
            "monotone-direction",
            "nearest-source-path",
            "sign-path",
        ],
        "raw_observables": [
            {
                "cost": 1.0,
                "field": "max_eps2",
                "provides": ["nonlinearity"],
                "reliability": 0.99,
            },
            {
                "cost": 0.5,
                "field": "mean_ey",
                "provides": ["global-charge"],
                "reliability": 0.995,
            },
            {
                "cost": 3.0,
                "field": "phase_profile_x_16",
                "provides": ["distributed-phase-flow"],
                "reliability": 0.99,
            },
            {
                "cost": 5.0,
                "field": "phase_topology_xyz_4",
                "provides": ["phase-current-topology"],
                "reliability": 0.99,
            },
            {
                "cost": 6.0,
                "field": "phase_winding_native_3x3",
                "provides": ["native-phase-winding", "phase-current-topology"],
                "reliability": 0.99,
            },
            {
                "cost": 1.0,
                "field": "top_phase_current_x",
                "provides": ["phase-flow-direction"],
                "reliability": 0.99,
            },
            {
                "cost": 0.75,
                "field": "top_q",
                "provides": ["coherence", "peak_q"],
                "reliability": 0.995,
            },
            {
                "cost": 0.75,
                "field": "top_x",
                "provides": [
                    "dominance",
                    "temporal-path",
                    "trajectory-position",
                ],
                "reliability": 0.99,
            },
        ],
        "sources": [
            {
                "sigma": 1.0,
                "source_id": "center",
                "x": 0.0,
                "y": 0.08,
                "z": -0.11,
            },
            {
                "sigma": 1.0,
                "source_id": "left",
                "x": -0.55,
                "y": 0.08,
                "z": -0.11,
            },
            {
                "sigma": 1.0,
                "source_id": "right",
                "x": 0.55,
                "y": 0.08,
                "z": -0.11,
            },
        ],
        "step_counts": [16, 32, 64],
        "strengths": [4.0, 8.0, 12.0],
    }


def _experiment_channels(curriculum: AutonomousPhysicsCurriculum) -> list[dict[str, Any]]:
    return [
        {
            "channel_id": "physics:delayed-collision",
            "cost": 2.0,
            "latency": 0.2,
            "novelty": 1.0,
            "provides": ["dominance"],
            "reliability": 0.99,
            "request": {
                "experiment_id": "delayed-collision",
                "world_ids": [
                    world.world_id
                    for world in (
                        curriculum.delayed_training
                        + curriculum.delayed_holdout
                        + curriculum.delayed_transfer
                    )
                ],
            },
        },
        {
            "channel_id": "physics:more-simultaneous-collisions",
            "cost": 1.0,
            "latency": 0.1,
            "novelty": 0.2,
            "provides": ["dominance"],
            "reliability": 0.85,
            "request": {"experiment_id": "more-simultaneous-collisions"},
        },
        {
            "channel_id": "physics:clamp-sweep",
            "cost": 2.5,
            "latency": 0.5,
            "novelty": 0.9,
            "provides": ["clamp_regime", "temporal_direction"],
            "reliability": 0.98,
            "request": {"experiment_id": "clamp-sweep"},
        },
    ]


def build_autonomous_physics_manifest(
    curriculum: AutonomousPhysicsCurriculum | None = None,
) -> dict[str, Any]:
    curriculum = build_autonomous_physics_curriculum() if curriculum is None else curriculum
    sealed_groups = {
        name: [world.as_dict() for world in worlds]
        for name, worlds in curriculum.groups.items()
        if name.endswith("transfer") or name in {"collision_surprise", "repeats"}
    }
    sealed = {
        "experiment_channels": _experiment_channels(curriculum),
        "experiment_primitive_grammar": build_experiment_primitive_grammar(),
        "world_groups": sealed_groups,
    }
    return {
        "schema": MANIFEST_SCHEMA,
        "engine": {
            "auto_step": False,
            "grid_n": GRID_N,
            "maximum_horizon": max(world.horizons[-1] for world in curriculum.all_worlds),
            "scene": "res://scenes/mind_engine_64.tscn",
        },
        "learning_boundary": {
            "adaptive_state": "QiFieldState.field",
            "candidate_families_supplied": False,
            "external_model": False,
            "field_originates_typed_representation_candidates": True,
            "field_originates_experiment_language_candidates": True,
            "field_originates_observables_and_distinctions": True,
            "field_revises_experiment_constructor": True,
            "field_composes_multi_experiment_research_programs": True,
            "field_originates_bounded_authority_requests": True,
            "field_designs_matched_mechanism_controls": True,
            "field_resolves_research_mechanism_from_raw_observations": True,
            "field_continues_into_distributed_flow_worldlines": True,
            "field_continues_into_3d_phase_current_topology": True,
            "field_revises_same_representation_identity": True,
            "owner_supplies_only_safe_experiment_primitives": True,
            "owner_grants_no_implicit_experiment_authority": True,
            "sidecar_learned_state": False,
            "resident_profile": dict(_RESIDENT_PROFILE),
            "resident_capacity_bytes": {
                "state": _RESIDENT_LIMITS.max_state_bytes,
                "workspace": _RESIDENT_LIMITS.max_workspace_bytes,
            },
        },
        "representation_targets": {
            "clamp": CLAMP_REPRESENTATION_ID,
            "collision": COLLISION_REPRESENTATION_ID,
            "composition": COMPOSITION_REPRESENTATION_ID,
            "experiment_constructor": EXPERIMENT_CONSTRUCTOR_ID,
            "experiment_languages": [
                EXPERIMENT_LANGUAGE_GENERATION_1_ID,
                EXPERIMENT_LANGUAGE_GENERATION_2_ID,
                EXPERIMENT_LANGUAGE_GENERATION_3_ID,
            ],
            "research_program": RESEARCH_PROGRAM_ID,
            "mechanism_experiment": MECHANISM_EXPERIMENT_ID,
            "distributed_phase_experiment": DISTRIBUTED_PHASE_EXPERIMENT_ID,
            "research_program_stage": RESEARCH_STAGE_GENERATION_3_ID,
            "temporal": TEMPORAL_REPRESENTATION_ID,
        },
        "sealed": sealed,
        "sealed_sha256": sha256_value(sealed),
        "world_groups": {
            name: [world.as_dict() for world in worlds]
            for name, worlds in curriculum.groups.items()
            if name not in sealed_groups
        },
    }


def _commit_bytes(path: Path, content: bytes) -> None:
    if path.exists():
        if path.read_bytes() != content:
            raise AutonomousPhysicsResidencyError(f"immutable campaign artifact changed: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".pending")
    with temporary.open("wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _validated_receipt(path: Path) -> dict[str, Any]:
    try:
        receipt = json.loads(path.read_bytes())
        digest = receipt.pop("body_sha256")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise AutonomousPhysicsResidencyError("existing autonomous physics receipt is invalid") from exc
    if digest != sha256_value(receipt):
        raise AutonomousPhysicsResidencyError("autonomous physics receipt digest diverges")
    return {**receipt, "body_sha256": digest}


class AutonomousPhysicsResidency:
    """One continuing residency whose physical concepts live only in its field."""

    def __init__(
        self,
        run_home: Path,
        *,
        run_id: str,
        host: str = "127.0.0.1",
        port: int = 7599,
    ) -> None:
        if not isinstance(run_id, str) or _RUN_ID.fullmatch(run_id) is None:
            raise AutonomousPhysicsResidencyError("run_id must be a bounded filesystem-safe identity")
        self.run_home = Path(run_home).resolve()
        self.run_id = run_id
        self.host = host
        self.port = port
        self.curriculum = build_autonomous_physics_curriculum()
        self.manifest = build_autonomous_physics_manifest(self.curriculum)
        self.experiment_grammar = dict(
            self.manifest["sealed"]["experiment_primitive_grammar"]
        )
        self.manifest_bytes = canonical_json_bytes(self.manifest)
        self.resident_home = self.run_home / "resident"
        self.controller = CassiCosmosWorldFactoryController(
            authorization=authorize_cassicosmos_seed(
                "scheduled worlds for the owner-requested autonomous physics residency"
            ),
            host=host,
            port=port,
            timeout=180.0,
        )
        self.controller.bind_durable_journal(self.run_home / "world-journal")

    @property
    def receipt_path(self) -> Path:
        return self.run_home / "receipt.json"

    def _open_resident(self) -> ResearchResidency:
        resident = open_research_residency(
            self.resident_home,
            limits=_RESIDENT_LIMITS,
        )
        resident.initialize(
            workspace=Path(__file__).resolve().parent,
            mission=(
                "Originate, test, and revise physical representations across scheduled, "
                "colliding, nonlinear, and long-horizon CassiCosmos worlds"
            ),
            work=[
                {
                    "id": "autonomous-physics-residency",
                    "summary": "Continue autonomous physical representation discovery",
                    "request": {"kind": "autonomous-physics-residency"},
                }
            ],
            profile=_RESIDENT_PROFILE,
        )
        return resident

    def _archive(
        self,
        resident: ResearchResidency,
        *,
        source_id: str,
        content: bytes,
        category: str,
        context: Mapping[str, Any],
    ) -> str:
        archived = resident.owner.archive_source(
            operation_id=f"{self.run_id}:archive:{source_id}",
            source=SourceInput(
                source_id=f"{self.run_id}:{source_id}",
                content=content,
                media_type="application/json",
                codec=CODEC_JSON,
                observed_timestamp=f"{self.run_id}:{source_id}",
                scope="autonomous-physics-residency",
                claim_category=category,
                fidelity="exact-observed-bytes",
                labels=("autonomous-physics-residency", category),
            ),
            context=dict(context),
        )
        return str(archived["source"]["revision_id"])

    def _execute_world(
        self,
        world: ScheduledPhysicsWorld,
        *,
        phase_profile_bins: int = 0,
        phase_topology_bins: int = 0,
        phase_winding_probe: int = 0,
    ) -> dict[str, Any]:
        acknowledgment = self.controller.execute_scheduled_world(
            operation_id=f"{self.run_id}:world:{world.world_id}",
            segments=[segment.as_dict() for segment in world.segments],
            phase_winding_probe=phase_winding_probe,
            projection_k=8,
            phase_profile_bins=phase_profile_bins,
            phase_topology_bins=phase_topology_bins,
        )
        if acknowledgment.status != "succeeded":
            raise AutonomousPhysicsResidencyError(
                f"world {world.world_id} ended {acknowledgment.status}: {acknowledgment.context}"
            )
        return {
            "acknowledgment": acknowledgment.as_dict(),
            "observed": dict(acknowledgment.observed_values),
            "world": world.as_dict(),
        }

    def _authorize_generated_experiment(
        self,
        proposal: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Apply the fixed owner safety boundary without choosing an experiment."""

        grammar = self.experiment_grammar
        bounds = grammar["bounds"]
        source_rows = {
            str(row["source_id"]): dict(row) for row in grammar["sources"]
        }
        strengths = {float(value) for value in grammar["strengths"]}
        step_counts = {int(value) for value in grammar["step_counts"]}
        raw_fields = {
            str(row["field"]) for row in grammar["raw_observables"]
        }
        derived_operations = {
            str(value) for value in grammar["derived_operations"]
        }
        checks = {
            "mirrored_transfer": False,
            "observation_program": False,
            "primitive_vocabulary": False,
            "proposal_shape": False,
            "resource_bounds": False,
        }
        try:
            unsigned_proposal = dict(proposal)
            candidate_id = unsigned_proposal.pop("candidate_id", None)
            discrimination = proposal.get("expected_discrimination")
            discrimination_valid = (
                isinstance(discrimination, Mapping)
                and set(discrimination)
                == {
                    "constructor_alignment",
                    "coverage",
                    "derived_observable_count",
                    "minimum_reliability",
                    "novelty",
                    "raw_cost",
                    "score",
                    "source_transitions",
                }
                and all(
                    not isinstance(value, bool)
                    and isinstance(value, (int, float))
                    and math.isfinite(float(value))
                    for value in discrimination.values()
                )
            )
            construction = proposal.get("construction")
            construction_valid = (
                isinstance(construction, Mapping)
                and set(construction)
                == {
                    "constructor_id",
                    "constructor_version",
                    "generation",
                    "parent_language_id",
                    "research_program_id",
                    "research_stage_id",
                    "route_shape",
                    "schedule_fingerprint",
                    "step_profile",
                    "strength_profile",
                    "topology",
                }
                and isinstance(construction["constructor_id"], str)
                and bool(construction["constructor_id"])
                and isinstance(construction["constructor_version"], int)
                and not isinstance(construction["constructor_version"], bool)
                and int(construction["constructor_version"]) >= 1
                and isinstance(construction["generation"], int)
                and not isinstance(construction["generation"], bool)
                and int(construction["generation"]) >= 1
                and (
                    construction["parent_language_id"] is None
                    or isinstance(construction["parent_language_id"], str)
                )
                and (
                    (
                        construction["research_program_id"] is None
                        and construction["research_stage_id"] is None
                    )
                    or (
                        isinstance(construction["research_program_id"], str)
                        and bool(construction["research_program_id"])
                        and isinstance(construction["research_stage_id"], str)
                        and bool(construction["research_stage_id"])
                    )
                )
                and isinstance(construction["schedule_fingerprint"], str)
                and re.fullmatch(
                    r"[0-9a-f]{64}",
                    str(construction["schedule_fingerprint"]),
                )
                is not None
                and all(
                    isinstance(construction[name], str)
                    and bool(construction[name])
                    for name in (
                        "route_shape",
                        "step_profile",
                        "strength_profile",
                        "topology",
                    )
                )
            )
            checks["proposal_shape"] = (
                set(proposal)
                == {
                    "candidate_id",
                    "candidate_origin",
                    "construction",
                    "expected_discrimination",
                    "family",
                    "representation_roles",
                    "requested_support",
                    "schema",
                    "transfer_world",
                    "trial_world",
                }
                and proposal["schema"]
                == "cassifi.experiment-language-proposal.v3"
                and proposal["candidate_origin"] == "field-generated"
                and isinstance(candidate_id, str)
                and candidate_id
                == "auto:experiment-language:"
                + sha256_value(unsigned_proposal)[:16]
                and isinstance(proposal["family"], str)
                and bool(proposal["family"])
                and construction_valid
                and discrimination_valid
                and isinstance(proposal["representation_roles"], list)
                and proposal["representation_roles"]
                == sorted(set(proposal["representation_roles"]))
                and all(
                    isinstance(value, str) and value
                    for value in proposal["representation_roles"]
                )
                and isinstance(proposal["requested_support"], list)
                and proposal["requested_support"]
                == sorted(set(proposal["requested_support"]))
                and all(
                    isinstance(value, str) and value
                    for value in proposal["requested_support"]
                )
            )

            worlds = [
                cast_world
                for cast_world in (
                    proposal["trial_world"],
                    proposal["transfer_world"],
                )
                if isinstance(cast_world, Mapping)
            ]
            world_shapes = len(worlds) == 2 and all(
                set(world)
                == {
                    "derived_observables",
                    "distinction",
                    "expected",
                    "observations",
                    "schema",
                    "segments",
                    "variant",
                }
                and world["schema"]
                == "cassifi.generated-scheduled-world.v2"
                and world["variant"] == variant
                for world, variant in zip(worlds, ("trial", "transfer"))
            )
            checks["proposal_shape"] = checks["proposal_shape"] and world_shapes

            primitive_valid = world_shapes
            resource_valid = world_shapes
            observation_valid = world_shapes
            for world in worlds:
                segments = world["segments"]
                primitive_valid = primitive_valid and isinstance(segments, list)
                if not isinstance(segments, list):
                    continue
                deposit_count = 0
                total_charge = 0.0
                total_steps = 0
                horizons: list[int] = []
                for segment in segments:
                    if (
                        not isinstance(segment, Mapping)
                        or set(segment) != {"pulses", "steps"}
                        or not isinstance(segment["pulses"], list)
                        or isinstance(segment["steps"], bool)
                        or not isinstance(segment["steps"], int)
                    ):
                        primitive_valid = False
                        resource_valid = False
                        continue
                    steps = int(segment["steps"])
                    primitive_valid = primitive_valid and steps in step_counts
                    total_steps += steps
                    horizons.append(total_steps)
                    for pulse in segment["pulses"]:
                        if (
                            not isinstance(pulse, Mapping)
                            or set(pulse) != {"source_id", "strength"}
                            or pulse["source_id"] not in source_rows
                            or isinstance(pulse["strength"], bool)
                            or not isinstance(pulse["strength"], (int, float))
                        ):
                            primitive_valid = False
                            continue
                        strength = float(pulse["strength"])
                        primitive_valid = (
                            primitive_valid
                            and math.isfinite(strength)
                            and strength in strengths
                        )
                        deposit_count += 1
                        total_charge += abs(strength)
                resource_valid = resource_valid and (
                    1 <= len(segments) <= int(bounds["max_segments"])
                    and deposit_count <= int(bounds["max_deposits"])
                    and total_charge <= float(bounds["max_abs_charge"])
                    and total_steps <= int(bounds["max_total_steps"])
                )

                observations = world["observations"]
                derived = world["derived_observables"]
                distinction = world["distinction"]
                observation_valid = observation_valid and (
                    isinstance(observations, list)
                    and len(observations) == len(segments)
                    and isinstance(derived, list)
                    and isinstance(distinction, Mapping)
                    and set(distinction)
                    == {"classes", "expected_class", "name", "observable"}
                )
                selected_fields = {
                    str(field)
                    for row in observations
                    if isinstance(row, Mapping)
                    and isinstance(row.get("fields"), list)
                    for field in row["fields"]
                }
                available = set(selected_fields)
                derived_names: list[str] = []
                if isinstance(derived, list):
                    expected_anchors = [
                        {
                            "label": str(source["source_id"]),
                            "x": float(source["x"]),
                        }
                        for source in sorted(
                            source_rows.values(),
                            key=lambda item: float(item["x"]),
                        )
                    ]
                    for row in derived:
                        base_keys = {"name", "operation", "source"}
                        operation = (
                            row.get("operation")
                            if isinstance(row, Mapping)
                            else None
                        )
                        keys_valid = isinstance(row, Mapping) and set(row) == (
                            base_keys | {"parameters"}
                            if operation == "nearest-source-path"
                            else base_keys
                        )
                        parameters_valid = (
                            operation != "nearest-source-path"
                            or (
                                isinstance(row.get("parameters"), Mapping)
                                and set(row["parameters"]) == {"anchors"}
                                and row["parameters"]["anchors"]
                                == expected_anchors
                            )
                        )
                        if (
                            not keys_valid
                            or not isinstance(row["name"], str)
                            or not isinstance(row["source"], str)
                            or operation not in derived_operations
                            or row["source"] not in available
                            or not parameters_valid
                        ):
                            observation_valid = False
                            continue
                        derived_names.append(str(row["name"]))
                        available.add(str(row["name"]))
                expected = world["expected"]
                observable = distinction.get("observable")
                expected_observable = (
                    expected.get(observable)
                    if isinstance(expected, Mapping)
                    and isinstance(observable, str)
                    else None
                )
                expected_value_valid = (
                    isinstance(expected_observable, list)
                    and len(expected_observable) == len(segments)
                    and set(expected_observable) <= set(source_rows)
                ) or isinstance(expected_observable, str)
                observation_valid = observation_valid and (
                    len(derived_names) == len(set(derived_names))
                    and observable in set(derived_names)
                    and isinstance(distinction.get("classes"), list)
                    and len(distinction.get("classes", []))
                    == len(set(distinction.get("classes", [])))
                    and all(
                        isinstance(value, str) and value
                        for value in distinction.get("classes", [])
                    )
                    and distinction.get("expected_class")
                    in distinction.get("classes", [])
                    and isinstance(expected, Mapping)
                    and set(expected) == {"class", observable}
                    and expected.get("class")
                    == distinction.get("expected_class")
                    and expected_value_valid
                )
                if isinstance(observations, list):
                    for index, row in enumerate(observations):
                        if (
                            not isinstance(row, Mapping)
                            or set(row) != {"fields", "horizon"}
                            or index >= len(horizons)
                            or row["horizon"] != horizons[index]
                            or not isinstance(row["fields"], list)
                            or row["fields"] != sorted(set(row["fields"]))
                            or not set(row["fields"]) <= raw_fields
                            or len(row["fields"])
                            > int(bounds["max_observables"])
                        ):
                            observation_valid = False
            checks["primitive_vocabulary"] = primitive_valid
            checks["resource_bounds"] = resource_valid
            checks["observation_program"] = observation_valid

            trial = proposal["trial_world"]
            transfer = proposal["transfer_world"]
            mirrors: dict[str, str] = {}
            for source_id, source in source_rows.items():
                matches = [
                    candidate_id
                    for candidate_id, candidate in source_rows.items()
                    if math.isclose(
                        float(candidate["x"]),
                        -float(source["x"]),
                        rel_tol=0.0,
                        abs_tol=1.0e-12,
                    )
                    and all(
                        math.isclose(
                            float(candidate[name]),
                            float(source[name]),
                            rel_tol=0.0,
                            abs_tol=1.0e-12,
                        )
                        for name in ("sigma", "y", "z")
                    )
                ]
                if len(matches) == 1:
                    mirrors[source_id] = matches[0]
            segment_mirror = len(trial["segments"]) == len(
                transfer["segments"]
            ) and all(
                trial_segment["steps"] == transfer_segment["steps"]
                and len(trial_segment["pulses"])
                == len(transfer_segment["pulses"])
                and all(
                    mirrors.get(str(trial_pulse["source_id"]))
                    == transfer_pulse["source_id"]
                    and float(trial_pulse["strength"])
                    == float(transfer_pulse["strength"])
                    for trial_pulse, transfer_pulse in zip(
                        trial_segment["pulses"],
                        transfer_segment["pulses"],
                    )
                )
                for trial_segment, transfer_segment in zip(
                    trial["segments"], transfer["segments"]
                )
            )
            observable = trial["distinction"]["observable"]
            trial_expected = trial["expected"].get(observable)
            transfer_expected = transfer["expected"].get(observable)
            expected_mirror = (
                isinstance(trial_expected, list)
                and transfer_expected
                == [mirrors.get(str(value), str(value)) for value in trial_expected]
            ) or (
                not isinstance(trial_expected, list)
                and trial_expected == transfer_expected
            )
            fingerprint_valid = (
                proposal["construction"]["schedule_fingerprint"]
                == experiment_schedule_fingerprint(
                    trial, list(source_rows.values())
                )
                == experiment_schedule_fingerprint(
                    transfer, list(source_rows.values())
                )
            )
            checks["mirrored_transfer"] = (
                len(mirrors) == len(source_rows)
                and segment_mirror
                and expected_mirror
                and fingerprint_valid
                and trial["observations"] == transfer["observations"]
                and trial["derived_observables"]
                == transfer["derived_observables"]
                and trial["distinction"] == transfer["distinction"]
                and trial["expected"].get("class")
                == transfer["expected"].get("class")
            )
        except (KeyError, TypeError, ValueError):
            pass
        return {
            "authorized": all(checks.values()),
            "checks": checks,
            "grammar_sha256": sha256_value(grammar),
            "proposal_sha256": sha256_value(proposal),
        }

    def _generated_world(
        self,
        proposal: Mapping[str, Any],
        *,
        variant: str,
        world_id: str,
        split: str,
        source_of: str | None = None,
    ) -> ScheduledPhysicsWorld:
        source_rows = {
            str(row["source_id"]): row
            for row in self.experiment_grammar["sources"]
        }
        program = proposal[f"{variant}_world"]
        segments = tuple(
            ScheduledSegment(
                tuple(
                    Deposit(
                        x=float(source_rows[str(pulse["source_id"])]["x"]),
                        y=float(source_rows[str(pulse["source_id"])]["y"]),
                        z=float(source_rows[str(pulse["source_id"])]["z"]),
                        cy=float(pulse["strength"]),
                        ci=0.0,
                        sigma=float(
                            source_rows[str(pulse["source_id"])]["sigma"]
                        ),
                    )
                    for pulse in segment["pulses"]
                ),
                int(segment["steps"]),
            )
            for segment in program["segments"]
        )
        return ScheduledPhysicsWorld(
            world_id=world_id,
            regime=f"generated-{proposal['family']}",
            split=split,
            segments=segments,
            features=_features(
                deposit_count=float(
                    sum(len(segment.deposits) for segment in segments)
                ),
                segment_count=float(len(segments)),
                total_steps=float(sum(segment.steps for segment in segments)),
            ),
            source_of=source_of,
        )

    @staticmethod
    def _generated_observation_fields(
        world_program: Mapping[str, Any],
    ) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    str(field)
                    for observation in world_program["observations"]
                    for field in observation["fields"]
                }
            )
        )

    def _admit_world(
        self,
        resident: ResearchResidency,
        result: Mapping[str, Any],
        *,
        horizons: Sequence[int] | None = None,
        observable_fields: Sequence[str] | None = None,
        suffix: str = "full",
        admit_observations: bool = True,
    ) -> dict[str, Any]:
        world = result["world"]
        allowed_horizons = None if horizons is None else {int(value) for value in horizons}
        allowed_fields = (
            None if observable_fields is None else {str(value) for value in observable_fields}
        )
        observed = {
            key: float(value)
            for key, value in result["observed"].items()
            if (
                allowed_horizons is None
                or int(key.split("_", 1)[0][1:]) in allowed_horizons
            )
            and (
                allowed_fields is None
                or key.split("_", 1)[1] in allowed_fields
            )
        }
        if suffix == "full":
            evidence_payload = {
                "acknowledgment": result["acknowledgment"],
                "schema": WORLD_SCHEMA,
                "world": world,
            }
        else:
            evidence_payload = {
                "acknowledgment_id": result["acknowledgment"]["acknowledgment_id"],
                "observed": observed,
                "schema": WORLD_SCHEMA,
                "transcript_sha256": hashlib.sha256(
                    result["acknowledgment"]["source_content_base64"].encode("ascii")
                ).hexdigest(),
                "view": suffix,
                "world": world,
            }
        evidence = canonical_json_bytes(evidence_payload)
        root = self._archive(
            resident,
            source_id=f"world:{world['world_id']}:{suffix}",
            content=evidence,
            category="scheduled-physics-world",
            context={
                "acknowledgment_id": result["acknowledgment"]["acknowledgment_id"],
                "regime": world["regime"],
                "view": suffix,
                "world_id": world["world_id"],
            },
        )
        if not admit_observations:
            return {
                **dict(result),
                "evidence_sha256": hashlib.sha256(evidence).hexdigest(),
                "observed": observed,
                "source_revision_id": root,
                "view": suffix,
            }
        observations = [
            {
                "attribute": key,
                "frame": {
                    "physical_horizon": int(key.split("_", 1)[0][1:]),
                    "regime": world["regime"],
                    "split": world["split"],
                },
                "subject": world["world_id"],
                "value": value,
            }
            for key, value in sorted(observed.items())
        ]
        page_count = (
            len(observations) + _RESIDENT_OBSERVATION_PAGE_SIZE - 1
        ) // _RESIDENT_OBSERVATION_PAGE_SIZE
        for page_index in range(page_count):
            start = page_index * _RESIDENT_OBSERVATION_PAGE_SIZE
            page = observations[
                start : start + _RESIDENT_OBSERVATION_PAGE_SIZE
            ]
            page_suffix = (
                ""
                if page_count == 1
                else f":page:{page_index}"
            )
            resident.semantic(
                {
                    "operation": "observe",
                    "operation_id": (
                        f"{self.run_id}:observe:{world['world_id']}:{suffix}"
                        f"{page_suffix}"
                    ),
                    "delivery_id": (
                        f"delivery:{self.run_id}:{world['world_id']}:{suffix}"
                        f"{page_suffix}"
                    ),
                    "event_id": (
                        f"event:{self.run_id}:{world['world_id']}:{suffix}"
                        f"{page_suffix}"
                    ),
                    "observations": page,
                    "source": {"source_revision_id": root},
                    "support_roots": [root],
                }
            )
        return {
            **dict(result),
            "evidence_sha256": hashlib.sha256(evidence).hexdigest(),
            "observed": observed,
            "source_revision_id": root,
            "view": suffix,
        }

    def _run_and_admit(
        self,
        resident: ResearchResidency,
        worlds: Sequence[ScheduledPhysicsWorld],
    ) -> list[dict[str, Any]]:
        return [self._admit_world(resident, self._execute_world(world)) for world in worlds]

    @staticmethod
    def _global_sign(result: Mapping[str, Any]) -> str:
        horizon = int(result["world"]["horizons"][-1])
        value = float(result["observed"][f"h{horizon}_mean_ey"]) * float(GRID_N**3)
        if value > 1.0e-8:
            return "positive"
        if value < -1.0e-8:
            return "negative"
        return "zero"

    @staticmethod
    def _dominance(result: Mapping[str, Any]) -> str:
        horizon = int(result["world"]["horizons"][-1])
        return "left" if float(result["observed"][f"h{horizon}_top_x"]) < 0.0 else "right"

    @staticmethod
    def _clamp_regime(result: Mapping[str, Any]) -> str:
        return (
            "clamped"
            if float(result["observed"]["h1_max_eps2"]) >= CLAMP_EPS2_THRESHOLD
            else "unclamped"
        )

    @staticmethod
    def _direction(first: float, second: float) -> str:
        tolerance = 1.0e-12 * max(1.0, abs(first), abs(second))
        if second < first - tolerance:
            return "decreasing"
        if second > first + tolerance:
            return "increasing"
        return "stationary"

    def _learn_representation(
        self,
        resident: ResearchResidency,
        *,
        operation_name: str,
        representation_id: str,
        target: str,
        training: Sequence[Mapping[str, Any]],
        holdout: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        roots = sorted(
            {
                str(row["source_revision_id"])
                for row in (*training, *holdout)
                if row.get("source_revision_id")
            }
        )
        request = {
            "operation": "learn-representation",
            "operation_id": f"{self.run_id}:learn-representation:{operation_name}",
            "representation_id": representation_id,
            "examples": [
                {
                    "example_id": str(row["example_id"]),
                    "features": dict(row["features"]),
                    "outcome": row["outcome"],
                }
                for row in training
            ],
            "holdout": [
                {
                    "example_id": str(row["example_id"]),
                    "features": dict(row["features"]),
                    "outcome": row["outcome"],
                    "rare_case": True,
                }
                for row in holdout
            ],
            "information_boundary": {"available": ["features"]},
            "question": {"target": target},
            "support_roots": roots,
        }
        result = resident.semantic(request)
        if result["status"] != "supported":
            raise AutonomousPhysicsResidencyError(
                f"autonomous representation {representation_id} was insufficient: {result}"
            )
        if not str(result["selected_candidate"]).startswith("auto:"):
            raise AutonomousPhysicsResidencyError("representation family was not field-originated")
        return result

    def _invoke_experiment_language(
        self,
        resident: ResearchResidency,
        *,
        language_id: str,
        operation_name: str,
        variant: str,
    ) -> dict[str, Any]:
        return resident.semantic(
            {
                "operation": "invoke-experiment-language",
                "operation_id": (
                    f"{self.run_id}:invoke-experiment-language:{operation_name}"
                ),
                "language_id": language_id,
                "variant": variant,
            }
        )

    def _assess_generated_experiment(
        self,
        resident: ResearchResidency,
        *,
        language_id: str,
        operation_name: str,
        observations: Mapping[str, Any],
        safety_receipt: Mapping[str, Any],
        source_revision_id: str,
        variant: str,
    ) -> dict[str, Any]:
        return resident.semantic(
            {
                "operation": "assess-experiment-language",
                "operation_id": (
                    f"{self.run_id}:assess-experiment-language:{operation_name}"
                ),
                "language_id": language_id,
                "observations": dict(observations),
                "safety_receipt": dict(safety_receipt),
                "source_revision_id": source_revision_id,
                "variant": variant,
            }
        )

    def _run_generated_experiment_language(
        self,
        resident: ResearchResidency,
        *,
        generation_tag: str,
        language_id: str,
        manifest_root: str,
        parent_language_id: str | None = None,
        research_program_id: str | None = None,
        research_stage_id: str | None = None,
    ) -> dict[str, Any]:
        synthesis_request: dict[str, Any] = {
            "operation": "synthesize-experiment-language",
            "operation_id": (
                f"{self.run_id}:synthesize-experiment-language:{generation_tag}"
            ),
            "constructor_id": EXPERIMENT_CONSTRUCTOR_ID,
            "grammar": self.experiment_grammar,
            "language_id": language_id,
            "representation_id": COLLISION_REPRESENTATION_ID,
            "support_roots": [manifest_root],
        }
        if parent_language_id is not None:
            synthesis_request["parent_language_id"] = parent_language_id
        if (research_program_id is None) != (research_stage_id is None):
            raise AutonomousPhysicsResidencyError(
                "research program and stage must be supplied together"
            )
        if research_program_id is not None and research_stage_id is not None:
            synthesis_request["research_program_id"] = research_program_id
            synthesis_request["research_stage_id"] = research_stage_id
        synthesis = resident.semantic(synthesis_request)
        if (
            synthesis["status"] != "supported"
            or synthesis.get("candidate_families_supplied") is not False
            or not str(synthesis.get("selected_candidate", "")).startswith(
                "auto:experiment-language:"
            )
        ):
            raise AutonomousPhysicsResidencyError(
                f"field did not originate an experiment language: {synthesis}"
            )
        proposal = dict(synthesis["proposal"])
        authorization = self._authorize_generated_experiment(proposal)
        if not authorization["authorized"]:
            raise AutonomousPhysicsResidencyError(
                f"field-originated experiment failed the safety boundary: {authorization}"
            )

        precommit = {
            "field_state_sha256": resident.inspect()["field_state_sha256"],
            "generation_tag": generation_tag,
            "grammar_sha256": sha256_value(self.experiment_grammar),
            "manifest_sha256": hashlib.sha256(
                self.manifest_bytes
            ).hexdigest(),
            "proposal": proposal,
            "proposal_sha256": sha256_value(proposal),
            "sealed_sha256": self.manifest["sealed_sha256"],
        }
        precommit_bytes = canonical_json_bytes(precommit)
        precommit_root = self._archive(
            resident,
            source_id=(
                f"precommit:generated-experiment-language:{generation_tag}"
            ),
            content=precommit_bytes,
            category="field-originated-experiment-precommit",
            context={
                "candidate_id": proposal["candidate_id"],
                "generation_tag": generation_tag,
                "proposal_sha256": sha256_value(proposal),
                "sha256": hashlib.sha256(precommit_bytes).hexdigest(),
            },
        )

        trial_program = proposal["trial_world"]
        trial_world = self._generated_world(
            proposal,
            variant="trial",
            world_id=f"generated-language-{generation_tag}-trial",
            split=f"field-originated-{generation_tag}-trial",
        )
        trial = self._admit_world(
            resident,
            self._execute_world(trial_world),
            horizons=[
                int(row["horizon"])
                for row in trial_program["observations"]
            ],
            observable_fields=self._generated_observation_fields(
                trial_program
            ),
            suffix=f"{generation_tag}-field-selected-sensors",
        )
        trial_assessment = self._assess_generated_experiment(
            resident,
            language_id=language_id,
            operation_name=f"{generation_tag}:trial",
            observations=trial["observed"],
            safety_receipt=authorization,
            source_revision_id=trial["source_revision_id"],
            variant="trial",
        )
        if not trial_assessment.get("earned", False):
            return {
                "authorization": authorization,
                "candidate_families_supplied": False,
                "generation_tag": generation_tag,
                "precommit": precommit,
                "precommit_source_revision_id": precommit_root,
                "proposal": proposal,
                "repeat": None,
                "repeat_assessment": None,
                "repeat_exact": False,
                "synthesis": synthesis,
                "transfer": None,
                "transfer_assessment": None,
                "transfer_invocation": self._invoke_experiment_language(
                    resident,
                    language_id=language_id,
                    operation_name=(
                        f"{generation_tag}:transfer-after-failed-trial"
                    ),
                    variant="transfer",
                ),
                "trial": trial,
                "trial_assessment": trial_assessment,
            }

        transfer_invocation = self._invoke_experiment_language(
            resident,
            language_id=language_id,
            operation_name=f"{generation_tag}:transfer",
            variant="transfer",
        )
        if (
            transfer_invocation["status"] != "supported"
            or transfer_invocation["world"] != proposal["transfer_world"]
            or transfer_invocation["proposal_sha256"]
            != precommit["proposal_sha256"]
        ):
            raise AutonomousPhysicsResidencyError(
                "earned experiment language did not preserve its sealed transfer"
            )
        transfer_program = transfer_invocation["world"]
        transfer_world = self._generated_world(
            proposal,
            variant="transfer",
            world_id=f"generated-language-{generation_tag}-transfer",
            split=f"sealed-field-originated-{generation_tag}-transfer",
        )
        transfer = self._admit_world(
            resident,
            self._execute_world(transfer_world),
            horizons=[
                int(row["horizon"])
                for row in transfer_program["observations"]
            ],
            observable_fields=self._generated_observation_fields(
                transfer_program
            ),
            suffix=f"{generation_tag}-field-selected-sensors",
        )
        transfer_assessment = self._assess_generated_experiment(
            resident,
            language_id=language_id,
            operation_name=f"{generation_tag}:transfer",
            observations=transfer["observed"],
            safety_receipt=authorization,
            source_revision_id=transfer["source_revision_id"],
            variant="transfer",
        )

        repeat_invocation = self._invoke_experiment_language(
            resident,
            language_id=language_id,
            operation_name=f"{generation_tag}:transfer-repeat",
            variant="transfer",
        )
        if (
            repeat_invocation["status"] != "supported"
            or repeat_invocation["world"] != transfer_program
        ):
            raise AutonomousPhysicsResidencyError(
                "earned experiment language changed before exact repetition"
            )
        repeat_world = self._generated_world(
            proposal,
            variant="transfer",
            world_id=f"repeat-generated-language-{generation_tag}-transfer",
            split=f"exact-field-originated-{generation_tag}-repeat",
            source_of=transfer_world.world_id,
        )
        repeat = self._admit_world(
            resident,
            self._execute_world(repeat_world),
            horizons=[
                int(row["horizon"])
                for row in transfer_program["observations"]
            ],
            observable_fields=self._generated_observation_fields(
                transfer_program
            ),
            suffix=f"{generation_tag}-field-selected-sensors",
        )
        repeat_assessment = self._assess_generated_experiment(
            resident,
            language_id=language_id,
            operation_name=f"{generation_tag}:transfer-repeat",
            observations=repeat["observed"],
            safety_receipt=authorization,
            source_revision_id=repeat["source_revision_id"],
            variant="transfer",
        )
        return {
            "authorization": authorization,
            "candidate_families_supplied": False,
            "generation_tag": generation_tag,
            "precommit": precommit,
            "precommit_source_revision_id": precommit_root,
            "proposal": proposal,
            "repeat": repeat,
            "repeat_assessment": repeat_assessment,
            "repeat_exact": repeat["observed"] == transfer["observed"],
            "synthesis": synthesis,
            "transfer": transfer,
            "transfer_assessment": transfer_assessment,
            "transfer_invocation": transfer_invocation,
            "trial": trial,
            "trial_assessment": trial_assessment,
        }

    def _revise_experiment_constructor(
        self,
        resident: ResearchResidency,
        *,
        language_id: str,
    ) -> dict[str, Any]:
        result = resident.semantic(
            {
                "operation": "revise-experiment-constructor",
                "operation_id": (
                    f"{self.run_id}:revise-experiment-constructor:"
                    f"{language_id}"
                ),
                "constructor_id": EXPERIMENT_CONSTRUCTOR_ID,
                "language_id": language_id,
            }
        )
        if result["status"] != "supported":
            raise AutonomousPhysicsResidencyError(
                f"field did not revise its experiment constructor: {result}"
            )
        return result

    def _synthesize_research_program(
        self,
        resident: ResearchResidency,
    ) -> dict[str, Any]:
        result = resident.semantic(
            {
                "operation": "synthesize-research-program",
                "operation_id": f"{self.run_id}:synthesize-research-program",
                "constructor_id": EXPERIMENT_CONSTRUCTOR_ID,
                "next_language_id": EXPERIMENT_LANGUAGE_GENERATION_3_ID,
                "program_id": RESEARCH_PROGRAM_ID,
            }
        )
        if (
            result["status"] != "supported"
            or result["next_stage"]["stage_id"]
            != RESEARCH_STAGE_GENERATION_3_ID
        ):
            raise AutonomousPhysicsResidencyError(
                f"field did not compose its research program: {result}"
            )
        return result

    def _review_research_authority_request(
        self,
        synthesis: Mapping[str, Any],
    ) -> dict[str, Any]:
        authority_request = synthesis.get("authority_request")
        authority_ref = synthesis.get("authority_request_ref")
        grammar_sha256 = sha256_value(self.experiment_grammar)
        expected_keys = {
            "bounds",
            "primitive",
            "program_id",
            "purpose",
            "schema",
            "state",
            "uncertainty_id",
        }
        request_shape = (
            isinstance(authority_request, Mapping)
            and set(authority_request) == expected_keys
            and authority_request.get("schema")
            == "cassifi.research-authority-request.v1"
            and authority_request.get("program_id") == RESEARCH_PROGRAM_ID
            and authority_request.get("state") == "pending-owner-review"
            and isinstance(authority_ref, Mapping)
        )
        bounds = (
            authority_request.get("bounds", {})
            if isinstance(authority_request, Mapping)
            else {}
        )
        primitive = (
            authority_request.get("primitive", {})
            if isinstance(authority_request, Mapping)
            else {}
        )
        top_cell_scope = (
            set(bounds) == {"max_samples_per_world", "read_only"}
            and bounds.get("read_only") is True
            and bounds.get("max_samples_per_world") == 3
            and primitive.get("kind") == "raw-observable"
            and primitive.get("scope") == "top-coherence-cell"
        )
        distributed_scope = (
            set(bounds)
            == {
                "axis",
                "bin_count",
                "max_samples_per_world",
                "read_only",
            }
            and bounds.get("axis") == "x"
            and bounds.get("bin_count") == 16
            and bounds.get("max_samples_per_world") == 8
            and bounds.get("read_only") is True
            and primitive.get("kind") == "raw-observable-family"
            and primitive.get("scope") == "sixteen-x-slabs-full-yz"
        )
        topology_scope = (
            set(bounds)
            == {
                "bin_count_per_axis",
                "max_samples_per_world",
                "native_winding_grid_n",
                "native_winding_planes",
                "native_winding_radii_cells",
                "read_only",
                "vector_components",
            }
            and bounds.get("bin_count_per_axis") == 4
            and bounds.get("max_samples_per_world") == 3
            and bounds.get("native_winding_grid_n") == 64
            and bounds.get("native_winding_planes") == ["xy", "xz", "yz"]
            and bounds.get("native_winding_radii_cells") == [2, 4, 8]
            and bounds.get("read_only") is True
            and bounds.get("vector_components") == 3
            and primitive.get("kind") == "raw-observable-family"
            and primitive.get("scope")
            == (
                "four-cubed-periodic-phase-current-lattice-plus-"
                "native-closed-loops"
            )
        )
        bounded_scope = (
            isinstance(bounds, Mapping)
            and isinstance(primitive, Mapping)
            and set(primitive)
            == {"field", "kind", "provides", "scope"}
            and isinstance(primitive.get("provides"), list)
            and primitive["provides"]
            == sorted(set(primitive["provides"]))
            and (top_cell_scope or distributed_scope or topology_scope)
        )
        available_rows = [
            row
            for row in self.experiment_grammar["raw_observables"]
            if row["field"] == primitive.get("field")
        ]
        available_primitive = (
            len(available_rows) == 1
            and set(primitive.get("provides", []))
            <= set(available_rows[0]["provides"])
        )
        authorized = bool(
            request_shape and bounded_scope and available_primitive
        )
        normalized_authority_ref = (
            dict(authority_ref)
            if isinstance(authority_ref, Mapping)
            else authority_ref
        )
        return {
            "authorized": authorized,
            "checks": {
                "available_primitive": available_primitive,
                "bounded_scope": bounded_scope,
                "grammar_unchanged": True,
                "no_implicit_grant": True,
                "request_shape": request_shape,
            },
            "decision": (
                "authorized-existing-primitive"
                if authorized
                else "deferred-unavailable"
            ),
            "grammar_sha256_after": grammar_sha256,
            "grammar_sha256_before": grammar_sha256,
            "grant": (
                {
                    "field": primitive["field"],
                    "scope": primitive["scope"],
                }
                if authorized
                else None
            ),
            "request_ref": normalized_authority_ref,
            "request_sha256": (
                sha256_value(authority_request)
                if isinstance(authority_request, Mapping)
                else ""
            ),
            "schema": "cassifi.research-authority-receipt.v1",
        }

    def _record_research_authority(
        self,
        resident: ResearchResidency,
        receipt: Mapping[str, Any],
        *,
        operation_name: str = "initial",
    ) -> dict[str, Any]:
        result = resident.semantic(
            {
                "operation": "record-research-authority",
                "operation_id": (
                    f"{self.run_id}:record-research-authority:{operation_name}"
                ),
                "authority_receipt": dict(receipt),
                "program_id": RESEARCH_PROGRAM_ID,
            }
        )
        expected_status = (
            "supported"
            if receipt.get("authorized") is True
            else "authority-denied"
        )
        if result["status"] != expected_status:
            raise AutonomousPhysicsResidencyError(
                f"field did not record the authority decision: {result}"
            )
        return result

    def _advance_research_program(
        self,
        resident: ResearchResidency,
    ) -> dict[str, Any]:
        result = resident.semantic(
            {
                "operation": "advance-research-program",
                "operation_id": f"{self.run_id}:advance-research-program",
                "constructor_id": EXPERIMENT_CONSTRUCTOR_ID,
                "language_id": EXPERIMENT_LANGUAGE_GENERATION_3_ID,
                "program_id": RESEARCH_PROGRAM_ID,
                "stage_id": RESEARCH_STAGE_GENERATION_3_ID,
            }
        )
        if result["status"] != "supported":
            raise AutonomousPhysicsResidencyError(
                f"field did not advance its research program: {result}"
            )
        return result

    def _design_mechanism_experiment(
        self,
        resident: ResearchResidency,
    ) -> dict[str, Any]:
        result = resident.semantic(
            {
                "operation": "design-mechanism-experiment",
                "operation_id": f"{self.run_id}:design-mechanism-experiment",
                "experiment_id": MECHANISM_EXPERIMENT_ID,
                "grammar": self.experiment_grammar,
                "program_id": RESEARCH_PROGRAM_ID,
            }
        )
        if (
            result["status"] != "supported"
            or result.get("candidate_families_supplied") is not False
            or not str(result.get("selected_candidate", "")).startswith(
                "auto:mechanism-experiment:"
            )
        ):
            raise AutonomousPhysicsResidencyError(
                f"field did not design the mechanism experiment: {result}"
            )
        return result

    def _authorize_mechanism_experiment(
        self,
        proposal: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Validate only the fixed primitive and resource boundary."""

        grammar = self.experiment_grammar
        bounds = grammar["bounds"]
        sources = {
            str(row["source_id"]): dict(row) for row in grammar["sources"]
        }
        strengths = {float(value) for value in grammar["strengths"]}
        step_counts = {int(value) for value in grammar["step_counts"]}
        fields = {
            str(row["field"]) for row in grammar["raw_observables"]
        }
        checks = {
            "grammar_bound": False,
            "matched_control": False,
            "mirrored_prior": False,
            "phase_current_available": (
                "top_phase_current_x" in fields
            ),
            "resource_bounds": False,
        }
        try:
            checks["grammar_bound"] = (
                set(proposal)
                == {
                    "candidate_id",
                    "control_world",
                    "decision_rule",
                    "family",
                    "mirror_trial_world",
                    "question",
                    "research_program_ref",
                    "schema",
                    "selection",
                    "trial_world",
                }
                and proposal["schema"]
                == "cassifi.mechanism-experiment.v1"
                and proposal["family"] == "matched-phase-current"
                and str(proposal["candidate_id"]).startswith(
                    "auto:mechanism-experiment:"
                )
                and isinstance(proposal["research_program_ref"], Mapping)
                and isinstance(proposal["decision_rule"], Mapping)
                and isinstance(proposal["selection"], Mapping)
            )
            worlds = {
                variant: proposal[f"{variant}_world"]
                for variant in ("control", "trial", "mirror_trial")
            }
            valid_resources = checks["grammar_bound"]
            normalized_segments: dict[str, list[dict[str, Any]]] = {}
            for variant, world in worlds.items():
                expected_segments = 1 if variant == "control" else 2
                world_valid = (
                    isinstance(world, Mapping)
                    and set(world)
                    == {"observations", "segments", "variant"}
                    and world["variant"] == variant
                    and isinstance(world["segments"], list)
                    and len(world["segments"]) == expected_segments
                    and isinstance(world["observations"], list)
                    and len(world["observations"]) == expected_segments
                )
                total_steps = 0
                total_charge = 0.0
                deposits = 0
                horizons: list[int] = []
                segments: list[dict[str, Any]] = []
                if not world_valid:
                    valid_resources = False
                    normalized_segments[variant] = segments
                    continue
                for segment in world["segments"]:
                    segment_valid = (
                        isinstance(segment, Mapping)
                        and set(segment) == {"pulses", "steps"}
                        and isinstance(segment["pulses"], list)
                        and len(segment["pulses"]) == 1
                        and isinstance(segment["steps"], int)
                        and not isinstance(segment["steps"], bool)
                    )
                    if not segment_valid:
                        valid_resources = False
                        continue
                    pulse = segment["pulses"][0]
                    pulse_valid = (
                        isinstance(pulse, Mapping)
                        and set(pulse)
                        == {"channel", "source_id", "strength"}
                        and pulse.get("channel") == "cy"
                        and pulse.get("source_id") in sources
                        and isinstance(pulse.get("strength"), (int, float))
                        and not isinstance(pulse.get("strength"), bool)
                        and float(pulse["strength"]) in strengths
                        and int(segment["steps"]) in step_counts
                    )
                    if not pulse_valid:
                        valid_resources = False
                        continue
                    normalized = {
                        "source_id": str(pulse["source_id"]),
                        "steps": int(segment["steps"]),
                        "strength": float(pulse["strength"]),
                    }
                    segments.append(normalized)
                    deposits += 1
                    total_charge += abs(normalized["strength"])
                    total_steps += normalized["steps"]
                    horizons.append(total_steps)
                observation_valid = all(
                    isinstance(row, Mapping)
                    and set(row) == {"fields", "horizon"}
                    and row["fields"]
                    == [
                        "top_phase_current_x",
                        "top_q",
                        "top_x",
                    ]
                    and int(row["horizon"]) in horizons
                    for row in world["observations"]
                )
                valid_resources = valid_resources and (
                    observation_valid
                    and 1 <= len(segments) <= int(bounds["max_segments"])
                    and deposits <= int(bounds["max_deposits"])
                    and total_charge <= float(bounds["max_abs_charge"])
                    and total_steps <= int(bounds["max_total_steps"])
                    and len(world["observations"])
                    <= int(bounds["max_observables"])
                )
                normalized_segments[variant] = segments
            checks["resource_bounds"] = bool(valid_resources)
            control = normalized_segments["control"]
            trial = normalized_segments["trial"]
            mirror = normalized_segments["mirror_trial"]
            checks["matched_control"] = (
                len(control) == 1
                and len(trial) == 2
                and len(mirror) == 2
                and control[0] == trial[1] == mirror[1]
            )
            if checks["matched_control"]:
                target_x = float(sources[control[0]["source_id"]]["x"])
                left_x = float(sources[trial[0]["source_id"]]["x"])
                right_x = float(sources[mirror[0]["source_id"]]["x"])
                checks["mirrored_prior"] = (
                    left_x < target_x < right_x
                    and math.isclose(
                        target_x - left_x,
                        right_x - target_x,
                        rel_tol=0.0,
                        abs_tol=1.0e-12,
                    )
                    and trial[0]["strength"] == mirror[0]["strength"]
                    and trial[0]["steps"] == mirror[0]["steps"]
                )
        except (KeyError, TypeError, ValueError):
            pass
        authorized = all(checks.values())
        return {
            "authorized": authorized,
            "checks": checks,
            "grammar_sha256": sha256_value(grammar),
            "proposal_sha256": sha256_value(proposal),
            "schema": "cassifi.mechanism-experiment-authority.v1",
        }

    def _run_mechanism_experiment(
        self,
        resident: ResearchResidency,
    ) -> dict[str, Any]:
        design = self._design_mechanism_experiment(resident)
        proposal = dict(design["proposal"])
        authorization = self._authorize_mechanism_experiment(proposal)
        if not authorization["authorized"]:
            raise AutonomousPhysicsResidencyError(
                "field-designed mechanism experiment crossed its safety boundary: "
                f"{authorization}"
            )
        precommit = {
            "authorization": authorization,
            "field_state_sha256": resident.inspect()["field_state_sha256"],
            "manifest_sha256": hashlib.sha256(
                self.manifest_bytes
            ).hexdigest(),
            "proposal": proposal,
            "proposal_sha256": sha256_value(proposal),
            "sealed_sha256": self.manifest["sealed_sha256"],
        }
        precommit_bytes = canonical_json_bytes(precommit)
        precommit_root = self._archive(
            resident,
            source_id="precommit:mechanism-experiment",
            content=precommit_bytes,
            category="field-originated-mechanism-precommit",
            context={
                "candidate_id": proposal["candidate_id"],
                "proposal_sha256": sha256_value(proposal),
                "sha256": hashlib.sha256(precommit_bytes).hexdigest(),
            },
        )
        arms: dict[str, dict[str, Any]] = {}
        for variant in ("control", "trial", "mirror_trial"):
            world_program = proposal[f"{variant}_world"]
            world = self._generated_world(
                proposal,
                variant=variant,
                world_id=f"mechanism-phase-current-{variant.replace('_', '-')}",
                split=f"mechanism-{variant.replace('_', '-')}",
            )
            arms[variant] = self._admit_world(
                resident,
                self._execute_world(world),
                horizons=[
                    int(row["horizon"])
                    for row in world_program["observations"]
                ],
                observable_fields=self._generated_observation_fields(
                    world_program
                ),
                suffix="phase-current-selected-sensors",
            )
        assessment = resident.semantic(
            {
                "operation": "assess-mechanism-experiment",
                "operation_id": f"{self.run_id}:assess-mechanism-experiment",
                "experiment_id": MECHANISM_EXPERIMENT_ID,
                "observations": {
                    variant: arm["observed"]
                    for variant, arm in arms.items()
                },
                "safety_receipt": authorization,
                "evidence_sources": {
                    variant: arm["source_revision_id"]
                    for variant, arm in arms.items()
                },
            }
        )
        if (
            assessment["status"] != "supported"
            or assessment["program_state"] != "resolved"
            or assessment["verdict"]
            not in {
                "inconclusive",
                "local-rewriting-at-peak",
                "transport-coupled-at-peak",
            }
        ):
            raise AutonomousPhysicsResidencyError(
                f"field did not resolve the mechanism experiment: {assessment}"
            )
        return {
            "arms": arms,
            "assessment": assessment,
            "authorization": authorization,
            "candidate_families_supplied": design[
                "candidate_families_supplied"
            ],
            "design": design,
            "precommit": precommit,
            "precommit_source_revision_id": precommit_root,
            "proposal": proposal,
        }

    def _continue_distributed_phase_flow(
        self,
        resident: ResearchResidency,
    ) -> dict[str, Any]:
        result = resident.semantic(
            {
                "operation": "continue-distributed-phase-flow",
                "operation_id": (
                    f"{self.run_id}:continue-distributed-phase-flow"
                ),
                "program_id": RESEARCH_PROGRAM_ID,
            }
        )
        if (
            result["status"] != "supported"
            or result["uncertainty"]["uncertainty_id"]
            != "distributed-phase-flow-mechanism"
        ):
            raise AutonomousPhysicsResidencyError(
                f"field did not continue into distributed flow: {result}"
            )
        return result

    def _design_distributed_phase_flow(
        self,
        resident: ResearchResidency,
    ) -> dict[str, Any]:
        result = resident.semantic(
            {
                "operation": "design-distributed-phase-flow",
                "operation_id": (
                    f"{self.run_id}:design-distributed-phase-flow"
                ),
                "experiment_id": DISTRIBUTED_PHASE_EXPERIMENT_ID,
                "grammar": self.experiment_grammar,
                "program_id": RESEARCH_PROGRAM_ID,
            }
        )
        if (
            result["status"] != "supported"
            or result.get("candidate_families_supplied") is not False
            or not str(result.get("selected_candidate", "")).startswith(
                "auto:distributed-phase-flow:"
            )
        ):
            raise AutonomousPhysicsResidencyError(
                f"field did not design distributed flow study: {result}"
            )
        return result

    def _authorize_distributed_phase_flow(
        self,
        proposal: Mapping[str, Any],
    ) -> dict[str, Any]:
        grammar = self.experiment_grammar
        sources = {
            str(row["source_id"]): dict(row)
            for row in grammar["sources"]
        }
        strengths = {float(value) for value in grammar["strengths"]}
        steps = {int(value) for value in grammar["step_counts"]}
        expected_fields = ["top_q", "top_x", *_distributed_phase_fields()]
        checks = {
            "distributed_profile_available": any(
                row["field"] == "phase_profile_x_16"
                and "distributed-phase-flow" in row["provides"]
                for row in grammar["raw_observables"]
            ),
            "grammar_bound": False,
            "mirrored_prior": False,
            "read_only": False,
            "resource_bounds": False,
            "time_resolved": False,
        }
        try:
            checks["grammar_bound"] = (
                set(proposal)
                == {
                    "candidate_id",
                    "control_world",
                    "decision_rule",
                    "family",
                    "mirror_trial_world",
                    "question",
                    "research_program_ref",
                    "schema",
                    "selection",
                    "trial_world",
                }
                and proposal["schema"]
                == "cassifi.distributed-phase-flow-experiment.v1"
                and proposal["family"]
                == "distributed-phase-flow-worldlines"
                and isinstance(proposal["research_program_ref"], Mapping)
            )
            valid_resources = checks["grammar_bound"]
            normalized: dict[str, list[dict[str, Any]]] = {}
            for variant in ("control", "trial", "mirror_trial"):
                world = proposal[f"{variant}_world"]
                expected_segments = 4 if variant == "control" else 8
                segments = world["segments"]
                observations = world["observations"]
                valid_world = (
                    isinstance(segments, list)
                    and len(segments) == expected_segments
                    and isinstance(observations, list)
                    and len(observations) == expected_segments
                    and world["variant"] == variant
                )
                elapsed = 0
                deposits = 0
                charge = 0.0
                rows: list[dict[str, Any]] = []
                for index, segment in enumerate(segments):
                    segment_valid = (
                        isinstance(segment, Mapping)
                        and set(segment) == {"pulses", "steps"}
                        and isinstance(segment["pulses"], list)
                        and len(segment["pulses"]) <= 1
                        and int(segment["steps"]) in steps
                    )
                    if not segment_valid:
                        valid_world = False
                        continue
                    elapsed += int(segment["steps"])
                    for pulse in segment["pulses"]:
                        pulse_valid = (
                            isinstance(pulse, Mapping)
                            and set(pulse)
                            == {"channel", "source_id", "strength"}
                            and pulse["channel"] == "cy"
                            and pulse["source_id"] in sources
                            and float(pulse["strength"]) in strengths
                        )
                        valid_world = valid_world and pulse_valid
                        if pulse_valid:
                            deposits += 1
                            charge += abs(float(pulse["strength"]))
                    observation = observations[index]
                    valid_world = valid_world and (
                        observation
                        == {"fields": expected_fields, "horizon": elapsed}
                    )
                    rows.append(
                        {
                            "pulses": [dict(pulse) for pulse in segment["pulses"]],
                            "steps": int(segment["steps"]),
                        }
                    )
                expected_deposits = 1 if variant == "control" else 2
                valid_resources = valid_resources and (
                    valid_world
                    and deposits == expected_deposits
                    and deposits <= int(grammar["bounds"]["max_deposits"])
                    and charge <= float(grammar["bounds"]["max_abs_charge"])
                    and elapsed <= int(grammar["bounds"]["max_total_steps"])
                    and len(segments)
                    <= int(grammar["bounds"]["max_segments"])
                )
                normalized[variant] = rows
            checks["resource_bounds"] = bool(valid_resources)
            selection = proposal["selection"]
            control = normalized["control"]
            trial = normalized["trial"]
            mirror = normalized["mirror_trial"]
            checks["mirrored_prior"] = (
                trial[0]["pulses"][0]["source_id"]
                == selection["left_source_id"]
                and mirror[0]["pulses"][0]["source_id"]
                == selection["right_source_id"]
                and trial[0]["pulses"][0]["strength"]
                == mirror[0]["pulses"][0]["strength"]
                and trial[4]["pulses"] == mirror[4]["pulses"]
                == control[0]["pulses"]
                and math.isclose(
                    float(selection["left_source_x"])
                    + float(selection["right_source_x"]),
                    2.0 * float(selection["target_source_x"]),
                    abs_tol=1.0e-12,
                )
            )
            checks["read_only"] = all(
                row["fields"] == expected_fields
                for variant in ("control", "trial", "mirror_trial")
                for row in proposal[f"{variant}_world"]["observations"]
            )
            checks["time_resolved"] = (
                len(proposal["control_world"]["observations"]) == 4
                and len(proposal["trial_world"]["observations"]) == 8
                and len(proposal["mirror_trial_world"]["observations"]) == 8
            )
        except (IndexError, KeyError, TypeError, ValueError):
            pass
        authorized = all(checks.values())
        return {
            "authorized": authorized,
            "checks": checks,
            "grammar_sha256": sha256_value(grammar),
            "proposal_sha256": sha256_value(proposal),
            "schema": "cassifi.distributed-phase-flow-authority.v1",
        }

    def _run_distributed_phase_flow(
        self,
        resident: ResearchResidency,
    ) -> dict[str, Any]:
        continuation = self._continue_distributed_phase_flow(resident)
        authority_review = self._review_research_authority_request(
            continuation
        )
        if not authority_review["authorized"]:
            raise AutonomousPhysicsResidencyError(
                f"distributed sensor authority was not granted: {authority_review}"
            )
        authority_assessment = self._record_research_authority(
            resident,
            authority_review,
            operation_name="distributed-phase-flow",
        )
        design = self._design_distributed_phase_flow(resident)
        proposal = dict(design["proposal"])
        authorization = self._authorize_distributed_phase_flow(proposal)
        if not authorization["authorized"]:
            raise AutonomousPhysicsResidencyError(
                f"distributed design crossed safety boundary: {authorization}"
            )
        precommit = {
            "authorization": authorization,
            "field_state_sha256": resident.inspect()["field_state_sha256"],
            "manifest_sha256": hashlib.sha256(self.manifest_bytes).hexdigest(),
            "proposal": proposal,
            "proposal_sha256": sha256_value(proposal),
            "sealed_sha256": self.manifest["sealed_sha256"],
        }
        precommit_bytes = canonical_json_bytes(precommit)
        precommit_root = self._archive(
            resident,
            source_id="precommit:distributed-phase-flow",
            content=precommit_bytes,
            category="field-originated-distributed-flow-precommit",
            context={
                "candidate_id": proposal["candidate_id"],
                "sha256": hashlib.sha256(precommit_bytes).hexdigest(),
            },
        )
        arms: dict[str, dict[str, Any]] = {}
        for variant in ("control", "trial", "mirror_trial"):
            world_program = proposal[f"{variant}_world"]
            world = self._generated_world(
                proposal,
                variant=variant,
                world_id=f"distributed-phase-flow-{variant.replace('_', '-')}",
                split=f"distributed-{variant.replace('_', '-')}",
            )
            arms[variant] = self._admit_world(
                resident,
                self._execute_world(
                    world,
                    phase_profile_bins=16,
                ),
                horizons=[
                    int(row["horizon"])
                    for row in world_program["observations"]
                ],
                observable_fields=self._generated_observation_fields(
                    world_program
                ),
                suffix="distributed-phase-flow-selected-sensors",
                admit_observations=False,
            )
        assessment = resident.semantic(
            {
                "operation": "assess-distributed-phase-flow",
                "operation_id": (
                    f"{self.run_id}:assess-distributed-phase-flow"
                ),
                "experiment_id": DISTRIBUTED_PHASE_EXPERIMENT_ID,
                "observations": {
                    variant: arm["observed"]
                    for variant, arm in arms.items()
                },
                "safety_receipt": authorization,
                "evidence_sources": {
                    variant: arm["source_revision_id"]
                    for variant, arm in arms.items()
                },
            }
        )
        if (
            assessment["status"] != "supported"
            or assessment["program_state"] != "resolved"
            or assessment["verdict"]
            not in {
                "advective-transport",
                "local-nucleation",
                "local-nucleation-with-remote-persistence",
                "remote-conditioning",
            }
        ):
            raise AutonomousPhysicsResidencyError(
                f"field did not resolve distributed phase flow: {assessment}"
            )
        return {
            "arms": arms,
            "assessment": assessment,
            "authority_assessment": authority_assessment,
            "authority_review": authority_review,
            "authorization": authorization,
            "candidate_families_supplied": design[
                "candidate_families_supplied"
            ],
            "continuation": continuation,
            "design": design,
            "precommit": precommit,
            "precommit_source_revision_id": precommit_root,
            "proposal": proposal,
        }
    def _continue_phase_current_topology(
        self,
        resident: ResearchResidency,
    ) -> dict[str, Any]:
        return resident.semantic(
            {
                "operation": "continue-phase-current-topology",
                "operation_id": (
                    f"{self.run_id}:continue-phase-current-topology"
                ),
                "program_id": RESEARCH_PROGRAM_ID,
            }
        )

    def _design_phase_current_topology(
        self,
        resident: ResearchResidency,
    ) -> dict[str, Any]:
        return resident.semantic(
            {
                "operation": "design-phase-current-topology",
                "operation_id": (
                    f"{self.run_id}:design-phase-current-topology"
                ),
                "experiment_id": PHASE_CURRENT_TOPOLOGY_EXPERIMENT_ID,
                "grammar": self.experiment_grammar,
                "program_id": RESEARCH_PROGRAM_ID,
            }
        )

    def _authorize_phase_current_topology(
        self,
        proposal: Mapping[str, Any],
    ) -> dict[str, Any]:
        grammar = self.experiment_grammar
        bounds = grammar["bounds"]
        source_ids = {
            str(row["source_id"]) for row in grammar["sources"]
        }
        strengths = {float(value) for value in grammar["strengths"]}
        variants = (
            "left_control",
            "left_trial",
            "right_control",
            "right_trial",
        )
        checks = {
            "four_cubed_lattice": False,
            "grammar_bound": False,
            "matched_controls": False,
            "mirrored_prior": False,
            "read_only": False,
            "resource_bounds": False,
        }
        try:
            selection = proposal["selection"]
            checks["four_cubed_lattice"] = (
                proposal["schema"]
                == "cassifi.phase-current-topology-experiment.v1"
                and proposal["family"]
                == "three-dimensional-phase-current-topology"
                and selection["bin_count_per_axis"] == 4
                and selection["native_winding_grid_n"] == 64
                and selection["native_winding_planes"]
                == ["xy", "xz", "yz"]
                and selection["native_winding_radii_cells"] == [2, 4, 8]
                and selection["sample_horizons"] == [32, 33, 96]
                and str(proposal["candidate_id"]).startswith(
                    "auto:phase-current-topology:"
                )
            )
            worlds = {
                variant: proposal[f"{variant}_world"]
                for variant in variants
            }
            expected_steps = [32, 1, 63]
            checks["grammar_bound"] = all(
                world["variant"] == variant
                and len(world["segments"]) == 3
                and [
                    int(segment["steps"]) for segment in world["segments"]
                ]
                == expected_steps
                and all(
                    all(
                        pulse["channel"] == "cy"
                        and str(pulse["source_id"]) in source_ids
                        and float(pulse["strength"]) in strengths
                        for pulse in segment["pulses"]
                    )
                    for segment in world["segments"]
                )
                for variant, world in worlds.items()
            )
            checks["resource_bounds"] = all(
                len(world["segments"]) <= int(bounds["max_segments"])
                and sum(
                    int(segment["steps"])
                    for segment in world["segments"]
                )
                <= int(bounds["max_total_steps"])
                and sum(
                    len(segment["pulses"])
                    for segment in world["segments"]
                )
                <= int(bounds["max_deposits"])
                and len(world["observations"]) == 3
                for world in worlds.values()
            )
            checks["read_only"] = all(
                row["fields"]
                == [
                    "top_q",
                    "top_x",
                    "phase_topology_xyz_4",
                    "phase_winding_native_3x3",
                ]
                for world in worlds.values()
                for row in world["observations"]
            )

            def without_target(world: Mapping[str, Any]) -> list[dict[str, Any]]:
                return [
                    {
                        "pulses": [
                            dict(pulse)
                            for pulse in segment["pulses"]
                            if pulse["source_id"]
                            != selection["target_source_id"]
                        ],
                        "steps": int(segment["steps"]),
                    }
                    for segment in world["segments"]
                ]

            checks["matched_controls"] = (
                without_target(world=worlds["left_trial"])
                == [
                    {
                        "pulses": [
                            dict(pulse) for pulse in segment["pulses"]
                        ],
                        "steps": int(segment["steps"]),
                    }
                    for segment in worlds["left_control"]["segments"]
                ]
                and without_target(world=worlds["right_trial"])
                == [
                    {
                        "pulses": [
                            dict(pulse) for pulse in segment["pulses"]
                        ],
                        "steps": int(segment["steps"]),
                    }
                    for segment in worlds["right_control"]["segments"]
                ]
                and len(worlds["left_trial"]["segments"][1]["pulses"]) == 1
                and len(worlds["right_trial"]["segments"][1]["pulses"]) == 1
            )
            left_prior = worlds["left_control"]["segments"][0]["pulses"]
            right_prior = worlds["right_control"]["segments"][0]["pulses"]
            checks["mirrored_prior"] = (
                len(left_prior) == 1
                and len(right_prior) == 1
                and left_prior[0]["source_id"]
                == selection["left_source_id"]
                and right_prior[0]["source_id"]
                == selection["right_source_id"]
                and float(left_prior[0]["strength"])
                == float(right_prior[0]["strength"])
                == float(selection["prior_strength"])
                and abs(
                    float(selection["left_source_x"])
                    + float(selection["right_source_x"])
                )
                <= 1.0e-12
            )
        except (IndexError, KeyError, TypeError, ValueError):
            pass
        authorized = all(checks.values())
        return {
            "authorized": authorized,
            "checks": checks,
            "grammar_sha256": sha256_value(grammar),
            "proposal_sha256": sha256_value(proposal),
            "schema": "cassifi.phase-current-topology-authority.v1",
        }

    def _run_phase_current_topology(
        self,
        resident: ResearchResidency,
    ) -> dict[str, Any]:
        continuation = self._continue_phase_current_topology(resident)
        authority_review = self._review_research_authority_request(
            continuation
        )
        if not authority_review["authorized"]:
            raise AutonomousPhysicsResidencyError(
                f"topology sensor authority was not granted: {authority_review}"
            )
        authority_assessment = self._record_research_authority(
            resident,
            authority_review,
            operation_name="phase-current-topology",
        )
        design = self._design_phase_current_topology(resident)
        proposal = dict(design["proposal"])
        authorization = self._authorize_phase_current_topology(proposal)
        if not authorization["authorized"]:
            raise AutonomousPhysicsResidencyError(
                f"topology design crossed safety boundary: {authorization}"
            )
        precommit = {
            "authorization": authorization,
            "field_state_sha256": resident.inspect()["field_state_sha256"],
            "manifest_sha256": hashlib.sha256(self.manifest_bytes).hexdigest(),
            "proposal": proposal,
            "proposal_sha256": sha256_value(proposal),
            "sealed_sha256": self.manifest["sealed_sha256"],
        }
        precommit_bytes = canonical_json_bytes(precommit)
        precommit_root = self._archive(
            resident,
            source_id="precommit:phase-current-topology",
            content=precommit_bytes,
            category="field-originated-phase-current-topology-precommit",
            context={
                "candidate_id": proposal["candidate_id"],
                "sha256": hashlib.sha256(precommit_bytes).hexdigest(),
            },
        )
        arms: dict[str, dict[str, Any]] = {}
        for variant in (
            "left_control",
            "left_trial",
            "right_control",
            "right_trial",
        ):
            world_program = proposal[f"{variant}_world"]
            world = self._generated_world(
                proposal,
                variant=variant,
                world_id=f"phase-current-topology-{variant.replace('_', '-')}",
                split=f"topology-{variant.replace('_', '-')}",
            )
            arms[variant] = self._admit_world(
                resident,
                self._execute_world(
                    world,
                    phase_topology_bins=4,
                    phase_winding_probe=1,
                ),
                horizons=[
                    int(row["horizon"])
                    for row in world_program["observations"]
                ],
                observable_fields=[
                    "top_q",
                    "top_x",
                    *_phase_topology_fields(),
                    *_phase_winding_fields(),
                ],
                suffix="phase-current-topology-selected-sensors",
                admit_observations=False,
            )
        assessment = resident.semantic(
            {
                "operation": "assess-phase-current-topology",
                "operation_id": (
                    f"{self.run_id}:assess-phase-current-topology"
                ),
                "experiment_id": PHASE_CURRENT_TOPOLOGY_EXPERIMENT_ID,
                "observations": {
                    variant: arm["observed"]
                    for variant, arm in arms.items()
                },
                "safety_receipt": authorization,
                "evidence_sources": {
                    variant: arm["source_revision_id"]
                    for variant, arm in arms.items()
                },
            }
        )
        if (
            assessment["status"] != "supported"
            or assessment["program_state"] != "resolved"
            or assessment["verdict"]
            not in {
                "vortical-circulation",
                "recirculating-return-flow",
                "delayed-three-dimensional-transport",
                "static-remote-persistence",
            }
        ):
            raise AutonomousPhysicsResidencyError(
                f"field did not resolve phase-current topology: {assessment}"
            )
        return {
            "arms": arms,
            "assessment": assessment,
            "authority_assessment": authority_assessment,
            "authority_review": authority_review,
            "authorization": authorization,
            "candidate_families_supplied": design[
                "candidate_families_supplied"
            ],
            "continuation": continuation,
            "design": design,
            "precommit": precommit,
            "precommit_source_revision_id": precommit_root,
            "proposal": proposal,
        }


    def _query_research_program(
        self,
        resident: ResearchResidency,
        *,
        operation_name: str,
    ) -> dict[str, Any]:
        return resident.semantic(
            {
                "operation": "query-research-program",
                "operation_id": (
                    f"{self.run_id}:query-research-program:{operation_name}"
                ),
                "program_id": RESEARCH_PROGRAM_ID,
            }
        )

    def _query_representation(
        self,
        resident: ResearchResidency,
        *,
        operation_name: str,
        representation_id: str,
        features: Mapping[str, Any],
    ) -> dict[str, Any]:
        result = resident.semantic(
            {
                "operation": "query",
                "operation_id": f"{self.run_id}:query:{operation_name}",
                "query": {
                    "features": dict(features),
                    "kind": "representation",
                    "representation_id": representation_id,
                },
            }
        )
        if result["status"] != "supported":
            raise AutonomousPhysicsResidencyError(
                f"representation query {operation_name} ended {result['status']}: {result}"
            )
        return result

    @staticmethod
    def _base_examples(
        results: Sequence[Mapping[str, Any]],
        outcome,
    ) -> list[dict[str, Any]]:
        return [
            {
                "example_id": str(result["world"]["world_id"]),
                "features": dict(result["world"]["features"]),
                "outcome": outcome(result),
                "source_revision_id": result.get("source_revision_id"),
            }
            for result in results
        ]

    def _predict_static_transfers(
        self,
        resident: ResearchResidency,
        *,
        representation_id: str,
        prefix: str,
        worlds: Sequence[ScheduledPhysicsWorld],
    ) -> dict[str, dict[str, Any]]:
        predictions = {}
        for world in worlds:
            predictions[world.world_id] = self._query_representation(
                resident,
                operation_name=f"{prefix}:{world.world_id}",
                representation_id=representation_id,
                features=world.feature_values,
            )
        payload = {
            "field_state_sha256": resident.inspect()["field_state_sha256"],
            "manifest_sha256": hashlib.sha256(self.manifest_bytes).hexdigest(),
            "predictions": predictions,
            "representation_id": representation_id,
            "sealed_sha256": self.manifest["sealed_sha256"],
        }
        content = canonical_json_bytes(payload)
        root = self._archive(
            resident,
            source_id=f"precommit:{prefix}",
            content=content,
            category="prospective-representation-precommit",
            context={
                "prediction_count": len(predictions),
                "representation_id": representation_id,
                "sha256": hashlib.sha256(content).hexdigest(),
            },
        )
        return {
            world_id: {**prediction, "precommit_source_revision_id": root}
            for world_id, prediction in predictions.items()
        }

    @staticmethod
    def _assess_predictions(
        predictions: Mapping[str, Mapping[str, Any]],
        results: Sequence[Mapping[str, Any]],
        outcome,
    ) -> list[dict[str, Any]]:
        rows = []
        for result in results:
            world_id = str(result["world"]["world_id"])
            actual = outcome(result)
            predicted = predictions[world_id]["answer"]
            rows.append(
                {
                    "actual": actual,
                    "correct": predicted == actual,
                    "predicted": predicted,
                    "world_id": world_id,
                }
            )
        return rows

    def _enhanced_collision_features(
        self,
        result: Mapping[str, Any],
        calibration_q: float,
    ) -> dict[str, float]:
        features = dict(result["world"]["features"])
        delay = int(features["delay_steps"])
        left = float(features["left_strength"])
        right = float(features["right_strength"])
        if delay == 0:
            resident_peak = min(64.0, calibration_q * left * left)
        else:
            resident_peak = float(result["observed"][f"h{delay}_top_q"])
        incoming_peak = min(64.0, calibration_q * right * right)
        return {
            **features,
            "incoming_peak_q": incoming_peak,
            "resident_peak_q": resident_peak,
        }

    def _register_surprise_assessment(
        self,
        resident: ResearchResidency,
        *,
        prediction: Mapping[str, Any],
        result: Mapping[str, Any],
    ) -> dict[str, Any]:
        actual = self._dominance(result)
        predicted = prediction["answer"]
        return resident.semantic(
            {
                "operation": "register",
                "operation_id": f"{self.run_id}:register:collision-surprise",
                "record_id": "physics:collision-surprise-assessment",
                "kind": "Assessment",
                "payload": {
                    "actual": {"dominance": actual},
                    "loss": 0.0 if actual == predicted else 1.0,
                    "predicted": {"dominance": predicted},
                    "purpose": "prediction",
                    "world_id": result["world"]["world_id"],
                },
                "status": "assessed",
                "epistemic_kind": "assessed",
                "support_roots": [result["source_revision_id"]],
            }
        )

    def _field_select_experiment(
        self,
        resident: ResearchResidency,
        assessment: Mapping[str, Any],
    ) -> dict[str, Any]:
        channels = _experiment_channels(self.curriculum)
        agenda = resident.semantic(
            {
                "operation": "autonomous-agenda",
                "operation_id": f"{self.run_id}:autonomous-physics-agenda",
                "goal": {"objective": "revise the failed physical representation"},
                "max_items": 4,
                "observation_channels": channels,
            }
        )
        perception = resident.semantic(
            {
                "operation": "autonomous-perception",
                "operation_id": f"{self.run_id}:autonomous-experiment-selection",
                "goal": {
                    "objective": {
                        "kind": "reduce-prediction-error",
                        "requested": ["dominance"],
                    },
                    "source": assessment["record"],
                },
                "channels": channels,
            }
        )
        selected = perception.get("observation_request")
        if not isinstance(selected, Mapping):
            raise AutonomousPhysicsResidencyError("field did not select a physics experiment")
        request = selected.get("request")
        if not isinstance(request, Mapping) or request.get("experiment_id") != "delayed-collision":
            raise AutonomousPhysicsResidencyError(
                f"field selected an unsupported experiment: {selected}"
            )
        return {"agenda": agenda, "perception": perception, "selected": dict(selected)}

    def _temporal_examples(
        self,
        results: Sequence[Mapping[str, Any]],
        *,
        revision: int,
    ) -> list[dict[str, Any]]:
        rows = []
        for result in results:
            if revision == 1:
                first = float(result["observed"]["h1_top_q"])
                second = float(result["observed"]["h8_top_q"])
                outcome = self._direction(
                    float(result["observed"]["h8_top_q"]),
                    float(result["observed"]["h32_top_q"]),
                )
            else:
                first = float(result["observed"]["h8_top_q"])
                second = float(result["observed"]["h32_top_q"])
                outcome = self._direction(
                    float(result["observed"]["h32_top_q"]),
                    float(result["observed"]["h128_top_q"]),
                )
            rows.append(
                {
                    "example_id": f"{result['world']['world_id']}:temporal-v{revision}",
                    "features": {"earlier_peak": first, "later_peak": second},
                    "outcome": outcome,
                    "source_revision_id": result.get("source_revision_id"),
                }
            )
        return rows

    def _restart_probe(
        self,
        resident: ResearchResidency,
    ) -> tuple[dict[str, Any], str]:
        before = {
            "experiment_languages": {
                generation: self._invoke_experiment_language(
                    resident,
                    language_id=language_id,
                    operation_name=f"restart:before:{generation}",
                    variant="transfer",
                )
                for generation, language_id in (
                    ("generation_1", EXPERIMENT_LANGUAGE_GENERATION_1_ID),
                    ("generation_2", EXPERIMENT_LANGUAGE_GENERATION_2_ID),
                    ("generation_3", EXPERIMENT_LANGUAGE_GENERATION_3_ID),
                )
            },
            "research_program": self._query_research_program(
                resident,
                operation_name="restart:before",
            ),
            "representation": self._query_representation(
                resident,
                operation_name="restart:before",
                representation_id=COMPOSITION_REPRESENTATION_ID,
                features={"first_charge": 3.0, "second_charge": 3.0},
            ),
        }
        return before, resident.inspect()["field_state_sha256"]

    def _finish_restart_probe(
        self,
        before: Mapping[str, Any],
        field_sha256: str,
    ) -> tuple[dict[str, Any], ResearchResidency]:
        resident = self._open_resident()
        reopened_sha256 = resident.inspect()["field_state_sha256"]
        after_representation = self._query_representation(
            resident,
            operation_name="restart:after",
            representation_id=COMPOSITION_REPRESENTATION_ID,
            features={"first_charge": 3.0, "second_charge": 3.0},
        )
        after_languages = {
            generation: self._invoke_experiment_language(
                resident,
                language_id=language_id,
                operation_name=f"restart:after:{generation}",
                variant="transfer",
            )
            for generation, language_id in (
                ("generation_1", EXPERIMENT_LANGUAGE_GENERATION_1_ID),
                ("generation_2", EXPERIMENT_LANGUAGE_GENERATION_2_ID),
                ("generation_3", EXPERIMENT_LANGUAGE_GENERATION_3_ID),
            )
        }
        after_research_program = self._query_research_program(
            resident,
            operation_name="restart:after",
        )
        before_representation = before["representation"]
        before_languages = before["experiment_languages"]
        languages_preserved = all(
            before_language["status"] == "supported"
            and before_language["world"] == after_languages[generation]["world"]
            and before_language["proposal_sha256"]
            == after_languages[generation]["proposal_sha256"]
            for generation, before_language in before_languages.items()
        )
        return (
            {
                "constructor_preserved": (
                    before_languages["generation_3"]["constructor"]
                    == after_languages["generation_3"]["constructor"]
                ),
                "experiment_languages_after": after_languages,
                "experiment_languages_before": before_languages,
                "experiment_languages_preserved": languages_preserved,
                "research_program_after": after_research_program,
                "research_program_before": before["research_program"],
                "research_program_preserved": (
                    before["research_program"]["status"] == "supported"
                    and before["research_program"]["research"]
                    == after_research_program["research"]
                    and before["research_program"]["program"]
                    == after_research_program["program"]
                ),
                "field_sha256_after_reopen": reopened_sha256,
                "field_sha256_before_close": field_sha256,
                "prediction_after": after_representation["answer"],
                "prediction_before": before_representation["answer"],
                "prediction_preserved": (
                    before_representation["answer"]
                    == after_representation["answer"]
                ),
                "state_restored_exactly": reopened_sha256 == field_sha256,
            },
            resident,
        )

    def _lesion_probe(self) -> dict[str, Any]:
        lesion = open_research_residency(self.run_home / "lesion-resident")
        try:
            lesion.initialize(
                workspace=Path(__file__).resolve().parent,
                mission="Autonomous physics field-lesion control",
                work=[
                    {
                        "id": "field-lesion",
                        "summary": "Query physics without the learned field",
                        "request": {"kind": "field-lesion"},
                    }
                ],
            )
            representation = lesion.semantic(
                {
                    "operation": "query",
                    "operation_id": f"{self.run_id}:lesion:composition-query",
                    "query": {
                        "features": {
                            "first_charge": 3.0,
                            "second_charge": 3.0,
                        },
                        "kind": "representation",
                        "representation_id": COMPOSITION_REPRESENTATION_ID,
                    },
                }
            )
            languages = {
                generation: lesion.semantic(
                    {
                        "operation": "invoke-experiment-language",
                        "operation_id": (
                            f"{self.run_id}:lesion:"
                            f"experiment-language-query:{generation}"
                        ),
                        "language_id": language_id,
                        "variant": "transfer",
                    }
                )
                for generation, language_id in (
                    ("generation_1", EXPERIMENT_LANGUAGE_GENERATION_1_ID),
                    ("generation_2", EXPERIMENT_LANGUAGE_GENERATION_2_ID),
                    ("generation_3", EXPERIMENT_LANGUAGE_GENERATION_3_ID),
                )
            }
            research_program = lesion.semantic(
                {
                    "operation": "query-research-program",
                    "operation_id": (
                        f"{self.run_id}:lesion:research-program-query"
                    ),
                    "program_id": RESEARCH_PROGRAM_ID,
                }
            )
            return {
                "answer": representation.get("answer"),
                "experiment_languages_available": {
                    generation: language["status"] == "supported"
                    for generation, language in languages.items()
                },
                "experiment_language_statuses": {
                    generation: language["status"]
                    for generation, language in languages.items()
                },
                "learned_representation_available": (
                    representation["status"] == "supported"
                ),
                "limitations": representation.get("limitations", []),
                "status": representation["status"],
                "research_program_available": (
                    research_program["status"] == "supported"
                ),
                "research_program_status": research_program["status"],
            }
        finally:
            lesion.close()

    @staticmethod
    def _compact(result: Mapping[str, Any]) -> dict[str, Any]:
        return {
            key: result[key]
            for key in (
                "acknowledgment",
                "evidence_sha256",
                "observed",
                "source_revision_id",
                "view",
                "world",
            )
            if key in result
        }

    def run(self) -> dict[str, Any]:
        if self.receipt_path.exists():
            receipt = _validated_receipt(self.receipt_path)
            if (
                receipt.get("run_id") != self.run_id
                or receipt.get("manifest_sha256")
                != hashlib.sha256(self.manifest_bytes).hexdigest()
                or receipt.get("sealed_sha256") != self.manifest["sealed_sha256"]
            ):
                raise AutonomousPhysicsResidencyError(
                    "existing receipt belongs to a different autonomous physics contract"
                )
            return receipt

        self.run_home.mkdir(parents=True, exist_ok=True)
        _commit_bytes(self.run_home / "manifest.json", self.manifest_bytes)
        resident = self._open_resident()
        try:
            manifest_root = self._archive(
                resident,
                source_id="manifest",
                content=self.manifest_bytes,
                category="sealed-autonomous-physics-curriculum",
                context={
                    "manifest_sha256": hashlib.sha256(self.manifest_bytes).hexdigest(),
                    "sealed_sha256": self.manifest["sealed_sha256"],
                },
            )

            calibration = self._run_and_admit(resident, (self.curriculum.calibration,))[0]
            calibration_q = float(calibration["observed"]["h8_top_q"])

            composition_training = self._run_and_admit(
                resident, self.curriculum.composition_training
            )
            composition_holdout = self._run_and_admit(
                resident, self.curriculum.composition_holdout
            )
            composition_learning = self._learn_representation(
                resident,
                operation_name="composition-v1",
                representation_id=COMPOSITION_REPRESENTATION_ID,
                target="late-global-pulse-sign",
                training=self._base_examples(composition_training, self._global_sign),
                holdout=self._base_examples(composition_holdout, self._global_sign),
            )
            composition_predictions = self._predict_static_transfers(
                resident,
                representation_id=COMPOSITION_REPRESENTATION_ID,
                prefix="composition-transfer",
                worlds=self.curriculum.composition_transfer,
            )
            composition_transfer = self._run_and_admit(
                resident, self.curriculum.composition_transfer
            )
            composition_assessments = self._assess_predictions(
                composition_predictions, composition_transfer, self._global_sign
            )

            collision_training = self._run_and_admit(
                resident, self.curriculum.collision_training
            )
            collision_holdout = self._run_and_admit(
                resident, self.curriculum.collision_holdout
            )
            collision_learning_v1 = self._learn_representation(
                resident,
                operation_name="collision-v1",
                representation_id=COLLISION_REPRESENTATION_ID,
                target="spatial-dominance",
                training=self._base_examples(collision_training, self._dominance),
                holdout=self._base_examples(collision_holdout, self._dominance),
            )
            collision_predictions = self._predict_static_transfers(
                resident,
                representation_id=COLLISION_REPRESENTATION_ID,
                prefix="collision-transfer",
                worlds=self.curriculum.collision_transfer,
            )
            collision_transfer = self._run_and_admit(
                resident, self.curriculum.collision_transfer
            )
            collision_assessments = self._assess_predictions(
                collision_predictions, collision_transfer, self._dominance
            )

            surprise_prediction = self._query_representation(
                resident,
                operation_name="collision-surprise",
                representation_id=COLLISION_REPRESENTATION_ID,
                features=self.curriculum.collision_surprise.feature_values,
            )
            surprise_precommit = canonical_json_bytes(
                {
                    "field_state_sha256": resident.inspect()["field_state_sha256"],
                    "prediction": surprise_prediction,
                    "sealed_sha256": self.manifest["sealed_sha256"],
                    "world_id": self.curriculum.collision_surprise.world_id,
                }
            )
            surprise_precommit_root = self._archive(
                resident,
                source_id="precommit:collision-surprise",
                content=surprise_precommit,
                category="prospective-representation-precommit",
                context={"sha256": hashlib.sha256(surprise_precommit).hexdigest()},
            )
            surprise = self._admit_world(
                resident, self._execute_world(self.curriculum.collision_surprise)
            )
            surprise_assessment = self._register_surprise_assessment(
                resident,
                prediction=surprise_prediction,
                result=surprise,
            )
            experiment_selection = self._field_select_experiment(
                resident, surprise_assessment
            )

            delayed_training = self._run_and_admit(
                resident, self.curriculum.delayed_training
            )
            delayed_holdout = self._run_and_admit(
                resident, self.curriculum.delayed_holdout
            )
            revision_training_results = [
                *collision_training,
                *collision_holdout,
                surprise,
                *delayed_training,
            ]
            revision_training = [
                {
                    "example_id": result["world"]["world_id"],
                    "features": self._enhanced_collision_features(result, calibration_q),
                    "outcome": self._dominance(result),
                    "source_revision_id": result["source_revision_id"],
                }
                for result in revision_training_results
            ]
            revision_holdout = [
                {
                    "example_id": result["world"]["world_id"],
                    "features": self._enhanced_collision_features(result, calibration_q),
                    "outcome": self._dominance(result),
                    "source_revision_id": result["source_revision_id"],
                }
                for result in delayed_holdout
            ]
            collision_learning_v2 = self._learn_representation(
                resident,
                operation_name="collision-v2",
                representation_id=COLLISION_REPRESENTATION_ID,
                target="spatiotemporal-dominance",
                training=revision_training,
                holdout=revision_holdout,
            )

            delayed_transfer = []
            delayed_predictions: dict[str, dict[str, Any]] = {}
            for world in self.curriculum.delayed_transfer:
                executed = self._execute_world(world)
                partial = self._admit_world(
                    resident,
                    executed,
                    horizons=(world.horizons[0],),
                    suffix="pre-outcome",
                )
                enhanced = self._enhanced_collision_features(partial, calibration_q)
                delayed_predictions[world.world_id] = self._query_representation(
                    resident,
                    operation_name=f"delayed-transfer:{world.world_id}",
                    representation_id=COLLISION_REPRESENTATION_ID,
                    features=enhanced,
                )
                delayed_transfer.append(self._admit_world(resident, executed))
            delayed_assessments = self._assess_predictions(
                delayed_predictions, delayed_transfer, self._dominance
            )
            generated_experiment_generation_1 = (
                self._run_generated_experiment_language(
                    resident,
                    generation_tag="generation-1",
                    language_id=EXPERIMENT_LANGUAGE_GENERATION_1_ID,
                    manifest_root=manifest_root,
                )
            )
            constructor_revision_generation_1 = (
                self._revise_experiment_constructor(
                    resident,
                    language_id=EXPERIMENT_LANGUAGE_GENERATION_1_ID,
                )
            )
            generated_experiment_generation_2 = (
                self._run_generated_experiment_language(
                    resident,
                    generation_tag="generation-2",
                    language_id=EXPERIMENT_LANGUAGE_GENERATION_2_ID,
                    manifest_root=manifest_root,
                    parent_language_id=(
                        EXPERIMENT_LANGUAGE_GENERATION_1_ID
                    ),
                )
            )
            constructor_revision_generation_2 = (
                self._revise_experiment_constructor(
                    resident,
                    language_id=EXPERIMENT_LANGUAGE_GENERATION_2_ID,
                )
            )
            research_program_synthesis = (
                self._synthesize_research_program(resident)
            )
            research_authority_review = (
                self._review_research_authority_request(
                    research_program_synthesis
                )
            )
            research_authority_assessment = (
                self._record_research_authority(
                    resident, research_authority_review
                )
            )
            generated_experiment_generation_3 = (
                self._run_generated_experiment_language(
                    resident,
                    generation_tag="generation-3",
                    language_id=EXPERIMENT_LANGUAGE_GENERATION_3_ID,
                    manifest_root=manifest_root,
                    parent_language_id=(
                        EXPERIMENT_LANGUAGE_GENERATION_2_ID
                    ),
                    research_program_id=RESEARCH_PROGRAM_ID,
                    research_stage_id=RESEARCH_STAGE_GENERATION_3_ID,
                )
            )
            constructor_revision_generation_3 = (
                self._revise_experiment_constructor(
                    resident,
                    language_id=EXPERIMENT_LANGUAGE_GENERATION_3_ID,
                )
            )
            research_program_advance = self._advance_research_program(
                resident
            )
            mechanism_experiment = self._run_mechanism_experiment(resident)
            distributed_phase_flow = self._run_distributed_phase_flow(
                resident
            )
            phase_current_topology = self._run_phase_current_topology(
                resident
            )

            clamp_training = self._run_and_admit(resident, self.curriculum.clamp_training)
            clamp_holdout = self._run_and_admit(resident, self.curriculum.clamp_holdout)
            clamp_learning = self._learn_representation(
                resident,
                operation_name="clamp-v1",
                representation_id=CLAMP_REPRESENTATION_ID,
                target="nonlinear-clamp-regime",
                training=self._base_examples(clamp_training, self._clamp_regime),
                holdout=self._base_examples(clamp_holdout, self._clamp_regime),
            )
            temporal_learning_v1 = self._learn_representation(
                resident,
                operation_name="temporal-v1",
                representation_id=TEMPORAL_REPRESENTATION_ID,
                target="short-horizon-direction",
                training=self._temporal_examples(clamp_training, revision=1),
                holdout=self._temporal_examples(clamp_holdout, revision=1),
            )
            temporal_learning_v2 = self._learn_representation(
                resident,
                operation_name="temporal-v2",
                representation_id=TEMPORAL_REPRESENTATION_ID,
                target="long-horizon-direction",
                training=self._temporal_examples(clamp_training, revision=2),
                holdout=self._temporal_examples(clamp_holdout, revision=2),
            )

            clamp_predictions = self._predict_static_transfers(
                resident,
                representation_id=CLAMP_REPRESENTATION_ID,
                prefix="clamp-transfer",
                worlds=self.curriculum.clamp_transfer,
            )
            clamp_transfer = []
            temporal_predictions: dict[str, dict[str, Any]] = {}
            for world in self.curriculum.clamp_transfer:
                executed = self._execute_world(world)
                partial = self._admit_world(
                    resident,
                    executed,
                    horizons=(1, 8, 32),
                    suffix="pre-h128",
                )
                temporal_predictions[world.world_id] = self._query_representation(
                    resident,
                    operation_name=f"temporal-transfer:{world.world_id}",
                    representation_id=TEMPORAL_REPRESENTATION_ID,
                    features={
                        "earlier_peak": float(partial["observed"]["h8_top_q"]),
                        "later_peak": float(partial["observed"]["h32_top_q"]),
                    },
                )
                clamp_transfer.append(self._admit_world(resident, executed))
            clamp_assessments = self._assess_predictions(
                clamp_predictions, clamp_transfer, self._clamp_regime
            )
            temporal_actual = {
                result["world"]["world_id"]: self._direction(
                    float(result["observed"]["h32_top_q"]),
                    float(result["observed"]["h128_top_q"]),
                )
                for result in clamp_transfer
            }
            temporal_assessments = [
                {
                    "actual": temporal_actual[world_id],
                    "correct": prediction["answer"] == temporal_actual[world_id],
                    "predicted": prediction["answer"],
                    "world_id": world_id,
                }
                for world_id, prediction in sorted(temporal_predictions.items())
            ]

            known_results = {
                result["world"]["world_id"]: result
                for result in (*composition_transfer, *collision_transfer)
            }
            repeat_results = self._run_and_admit(resident, self.curriculum.repeats)
            repeatability = [
                {
                    "exact_observations": (
                        result["observed"]
                        == known_results[result["world"]["source_of"]]["observed"]
                    ),
                    "repeat_world_id": result["world"]["world_id"],
                    "source_world_id": result["world"]["source_of"],
                }
                for result in repeat_results
            ]
            replay_world = self.curriculum.repeats[0]
            replay_operation_id = (
                f"{self.run_id}:world:{replay_world.world_id}"
            )
            journal_home = self.run_home / "world-journal"
            journal_path = journal_home / hashlib.sha256(
                replay_operation_id.encode("utf-8")
            ).hexdigest()
            journal_entries_before_replay = sum(
                path.is_file() for path in journal_home.iterdir()
            )
            execute_count_before_replay = self.controller.execute_count
            replay_ack = self.controller.execute_scheduled_world(
                operation_id=replay_operation_id,
                segments=[
                    segment.as_dict() for segment in replay_world.segments
                ],
                projection_k=8,
            )
            execute_count_after_replay = self.controller.execute_count
            journal_entries_after_replay = sum(
                path.is_file() for path in journal_home.iterdir()
            )
            journal_bytes = journal_path.read_bytes()
            journal_record = json.loads(journal_bytes)
            original_acknowledgment_sha256 = sha256_value(
                repeat_results[0]["acknowledgment"]
            )
            replay_acknowledgment_sha256 = sha256_value(
                replay_ack.as_dict()
            )
            journal_replay = {
                "acknowledgment_sha256": journal_record[
                    "acknowledgment_sha256"
                ],
                "exact_acknowledgment": (
                    replay_acknowledgment_sha256
                    == original_acknowledgment_sha256
                    == journal_record["acknowledgment_sha256"]
                ),
                "execute_count_after": execute_count_after_replay,
                "execute_count_before": execute_count_before_replay,
                "execute_count_unchanged": (
                    execute_count_after_replay
                    == execute_count_before_replay
                ),
                "journal_entries_after": journal_entries_after_replay,
                "journal_entries_before": journal_entries_before_replay,
                "journal_entries_unchanged": (
                    journal_entries_after_replay
                    == journal_entries_before_replay
                ),
                "journal_record_sha256": hashlib.sha256(
                    journal_bytes
                ).hexdigest(),
                "operation_id": replay_operation_id,
                "operation_path_sha256": journal_path.name,
                "original_acknowledgment_sha256": (
                    original_acknowledgment_sha256
                ),
                "replay_acknowledgment_sha256": (
                    replay_acknowledgment_sha256
                ),
                "request_sha256": journal_record["request_sha256"],
            }

            before_restart, field_sha256 = self._restart_probe(resident)
        finally:
            resident.close()

        restart, resident = self._finish_restart_probe(before_restart, field_sha256)
        try:
            final_field_sha256 = resident.inspect()["field_state_sha256"]
        finally:
            resident.close()
        lesion = self._lesion_probe()

        prediction_groups = {
            "clamp": clamp_assessments,
            "collision": collision_assessments,
            "composition": composition_assessments,
            "delayed_collision": delayed_assessments,
            "temporal": temporal_assessments,
        }
        representation_learning = {
            "clamp": clamp_learning,
            "collision_v1": collision_learning_v1,
            "collision_v2": collision_learning_v2,
            "composition": composition_learning,
            "temporal_v1": temporal_learning_v1,
            "temporal_v2": temporal_learning_v2,
        }
        surprise_actual = self._dominance(surprise)
        surprise_loss = 0.0 if surprise_prediction["answer"] == surprise_actual else 1.0
        generated_experiments = {
            "generation_1": generated_experiment_generation_1,
            "generation_2": generated_experiment_generation_2,
            "generation_3": generated_experiment_generation_3,
        }
        generated_world_count = sum(
            row is not None
            for result in generated_experiments.values()
            for row in (
                result["trial"],
                result["transfer"],
                result["repeat"],
            )
        )
        generated_proposals = {
            name: result["proposal"]
            for name, result in generated_experiments.items()
        }
        generated_horizon = max(
            sum(
                int(segment["steps"])
                for segment in proposal[world_name]["segments"]
            )
            for proposal in generated_proposals.values()
            for world_name in ("trial_world", "transfer_world")
        )
        generated_checks = {
            name: {
                "authorized": result["authorization"]["authorized"],
                "earned": result["trial_assessment"]["earned"],
                "field_originated": (
                    result["proposal"]["candidate_origin"]
                    == "field-generated"
                    and str(result["proposal"]["candidate_id"]).startswith(
                        "auto:experiment-language:"
                    )
                ),
                "repeat_exact": result["repeat_exact"],
                "transfer_correct": (
                    isinstance(result["transfer_assessment"], Mapping)
                    and result["transfer_assessment"]["correct"]
                ),
            }
            for name, result in generated_experiments.items()
        }
        generation_1_fingerprint = generated_proposals["generation_1"][
            "construction"
        ]["schedule_fingerprint"]
        generation_2_fingerprint = generated_proposals["generation_2"][
            "construction"
        ]["schedule_fingerprint"]
        generation_3_fingerprint = generated_proposals["generation_3"][
            "construction"
        ]["schedule_fingerprint"]
        summary = {
            "all_transfer_predictions_correct": all(
                row["correct"]
                for rows in prediction_groups.values()
                for row in rows
            ),
            "autonomous_experiment": experiment_selection["selected"][
                "request"
            ]["experiment_id"],
            "candidate_families_supplied": (
                any(
                    result["candidate_families_supplied"]
                    for result in generated_experiments.values()
                )
                or mechanism_experiment["candidate_families_supplied"]
                or distributed_phase_flow["candidate_families_supplied"]
                or phase_current_topology["candidate_families_supplied"]
            ),
            "collision_representation_revised": (
                collision_learning_v2["representation"]["content_version"] == 2
            ),
            "constructor_generation": constructor_revision_generation_3[
                "generation"
            ],
            "constructor_history_count": len(
                constructor_revision_generation_3[
                    "successful_distinctions"
                ]
            ),
            "constructor_revised": (
                constructor_revision_generation_1["constructor"][
                    "content_version"
                ]
                == 2
                and constructor_revision_generation_2["constructor"][
                    "content_version"
                ]
                == 3
                and constructor_revision_generation_3["constructor"][
                    "content_version"
                ]
                == 4
                and constructor_revision_generation_3["generation"] == 4
            ),
            "executed_worlds": (
                len(self.curriculum.all_worlds)
                + generated_world_count
                + len(mechanism_experiment["arms"])
                + len(distributed_phase_flow["arms"])
                + len(phase_current_topology["arms"])
            ),
            "experiment_generations": generated_checks,
            "field_lesion_removed_experiment_languages": not any(
                lesion["experiment_languages_available"].values()
            ),
            "field_lesion_removed_representations": not lesion[
                "learned_representation_available"
            ],
            "field_lesion_removed_research_program": not lesion[
                "research_program_available"
            ],
            "generation_2_distinction": generated_proposals["generation_2"][
                "trial_world"
            ]["distinction"]["name"],
            "generation_2_novel": (
                generation_2_fingerprint != generation_1_fingerprint
                and generation_1_fingerprint
                in constructor_revision_generation_1[
                    "tested_schedule_fingerprints"
                ]
            ),
            "generation_2_schedule_fingerprint": generation_2_fingerprint,
            "generation_3_distinction": generated_proposals["generation_3"][
                "trial_world"
            ]["distinction"]["name"],
            "generation_3_novel": (
                generation_3_fingerprint
                not in {
                    generation_1_fingerprint,
                    generation_2_fingerprint,
                }
                and {
                    generation_1_fingerprint,
                    generation_2_fingerprint,
                    generation_3_fingerprint,
                }
                <= set(
                    constructor_revision_generation_3[
                        "tested_schedule_fingerprints"
                    ]
                )
            ),
            "generation_3_schedule_fingerprint": generation_3_fingerprint,
            "journal_replay_exact": (
                journal_replay["exact_acknowledgment"]
                and journal_replay["execute_count_unchanged"]
                and journal_replay["journal_entries_unchanged"]
            ),
            "longest_horizon": max(
                generated_horizon,
                max(
                    world.horizons[-1]
                    for world in self.curriculum.all_worlds
                ),
                max(
                    int(arm["world"]["horizons"][-1])
                    for arm in mechanism_experiment["arms"].values()
                ),
                max(
                    int(arm["world"]["horizons"][-1])
                    for arm in distributed_phase_flow["arms"].values()
                ),
                max(
                    int(arm["world"]["horizons"][-1])
                    for arm in phase_current_topology["arms"].values()
                ),
            ),
            "representation_families": {
                name: result["selected_candidate"]
                for name, result in representation_learning.items()
            },
            "representation_versions": {
                name: result["representation"]["content_version"]
                for name, result in representation_learning.items()
            },
            "research_authority_boundary_preserved": (
                research_authority_review["authorized"] is True
                and research_authority_review["decision"]
                == "authorized-existing-primitive"
                and research_authority_review["grant"]
                == {
                    "field": "top_phase_current_x",
                    "scope": "top-coherence-cell",
                }
                and research_authority_review["checks"]["grammar_unchanged"]
                and distributed_phase_flow["authority_review"]["authorized"]
                is True
                and distributed_phase_flow["authority_review"]["grant"]
                == {
                    "field": "phase_profile_x_16",
                    "scope": "sixteen-x-slabs-full-yz",
                }
                and distributed_phase_flow["authority_assessment"]["status"]
                == "supported"
                and phase_current_topology["authority_review"]["authorized"]
                is True
                and phase_current_topology["authority_review"]["grant"]
                == {
                    "field": "phase_winding_native_3x3",
                    "scope": (
                        "four-cubed-periodic-phase-current-lattice-plus-"
                        "native-closed-loops"
                    ),
                }
                and phase_current_topology["authority_assessment"]["status"]
                == "supported"
            ),
            "research_authority_requested": (
                research_program_synthesis["authority_request"][
                    "primitive"
                ]["field"]
                == "top_phase_current_x"
            ),
            "research_program_active": (
                research_program_advance["status"] == "supported"
                and mechanism_experiment["assessment"]["status"]
                == "supported"
                and mechanism_experiment["assessment"]["program_state"]
                == "resolved"
                and distributed_phase_flow["assessment"]["status"]
                == "supported"
                and distributed_phase_flow["assessment"]["program_state"]
                == "resolved"
                and phase_current_topology["assessment"]["status"]
                == "supported"
                and phase_current_topology["assessment"]["program_state"]
                == "resolved"
            ),
            "research_program_completed_discoveries": len(
                research_program_advance["discovery_history"]
            ),
            "research_program_uncertainty": (
                research_program_synthesis["uncertainty"][
                    "uncertainty_id"
                ]
            ),
            "mechanism_authorized": mechanism_experiment["authorization"][
                "authorized"
            ],
            "mechanism_candidate_field_originated": (
                mechanism_experiment["candidate_families_supplied"] is False
                and str(
                    mechanism_experiment["proposal"]["candidate_id"]
                ).startswith("auto:mechanism-experiment:")
            ),
            "mechanism_scope": mechanism_experiment["assessment"]["scope"],
            "mechanism_verdict": mechanism_experiment["assessment"][
                "verdict"
            ],
            "distributed_flow_authorized": distributed_phase_flow[
                "authorization"
            ]["authorized"],
            "distributed_flow_candidate_field_originated": (
                distributed_phase_flow["candidate_families_supplied"] is False
                and str(
                    distributed_phase_flow["proposal"]["candidate_id"]
                ).startswith("auto:distributed-phase-flow:")
            ),
            "distributed_flow_primary_mechanism": distributed_phase_flow[
                "assessment"
            ]["metrics"]["primary_mechanism"],
            "distributed_flow_scope": distributed_phase_flow["assessment"][
                "scope"
            ],
            "distributed_flow_verdict": distributed_phase_flow["assessment"][
                "verdict"
            ],
            "phase_topology_authorized": phase_current_topology[
                "authorization"
            ]["authorized"],
            "phase_topology_candidate_field_originated": (
                phase_current_topology["candidate_families_supplied"] is False
                and str(
                    phase_current_topology["proposal"]["candidate_id"]
                ).startswith("auto:phase-current-topology:")
            ),
            "phase_topology_material_current": phase_current_topology[
                "assessment"
            ]["metrics"]["material_current"],
            "phase_topology_mirror_relative_error": phase_current_topology[
                "assessment"
            ]["metrics"]["mirror_relative_error"],
            "phase_topology_normalized_curl": phase_current_topology[
                "assessment"
            ]["metrics"]["normalized_curl"],
            "phase_topology_native_flow_detected": phase_current_topology[
                "assessment"
            ]["metrics"]["native_flow_detected"],
            "phase_topology_native_mirror_relative_error": phase_current_topology[
                "assessment"
            ]["metrics"]["native_mirror_relative_error"],
            "phase_topology_native_readout_available": phase_current_topology[
                "assessment"
            ]["metrics"]["native_readout_available"],
            "phase_topology_native_verdict": phase_current_topology[
                "assessment"
            ]["metrics"]["native_verdict"],
            "phase_topology_native_winding_detected": phase_current_topology[
                "assessment"
            ]["metrics"]["native_winding_detected"],
            "phase_topology_scope": phase_current_topology["assessment"][
                "scope"
            ],
            "phase_topology_verdict": phase_current_topology["assessment"][
                "verdict"
            ],
            "restart_exact": (
                restart["state_restored_exactly"]
                and restart["prediction_preserved"]
                and restart["experiment_languages_preserved"]
                and restart["constructor_preserved"]
                and restart["research_program_preserved"]
            ),
            "scheduled_repeat_pairs": len(repeatability) + sum(
                result["repeat"] is not None
                for result in generated_experiments.values()
            ),
            "scheduled_repeats_exact": (
                all(row["exact_observations"] for row in repeatability)
                and all(
                    result["repeat_exact"]
                    for result in generated_experiments.values()
                )
            ),
            "surprise_prediction_failed": surprise_loss > 0.0,
            "transfer_predictions": {
                name: {
                    "attempted": len(rows),
                    "correct": sum(row["correct"] for row in rows),
                }
                for name, rows in prediction_groups.items()
            },
        }
        supported = (
            summary["all_transfer_predictions_correct"]
            and summary["autonomous_experiment"] == "delayed-collision"
            and summary["candidate_families_supplied"] is False
            and summary["collision_representation_revised"]
            and summary["constructor_revised"]
            and summary["generation_2_novel"]
            and summary["generation_3_novel"]
            and summary["constructor_history_count"] == 3
            and summary["research_authority_boundary_preserved"]
            and summary["research_authority_requested"]
            and summary["research_program_active"]
            and summary["research_program_completed_discoveries"] == 3
            and summary["research_program_uncertainty"]
            == "trajectory-transport-mechanism"
            and summary["mechanism_authorized"]
            and summary["mechanism_candidate_field_originated"]
            and summary["mechanism_verdict"]
            in {
                "local-rewriting-at-peak",
                "transport-coupled-at-peak",
            }
            and summary["distributed_flow_authorized"]
            and summary["distributed_flow_candidate_field_originated"]
            and summary["distributed_flow_verdict"]
            in {
                "advective-transport",
                "local-nucleation",
                "local-nucleation-with-remote-persistence",
                "remote-conditioning",
            }
            and summary["phase_topology_authorized"]
            and summary["phase_topology_native_readout_available"]
            and summary["phase_topology_candidate_field_originated"]
            and summary["phase_topology_verdict"]
            in {
                "vortical-circulation",
                "recirculating-return-flow",
                "delayed-three-dimensional-transport",
                "static-remote-persistence",
            }
            and all(
                all(checks.values())
                for checks in summary["experiment_generations"].values()
            )
            and summary["field_lesion_removed_experiment_languages"]
            and summary["field_lesion_removed_representations"]
            and summary["field_lesion_removed_research_program"]
            and summary["journal_replay_exact"]
            and summary["restart_exact"]
            and summary["scheduled_repeats_exact"]
            and summary["surprise_prediction_failed"]
            and all(
                str(value).startswith("auto:")
                for value in summary["representation_families"].values()
            )
        )
        receipt: dict[str, Any] = {
            "schema": SCHEMA,
            "run_id": self.run_id,
            "status": "supported" if supported else "measured-boundary",
            "manifest_sha256": hashlib.sha256(self.manifest_bytes).hexdigest(),
            "manifest_source_revision_id": manifest_root,
            "sealed_sha256": self.manifest["sealed_sha256"],
            "calibration": self._compact(calibration),
            "composition": {
                "assessments": composition_assessments,
                "holdout": [self._compact(row) for row in composition_holdout],
                "learning": composition_learning,
                "predictions": composition_predictions,
                "training": [self._compact(row) for row in composition_training],
                "transfer": [self._compact(row) for row in composition_transfer],
            },
            "collision": {
                "assessments": collision_assessments,
                "delayed_assessments": delayed_assessments,
                "delayed_holdout": [self._compact(row) for row in delayed_holdout],
                "delayed_predictions": delayed_predictions,
                "delayed_training": [self._compact(row) for row in delayed_training],
                "delayed_transfer": [self._compact(row) for row in delayed_transfer],
                "experiment_selection": experiment_selection,
                "holdout": [self._compact(row) for row in collision_holdout],
                "learning_v1": collision_learning_v1,
                "learning_v2": collision_learning_v2,
                "predictions": collision_predictions,
                "surprise": self._compact(surprise),
                "surprise_actual": surprise_actual,
                "surprise_assessment": surprise_assessment,
                "surprise_precommit_source_revision_id": surprise_precommit_root,
                "surprise_prediction": surprise_prediction,
                "training": [self._compact(row) for row in collision_training],
                "transfer": [self._compact(row) for row in collision_transfer],
            },
            "generated_experiment_languages": {
                "constructor_revisions": {
                    "after_generation_1": constructor_revision_generation_1,
                    "after_generation_2": constructor_revision_generation_2,
                    "after_generation_3": constructor_revision_generation_3,
                },
                "generations": {
                    name: {
                        "authorization": result["authorization"],
                        "candidate_families_supplied": result[
                            "candidate_families_supplied"
                        ],
                        "precommit": result["precommit"],
                        "precommit_source_revision_id": result[
                            "precommit_source_revision_id"
                        ],
                        "proposal": result["proposal"],
                        "repeat": (
                            None
                            if result["repeat"] is None
                            else self._compact(result["repeat"])
                        ),
                        "repeat_assessment": result["repeat_assessment"],
                        "repeat_exact": result["repeat_exact"],
                        "synthesis": result["synthesis"],
                        "transfer": (
                            None
                            if result["transfer"] is None
                            else self._compact(result["transfer"])
                        ),
                        "transfer_assessment": result[
                            "transfer_assessment"
                        ],
                        "transfer_invocation": result[
                            "transfer_invocation"
                        ],
                        "trial": self._compact(result["trial"]),
                        "trial_assessment": result["trial_assessment"],
                    }
                    for name, result in generated_experiments.items()
                },
            },
            "research_program": {
                "advance": research_program_advance,
                "authority_assessment": research_authority_assessment,
                "authority_review": research_authority_review,
                "synthesis": research_program_synthesis,
                "mechanism_experiment": {
                    "arms": {
                        variant: self._compact(arm)
                        for variant, arm in mechanism_experiment["arms"].items()
                    },
                    "assessment": mechanism_experiment["assessment"],
                    "authorization": mechanism_experiment["authorization"],
                    "candidate_families_supplied": mechanism_experiment[
                        "candidate_families_supplied"
                    ],
                    "design": mechanism_experiment["design"],
                    "precommit": mechanism_experiment["precommit"],
                    "precommit_source_revision_id": mechanism_experiment[
                        "precommit_source_revision_id"
                    ],
                    "proposal": mechanism_experiment["proposal"],
                },
                "distributed_phase_flow": {
                    "arms": {
                        variant: self._compact(arm)
                        for variant, arm in distributed_phase_flow["arms"].items()
                    },
                    "assessment": distributed_phase_flow["assessment"],
                    "authority_assessment": distributed_phase_flow[
                        "authority_assessment"
                    ],
                    "authority_review": distributed_phase_flow[
                        "authority_review"
                    ],
                    "authorization": distributed_phase_flow["authorization"],
                    "candidate_families_supplied": distributed_phase_flow[
                        "candidate_families_supplied"
                    ],
                    "continuation": distributed_phase_flow["continuation"],
                    "design": distributed_phase_flow["design"],
                    "precommit": distributed_phase_flow["precommit"],
                    "precommit_source_revision_id": distributed_phase_flow[
                        "precommit_source_revision_id"
                    ],
                    "proposal": distributed_phase_flow["proposal"],
                },
                "phase_current_topology": {
                    "arms": {
                        variant: self._compact(arm)
                        for variant, arm in phase_current_topology["arms"].items()
                    },
                    "assessment": phase_current_topology["assessment"],
                    "authority_assessment": phase_current_topology[
                        "authority_assessment"
                    ],
                    "authority_review": phase_current_topology[
                        "authority_review"
                    ],
                    "authorization": phase_current_topology["authorization"],
                    "candidate_families_supplied": phase_current_topology[
                        "candidate_families_supplied"
                    ],
                    "continuation": phase_current_topology["continuation"],
                    "design": phase_current_topology["design"],
                    "precommit": phase_current_topology["precommit"],
                    "precommit_source_revision_id": phase_current_topology[
                        "precommit_source_revision_id"
                    ],
                    "proposal": phase_current_topology["proposal"],
                },
            },
            "nonlinear_temporal": {
                "clamp_assessments": clamp_assessments,
                "clamp_holdout": [self._compact(row) for row in clamp_holdout],
                "clamp_learning": clamp_learning,
                "clamp_predictions": clamp_predictions,
                "clamp_training": [self._compact(row) for row in clamp_training],
                "clamp_transfer": [self._compact(row) for row in clamp_transfer],
                "temporal_assessments": temporal_assessments,
                "temporal_learning_v1": temporal_learning_v1,
                "temporal_learning_v2": temporal_learning_v2,
                "temporal_predictions": temporal_predictions,
            },
            "repeatability": repeatability,
            "journal_replay": journal_replay,
            "restart": restart,
            "lesion": lesion,
            "final_field_state_sha256": final_field_sha256,
            "summary": summary,
            "digest_rule": {
                "algorithm": "sha256-canonical-json",
                "excluded_top_level_keys": ["body_sha256"],
            },
        }
        receipt["body_sha256"] = sha256_value(receipt)
        _commit_bytes(self.receipt_path, canonical_json_bytes(receipt))
        return receipt


def run_autonomous_physics_residency(
    run_home: Path,
    *,
    run_id: str,
    host: str = "127.0.0.1",
    port: int = 7599,
) -> dict[str, Any]:
    return AutonomousPhysicsResidency(
        run_home,
        run_id=run_id,
        host=host,
        port=port,
    ).run()


__all__ = [
    "AutonomousPhysicsCurriculum",
    "AutonomousPhysicsResidency",
    "AutonomousPhysicsResidencyError",
    "ScheduledPhysicsWorld",
    "ScheduledSegment",
    "build_autonomous_physics_curriculum",
    "build_autonomous_physics_manifest",
    "build_experiment_primitive_grammar",
    "run_autonomous_physics_residency",
]
