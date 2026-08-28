"""Canonical typed state and checkpoint for the Cassi field organism.

The organism owns one adaptive ``torch.float32`` arena with logical shape
``[T, S, 9, M]``.  Every named sector is a non-overlapping typed view into
whole tiles of that arena.  Runtime helpers may decode transient Qi/world
objects, but they never become a second checkpoint owner.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
import tempfile
from dataclasses import asdict, dataclass, field as dataclass_field
from pathlib import Path
from typing import Any, Final, Mapping

import torch
from torch import Tensor

from cassi_qi_field import QI_COMPONENT_ORDER, QiFieldConfig, QiFieldController, QiFieldState
from cassi_world_model import CassiWorldModelConfig, CassiWorldModelState

ORGANISM_CHECKPOINT_SCHEMA: Final[str] = "cassi.organism.checkpoint.v3"
ORGANISM_LAYOUT_ID: Final[str] = "cassi.organism.arena-t-s-9-m.v3"
ORGANISM_CONSTITUTION_SCHEMA: Final[str] = "cassi.organism.constitution.v3"
ORGANISM_SECTOR_ORDER: Final[tuple[str, ...]] = (
    "qi",
    "b",
    "a",
    "z",
    "y",
    "u",
    "u_hat",
    "h",
    "m",
    "m_hat",
    "p",
    "g",
    "e_Theta",
    "Theta",
    "Sigma",
)
ACTION_META_WIDTH: Final[int] = 8
ACTION_FITNESS_OFFSET: Final[int] = 0
ACTION_SCORE_OFFSET: Final[int] = 1
ACTION_MASS_OFFSET: Final[int] = 2
ACTION_COMMITMENT_OFFSET: Final[int] = 3
ACTION_BAND_OFFSET: Final[int] = 4
ACTION_VIABILITY_OFFSET: Final[int] = 5
ACTION_PREDICTED_COST_OFFSET: Final[int] = 6
_MAX_CAUSAL_SCALAR: Final[float] = 1.0e6
ACTION_INFORMATION_OFFSET: Final[int] = 7
_MAX_CHECKPOINT_BYTES: Final[int] = 256 * 1024 * 1024
_MAX_METADATA_BYTES: Final[int] = 256 * 1024
_MAX_ARENA_VALUES: Final[int] = 64 * 1024 * 1024
_MAX_EXACT_FLOAT32_INTEGER: Final[int] = 1 << 24
_HEX: Final[frozenset[str]] = frozenset("0123456789abcdef")



class CassiOrganismError(ValueError):
    """An organism layout, state, sector, or checkpoint invariant failed."""


def _positive_int(name: str, value: object, *, maximum: int = 1 << 20) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > maximum:
        raise CassiOrganismError(f"{name} must be an integer in [1, {maximum}]")
    return value


def _canonical(value: Mapping[str, Any]) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise CassiOrganismError(f"value is not canonical finite JSON: {error}") from error


def _canonical_metadata(value: bytes | bytearray | memoryview | Mapping[str, Any]) -> bytes:
    if isinstance(value, Mapping):
        raw = _canonical(value)
    elif isinstance(value, bool) or not isinstance(value, (bytes, bytearray, memoryview)):
        raise CassiOrganismError("organism metadata must be canonical JSON bytes or a mapping")
    else:
        raw = bytes(value)
    if not raw or len(raw) > _MAX_METADATA_BYTES:
        raise CassiOrganismError("organism metadata exceeds its bounded size")
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CassiOrganismError("organism metadata is not valid UTF-8 JSON") from error
    if not isinstance(decoded, dict) or _canonical(decoded) != raw:
        raise CassiOrganismError("organism metadata is not a canonical JSON object")
    return raw


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _require_digest(name: str, value: object) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(char not in _HEX for char in value):
        raise CassiOrganismError(f"{name} must be a lowercase SHA-256 digest")
    return value


def _ceil_div(value: int, divisor: int) -> int:
    return (value + divisor - 1) // divisor

def _finite_real(name: str, value: object, *, minimum: float | None = None, maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CassiOrganismError(f"{name} must be a finite real number")
    result = float(value)
    if not math.isfinite(result):
        raise CassiOrganismError(f"{name} must be a finite real number")
    if minimum is not None and result < minimum:
        raise CassiOrganismError(f"{name} must be at least {minimum}")
    if maximum is not None and result > maximum:
        raise CassiOrganismError(f"{name} must be at most {maximum}")
    return result


@dataclass(frozen=True)
class CassiOrganismLawConfig:
    """Fixed coefficients for one constrained extended-becoming step."""

    time_step: float = 0.1
    conversion_rate: float = 0.05
    initial_boundary: float = 0.5
    boundary_self_rate: float = 0.2
    boundary_world_rate: float = 0.04
    boundary_unexpected_rate: float = 0.15
    reserve_capacity: float = 1.0
    initial_reserve: float = 1.0
    passive_dissipation: float = 0.001
    field_step_cost: float = 0.002
    history_write_cost: float = 0.001
    model_step_cost: float = 0.002
    shadow_step_cost: float = 0.0001
    action_step_cost: float = 0.002
    attention_step_cost: float = 0.001
    plasticity_step_cost: float = 0.002
    history_decay: float = 0.98
    model_rate: float = 0.25
    shadow_rate: float = 0.2
    population_diffusion: float = 0.04
    population_selection_rate: float = 0.35
    attention_diffusion: float = 0.04
    attention_selection_rate: float = 0.35
    eligibility_decay: float = 0.9
    eligibility_rate: float = 0.2
    theta_prediction_rate: float = 0.01
    theta_outcome_rate: float = 0.02
    theta_homeostasis: float = 0.001
    theta_absolute_bound: float = 1.0
    theta_step_bound: float = 0.02
    commitment_threshold: float = 0.8
    release_threshold: float = 0.5
    unexpected_threshold: float = 0.25

    def __post_init__(self) -> None:
        unit_interval = (
            "time_step",
            "conversion_rate",
            "initial_boundary",
            "boundary_self_rate",
            "boundary_world_rate",
            "boundary_unexpected_rate",
            "history_decay",
            "model_rate",
            "shadow_rate",
            "population_diffusion",
            "population_selection_rate",
            "attention_diffusion",
            "attention_selection_rate",
            "eligibility_decay",
            "eligibility_rate",
            "theta_prediction_rate",
            "theta_outcome_rate",
            "theta_homeostasis",
            "theta_step_bound",
            "commitment_threshold",
            "release_threshold",
            "unexpected_threshold",
        )
        for name in unit_interval:
            object.__setattr__(self, name, _finite_real(name, getattr(self, name), minimum=0.0, maximum=1.0))
        positive = ("reserve_capacity", "theta_absolute_bound")
        for name in positive:
            object.__setattr__(
                self,
                name,
                _finite_real(
                    name,
                    getattr(self, name),
                    minimum=torch.finfo(torch.float32).eps,
                    maximum=_MAX_CAUSAL_SCALAR,
                ),
            )
        nonnegative = (
            "initial_reserve",
            "passive_dissipation",
            "field_step_cost",
            "history_write_cost",
            "model_step_cost",
            "shadow_step_cost",
            "action_step_cost",
            "attention_step_cost",
            "plasticity_step_cost",
        )
        for name in nonnegative:
            object.__setattr__(
                self,
                name,
                _finite_real(
                    name,
                    getattr(self, name),
                    minimum=0.0,
                    maximum=_MAX_CAUSAL_SCALAR,
                ),
            )
        if self.initial_reserve > self.reserve_capacity:
            raise CassiOrganismError("initial_reserve cannot exceed reserve_capacity")
        if self.release_threshold >= self.commitment_threshold:
            raise CassiOrganismError("release_threshold must be below commitment_threshold")
        if self.theta_step_bound > self.theta_absolute_bound:
            raise CassiOrganismError("theta_step_bound cannot exceed theta_absolute_bound")

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CassiOrganismLawConfig":
        if not isinstance(value, Mapping):
            raise CassiOrganismError("organism law configuration must be a mapping")
        expected = set(cls.__dataclass_fields__)
        unknown = set(value) - expected
        if unknown:
            raise CassiOrganismError(f"organism law configuration has unknown fields: {sorted(unknown)}")
        try:
            return cls(**dict(value))
        except CassiOrganismError:
            raise
        except (TypeError, ValueError) as error:
            raise CassiOrganismError(f"invalid organism law configuration: {error}") from error


@dataclass(frozen=True)
class CassiOrganismConfig:
    """Fixed dimensions and identities that define one organism arena."""

    scale_count: int
    qi_mode_count: int
    qi_config_fingerprint: str
    qi_phi: float
    qi_max_mode_amplitude: float
    qi_max_mean_energy: float
    qi_epsilon_clip: float
    qi_alphabet_size: int
    qi_primes: tuple[int, ...]
    world_mode_count: int
    world_latent_dim: int
    world_action_dim: int
    world_observation_dim: int
    world_config_fingerprint: str
    action_horizon: int = 64
    shadow_branches: int = 8
    shadow_steps: int = 64
    history_capacity: int = 128
    history_width: int = 12
    action_population_capacity: int = 16
    attention_slots: int = 256
    theta_width: int = 256
    teacher_layer_count: int = 64
    teacher_layer_width: int = 5120
    law: CassiOrganismLawConfig = dataclass_field(default_factory=CassiOrganismLawConfig)
    constitution_schema: str = ORGANISM_CONSTITUTION_SCHEMA

    def __post_init__(self) -> None:
        for name in (
            "scale_count",
            "qi_mode_count",
            "world_mode_count",
            "world_latent_dim",
            "world_action_dim",
            "world_observation_dim",
            "action_horizon",
            "shadow_branches",
            "shadow_steps",
            "history_capacity",
            "history_width",
            "action_population_capacity",
            "attention_slots",
            "theta_width",
            "teacher_layer_count",
            "teacher_layer_width",
        ):
            object.__setattr__(self, name, _positive_int(name, getattr(self, name)))
        object.__setattr__(
            self,
            "qi_phi",
            _finite_real("qi_phi", self.qi_phi, minimum=torch.finfo(torch.float32).eps),
        )
        object.__setattr__(
            self,
            "qi_max_mode_amplitude",
            _finite_real(
                "qi_max_mode_amplitude",
                self.qi_max_mode_amplitude,
                minimum=torch.finfo(torch.float32).eps,
            ),
        )
        object.__setattr__(
            self,
            "qi_max_mean_energy",
            _finite_real(
                "qi_max_mean_energy",
                self.qi_max_mean_energy,
                minimum=torch.finfo(torch.float32).eps,
            ),
        )
        object.__setattr__(
            self,
            "qi_epsilon_clip",
            _finite_real(
                "qi_epsilon_clip",
                self.qi_epsilon_clip,
                minimum=torch.finfo(torch.float32).eps,
            ),
        )
        object.__setattr__(self, "qi_alphabet_size", _positive_int("qi_alphabet_size", self.qi_alphabet_size))
        if isinstance(self.qi_primes, (str, bytes, bytearray)):
            raise CassiOrganismError("qi_primes must contain one fixed prime per Qi scale")
        try:
            primes = tuple(self.qi_primes)
        except TypeError as error:
            raise CassiOrganismError("qi_primes must contain one fixed prime per Qi scale") from error
        if (
            len(primes) != self.scale_count
            or any(isinstance(value, bool) or not isinstance(value, int) or value < 3 for value in primes)
            or len(set(primes)) != len(primes)
        ):
            raise CassiOrganismError("qi_primes must contain distinct integers greater than two for every Qi scale")
        object.__setattr__(self, "qi_primes", primes)
        if self.qi_mode_count < 4 or self.qi_mode_count % 2:
            raise CassiOrganismError("qi_mode_count must be even and at least four")
        if self.attention_slots < 7:
            raise CassiOrganismError(
                "attention_slots must provide all seven causal work allocations"
            )
        if self.theta_width < 4:
            raise CassiOrganismError("theta_width must provide coefficients and two maturation slots")
        if self.shadow_branches > self.action_population_capacity:
            raise CassiOrganismError("shadow_branches cannot exceed action_population_capacity")
        if (
            self.teacher_layer_count > 1024
            or self.teacher_layer_width > 65536
            or self.teacher_layer_count * self.teacher_layer_width > 16 * 1024 * 1024
        ):
            raise CassiOrganismError("teacher weave exceeds its bounded layer geometry")
        if self.action_population_capacity * self.shadow_steps > 65536:
            raise CassiOrganismError(
                "action-population shadow geometry exceeds 65536 bounded future steps"
            )
        _require_digest("Qi configuration fingerprint", self.qi_config_fingerprint)
        _require_digest("world configuration fingerprint", self.world_config_fingerprint)
        if not isinstance(self.constitution_schema, str) or not self.constitution_schema:
            raise CassiOrganismError("constitution_schema must be nonempty")
        if not isinstance(self.law, CassiOrganismLawConfig):
            raise CassiOrganismError("law must be a CassiOrganismLawConfig")
        if self.constitution_schema != ORGANISM_CONSTITUTION_SCHEMA:
            raise CassiOrganismError("constitution_schema must use the current organism constitution")
        if math.prod(self.arena_shape) > _MAX_ARENA_VALUES:
            raise CassiOrganismError("organism arena exceeds its bounded value count")

    @classmethod
    def from_components(
        cls,
        qi: QiFieldConfig,
        world: CassiWorldModelConfig,
        *,
        action_horizon: int = 64,
        **overrides: Any,
    ) -> "CassiOrganismConfig":
        if not isinstance(qi, QiFieldConfig) or not isinstance(world, CassiWorldModelConfig):
            raise CassiOrganismError("Qi and world configurations are required")
        return cls(
            scale_count=qi.scale_count,
            qi_mode_count=qi.mode_count,
            qi_config_fingerprint=qi.fingerprint,
            qi_phi=qi.phi,
            qi_max_mode_amplitude=qi.physics.max_mode_amplitude,
            qi_max_mean_energy=qi.physics.max_mean_energy,
            qi_epsilon_clip=qi.epsilon_clip,
            qi_alphabet_size=qi.alphabet_size,
            qi_primes=qi.primes,
            world_mode_count=world.mode_count,
            world_latent_dim=world.latent_dim,
            world_action_dim=world.action_dim,
            world_observation_dim=world.observation_dim,
            world_config_fingerprint=world.fingerprint,
            action_horizon=action_horizon,
            **overrides,
        )

    @property
    def tile_capacity(self) -> int:
        return self.scale_count * len(QI_COMPONENT_ORDER) * self.qi_mode_count

    @property
    def world_field_width(self) -> int:
        return 8 * self.world_mode_count

    @property
    def model_width(self) -> int:
        return self.world_field_width + self.world_latent_dim + 1

    @property
    def action_width(self) -> int:
        return self.action_horizon * self.world_action_dim

    @property
    def arena_shape(self) -> tuple[int, int, int, int]:
        return (CassiOrganismLayout.build(self).tile_count, self.scale_count, len(QI_COMPONENT_ORDER), self.qi_mode_count)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CassiOrganismConfig":
        if not isinstance(value, Mapping):
            raise CassiOrganismError("organism configuration must be a mapping")
        fields = dict(value)
        if isinstance(fields.get("law"), Mapping):
            fields["law"] = CassiOrganismLawConfig.from_dict(fields["law"])
        if "qi_primes" in fields:
            try:
                fields["qi_primes"] = tuple(fields["qi_primes"])
            except TypeError as error:
                raise CassiOrganismError("qi_primes must contain one fixed prime per Qi scale") from error
        try:
            return cls(**fields)
        except (TypeError, CassiOrganismError) as error:
            if isinstance(error, CassiOrganismError):
                raise
            raise CassiOrganismError(f"invalid organism configuration: {error}") from error

    @property
    def fingerprint(self) -> str:
        return _digest(_canonical(self.to_dict()))


@dataclass(frozen=True)
class CassiArenaRange:
    """One typed, whole-tile allocation within the arena."""

    name: str
    start_tile: int
    tile_count: int
    width: int
    logical_shape: tuple[int, ...]

    @property
    def stop_tile(self) -> int:
        return self.start_tile + self.tile_count




@dataclass(frozen=True)
class CassiOrganismLayout:
    """Deterministic non-overlapping sector registry."""

    ranges: tuple[CassiArenaRange, ...]
    tile_capacity: int
    tile_count: int
    qi_phi: float

    @classmethod
    def build(cls, config: CassiOrganismConfig) -> "CassiOrganismLayout":
        capacity = config.scale_count * len(QI_COMPONENT_ORDER) * config.qi_mode_count
        widths: tuple[tuple[str, int, tuple[int, ...]], ...] = (
            ("qi", capacity, (config.scale_count, len(QI_COMPONENT_ORDER), config.qi_mode_count)),
            ("b", config.scale_count, (config.scale_count,)),
            ("a", config.scale_count, (config.scale_count,)),
            ("z", config.scale_count, (config.scale_count,)),
            ("y", 8 * config.scale_count, (config.scale_count, 8)),
            ("u", config.action_width, (config.action_horizon, config.world_action_dim)),
            ("u_hat", config.action_width, (config.action_horizon, config.world_action_dim)),
            ("h", config.history_capacity * config.history_width, (config.history_capacity, config.history_width)),
            ("m", config.model_width, (config.model_width,)),
            (
                "m_hat",
                config.action_population_capacity * config.shadow_steps * config.model_width,
                (config.action_population_capacity, config.shadow_steps, config.model_width),
            ),
            (
                "p",
                config.action_population_capacity * (config.action_width + ACTION_META_WIDTH),
                (config.action_population_capacity, config.action_width + ACTION_META_WIDTH),
            ),
            ("g", config.attention_slots, (config.attention_slots,)),
            ("e_Theta", config.theta_width, (config.theta_width,)),
            ("Theta", config.theta_width, (config.theta_width,)),
            (
                "Sigma",
                1 + config.world_latent_dim + config.teacher_layer_count,
                (1 + config.world_latent_dim + config.teacher_layer_count,),
            ),
        )
        start = 0
        ranges: list[CassiArenaRange] = []
        for name, width, shape in widths:
            tiles = _ceil_div(width, capacity)
            ranges.append(CassiArenaRange(name, start, tiles, width, shape))
            start += tiles
        return cls(
            tuple(ranges),
            capacity,
            start,
            config.qi_phi,
        )

    def sector(self, name: str) -> CassiArenaRange:
        for entry in self.ranges:
            if entry.name == name:
                return entry
        raise CassiOrganismError(f"unknown organism sector: {name}")

    @property
    def fingerprint(self) -> str:
        return _digest(
            _canonical(
                {
                    "layout_id": ORGANISM_LAYOUT_ID,
                    "tile_capacity": self.tile_capacity,
                    "tile_count": self.tile_count,
                    "qi_phi": self.qi_phi,
                    "ranges": [
                        {
                            "name": entry.name,
                            "start_tile": entry.start_tile,
                            "tile_count": entry.tile_count,
                            "width": entry.width,
                            "logical_shape": list(entry.logical_shape),
                        }
                        for entry in self.ranges
                    ],
                }
            )
        )


@dataclass(frozen=True, init=False)
class CassiOrganismState:
    """Immutable successor-state handle owning one private organism tensor."""

    _arena: Tensor
    config_fingerprint: str
    layout: CassiOrganismLayout
    metadata: bytes

    def __init__(
        self,
        arena: Tensor,
        config_fingerprint: str,
        layout: CassiOrganismLayout,
        metadata: bytes,
    ) -> None:
        if not torch.is_tensor(arena):
            raise CassiOrganismError("organism arena must be a torch.Tensor")
        try:
            owned = arena.detach().contiguous().clone()
        except Exception as error:
            raise CassiOrganismError(
                f"organism arena cannot be owned: {error}"
            ) from error
        object.__setattr__(self, "_arena", owned)
        object.__setattr__(self, "config_fingerprint", config_fingerprint)
        object.__setattr__(self, "layout", layout)
        object.__setattr__(self, "metadata", metadata)

    @classmethod
    def _from_owned(
        cls,
        arena: Tensor,
        config_fingerprint: str,
        layout: CassiOrganismLayout,
        metadata: bytes,
    ) -> "CassiOrganismState":
        """Construct from a fresh tensor whose sole owner is this state."""
        result = object.__new__(cls)
        object.__setattr__(result, "_arena", arena.detach())
        object.__setattr__(result, "config_fingerprint", config_fingerprint)
        object.__setattr__(result, "layout", layout)
        object.__setattr__(result, "metadata", metadata)
        return result

    @property
    def arena(self) -> Tensor:
        """Return a detached snapshot; mutating it cannot change this state."""
        return self._arena.detach().clone()

    @property
    def device(self) -> torch.device:
        return self._arena.device

    @property
    def dtype(self) -> torch.dtype:
        return self._arena.dtype
    @property
    def layout_fingerprint(self) -> str:
        return self.layout.fingerprint

    def validate(
        self,
        config: CassiOrganismConfig,
        *,
        device: torch.device | None = None,
    ) -> None:
        if not isinstance(config, CassiOrganismConfig):
            raise CassiOrganismError("organism configuration is required")
        layout = CassiOrganismLayout.build(config)
        if not torch.is_tensor(self._arena):
            raise CassiOrganismError("organism arena must be a torch.Tensor")
        if tuple(self._arena.shape) != config.arena_shape:
            raise CassiOrganismError(f"organism arena must have shape {config.arena_shape}")
        if self._arena.dtype is not torch.float32:
            raise CassiOrganismError("organism arena must use torch.float32")
        if device is not None and self._arena.device != device:
            raise CassiOrganismError("organism arena is on the wrong device")
        if not bool(torch.isfinite(self._arena).all().item()):
            raise CassiOrganismError("organism arena contains non-finite values")
        if self.config_fingerprint != config.fingerprint:
            raise CassiOrganismError("organism configuration fingerprint mismatch")
        if self.layout != layout:
            raise CassiOrganismError("organism layout fingerprint mismatch")
        _canonical_metadata(self.metadata)
        for entry in layout.ranges:
            storage = self._arena[entry.start_tile : entry.stop_tile].reshape(-1)
            if storage.numel() > entry.width and bool(torch.any(storage[entry.width :] != 0.0).item()):
                raise CassiOrganismError(f"{entry.name} reserved tail is not zero")
        model = self._sector_view("m")
        step = float(model.reshape(-1)[-1].item())
        if step < 0.0 or step > _MAX_EXACT_FLOAT32_INTEGER or step != math.floor(step):
            raise CassiOrganismError("world step is not an exact bounded integer")
        if bool(torch.any(model[:-1].abs() > 1.0 + 1.0e-6).item()):
            raise CassiOrganismError("world-model core must stay in [-1, 1]")
        qi = self._sector_view("qi")
        if bool(torch.any(qi[:, :8, :].abs() > config.qi_max_mode_amplitude + 1.0e-6).item()):
            raise CassiOrganismError("Qi modes exceed their configured amplitude bound")
        qi_energy = qi[:, :8, :].square().sum(dim=1).mean(dim=1)
        if bool(torch.any(qi_energy > config.qi_max_mean_energy + 1.0e-5).item()):
            raise CassiOrganismError("Qi modes exceed their configured mean-energy bound")
        if bool(
            torch.any(
                (qi[:, 8, :] < 0.0)
                | (qi[:, 8, :] > config.qi_epsilon_clip + 1.0e-6)
            ).item()
        ):
            raise CassiOrganismError("Qi imbalance memory exceeds its configured bound")
        boundary = self._sector_view("b")
        reserve = self._sector_view("a")
        viability = self._sector_view("z")
        if bool(torch.any((boundary < 0.0) | (boundary > 1.0)).item()):
            raise CassiOrganismError("boundary membership must stay in [0, 1]")
        if bool(torch.any((reserve < 0.0) | (reserve > config.law.reserve_capacity)).item()):
            raise CassiOrganismError("resource reserve violates its configured bounds")
        expected_viability = torch.clamp(
            boundary * reserve / config.law.reserve_capacity,
            min=0.0,
            max=1.0,
        )
        if not torch.allclose(viability, expected_viability, atol=1.0e-6, rtol=1.0e-6):
            raise CassiOrganismError("viability must equal the canonical boundary-resource product")
        sensation = self._sector_view("y")
        if bool(torch.any((sensation < -1.0) | (sensation > 1.0)).item()):
            raise CassiOrganismError("sensation state must stay in [-1, 1]")
        history = self._sector_view("h")
        if bool(torch.any(history.abs() > 1.0 + 1.0e-6).item()):
            raise CassiOrganismError("history rows must stay in [-1, 1]")
        action = self._sector_view("u")
        imagined_action = self._sector_view("u_hat")
        if bool(torch.any((action < -1.0) | (action > 1.0)).item()) or bool(
            torch.any((imagined_action < -1.0) | (imagined_action > 1.0)).item()
        ):
            raise CassiOrganismError("action trajectories must stay in [-1, 1]")
        shadow_futures = self._sector_view("m_hat")
        shadow_core = shadow_futures[..., :-1]
        shadow_steps = shadow_futures[..., -1]
        if bool(torch.any((shadow_core < -1.0) | (shadow_core > 1.0)).item()):
            raise CassiOrganismError("shadow-model cores must stay in [-1, 1]")
        if bool(
            torch.any(
                (shadow_steps < 0.0)
                | (shadow_steps > _MAX_EXACT_FLOAT32_INTEGER)
                | (shadow_steps != torch.floor(shadow_steps))
            ).item()
        ):
            raise CassiOrganismError("shadow-model steps must be exact bounded integers")
        population = self._sector_view("p")
        actions = population[:, : config.action_width]
        metadata = population[:, config.action_width :]
        fitness = metadata[:, ACTION_FITNESS_OFFSET]
        scores = metadata[:, ACTION_SCORE_OFFSET]
        masses = metadata[:, ACTION_MASS_OFFSET]
        commitment = metadata[:, ACTION_COMMITMENT_OFFSET]
        bands = metadata[:, ACTION_BAND_OFFSET]
        population_viability = metadata[:, ACTION_VIABILITY_OFFSET]
        predicted_cost = metadata[:, ACTION_PREDICTED_COST_OFFSET]
        information = metadata[:, ACTION_INFORMATION_OFFSET]
        if bool(torch.any((actions < -1.0) | (actions > 1.0)).item()):
            raise CassiOrganismError("action-population trajectories must stay in [-1, 1]")
        if bool(torch.any((fitness < -1.0) | (fitness > 1.0)).item()):
            raise CassiOrganismError("action-population fitness must stay in [-1, 1]")
        score_sum = scores.sum()
        if bool(torch.any((scores < 0.0) | (scores > 1.0)).item()) or not (
            torch.isclose(score_sum, torch.zeros_like(score_sum), atol=1.0e-6, rtol=0.0)
            or torch.isclose(score_sum, torch.ones_like(score_sum), atol=1.0e-5, rtol=1.0e-5)
        ):
            raise CassiOrganismError("action-population scores must be empty or a probability simplex")
        if bool(torch.any(masses < 0.0).item()) or not torch.isclose(
            masses.sum(),
            torch.ones((), dtype=masses.dtype, device=masses.device),
            atol=1.0e-5,
            rtol=1.0e-5,
        ):
            raise CassiOrganismError("action-population mass must be a probability simplex")
        if bool(torch.any((commitment < 0.0) | (commitment > 1.0)).item()):
            raise CassiOrganismError("action-population commitment must stay in [0, 1]")
        max_band = math.ceil(config.action_population_capacity / config.shadow_branches) - 1
        if bool(
            torch.any((bands < -1.0) | (bands > float(max_band)) | (bands != torch.round(bands))).item()
        ):
            raise CassiOrganismError("action-population band identity is invalid")
        expected_population_viability = viability.mean().expand_as(population_viability)
        if not torch.allclose(
            population_viability,
            expected_population_viability,
            atol=1.0e-6,
            rtol=1.0e-6,
        ):
            raise CassiOrganismError("action-population viability is stale")
        if bool(torch.any((predicted_cost < 0.0) | (predicted_cost > 1.0)).item()):
            raise CassiOrganismError("action-population predicted cost must stay in [0, 1]")
        if bool(torch.any((information < 0.0) | (information > 1.0)).item()):
            raise CassiOrganismError("action-population information must stay in [0, 1]")
        attention = self._sector_view("g")
        if bool(torch.any(attention < 0.0).item()) or not torch.isclose(
            attention.sum(),
            torch.ones((), dtype=attention.dtype, device=attention.device),
            atol=1.0e-5,
            rtol=1.0e-5,
        ):
            raise CassiOrganismError("attention must be a conserved probability simplex")
        eligibility = self._sector_view("e_Theta")
        if bool(torch.any(eligibility.abs() > 1.0).item()):
            raise CassiOrganismError("constitutive eligibility must stay in [-1, 1]")
        theta = self._sector_view("Theta")
        sigma = self._sector_view("Sigma")
        if bool(torch.any(theta.abs() > config.law.theta_absolute_bound).item()):
            raise CassiOrganismError("constitutive state violates its absolute bound")
        if bool(torch.any((sigma < 0.0) | (sigma > 10.0)).item()):
            raise CassiOrganismError("uncertainty state violates its bounded nonnegative contract")

    def _sector_view(self, name: str) -> Tensor:
        entry = self.layout.sector(name)
        return self._arena[entry.start_tile : entry.stop_tile].reshape(-1)[: entry.width].reshape(entry.logical_shape)

    def sector(self, config: CassiOrganismConfig, name: str) -> Tensor:
        """Return an owned snapshot of one typed sector."""
        if config.fingerprint != self.config_fingerprint or CassiOrganismLayout.build(config) != self.layout:
            raise CassiOrganismError("sector request uses the wrong organism configuration")
        return self._sector_view(name).detach().clone()

    @property
    def qi(self) -> Tensor:
        return self._sector_view("qi").detach().clone()

    @property
    def rho(self) -> Tensor:
        """Derived total Yang/Yin density by scale and mode."""
        qi = self._sector_view("qi")
        return qi[:, :4, :].square().sum(dim=1)

    @property
    def epsilon(self) -> Tensor:
        """Derived Yang-minus-phi-Yin imbalance by scale and mode."""
        qi = self._sector_view("qi")
        yang = qi[:, :2, :].square().sum(dim=1)
        yin = qi[:, 2:4, :].square().sum(dim=1)
        return yang - self.layout.qi_phi * yin

    @property
    def q(self) -> Tensor:
        """Derived bounded density/balance diagnostic; never an owned sector."""
        qi = self._sector_view("qi")
        rho2 = qi[:, :4, :].square().sum(dim=1).square()
        yang = qi[:, :2, :].square().sum(dim=1)
        yin = qi[:, 2:4, :].square().sum(dim=1)
        epsilon = yang - self.layout.qi_phi * yin
        phi_inverse2 = self.layout.qi_phi**-2
        return rho2 / (rho2 + phi_inverse2 + epsilon.square()).clamp_min(torch.finfo(qi.dtype).tiny)

    @property
    def epsilon2_ema(self) -> Tensor:
        return self._sector_view("qi")[:, 8, :].detach().clone()

def _sector_property(name: str):
    def read_sector(self: CassiOrganismState) -> Tensor:
        return self._sector_view(name).detach().clone()

    return property(read_sector)


for _sector_name in ORGANISM_SECTOR_ORDER[1:]:
    setattr(CassiOrganismState, _sector_name, _sector_property(_sector_name))




def empty_organism_state(
    config: CassiOrganismConfig,
    *,
    device: torch.device | str = "cpu",
    metadata: bytes | bytearray | memoryview | Mapping[str, Any] = {},
) -> CassiOrganismState:
    if not isinstance(config, CassiOrganismConfig):
        raise CassiOrganismError("organism configuration is required")
    try:
        target = torch.device(device)
        arena = torch.zeros(config.arena_shape, dtype=torch.float32, device=target)
        layout = CassiOrganismLayout.build(config)

        def initialized_view(name: str) -> Tensor:
            entry = layout.sector(name)
            return arena[entry.start_tile : entry.stop_tile].reshape(-1)[: entry.width].reshape(entry.logical_shape)

        initialized_view("b").fill_(config.law.initial_boundary)
        initialized_view("a").fill_(config.law.initial_reserve)
        initialized_view("z").fill_(
            config.law.initial_boundary * config.law.initial_reserve / config.law.reserve_capacity
        )
        initialized_view("g").fill_(1.0 / config.attention_slots)
        population = initialized_view("p")
        population[:, config.action_width + ACTION_MASS_OFFSET].fill_(1.0 / config.action_population_capacity)
        population[:, config.action_width + ACTION_BAND_OFFSET].fill_(-1.0)
        population[:, config.action_width + ACTION_VIABILITY_OFFSET].fill_(
            config.law.initial_boundary
            * config.law.initial_reserve
            / config.law.reserve_capacity
        )
        times = torch.arange(config.action_horizon, dtype=torch.float32, device=target).reshape(-1, 1)
        dimensions = torch.arange(config.world_action_dim, dtype=torch.float32, device=target).reshape(1, -1)
        strength = 1.0 / max(1, config.action_horizon)
        for index in range(1, config.action_population_capacity):
            phase = (2.0 * math.pi * index / config.action_population_capacity) + dimensions * (math.pi / 4.0)
            trajectory = strength * torch.sin(phase + times * (math.pi / max(1, config.action_horizon - 1)))
            population[index, : config.action_width].copy_(trajectory.reshape(-1))
    except Exception as error:
        raise CassiOrganismError(f"organism arena cannot be allocated: {error}") from error
    state = CassiOrganismState._from_owned(
        arena, config.fingerprint, layout, _canonical_metadata(metadata)
    )
    state.validate(config, device=target)
    return state


def _copy_sector(arena: Tensor, config: CassiOrganismConfig, name: str, value: Tensor) -> None:
    entry = CassiOrganismLayout.build(config).sector(name)
    if not torch.is_tensor(value) or tuple(value.shape) != entry.logical_shape:
        raise CassiOrganismError(f"{name} must have shape {entry.logical_shape}")
    if value.dtype is not torch.float32 or value.device != arena.device or not bool(torch.isfinite(value).all().item()):
        raise CassiOrganismError(f"{name} must be finite float32 on the arena device")
    target = arena[entry.start_tile : entry.stop_tile].reshape(-1)
    target.zero_()
    target[: entry.width].copy_(value.detach().reshape(-1))


def successor_organism_state(
    state: CassiOrganismState,
    config: CassiOrganismConfig,
    *,
    sectors: Mapping[str, Tensor] | None = None,
    metadata: bytes | bytearray | memoryview | Mapping[str, Any] | None = None,
) -> CassiOrganismState:
    state.validate(config)
    updates = {} if sectors is None else dict(sectors)
    unknown = set(updates) - set(ORGANISM_SECTOR_ORDER)
    if unknown:
        raise CassiOrganismError(f"unknown organism sectors: {sorted(unknown)}")
    arena = state._arena.detach().clone()
    for name, value in updates.items():
        _copy_sector(arena, config, name, value)
    result = CassiOrganismState._from_owned(
        arena,
        config.fingerprint,
        state.layout,
        state.metadata if metadata is None else _canonical_metadata(metadata),
    )
    result.validate(config, device=arena.device)
    return result


def qi_state_from_organism(state: CassiOrganismState, config: CassiOrganismConfig) -> QiFieldState:
    state.validate(config)
    field = state._sector_view("qi").reshape(config.scale_count, 9 * config.qi_mode_count, 1).detach().clone()
    return QiFieldState(field)


def world_state_from_organism(state: CassiOrganismState, config: CassiOrganismConfig) -> CassiWorldModelState:
    state.validate(config)
    model = state._sector_view("m").reshape(-1)
    field = model[: config.world_field_width].reshape(config.world_field_width, 1).detach().clone()
    stochastic = model[
        config.world_field_width : config.world_field_width + config.world_latent_dim
    ].reshape(1, config.world_latent_dim).detach().clone()
    step = torch.tensor([int(model[-1].item())], dtype=torch.int64, device=state.device)
    return CassiWorldModelState(field, stochastic, step)


def _state_sectors(
    config: CassiOrganismConfig,
    qi_state: QiFieldState,
    world_state: CassiWorldModelState,
) -> dict[str, Tensor]:
    if qi_state.batch_size != 1 or qi_state.field.dtype is not torch.float32:
        raise CassiOrganismError("Qi state must be one-lane float32")
    if world_state.batch_size != 1 or world_state.field.dtype is not torch.float32 or world_state.stochastic.dtype is not torch.float32:
        raise CassiOrganismError("world state must be one-lane float32")
    if qi_state.field.device != world_state.field.device or world_state.field.device != world_state.stochastic.device or world_state.field.device != world_state.step.device:
        raise CassiOrganismError("Qi and world states must share one device")
    if tuple(qi_state.field.shape) != (config.scale_count, 9 * config.qi_mode_count, 1):
        raise CassiOrganismError("Qi state shape does not match the organism layout")
    if tuple(world_state.field.shape) != (config.world_field_width, 1) or tuple(world_state.stochastic.shape) != (1, config.world_latent_dim) or tuple(world_state.step.shape) != (1,) or world_state.step.dtype is not torch.int64:
        raise CassiOrganismError("world state shape does not match the organism layout")
    if not bool(torch.isfinite(qi_state.field).all().item()) or not bool(torch.isfinite(world_state.field).all().item()) or not bool(torch.isfinite(world_state.stochastic).all().item()):
        raise CassiOrganismError("Qi and world states must be finite")
    step = int(world_state.step.item())
    if step < 0 or step > _MAX_EXACT_FLOAT32_INTEGER:
        raise CassiOrganismError("world step exceeds exact float32 integer storage")
    model = torch.zeros(config.model_width, dtype=torch.float32, device=world_state.field.device)
    model[: config.world_field_width].copy_(world_state.field.reshape(-1))
    model[config.world_field_width : config.world_field_width + config.world_latent_dim].copy_(
        world_state.stochastic.reshape(-1)
    )
    model[-1] = step
    return {
        "qi": qi_state.field.reshape(config.scale_count, 9, config.qi_mode_count),
        "m": model,
    }


def create_organism_state(
    config: CassiOrganismConfig,
    qi_state: QiFieldState,
    world_state: CassiWorldModelState,
    *,
    metadata: bytes | bytearray | memoryview | Mapping[str, Any] = {},
) -> CassiOrganismState:
    base = empty_organism_state(config, device=qi_state.field.device, metadata=metadata)
    return successor_organism_state(base, config, sectors=_state_sectors(config, qi_state, world_state))




def organism_state_sha256(state: CassiOrganismState, config: CassiOrganismConfig) -> str:
    state.validate(config)
    arena = state._arena.detach().contiguous().cpu()
    header = _canonical(
        {
            "schema": ORGANISM_CHECKPOINT_SCHEMA,
            "layout_id": ORGANISM_LAYOUT_ID,
            "config_fingerprint": config.fingerprint,
            "layout_fingerprint": CassiOrganismLayout.build(config).fingerprint,
            "shape": list(arena.shape),
            "dtype": "torch.float32",
            "metadata_sha256": _digest(state.metadata),
        }
    )
    return _digest(header + state.metadata + arena.numpy().tobytes())


def dump_organism_state_bytes(state: CassiOrganismState, config: CassiOrganismConfig) -> bytes:
    state.validate(config)
    payload = {
        "schema": ORGANISM_CHECKPOINT_SCHEMA,
        "layout_id": ORGANISM_LAYOUT_ID,
        "constitution_schema": config.constitution_schema,
        "config": config.to_dict(),
        "config_fingerprint": config.fingerprint,
        "layout_fingerprint": CassiOrganismLayout.build(config).fingerprint,
        "state_sha256": organism_state_sha256(state, config),
        "metadata": state.metadata,
        "arena": state._arena.detach().contiguous().cpu(),
    }
    stream = io.BytesIO()
    try:
        torch.save(payload, stream)
    except Exception as error:
        raise CassiOrganismError(f"organism checkpoint cannot be serialized: {error}") from error
    serialized = stream.getvalue()
    if not serialized or len(serialized) > _MAX_CHECKPOINT_BYTES:
        raise CassiOrganismError("organism checkpoint exceeds its bounded size")
    return serialized


def _coerce_checkpoint_bytes(value: bytes | bytearray | memoryview) -> bytes:
    if isinstance(value, bool) or not isinstance(value, (bytes, bytearray, memoryview)):
        raise CassiOrganismError("organism checkpoint must be bytes")
    if len(value) < 1 or len(value) > _MAX_CHECKPOINT_BYTES:
        raise CassiOrganismError("organism checkpoint exceeds its bounded size")
    return bytes(value)


def load_organism_state_bytes(
    payload: bytes | bytearray | memoryview,
    config: CassiOrganismConfig,
    *,
    device: torch.device | str = "cpu",
) -> CassiOrganismState:
    serialized = _coerce_checkpoint_bytes(payload)
    try:
        target = torch.device(device)
        value = torch.load(io.BytesIO(serialized), map_location=target, weights_only=True)
    except Exception as error:
        raise CassiOrganismError(f"organism checkpoint cannot be loaded: {error}") from error
    if not isinstance(value, dict):
        raise CassiOrganismError("organism checkpoint root must be a mapping")
    if value.get("schema") != ORGANISM_CHECKPOINT_SCHEMA:
        if any(key in value for key in ("field", "stochastic", "step", "qi_checkpoint", "world_runtime", "agent_runtime")):
            raise CassiOrganismError("legacy split-state artifact is rejected; no implicit conversion is permitted")
        raise CassiOrganismError("organism checkpoint schema mismatch")
    expected_keys = {
        "schema",
        "layout_id",
        "constitution_schema",
        "config",
        "config_fingerprint",
        "layout_fingerprint",
        "state_sha256",
        "metadata",
        "arena",
    }
    if set(value) != expected_keys:
        raise CassiOrganismError("organism checkpoint fields are non-canonical")
    loaded_config = CassiOrganismConfig.from_dict(value["config"])
    layout = CassiOrganismLayout.build(config)
    if loaded_config != config or value["config_fingerprint"] != config.fingerprint:
        raise CassiOrganismError("organism checkpoint configuration mismatch")
    if value["layout_id"] != ORGANISM_LAYOUT_ID or value["layout_fingerprint"] != layout.fingerprint:
        raise CassiOrganismError("organism checkpoint layout mismatch")
    if value["constitution_schema"] != config.constitution_schema:
        raise CassiOrganismError("organism checkpoint constitution mismatch")
    arena = value.get("arena")
    if not torch.is_tensor(arena):
        raise CassiOrganismError("organism checkpoint is missing its sole adaptive tensor")
    if arena.dtype is not torch.float32:
        raise CassiOrganismError("organism checkpoint arena must use torch.float32")
    if tuple(arena.shape) != config.arena_shape:
        raise CassiOrganismError(f"organism checkpoint arena must have shape {config.arena_shape}")
    try:
        owned = arena.detach().to(device=target, dtype=torch.float32).clone()
    except Exception as error:
        raise CassiOrganismError(f"organism arena cannot be restored: {error}") from error
    result = CassiOrganismState._from_owned(
        owned,
        config.fingerprint,
        layout,
        _canonical_metadata(value["metadata"]),
    )
    result.validate(config, device=target)
    if organism_state_sha256(result, config) != _require_digest("organism state SHA-256", value["state_sha256"]):
        raise CassiOrganismError("organism checkpoint state hash mismatch")
    return result


def save_organism_state(path: Path | str, state: CassiOrganismState, config: CassiOrganismConfig) -> str:
    target = Path(path)
    serialized = dump_organism_state_bytes(state, config)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent, delete=False)
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(serialized)
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return _digest(serialized)


def load_organism_state(
    path: Path | str,
    config: CassiOrganismConfig,
    *,
    device: torch.device | str = "cpu",
) -> CassiOrganismState:
    target = Path(path)
    if not target.is_file():
        raise CassiOrganismError(f"organism checkpoint does not exist: {target}")
    with target.open("rb") as handle:
        payload = handle.read(_MAX_CHECKPOINT_BYTES + 1)
    return load_organism_state_bytes(payload, config, device=device)


__all__ = [
    "ORGANISM_CHECKPOINT_SCHEMA",
    "ORGANISM_CONSTITUTION_SCHEMA",
    "ORGANISM_LAYOUT_ID",
    "ORGANISM_SECTOR_ORDER",
    "CassiArenaRange",
    "CassiOrganismConfig",
    "CassiOrganismError",
    "CassiOrganismLayout",
    "CassiOrganismState",
    "create_organism_state",
    "dump_organism_state_bytes",
    "empty_organism_state",
    "load_organism_state",
    "load_organism_state_bytes",
    "organism_state_sha256",
    "qi_state_from_organism",
    "save_organism_state",
    "successor_organism_state",
    "world_state_from_organism",
]
