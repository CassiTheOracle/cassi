from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from typing import Any, Literal

import torch

from cassi_bilateral_counterflow import (
    BasinReceipt,
    BilateralCounterflowConfig,
    BilateralCounterflowController,
)
from cassi_qi_field import QiFieldError, QiFieldState


RELATIONAL_BASIS_NAMES = (
    "target_minus_self",
    "absolute_self",
    "absolute_target",
    "identity_control",
)
RELATION_ATOM_SCHEMA = "cassi.counterflow.relation-atoms.v1"
_EVIDENCE_NAMES = (
    "closure",
    "inverse",
    "composition",
    "invariance",
    "collision",
    "boundary",
)


@dataclass(frozen=True)
class RelationalBasisConfig(BilateralCounterflowConfig):
    max_basins: int = 16
    basis_count: int = 4
    action_count: int = 4
    closure_weight: float = 1.0
    inverse_weight: float = 0.5
    composition_weight: float = 1.0
    invariance_weight: float = 2.0
    collision_weight: float = 2.0
    boundary_weight: float = 0.0
    selection_margin: float = 1.0e-4
    collision_margin: float = 0.05
    max_basis_score: float = 0.05

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.basis_count != len(RELATIONAL_BASIS_NAMES):
            raise QiFieldError(
                f"relational basis_count must be {len(RELATIONAL_BASIS_NAMES)}"
            )
        if self.action_count < 2 or self.max_basins != self.basis_count * self.action_count:
            raise QiFieldError(
                "relational max_basins must equal basis_count * action_count"
            )
        for name in (
            "closure_weight",
            "inverse_weight",
            "composition_weight",
            "invariance_weight",
            "collision_weight",
            "boundary_weight",
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0.0:
                raise QiFieldError(f"{name} must be finite and non-negative")
        for name in ("selection_margin", "collision_margin", "max_basis_score"):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0.0:
                raise QiFieldError(f"{name} must be finite and positive")

    @property
    def basis_evidence_width(self) -> int:
        return 1 + len(_EVIDENCE_NAMES)

    @property
    def basis_evidence_start(self) -> int:
        return self.basin_end

    @property
    def basis_evidence_end(self) -> int:
        return self.basis_evidence_start + self.basis_count * self.basis_evidence_width

    @property
    def metadata_start(self) -> int:
        return self.basis_evidence_end


@dataclass(frozen=True)
class BasisEvidence:
    basis_id: int
    basis_name: str
    support: int
    closure: float
    inverse: float
    composition: float
    invariance: float
    collision: float
    boundary: float
    score: float


@dataclass(frozen=True)
class BasisSelection:
    status: Literal[
        "selected",
        "ambiguous",
        "no_basis_evidence",
        "no_eligible_basis",
    ]
    basis_id: int | None
    basis_name: str | None
    margin: float | None
    evidence: tuple[BasisEvidence, ...]
    field_sha256: str


@dataclass(frozen=True)
class RelationEntity:
    entity_id: str
    x: float
    y: float

    def __post_init__(self) -> None:
        if not isinstance(self.entity_id, str) or not self.entity_id:
            raise QiFieldError("relation entity_id must be nonempty")
        for name in ("x", "y"):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not -1.0 <= value <= 1.0
            ):
                raise QiFieldError(
                    "relation entity coordinates must be finite numbers in [-1, 1]"
                )
            object.__setattr__(self, name, float(value))


@dataclass(frozen=True)
class RelationAtoms:
    world_id: str
    episode_id: str
    state_sha256: str
    regime: Literal["interior", "boundary"]
    entities: tuple[RelationEntity, RelationEntity]

    def __post_init__(self) -> None:
        if not isinstance(self.world_id, str) or not self.world_id:
            raise QiFieldError("relation world_id must be nonempty")
        if not isinstance(self.episode_id, str) or not self.episode_id:
            raise QiFieldError("relation episode_id must be nonempty")
        if (
            not isinstance(self.state_sha256, str)
            or len(self.state_sha256) != 64
            or any(character not in "0123456789abcdef" for character in self.state_sha256)
        ):
            raise QiFieldError("relation state_sha256 must be lowercase hexadecimal")
        if not isinstance(self.regime, str) or self.regime not in {
            "interior",
            "boundary",
        }:
            raise QiFieldError("unsupported relation regime")
        if (
            not isinstance(self.entities, tuple)
            or len(self.entities) != 2
            or not all(isinstance(entity, RelationEntity) for entity in self.entities)
            or self.entities[0].entity_id == self.entities[1].entity_id
        ):
            raise QiFieldError("relation atoms require two distinct entities")

    def payload(self) -> dict[str, Any]:
        body = {
            "schema": RELATION_ATOM_SCHEMA,
            "world_id": self.world_id,
            "episode_id": self.episode_id,
            "state_sha256": self.state_sha256,
            "regime": self.regime,
            "entities": [
                {"entity_id": entity.entity_id, "x": entity.x, "y": entity.y}
                for entity in self.entities
            ],
        }
        encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        return {**body, "payload_sha256": hashlib.sha256(encoded).hexdigest()}

    @classmethod
    def from_payload(cls, value: Mapping[str, Any]) -> RelationAtoms:
        if not isinstance(value, Mapping) or set(value) != {
            "schema",
            "world_id",
            "episode_id",
            "state_sha256",
            "regime",
            "entities",
            "payload_sha256",
        }:
            raise QiFieldError("relation atom payload fields mismatch")
        body = {key: value[key] for key in value if key != "payload_sha256"}
        encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        if value["schema"] != RELATION_ATOM_SCHEMA or value["payload_sha256"] != hashlib.sha256(encoded).hexdigest():
            raise QiFieldError("relation atom payload hash mismatch")
        entities = value["entities"]
        if not isinstance(entities, list) or len(entities) != 2:
            raise QiFieldError("relation atom entities must contain two values")
        parsed = []
        for entity in entities:
            if not isinstance(entity, Mapping) or set(entity) != {"entity_id", "x", "y"}:
                raise QiFieldError("relation entity fields mismatch")
            coordinates = (entity["x"], entity["y"])
            if any(
                isinstance(coordinate, bool)
                or not isinstance(coordinate, (int, float))
                for coordinate in coordinates
            ):
                raise QiFieldError("relation entity coordinates must be numeric")
            parsed.append(
                RelationEntity(
                    entity_id=entity["entity_id"],
                    x=coordinates[0],
                    y=coordinates[1],
                )
            )
        return cls(
            world_id=value["world_id"],
            episode_id=value["episode_id"],
            state_sha256=value["state_sha256"],
            regime=value["regime"],
            entities=(parsed[0], parsed[1]),
        )


def relational_basis_value(
    basis_id: int,
    atoms: RelationAtoms,
    *,
    self_index: int,
) -> torch.Tensor:
    if not 0 <= basis_id < len(RELATIONAL_BASIS_NAMES):
        raise QiFieldError("basis_id is outside the relational basis library")
    if self_index not in (0, 1):
        raise QiFieldError("self_index must be zero or one")
    self_entity = atoms.entities[self_index]
    target = atoms.entities[1 - self_index]
    if basis_id == 0:
        x, y = target.x - self_entity.x, target.y - self_entity.y
    elif basis_id == 1:
        x, y = self_entity.x, self_entity.y
    elif basis_id == 2:
        x, y = target.x, target.y
    else:
        digest = hashlib.sha256(
            f"{self_entity.entity_id}\x00{target.entity_id}".encode()
        ).digest()
        x = int.from_bytes(digest[:8], "big") / float((1 << 64) - 1) * 2.0 - 1.0
        y = int.from_bytes(digest[8:16], "big") / float((1 << 64) - 1) * 2.0 - 1.0
    return torch.tensor((x, y, 1.0, x * y), dtype=torch.complex128)


class RelationalBasisController(BilateralCounterflowController):
    """Field-selected fixed relational bases plus grouped action operators."""

    config: RelationalBasisConfig

    def __init__(self, config: RelationalBasisConfig | None = None) -> None:
        super().__init__(config or RelationalBasisConfig())

    def validate_state(self, state: QiFieldState) -> None:
        super().validate_state(state)
        packed = self._packed(state)
        c = self.config
        modes = slice(c.basis_evidence_start, c.basis_evidence_end)
        self._require_zero("relational evidence field components", packed[0, :8, modes, :])
        self._require_zero("non-root relational evidence", packed[1:, :, modes, :])
        evidence = packed[0, 8, modes, 0].reshape(c.basis_count, c.basis_evidence_width)
        if not torch.isfinite(evidence).all().item() or (evidence < 0.0).any().item():
            raise QiFieldError("relational basis evidence must be finite and non-negative")
        for basis_id, row in enumerate(evidence):
            support = self._require_integer(
                f"relation_basis_support[{basis_id}]",
                float(row[0].item()),
                0,
                self._MAX_EXACT_INTEGER,
            )
            if support == 0 and torch.count_nonzero(row[1:]).item() != 0:
                raise QiFieldError("unsupported relational basis evidence must be zero")

    def basin_id(self, basis_id: int, action_id: int) -> int:
        if not 0 <= basis_id < self.config.basis_count:
            raise QiFieldError("basis_id is outside the configured capacity")
        if not 0 <= action_id < self.config.action_count:
            raise QiFieldError("action_id is outside the configured capacity")
        return basis_id * self.config.action_count + action_id

    def observe_grouped_transitions(
        self,
        state: QiFieldState,
        basis_id: int,
        action_id: int,
        before: torch.Tensor | Sequence[Sequence[complex | float]],
        after: torch.Tensor | Sequence[Sequence[complex | float]],
    ) -> tuple[QiFieldState, BasinReceipt]:
        self.validate_state(state)
        packed = self._packed(state)
        _, status, _, _, _ = self._metadata(packed)
        if status != self._IDLE:
            raise QiFieldError("grouped transitions require an idle field")
        x = self._coerce_examples(before, state)
        y = self._coerce_examples(after, state)
        if x.shape != y.shape:
            raise QiFieldError("before and after examples must have equal shape")
        basin_id = self.basin_id(basis_id, action_id)
        support_values = self._basin_support(packed)
        occupied_before = int((support_values >= self.config.occupancy_floor).sum().item())
        support_before = int(round(float(support_values[basin_id].item())))
        if support_before and self._macro_definition(packed, basin_id)[0]:
            raise QiFieldError("grouped transitions cannot reinforce a macro basin")

        sample_count = int(x.shape[0])
        forward_gram = torch.einsum("ni,nj->ij", x, x.conj()) / float(sample_count)
        forward_cross = torch.einsum("ni,nj->ij", y, x.conj()) / float(sample_count)
        backward_gram = torch.einsum("ni,nj->ij", y, y.conj()) / float(sample_count)
        backward_cross = torch.einsum("ni,nj->ij", x, y.conj()) / float(sample_count)
        candidate = self._operator_from_moments(forward_cross, forward_gram)
        candidate_error = float(
            self._relative_residual(torch.einsum("ij,nj->ni", candidate, x), y)
            .mean()
            .item()
        )

        if support_before:
            (
                old_forward_cross,
                old_forward_gram,
                old_backward_cross,
                old_backward_gram,
                old_support,
                old_dispersion,
            ) = self._read_moments(packed, basin_id)
            support = old_support + sample_count
            forward_cross = (
                old_support * old_forward_cross + sample_count * forward_cross
            ) / float(support)
            forward_gram = (
                old_support * old_forward_gram + sample_count * forward_gram
            ) / float(support)
            backward_cross = (
                old_support * old_backward_cross + sample_count * backward_cross
            ) / float(support)
            backward_gram = (
                old_support * old_backward_gram + sample_count * backward_gram
            ) / float(support)
            dispersion = (
                old_support * old_dispersion + sample_count * candidate_error
            ) / float(support)
            generation = self._basin_generation(packed, basin_id)
            decision: Literal["create", "reinforce"] = "reinforce"
        else:
            support = sample_count
            dispersion = candidate_error
            generation = max(1, self._basin_generation(packed, basin_id))
            decision = "create"
        if support > self._MAX_EXACT_INTEGER:
            raise QiFieldError("grouped basin support exceeds exact field capacity")

        result = QiFieldState(field=state.field.clone())
        target = self._packed(result)
        self._write_macro_metadata(target, basin_id, generation)
        self._write_moments(
            target,
            basin_id,
            forward_cross,
            forward_gram,
            backward_cross,
            backward_gram,
            support,
            dispersion,
        )
        self.validate_state(result)
        return result, BasinReceipt(
            decision=decision,
            basin_id=basin_id,
            best_residual=candidate_error,
            best_similarity=1.0,
            occupied_before=occupied_before,
            occupied_after=occupied_before + int(not support_before),
            support_before=support_before,
            support_after=support,
            dispersion_after=dispersion,
            field_sha256=self._tensor_sha256(result.field),
        )

    def operator(self, state: QiFieldState, basis_id: int, action_id: int) -> torch.Tensor:
        self.validate_state(state)
        basin_id = self.basin_id(basis_id, action_id)
        packed = self._packed(state)
        if self._basin_support(packed)[basin_id].item() < self.config.occupancy_floor:
            raise QiFieldError("requested relational operator has no field support")
        cross, gram, *_ = self._read_moments(packed, basin_id)
        return self._operator_from_moments(cross, gram)

    def observe_basis_evidence(
        self,
        state: QiFieldState,
        basis_id: int,
        *,
        transitions: Sequence[
            tuple[
                int,
                torch.Tensor | Sequence[complex | float],
                torch.Tensor | Sequence[complex | float],
            ]
        ],
        inverse_actions: Mapping[int, int],
        compositions: Sequence[
            tuple[
                Sequence[int],
                torch.Tensor | Sequence[complex | float],
                torch.Tensor | Sequence[complex | float],
            ]
        ],
        invariance_pairs: Sequence[
            tuple[
                torch.Tensor | Sequence[complex | float],
                torch.Tensor | Sequence[complex | float],
            ]
        ],
        collision_values: Sequence[torch.Tensor | Sequence[complex | float]],
        boundary_transitions: Sequence[
            tuple[
                int,
                torch.Tensor | Sequence[complex | float],
                torch.Tensor | Sequence[complex | float],
            ]
        ] = (),
    ) -> tuple[QiFieldState, BasisEvidence]:
        self.validate_state(state)
        if (
            not transitions
            or not compositions
            or not invariance_pairs
            or not collision_values
        ):
            raise QiFieldError(
                "basis evidence requires transition, composition, invariance, "
                "and collision observations"
            )
        actions = set(range(self.config.action_count))
        if set(inverse_actions) != actions or set(inverse_actions.values()) != actions:
            raise QiFieldError("inverse action metadata must cover every action exactly")
        operators = {
            action_id: self.operator(state, basis_id, action_id)
            for action_id in actions
        }

        def latent(value: torch.Tensor | Sequence[complex | float]) -> torch.Tensor:
            return self._coerce_latent(value, state)

        def residual(predicted: torch.Tensor, observed: torch.Tensor) -> float:
            return float(
                self._relative_residual(
                    predicted.unsqueeze(0),
                    observed.unsqueeze(0),
                )
                .mean()
                .item()
            )

        closure_values = []
        inverse_values = []
        for action_id, before_value, after_value in transitions:
            if action_id not in actions:
                raise QiFieldError("transition action is outside the configured capacity")
            before = latent(before_value)
            after = latent(after_value)
            predicted = operators[action_id] @ before
            closure_values.append(residual(predicted, after))
            cycled = operators[inverse_actions[action_id]] @ predicted
            inverse_values.append(residual(cycled, before))

        composition_values = []
        for action_ids, before_value, after_value in compositions:
            if not action_ids or any(action_id not in actions for action_id in action_ids):
                raise QiFieldError("composition actions are empty or outside capacity")
            predicted = latent(before_value)
            for action_id in action_ids:
                predicted = operators[action_id] @ predicted
            composition_values.append(residual(predicted, latent(after_value)))

        invariance_values = [
            residual(latent(left), latent(right))
            for left, right in invariance_pairs
        ]
        collision_values_measured = []
        for value in collision_values:
            before = latent(value)
            deltas = tuple(operators[action_id] @ before - before for action_id in actions)
            separation = min(
                float(torch.linalg.vector_norm(deltas[left] - deltas[right]).item())
                for left in range(self.config.action_count)
                for right in range(left + 1, self.config.action_count)
            )
            collision_values_measured.append(
                (
                    max(0.0, self.config.collision_margin - separation)
                    / self.config.collision_margin
                )
                ** 2
            )

        boundary_values = []
        for action_id, before_value, after_value in boundary_transitions:
            if action_id not in actions:
                raise QiFieldError("boundary action is outside the configured capacity")
            boundary_values.append(
                residual(
                    operators[action_id] @ latent(before_value),
                    latent(after_value),
                )
            )

        mean = lambda values: sum(values) / float(len(values))
        result = self._deposit_basis_evidence(
            state,
            basis_id,
            closure=mean(closure_values),
            inverse=mean(inverse_values),
            composition=mean(composition_values),
            invariance=mean(invariance_values),
            collision=mean(collision_values_measured),
            boundary=0.0 if not boundary_values else mean(boundary_values),
        )
        return result, self.basis_evidence(result)[basis_id]
    def _deposit_basis_evidence(
        self,
        state: QiFieldState,
        basis_id: int,
        *,
        closure: float,
        inverse: float,
        composition: float,
        invariance: float,
        collision: float,
        boundary: float = 0.0,
        samples: int = 1,
    ) -> QiFieldState:
        self.validate_state(state)
        if not 0 <= basis_id < self.config.basis_count:
            raise QiFieldError("basis_id is outside the configured capacity")
        if isinstance(samples, bool) or not isinstance(samples, int) or samples < 1:
            raise QiFieldError("basis evidence samples must be a positive integer")
        values = (closure, inverse, composition, invariance, collision, boundary)
        if any(not math.isfinite(value) or value < 0.0 for value in values):
            raise QiFieldError("basis evidence values must be finite and non-negative")
        result = QiFieldState(field=state.field.clone())
        packed = self._packed(result)
        start = self.config.basis_evidence_start + basis_id * self.config.basis_evidence_width
        row = packed[0, 8, start : start + self.config.basis_evidence_width, 0]
        support = self._require_integer(
            "relation_basis_support",
            float(row[0].item()),
            0,
            self._MAX_EXACT_INTEGER,
        )
        if support + samples > self._MAX_EXACT_INTEGER:
            raise QiFieldError("basis evidence support exceeds exact field capacity")
        row[0] = float(support + samples)
        row[1:] += torch.tensor(
            [samples * value for value in values],
            device=row.device,
            dtype=row.dtype,
        )
        self.validate_state(result)
        return result

    def basis_evidence(self, state: QiFieldState) -> tuple[BasisEvidence, ...]:
        self.validate_state(state)
        packed = self._packed(state)
        c = self.config
        rows = packed[
            0,
            8,
            c.basis_evidence_start : c.basis_evidence_end,
            0,
        ].reshape(c.basis_count, c.basis_evidence_width)
        result = []
        weights = (
            c.closure_weight,
            c.inverse_weight,
            c.composition_weight,
            c.invariance_weight,
            c.collision_weight,
            c.boundary_weight,
        )
        for basis_id, row in enumerate(rows):
            support = int(round(float(row[0].item())))
            means = tuple(
                0.0 if support == 0 else float(value.item()) / float(support)
                for value in row[1:]
            )
            score = math.inf if support == 0 else sum(
                weight * value for weight, value in zip(weights, means, strict=True)
            )
            result.append(
                BasisEvidence(
                    basis_id=basis_id,
                    basis_name=RELATIONAL_BASIS_NAMES[basis_id],
                    support=support,
                    closure=means[0],
                    inverse=means[1],
                    composition=means[2],
                    invariance=means[3],
                    collision=means[4],
                    boundary=means[5],
                    score=score,
                )
            )
        return tuple(result)

    def select_basis(self, state: QiFieldState) -> BasisSelection:
        evidence = self.basis_evidence(state)
        supported = sorted(
            (item for item in evidence if item.support),
            key=lambda item: (item.score, item.basis_id),
        )
        if not supported:
            return BasisSelection(
                status="no_basis_evidence",
                basis_id=None,
                basis_name=None,
                margin=None,
                evidence=evidence,
                field_sha256=self._tensor_sha256(state.field),
            )
        best = supported[0]
        if best.score > self.config.max_basis_score:
            return BasisSelection(
                status="no_eligible_basis",
                basis_id=None,
                basis_name=None,
                margin=None,
                evidence=evidence,
                field_sha256=self._tensor_sha256(state.field),
            )
        margin = (
            supported[1].score - best.score
            if len(supported) > 1
            else self.config.max_basis_score - best.score
        )
        if margin <= self.config.selection_margin:
            return BasisSelection(
                status="ambiguous",
                basis_id=None,
                basis_name=None,
                margin=margin,
                evidence=evidence,
                field_sha256=self._tensor_sha256(state.field),
            )
        return BasisSelection(
            status="selected",
            basis_id=supported[0].basis_id,
            basis_name=supported[0].basis_name,
            margin=margin,
            evidence=evidence,
            field_sha256=self._tensor_sha256(state.field),
        )

    def clear_basis_evidence(self, state: QiFieldState, basis_id: int) -> QiFieldState:
        self.validate_state(state)
        if not 0 <= basis_id < self.config.basis_count:
            raise QiFieldError("basis_id is outside the configured capacity")
        result = QiFieldState(field=state.field.clone())
        packed = self._packed(result)
        start = self.config.basis_evidence_start + basis_id * self.config.basis_evidence_width
        packed[
            0,
            8,
            start : start + self.config.basis_evidence_width,
            0,
        ] = 0.0
        self.validate_state(result)
        return result
