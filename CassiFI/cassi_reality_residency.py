from __future__ import annotations

"""Integrated field-owned learning campaign against fresh CassiCosmos worlds."""

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
from cassi_field_atlas import FieldIntelligenceError, canonical_json_bytes, sha256_value
from cassi_field_input import CODEC_JSON
from cassi_field_owner import SourceInput
from cassi_field_program import semantic_program_payload
from cassi_research_residency import (
    ResearchResidency,
    ResidencyError,
    open_research_residency,
)


SCHEMA = "cassifi.reality-residency-receipt.v1"
MANIFEST_SCHEMA = "cassifi.reality-residency-manifest.v1"
WORLD_EVIDENCE_SCHEMA = "cassifi.reality-world-evidence.v1"
LOCALIZATION_MECHANISM_ID = "reality:localization-law"
GLOBAL_RESPONSE_MECHANISM_ID = "reality:global-response-law"
HORIZONS = (1, 8, 32)
GRID_N = 64
DT = 0.005
OMEGA2 = 20.0
PHI = (1.0 + math.sqrt(5.0)) / 2.0
LOCALIZATION_TOLERANCE = 0.09
GLOBAL_RESPONSE_TOLERANCE = 2.0e-5
_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class RealityResidencyError(RuntimeError):
    """The integrated campaign cannot preserve its declared evidence boundary."""


@dataclass(frozen=True, slots=True)
class Deposit:
    x: float
    y: float
    z: float
    cy: float
    ci: float
    sigma: float = 1.0

    def as_dict(self) -> dict[str, float]:
        values = {
            "x": float(self.x),
            "y": float(self.y),
            "z": float(self.z),
            "cy": float(self.cy),
            "ci": float(self.ci),
            "sigma": float(self.sigma),
        }
        if any(not math.isfinite(value) for value in values.values()):
            raise RealityResidencyError("world deposits must be finite")
        if values["sigma"] <= 0.0:
            raise RealityResidencyError("world deposit sigma must be positive")
        return values


@dataclass(frozen=True, slots=True)
class RealityWorld:
    world_id: str
    arm: str
    deposits: tuple[Deposit, ...]
    focus: tuple[float, float, float] | None
    source_of: str | None = None

    @property
    def net_cy(self) -> float:
        return sum(deposit.cy for deposit in self.deposits)

    @property
    def net_ci(self) -> float:
        return sum(deposit.ci for deposit in self.deposits)

    def as_dict(self) -> dict[str, Any]:
        return {
            "world_id": self.world_id,
            "arm": self.arm,
            "deposits": [deposit.as_dict() for deposit in self.deposits],
            "focus": None if self.focus is None else list(self.focus),
            "net_cy": self.net_cy,
            "net_ci": self.net_ci,
            "source_of": self.source_of,
        }


@dataclass(frozen=True, slots=True)
class RealityCurriculum:
    training: tuple[RealityWorld, ...]
    holdout: tuple[RealityWorld, ...]
    transfer: tuple[RealityWorld, ...]
    null_controls: tuple[RealityWorld, ...]
    repeats: tuple[RealityWorld, ...]
    control_options: tuple[tuple[float, RealityWorld], ...]

    @property
    def prospective(self) -> tuple[RealityWorld, ...]:
        return self.holdout + self.transfer + self.null_controls + self.repeats

    @property
    def all_declared_worlds(self) -> tuple[RealityWorld, ...]:
        return self.training + self.prospective + tuple(
            world for _, world in self.control_options
        )


def _deposit(
    position: Sequence[float],
    channels: Sequence[float],
    *,
    sigma: float = 1.0,
) -> Deposit:
    return Deposit(
        x=float(position[0]),
        y=float(position[1]),
        z=float(position[2]),
        cy=float(channels[0]),
        ci=float(channels[1]),
        sigma=sigma,
    )


def build_reality_curriculum() -> RealityCurriculum:
    """Return the fixed disjoint curriculum used by every campaign run."""

    training_positions = (
        (-0.72, -0.38, 0.14),
        (-0.55, 0.22, 0.61),
        (-0.31, 0.67, -0.44),
        (-0.08, -0.71, -0.53),
        (0.18, -0.17, 0.74),
        (0.37, 0.58, 0.09),
        (0.63, -0.49, 0.42),
        (0.76, 0.33, -0.26),
    )
    training_channels = (
        (4.0, 1.6),
        (2.4, -0.8),
        (-3.2, 2.0),
        (4.8, -2.4),
        (-2.0, -2.8),
        (3.6, 0.0),
        (0.0, 3.2),
        (-4.4, 0.8),
    )
    training = tuple(
        RealityWorld(
            world_id=f"train-{index:02d}",
            arm="training-single-source",
            deposits=(_deposit(position, channels),),
            focus=position,
        )
        for index, (position, channels) in enumerate(
            zip(training_positions, training_channels, strict=True), start=1
        )
    )

    holdout_positions = (
        (-0.66, 0.51, -0.12),
        (-0.42, -0.09, 0.68),
        (-0.19, 0.43, 0.27),
        (0.11, -0.62, 0.49),
        (0.48, 0.13, -0.67),
        (0.69, -0.28, -0.06),
    )
    holdout_channels = (
        (2.8, -1.2),
        (-3.6, -0.4),
        (1.2, 3.6),
        (4.4, 0.4),
        (-1.6, 2.4),
        (3.2, -2.0),
    )
    holdout = tuple(
        RealityWorld(
            world_id=f"holdout-{index:02d}",
            arm="sealed-single-source",
            deposits=(_deposit(position, channels),),
            focus=position,
        )
        for index, (position, channels) in enumerate(
            zip(holdout_positions, holdout_channels, strict=True), start=1
        )
    )

    transfer_positions = (
        (-0.61, -0.56, 0.36),
        (-0.35, 0.08, -0.72),
        (0.24, 0.71, -0.18),
        (0.58, -0.04, 0.63),
    )
    transfer = tuple(
        RealityWorld(
            world_id=f"transfer-{index:02d}",
            arm="sealed-two-source-transfer",
            deposits=(
                _deposit(position, (4.0, 1.6)),
                _deposit(
                    (-0.75 * position[0], -0.75 * position[1], -0.75 * position[2]),
                    (0.88, -0.32),
                ),
            ),
            focus=position,
        )
        for index, position in enumerate(transfer_positions, start=1)
    )

    null_controls = (
        RealityWorld(
            world_id="null-01",
            arm="sealed-no-deposit-control",
            deposits=(),
            focus=(-0.27, 0.35, 0.59),
        ),
        RealityWorld(
            world_id="null-02",
            arm="sealed-no-deposit-control",
            deposits=(),
            focus=(0.53, -0.47, -0.21),
        ),
    )
    repeats = tuple(
        RealityWorld(
            world_id=f"repeat-{index:02d}",
            arm="sealed-exact-repeat",
            deposits=source.deposits,
            focus=source.focus,
            source_of=source.world_id,
        )
        for index, source in enumerate(holdout[:2], start=1)
    )

    control_position = (0.23, -0.41, 0.57)
    source = _deposit(control_position, (4.0, 1.6))
    control_rows = (
        (0.0, "control-none"),
        (-0.5, "control-half"),
        (-1.0, "control-cancel"),
        (-1.5, "control-over"),
    )
    control_options = tuple(
        (
            multiplier,
            RealityWorld(
                world_id=world_id,
                arm="sealed-field-selected-control",
                deposits=(
                    (source,)
                    if multiplier == 0.0
                    else (
                        source,
                        _deposit(
                            control_position,
                            (multiplier * source.cy, multiplier * source.ci),
                        ),
                    )
                ),
                focus=control_position,
            ),
        )
        for multiplier, world_id in control_rows
    )
    return RealityCurriculum(
        training=training,
        holdout=holdout,
        transfer=transfer,
        null_controls=null_controls,
        repeats=repeats,
        control_options=control_options,
    )


def _affine_expression(
    *,
    action_terms: Mapping[str, float],
    error: float,
    bias: float = 0.0,
) -> dict[str, Any]:
    return {
        "terms": {},
        "action_terms": dict(action_terms),
        "bias": bias,
        "error": error,
    }


def localization_candidates() -> list[dict[str, Any]]:
    mappings = {
        "translation-equivariant": (
            ("source_x", 1.0),
            ("source_y", 1.0),
            ("source_z", 1.0),
        ),
        "axis-swap": (
            ("source_y", 1.0),
            ("source_x", 1.0),
            ("source_z", 1.0),
        ),
        "axis-cycle": (
            ("source_y", 1.0),
            ("source_z", 1.0),
            ("source_x", 1.0),
        ),
        "spatial-mirror": (
            ("source_x", -1.0),
            ("source_y", -1.0),
            ("source_z", -1.0),
        ),
        "origin-collapse": (("source_x", 0.0),) * 3,
    }
    rows: list[dict[str, Any]] = []
    for candidate_id, mapping in mappings.items():
        outputs = {
            target: _affine_expression(
                action_terms={source: coefficient},
                error=LOCALIZATION_TOLERANCE,
            )
            for target, (source, coefficient) in zip(
                ("top_x", "top_y", "top_z"), mapping, strict=True
            )
        }
        rows.append(
            {
                "candidate_id": candidate_id,
                "program": semantic_program_payload(
                    program_kind="affine",
                    body={"clamp": {}, "outputs": outputs},
                    arguments={
                        name: {"required": True, "type": "number", "units": "box"}
                        for name in (
                            "source_x",
                            "source_y",
                            "source_z",
                            "physical_horizon",
                        )
                    },
                    writes=["top_x", "top_y", "top_z"],
                    max_work=3,
                    applicability={
                        "action_domain": "any",
                        "context_domain": "any",
                        "grid_n": GRID_N,
                        "interval_domain": "any",
                        "max_supported_horizon": 1,
                        "physical_horizons": list(HORIZONS),
                    },
                ),
                "selection_assumptions": [
                    "fresh-field reset",
                    "single-source training worlds",
                    "fixed periodic grid",
                ],
            }
        )
    return rows


def _global_mode_matrix(steps: int) -> tuple[tuple[float, float], tuple[float, float]]:
    def advance(ey: float, ei: float) -> tuple[float, float]:
        velocity_ey = 0.0
        velocity_ei = 0.0
        for _ in range(steps):
            difference = ey - PHI * ei
            velocity_ey += -OMEGA2 * difference * DT
            velocity_ei += OMEGA2 * difference * DT
            ey += velocity_ey * DT
            ei += velocity_ei * DT
        return ey, ei

    ey_basis = advance(1.0, 0.0)
    ei_basis = advance(0.0, 1.0)
    return (
        (ey_basis[0], ei_basis[0]),
        (ey_basis[1], ei_basis[1]),
    )


def global_response_candidates() -> list[dict[str, Any]]:
    physical = _global_mode_matrix(8)
    families = {
        "coupled-global-mode": physical,
        "uncoupled-charge": ((1.0, 0.0), (0.0, 1.0)),
        "channel-swap": ((0.0, 1.0), (1.0, 0.0)),
        "opposite-coupling": (
            (physical[0][0], -physical[0][1]),
            (-physical[1][0], physical[1][1]),
        ),
        "no-global-response": ((0.0, 0.0), (0.0, 0.0)),
    }
    rows: list[dict[str, Any]] = []
    for candidate_id, matrix in families.items():
        rows.append(
            {
                "candidate_id": candidate_id,
                "program": semantic_program_payload(
                    program_kind="affine",
                    body={
                        "clamp": {},
                        "outputs": {
                            "global_ey_charge": _affine_expression(
                                action_terms={
                                    "net_cy": matrix[0][0],
                                    "net_ci": matrix[0][1],
                                },
                                error=GLOBAL_RESPONSE_TOLERANCE,
                            ),
                            "global_ei_charge": _affine_expression(
                                action_terms={
                                    "net_cy": matrix[1][0],
                                    "net_ci": matrix[1][1],
                                },
                                error=GLOBAL_RESPONSE_TOLERANCE,
                            ),
                        },
                    },
                    arguments={
                        "net_cy": {"required": True, "type": "number", "units": "field-charge"},
                        "net_ci": {"required": True, "type": "number", "units": "field-charge"},
                    },
                    writes=["global_ey_charge", "global_ei_charge"],
                    max_work=2,
                    applicability={
                        "action_domain": "any",
                        "context_domain": "any",
                        "grid_n": GRID_N,
                        "interval_domain": "any",
                        "max_supported_horizon": 1,
                        "physical_horizon": 8,
                    },
                ),
                "selection_assumptions": [
                    "fresh-field reset",
                    "periodic global Laplacian sums to zero",
                    "unclamped linear field regime",
                ],
            }
        )
    return rows


def build_reality_manifest(curriculum: RealityCurriculum | None = None) -> dict[str, Any]:
    curriculum = build_reality_curriculum() if curriculum is None else curriculum
    candidate_families = {
        "localization": localization_candidates(),
        "global_response": global_response_candidates(),
    }
    prospective = [world.as_dict() for world in curriculum.prospective]
    controls = [
        {"counter_multiplier": multiplier, "world": world.as_dict()}
        for multiplier, world in curriculum.control_options
    ]
    sealed = {"prospective_worlds": prospective, "control_options": controls}
    return {
        "schema": MANIFEST_SCHEMA,
        "engine": {
            "scene": "res://scenes/mind_engine_64.tscn",
            "grid_n": GRID_N,
            "dt": DT,
            "auto_step": False,
            "horizons": list(HORIZONS),
        },
        "training_worlds": [world.as_dict() for world in curriculum.training],
        "sealed": sealed,
        "sealed_sha256": sha256_value(sealed),
        "candidate_families": candidate_families,
        "candidate_families_sha256": sha256_value(candidate_families),
        "learning_boundary": {
            "adaptive_state": "QiFieldState.field",
            "training_only_selection": True,
            "prospective_predictions_before_holdout_execution": True,
            "sidecar_learned_state": False,
        },
    }


def _commit_bytes(path: Path, content: bytes) -> None:
    if path.exists():
        if path.read_bytes() != content:
            raise RealityResidencyError(f"immutable campaign artifact changed: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(path.suffix + ".pending")
    with pending.open("wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(pending, path)


def _validate_existing_receipt(path: Path) -> dict[str, Any]:
    try:
        receipt = json.loads(path.read_bytes())
        digest = receipt.pop("body_sha256")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise RealityResidencyError("existing reality receipt is invalid") from exc
    if digest != sha256_value(receipt):
        raise RealityResidencyError("existing reality receipt body digest diverges")
    return {**receipt, "body_sha256": digest}


class RealityResidencyCampaign:
    """One resumable campaign whose only adaptive state is the resident field."""

    def __init__(
        self,
        run_home: Path,
        *,
        run_id: str,
        host: str = "127.0.0.1",
        port: int = 7599,
    ) -> None:
        if not isinstance(run_id, str) or _RUN_ID.fullmatch(run_id) is None:
            raise RealityResidencyError("run_id must be a bounded filesystem-safe identity")
        self.run_home = Path(run_home).resolve()
        self.run_id = run_id
        self.host = host
        self.port = port
        self.curriculum = build_reality_curriculum()
        self.manifest = build_reality_manifest(self.curriculum)
        self.manifest_bytes = canonical_json_bytes(self.manifest)
        self.resident_home = self.run_home / "resident"
        self.controller = CassiCosmosWorldFactoryController(
            authorization=authorize_cassicosmos_seed(
                "fresh deterministic worlds for the owner-requested Reality Residency"
            ),
            host=host,
            port=port,
            timeout=120.0,
        )
        self.controller.bind_durable_journal(self.run_home / "world-journal")

    @property
    def receipt_path(self) -> Path:
        return self.run_home / "receipt.json"

    def _open_resident(self) -> ResearchResidency:
        resident = open_research_residency(self.resident_home)
        resident.initialize(
            workspace=Path(__file__).resolve().parent,
            mission="Learn predictive and controllable laws from fresh CassiCosmos worlds",
            work=[
                {
                    "id": "reality-residency",
                    "summary": "Maintain the integrated fresh-world learning campaign",
                    "request": {"kind": "reality-residency"},
                }
            ],
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
                scope="reality-residency",
                claim_category=category,
                fidelity="exact-observed-bytes",
                labels=("reality-residency", category),
            ),
            context=dict(context),
        )
        return str(archived["source"]["revision_id"])

    def _observe_world(
        self,
        resident: ResearchResidency,
        world: RealityWorld,
        observed: Mapping[str, float],
        source_revision_id: str,
    ) -> str:
        observations = []
        for horizon in HORIZONS:
            for name in ("top_x", "top_y", "top_z", "top_q"):
                key = f"h{horizon}_{name}"
                observations.append(
                    {
                        "subject": world.world_id,
                        "attribute": key,
                        "value": observed[key],
                        "frame": {"physical_horizon": horizon, "arm": world.arm},
                    }
                )
        for name in ("mean_ey", "mean_ei"):
            key = f"h8_{name}"
            observations.append(
                {
                    "subject": world.world_id,
                    "attribute": key,
                    "value": observed[key],
                    "frame": {"physical_horizon": 8, "arm": world.arm},
                }
            )
        event_id = f"event:{self.run_id}:{world.world_id}"
        resident.semantic(
            {
                "operation": "observe",
                "operation_id": f"{self.run_id}:observe:{world.world_id}",
                "delivery_id": f"delivery:{self.run_id}:{world.world_id}",
                "event_id": event_id,
                "observations": observations,
                "source": {"source_revision_id": source_revision_id},
                "support_roots": [source_revision_id],
            }
        )
        return event_id

    def _run_world(
        self,
        resident: ResearchResidency,
        world: RealityWorld,
    ) -> dict[str, Any]:
        acknowledgment = self.controller.execute_world(
            operation_id=f"{self.run_id}:world:{world.world_id}",
            deposits=[deposit.as_dict() for deposit in world.deposits],
            horizons=HORIZONS,
            projection_k=8,
        )
        if acknowledgment.status != "succeeded":
            raise RealityResidencyError(
                f"world {world.world_id} ended {acknowledgment.status}: "
                f"{acknowledgment.context}"
            )
        evidence = canonical_json_bytes(
            {
                "schema": WORLD_EVIDENCE_SCHEMA,
                "world": world.as_dict(),
                "acknowledgment": acknowledgment.as_dict(),
            }
        )
        root = self._archive(
            resident,
            source_id=f"world:{world.world_id}",
            content=evidence,
            category="fresh-physics-world",
            context={
                "world_id": world.world_id,
                "arm": world.arm,
                "acknowledgment_id": acknowledgment.acknowledgment_id,
            },
        )
        event_id = self._observe_world(
            resident,
            world,
            acknowledgment.observed_values,
            root,
        )
        return {
            "world": world.as_dict(),
            "source_revision_id": root,
            "source_sha256": hashlib.sha256(evidence).hexdigest(),
            "event_id": event_id,
            "acknowledgment_id": acknowledgment.acknowledgment_id,
            "observed": dict(acknowledgment.observed_values),
        }

    @staticmethod
    def _collection(
        action: Mapping[str, Any],
        policy: str,
        available_actions: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        declared_actions = [dict(item) for item in available_actions]
        if dict(action) not in declared_actions:
            raise RealityResidencyError("selected action is absent from its declared curriculum")
        return {
            "available_actions": declared_actions,
            "policy_version": policy,
            "selected_action": dict(action),
            "selection_assumptions": ["predeclared-deterministic-curriculum"],
            "selection_mode": "deterministic",
        }

    def _localization_episode(
        self,
        result: Mapping[str, Any],
        horizon: int,
    ) -> dict[str, Any]:
        world = result["world"]
        focus = world["focus"]
        if focus is None:
            raise RealityResidencyError("localization training world lacks a focus")
        action = {
            "source_x": focus[0],
            "source_y": focus[1],
            "source_z": focus[2],
            "physical_horizon": horizon,
        }
        observed = result["observed"]
        return {
            "episode_id": f"episode:localization:{world['world_id']}:h{horizon}",
            "state": {},
            "action": action,
            "context": {"grid_n": GRID_N, "fresh_field": True},
            "interval": {"physical_steps": horizon},
            "next": {
                "top_x": observed[f"h{horizon}_top_x"],
                "top_y": observed[f"h{horizon}_top_y"],
                "top_z": observed[f"h{horizon}_top_z"],
            },
            "intervention": True,
            "outcome_status": "observed-and-scored",
            "collection": self._collection(
                action,
                "reality-localization-training-v1",
                [
                    {
                        "source_x": candidate.focus[0],
                        "source_y": candidate.focus[1],
                        "source_z": candidate.focus[2],
                        "physical_horizon": horizon,
                    }
                    for candidate in self.curriculum.training
                    if candidate.focus is not None
                ],
            ),
        }

    def _global_response_episode(self, result: Mapping[str, Any]) -> dict[str, Any]:
        world = result["world"]
        action = {"net_cy": world["net_cy"], "net_ci": world["net_ci"]}
        observed = result["observed"]
        return {
            "episode_id": f"episode:global-response:{world['world_id']}:h8",
            "state": {},
            "action": action,
            "context": {"grid_n": GRID_N, "fresh_field": True},
            "interval": {"physical_steps": 8},
            "next": {
                "global_ey_charge": observed["h8_mean_ey"] * float(GRID_N**3),
                "global_ei_charge": observed["h8_mean_ei"] * float(GRID_N**3),
            },
            "intervention": True,
            "outcome_status": "observed-and-scored",
            "collection": self._collection(
                action,
                "reality-global-response-training-v1",
                [
                    {"net_cy": candidate.net_cy, "net_ci": candidate.net_ci}
                    for candidate in self.curriculum.training
                ],
            ),
        }

    def _learn(
        self,
        resident: ResearchResidency,
        training: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        roots = [str(result["source_revision_id"]) for result in training]
        localization_episodes = [
            self._localization_episode(result, horizon)
            for result in training
            for horizon in (1, 8)
        ]
        response_episodes = [self._global_response_episode(result) for result in training]
        localization = resident.semantic(
            {
                "operation": "learn-mechanism",
                "operation_id": f"{self.run_id}:learn:localization",
                "mechanism_id": LOCALIZATION_MECHANISM_ID,
                "episodes": localization_episodes,
                "candidates": localization_candidates(),
                "identification": {
                    "assumptions": [
                        "fresh field before every episode",
                        "fixed grid, timestep, and source kernel",
                    ],
                    "controlled_variables": [
                        "source_x",
                        "source_y",
                        "source_z",
                        "physical_horizon",
                    ],
                    "design": "controlled-intervention",
                },
                "support_roots": roots,
            }
        )
        response = resident.semantic(
            {
                "operation": "learn-mechanism",
                "operation_id": f"{self.run_id}:learn:global-response",
                "mechanism_id": GLOBAL_RESPONSE_MECHANISM_ID,
                "episodes": response_episodes,
                "candidates": global_response_candidates(),
                "identification": {
                    "assumptions": [
                        "fresh field before every episode",
                        "periodic global Laplacian sums to zero",
                        "field amplitudes remain below the clamp",
                    ],
                    "controlled_variables": ["net_cy", "net_ci"],
                    "design": "controlled-intervention",
                },
                "support_roots": roots,
            }
        )
        if localization["status"] != "supported" or response["status"] != "supported":
            raise RealityResidencyError(
                "resident mechanism family did not cover training evidence: "
                f"localization={localization['status']} response={response['status']}"
            )
        return {"localization": localization, "global_response": response}

    def _predict(
        self,
        resident: ResearchResidency,
        world: RealityWorld,
        *,
        mechanism: str,
        horizon: int,
        manifest_root: str,
    ) -> dict[str, Any]:
        if mechanism == "localization":
            if world.focus is None:
                raise RealityResidencyError("localization prediction requires a focus")
            action = {
                "source_x": world.focus[0],
                "source_y": world.focus[1],
                "source_z": world.focus[2],
                "physical_horizon": horizon,
            }
            mechanism_id = LOCALIZATION_MECHANISM_ID
        elif mechanism == "global-response":
            action = {"net_cy": world.net_cy, "net_ci": world.net_ci}
            mechanism_id = GLOBAL_RESPONSE_MECHANISM_ID
        else:
            raise RealityResidencyError(f"unknown reality mechanism: {mechanism}")
        prediction_id = f"prediction:{self.run_id}:{mechanism}:{world.world_id}:h{horizon}"
        result = resident.semantic(
            {
                "operation": "predict",
                "operation_id": f"{self.run_id}:predict:{mechanism}:{world.world_id}:h{horizon}",
                "prediction_id": prediction_id,
                "mechanism_id": mechanism_id,
                "state": {},
                "action": action,
                "context": {"physical_horizon": horizon, "arm": world.arm},
                "interval": {"physical_steps": horizon},
                "horizon": 1,
                "query_kind": "intervention",
                "support_roots": [manifest_root],
            }
        )
        if result["status"] not in {"supported", "alternatives"}:
            raise RealityResidencyError(
                f"prospective {mechanism} prediction failed for {world.world_id}: {result}"
            )
        return {"prediction_id": prediction_id, "result": result}

    def _prospective_predictions(
        self,
        resident: ResearchResidency,
        manifest_root: str,
    ) -> dict[str, dict[str, Any]]:
        predictions: dict[str, dict[str, Any]] = {}
        for world in self.curriculum.prospective:
            world_predictions: dict[str, Any] = {}
            for horizon in HORIZONS:
                world_predictions[f"localization_h{horizon}"] = self._predict(
                    resident,
                    world,
                    mechanism="localization",
                    horizon=horizon,
                    manifest_root=manifest_root,
                )
            world_predictions["global_response_h8"] = self._predict(
                resident,
                world,
                mechanism="global-response",
                horizon=8,
                manifest_root=manifest_root,
            )
            predictions[world.world_id] = world_predictions
        return predictions

    def _assess(
        self,
        resident: ResearchResidency,
        result: Mapping[str, Any],
        predictions: Mapping[str, Any],
    ) -> dict[str, Any]:
        world = result["world"]
        observed = result["observed"]
        assessments: dict[str, Any] = {}
        for horizon in HORIZONS:
            key = f"localization_h{horizon}"
            assessment = resident.semantic(
                {
                    "operation": "assess-prediction",
                    "operation_id": f"{self.run_id}:assess:localization:{world['world_id']}:h{horizon}",
                    "prediction_id": predictions[key]["prediction_id"],
                    "event_id": result["event_id"],
                    "actual": {
                        "top_x": observed[f"h{horizon}_top_x"],
                        "top_y": observed[f"h{horizon}_top_y"],
                        "top_z": observed[f"h{horizon}_top_z"],
                    },
                }
            )
            assessments[key] = assessment["assessment_metrics"]
        response = resident.semantic(
            {
                "operation": "assess-prediction",
                "operation_id": f"{self.run_id}:assess:global-response:{world['world_id']}:h8",
                "prediction_id": predictions["global_response_h8"]["prediction_id"],
                "event_id": result["event_id"],
                "actual": {
                    "global_ey_charge": observed["h8_mean_ey"] * float(GRID_N**3),
                    "global_ei_charge": observed["h8_mean_ei"] * float(GRID_N**3),
                },
            }
        )
        assessments["global_response_h8"] = response["assessment_metrics"]
        return assessments

    def _control_prediction(
        self,
        resident: ResearchResidency,
        world: RealityWorld,
        multiplier: float,
    ) -> dict[str, Any]:
        stepped = resident.semantic(
            {
                "operation": "mechanism-step",
                "operation_id": f"{self.run_id}:control-predict:{world.world_id}",
                "mechanism_id": GLOBAL_RESPONSE_MECHANISM_ID,
                "state": {},
                "action": {"net_cy": world.net_cy, "net_ci": world.net_ci},
                "context": {"counter_multiplier": multiplier},
                "interval": {"physical_steps": 8},
            }
        )
        if stepped["status"] != "supported":
            raise RealityResidencyError(f"control prediction failed: {stepped}")
        values = stepped["outcome"]["values"]
        magnitude = math.hypot(
            float(values["global_ey_charge"]),
            float(values["global_ei_charge"]),
        )
        return {
            "counter_multiplier": multiplier,
            "world_id": world.world_id,
            "predicted_global_ey_charge": values["global_ey_charge"],
            "predicted_global_ei_charge": values["global_ei_charge"],
            "predicted_global_magnitude": magnitude,
        }

    def _run_control(
        self,
        resident: ResearchResidency,
    ) -> dict[str, Any]:
        predicted = [
            self._control_prediction(resident, world, multiplier)
            for multiplier, world in self.curriculum.control_options
        ]
        selected = min(
            predicted,
            key=lambda row: (
                float(row["predicted_global_magnitude"]),
                str(row["world_id"]),
            ),
        )
        by_id = {
            world.world_id: world for _, world in self.curriculum.control_options
        }
        baseline_world = by_id["control-none"]
        selected_world = by_id[str(selected["world_id"])]
        baseline = self._run_world(resident, baseline_world)
        controlled = (
            baseline
            if selected_world.world_id == baseline_world.world_id
            else self._run_world(resident, selected_world)
        )
        baseline_observed = baseline["observed"]
        controlled_observed = controlled["observed"]
        baseline_mean = math.hypot(
            baseline_observed["h8_mean_ey"], baseline_observed["h8_mean_ei"]
        )
        controlled_mean = math.hypot(
            controlled_observed["h8_mean_ey"], controlled_observed["h8_mean_ei"]
        )
        baseline_q = float(baseline_observed["h8_top_q"])
        controlled_q = float(controlled_observed["h8_top_q"])
        return {
            "candidate_predictions": predicted,
            "selected": selected,
            "baseline_world": baseline,
            "controlled_world": controlled,
            "mean_suppression": (
                1.0 if baseline_mean == 0.0 else 1.0 - controlled_mean / baseline_mean
            ),
            "peak_q_suppression": (
                1.0 if baseline_q == 0.0 else 1.0 - controlled_q / baseline_q
            ),
        }

    def _restart_probe(
        self,
        resident: ResearchResidency,
    ) -> tuple[dict[str, Any], str]:
        before = resident.semantic(
            {
                "operation": "mechanism-step",
                "operation_id": f"{self.run_id}:restart-probe:before",
                "mechanism_id": LOCALIZATION_MECHANISM_ID,
                "state": {},
                "action": {
                    "source_x": 0.27,
                    "source_y": -0.63,
                    "source_z": 0.31,
                    "physical_horizon": 32,
                },
                "context": {"probe": "restart"},
                "interval": {"physical_steps": 32},
            }
        )
        return before, resident.inspect()["field_state_sha256"]

    def _finish_restart_probe(
        self,
        before: Mapping[str, Any],
        field_sha256: str,
    ) -> tuple[dict[str, Any], ResearchResidency]:
        resident = self._open_resident()
        reopened_sha256 = resident.inspect()["field_state_sha256"]
        after = resident.semantic(
            {
                "operation": "mechanism-step",
                "operation_id": f"{self.run_id}:restart-probe:after",
                "mechanism_id": LOCALIZATION_MECHANISM_ID,
                "state": {},
                "action": {
                    "source_x": 0.27,
                    "source_y": -0.63,
                    "source_z": 0.31,
                    "physical_horizon": 32,
                },
                "context": {"probe": "restart"},
                "interval": {"physical_steps": 32},
            }
        )
        result = {
            "field_sha256_before_close": field_sha256,
            "field_sha256_after_reopen": reopened_sha256,
            "state_restored_exactly": reopened_sha256 == field_sha256,
            "prediction_before": before["outcome"],
            "prediction_after": after["outcome"],
            "prediction_preserved": before["outcome"] == after["outcome"],
        }
        return result, resident

    def _lesion_probe(self) -> dict[str, Any]:
        lesion = open_research_residency(self.run_home / "lesion-resident")
        try:
            lesion.initialize(
                workspace=Path(__file__).resolve().parent,
                mission="Reality Residency field-lesion control",
                work=[
                    {
                        "id": "field-lesion",
                        "summary": "Attempt the learned law without the learned field",
                        "request": {"kind": "field-lesion"},
                    }
                ],
            )
            try:
                lesion.semantic(
                    {
                        "operation": "mechanism-step",
                        "operation_id": f"{self.run_id}:lesion:mechanism-step",
                        "mechanism_id": LOCALIZATION_MECHANISM_ID,
                        "state": {},
                        "action": {
                            "source_x": 0.27,
                            "source_y": -0.63,
                            "source_z": 0.31,
                            "physical_horizon": 32,
                        },
                    }
                )
            except (FieldIntelligenceError, ResidencyError) as exc:
                return {
                    "learned_mechanism_available": False,
                    "error_type": type(exc).__name__,
                    "error_code": getattr(exc, "code", None),
                    "error": str(exc),
                }
            return {"learned_mechanism_available": True, "error": None}
        finally:
            lesion.close()

    @staticmethod
    def _compact_world(result: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "world": result["world"],
            "source_revision_id": result["source_revision_id"],
            "source_sha256": result["source_sha256"],
            "event_id": result["event_id"],
            "acknowledgment_id": result["acknowledgment_id"],
            "observed": result["observed"],
        }

    @staticmethod
    def _prediction_values(prediction: Mapping[str, Any]) -> Mapping[str, Any]:
        result = prediction.get("result")
        alternatives = (
            result.get("alternatives")
            if isinstance(result, Mapping)
            else None
        )
        if (
            not isinstance(alternatives, list)
            or len(alternatives) != 1
            or not isinstance(alternatives[0], Mapping)
            or not isinstance(alternatives[0].get("values"), Mapping)
        ):
            raise RealityResidencyError(
                "prospective prediction does not contain one determinate value set"
            )
        return alternatives[0]["values"]

    def run(self) -> dict[str, Any]:
        if self.receipt_path.exists():
            receipt = _validate_existing_receipt(self.receipt_path)
            expected = {
                "run_id": self.run_id,
                "manifest_sha256": hashlib.sha256(self.manifest_bytes).hexdigest(),
                "sealed_sha256": self.manifest["sealed_sha256"],
                "candidate_families_sha256": self.manifest[
                    "candidate_families_sha256"
                ],
            }
            if any(receipt.get(name) != value for name, value in expected.items()):
                raise RealityResidencyError(
                    "existing reality receipt belongs to a different campaign contract"
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
                category="sealed-curriculum",
                context={
                    "manifest_sha256": hashlib.sha256(self.manifest_bytes).hexdigest(),
                    "sealed_sha256": self.manifest["sealed_sha256"],
                },
            )
            training = [self._run_world(resident, world) for world in self.curriculum.training]
            learning = self._learn(resident, training)

            predictions = self._prospective_predictions(resident, manifest_root)
            prediction_ids = sorted(
                str(prediction["prediction_id"])
                for world_predictions in predictions.values()
                for prediction in world_predictions.values()
            )
            precommit_inspection = resident.inspect()
            precommit_payload = {
                "schema": "cassifi.reality-prospective-precommit.v1",
                "run_id": self.run_id,
                "sealed_sha256": self.manifest["sealed_sha256"],
                "prediction_count": len(prediction_ids),
                "prediction_ids": prediction_ids,
                "prediction_sha256_by_world": {
                    world_id: sha256_value(world_predictions)
                    for world_id, world_predictions in sorted(predictions.items())
                },
                "field_state_sha256": precommit_inspection["field_state_sha256"],
                "resident_operations": precommit_inspection["resident_operations"],
            }
            precommit_bytes = canonical_json_bytes(precommit_payload)
            precommit_root = self._archive(
                resident,
                source_id="prospective-precommit",
                content=precommit_bytes,
                category="prospective-prediction-precommit",
                context={
                    "sealed_sha256": self.manifest["sealed_sha256"],
                    "prediction_count": len(prediction_ids),
                    "precommit_sha256": hashlib.sha256(precommit_bytes).hexdigest(),
                },
            )
            prospective_precommit = {
                **precommit_payload,
                "source_revision_id": precommit_root,
            }
            prospective_results: dict[str, dict[str, Any]] = {}
            assessments: dict[str, dict[str, Any]] = {}
            for world in self.curriculum.prospective:
                result = self._run_world(resident, world)
                prospective_results[world.world_id] = result
                assessments[world.world_id] = self._assess(
                    resident, result, predictions[world.world_id]
                )

            control = self._run_control(resident)
            before_restart, field_sha256 = self._restart_probe(resident)
        finally:
            resident.close()

        restart, resident = self._finish_restart_probe(before_restart, field_sha256)
        try:
            final_field_sha256 = resident.inspect()["field_state_sha256"]
        finally:
            resident.close()
        lesion = self._lesion_probe()

        repeatability = []
        for world in self.curriculum.repeats:
            if world.source_of is None:
                raise RealityResidencyError("repeat world lacks its source identity")
            original = prospective_results[world.source_of]["observed"]
            repeated = prospective_results[world.world_id]["observed"]
            repeatability.append(
                {
                    "source_world_id": world.source_of,
                    "repeat_world_id": world.world_id,
                    "exact_observations": original == repeated,
                    "source_observation_sha256": sha256_value(original),
                    "repeat_observation_sha256": sha256_value(repeated),
                }
            )

        non_null_ids = [
            world.world_id
            for world in self.curriculum.holdout
            + self.curriculum.transfer
            + self.curriculum.repeats
        ]
        localization_errors: dict[str, list[float]] = {}
        for horizon in HORIZONS:
            errors = []
            for world_id in non_null_ids:
                values = self._prediction_values(
                    predictions[world_id][f"localization_h{horizon}"]
                )
                observed = prospective_results[world_id]["observed"]
                deltas = []
                for axis in ("x", "y", "z"):
                    difference = abs(
                        float(values[f"top_{axis}"])
                        - float(observed[f"h{horizon}_top_{axis}"])
                    )
                    deltas.append(min(difference, abs(2.0 - difference)))
                errors.append(math.sqrt(sum(delta * delta for delta in deltas)))
            localization_errors[str(horizon)] = errors
        localization_by_horizon = {
            str(horizon): {
                "passed": sum(
                    assessments[world_id][f"localization_h{horizon}"]["coverage"]
                    is True
                    for world_id in non_null_ids
                ),
                "attempted": len(non_null_ids),
                "max_loss": max(
                    float(assessments[world_id][f"localization_h{horizon}"]["loss"])
                    for world_id in non_null_ids
                ),
                "max_position_error": max(localization_errors[str(horizon)]),
                "mean_position_error": (
                    sum(localization_errors[str(horizon)])
                    / len(localization_errors[str(horizon)])
                ),
            }
            for horizon in HORIZONS
        }
        dose_ids = [world.world_id for world in self.curriculum.prospective]
        global_vector_errors = []
        global_component_errors = []
        for world_id in dose_ids:
            values = self._prediction_values(
                predictions[world_id]["global_response_h8"]
            )
            observed = prospective_results[world_id]["observed"]
            deltas = (
                abs(
                    float(values["global_ey_charge"])
                    - float(observed["h8_mean_ey"]) * float(GRID_N**3)
                ),
                abs(
                    float(values["global_ei_charge"])
                    - float(observed["h8_mean_ei"]) * float(GRID_N**3)
                ),
            )
            global_component_errors.extend(deltas)
            global_vector_errors.append(math.hypot(*deltas))
        global_response_summary = {
            "passed": sum(
                assessments[world_id]["global_response_h8"]["coverage"] is True
                for world_id in dose_ids
            ),
            "attempted": len(dose_ids),
            "max_loss": max(
                float(assessments[world_id]["global_response_h8"]["loss"])
                for world_id in dose_ids
            ),
            "max_charge_component_error": max(global_component_errors),
            "max_charge_vector_error": max(global_vector_errors),
            "mean_charge_vector_error": (
                sum(global_vector_errors) / len(global_vector_errors)
            ),
        }
        null_localization_fired = all(
            any(
                float(assessments[world.world_id][f"localization_h{horizon}"]["loss"])
                > 0.0
                for horizon in HORIZONS
            )
            for world in self.curriculum.null_controls
        )
        selected_laws = {
            name: str(result["candidate_comparison"][0]["candidate_id"])
            for name, result in learning.items()
        }
        causal_laws_identified = all(
            result["causal_authority"] is True
            for result in learning.values()
        )
        expected_prediction_count = len(self.curriculum.prospective) * (
            len(HORIZONS) + 1
        )
        predictions_precommitted = (
            len(prediction_ids) == expected_prediction_count
            and prospective_precommit["source_revision_id"] == precommit_root
        )
        summary = {
            "training_worlds": len(training),
            "prospective_worlds": len(prospective_results),
            "executed_worlds": len(training)
            + len(prospective_results)
            + (1 if control["baseline_world"] is control["controlled_world"] else 2),
            "physical_observations": (
                len(training)
                + len(prospective_results)
                + (1 if control["baseline_world"] is control["controlled_world"] else 2)
            )
            * len(HORIZONS),
            "localization_by_horizon": localization_by_horizon,
            "global_response": global_response_summary,
            "selected_laws": selected_laws,
            "causal_laws_identified": causal_laws_identified,
            "predictions_precommitted": predictions_precommitted,
            "prospective_prediction_count": len(prediction_ids),
            "null_localization_control_fired": null_localization_fired,
            "exact_repeat_pairs": sum(row["exact_observations"] for row in repeatability),
            "repeat_pairs": len(repeatability),
            "selected_control_multiplier": control["selected"]["counter_multiplier"],
            "mean_suppression": control["mean_suppression"],
            "peak_q_suppression": control["peak_q_suppression"],
            "restart_retained": restart["state_restored_exactly"]
            and restart["prediction_preserved"],
            "field_lesion_removed_mechanism": lesion["learned_mechanism_available"] is False,
        }
        status = "supported" if (
            all(
                row["passed"] == row["attempted"]
                for row in localization_by_horizon.values()
            )
            and global_response_summary["passed"] == global_response_summary["attempted"]
            and selected_laws
            == {
                "localization": "translation-equivariant",
                "global_response": "coupled-global-mode",
            }
            and causal_laws_identified
            and predictions_precommitted
            and null_localization_fired
            and summary["exact_repeat_pairs"] == summary["repeat_pairs"]
            and float(control["mean_suppression"]) > 0.99
            and summary["restart_retained"]
            and summary["field_lesion_removed_mechanism"]
        ) else "measured-boundary"

        receipt: dict[str, Any] = {
            "schema": SCHEMA,
            "run_id": self.run_id,
            "status": status,
            "manifest_sha256": hashlib.sha256(self.manifest_bytes).hexdigest(),
            "manifest_source_revision_id": manifest_root,
            "sealed_sha256": self.manifest["sealed_sha256"],
            "candidate_families_sha256": self.manifest["candidate_families_sha256"],
            "training": [self._compact_world(result) for result in training],
            "learning": learning,
            "prospective_precommit": prospective_precommit,
            "prospective": {
                world_id: {
                    "world": self._compact_world(result),
                    "predictions": predictions[world_id],
                    "assessments": assessments[world_id],
                }
                for world_id, result in prospective_results.items()
            },
            "control": {
                **{key: value for key, value in control.items() if key not in {"baseline_world", "controlled_world"}},
                "baseline_world": self._compact_world(control["baseline_world"]),
                "controlled_world": self._compact_world(control["controlled_world"]),
            },
            "repeatability": repeatability,
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


def run_reality_residency(
    run_home: Path,
    *,
    run_id: str,
    host: str = "127.0.0.1",
    port: int = 7599,
) -> dict[str, Any]:
    return RealityResidencyCampaign(
        run_home,
        run_id=run_id,
        host=host,
        port=port,
    ).run()


__all__ = [
    "Deposit",
    "RealityCurriculum",
    "RealityResidencyCampaign",
    "RealityResidencyError",
    "RealityWorld",
    "build_reality_curriculum",
    "build_reality_manifest",
    "global_response_candidates",
    "localization_candidates",
    "run_reality_residency",
]
