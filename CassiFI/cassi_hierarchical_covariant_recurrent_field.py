"""Field-owned hierarchical shrinkage for regime-covariant trajectory memory.

This V3 operator keeps the V2 causal coordinates and identity-bound rings but
fits them in an isotropic/anisotropic basis.  The shared coefficient multiplies
full jerk (radial plus transverse); a second coefficient multiplies the radial
minus transverse departure.  A stronger hierarchical ridge shrinks that
anisotropic departure to zero, and the field only releases it after independent
training worlds provide sufficient evidence.

All persistent adaptive values remain in the inherited float64 field tensor.
Per-world sufficient statistics are temporary training variables; only their
bounded support count and evidence sum are committed to the field.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import torch

from cassi_regime_covariant_recurrent_field import (
    CovariantFieldConfig,
    CovariantFieldError,
    CovariantForecast,
    CovariantFrame,
    RegimeCovariantRecurrentField,
    RegimeCovariantState,
)


SCHEMA = "cassifi.hierarchical-regime-covariant-recurrent-field.v3"
_MIN_RATIO = 1e-12


@dataclass(frozen=True, slots=True)
class HierarchicalCovariantFieldConfig:
    """Static layout and shrinkage law for one V3 recurrent field."""

    present_width: int
    max_identities: int = 256
    lags: tuple[int, ...] = (1, 2, 4, 8)
    snapshot_ridge: float = 1e-10
    correction_ridge: float = 0.1
    anisotropy_ridge: float = 8.0
    anisotropy_support_threshold: float = 0.2
    min_anisotropic_worlds: int = 2

    def __post_init__(self) -> None:
        # Delegate layout and common numeric validation to the immutable V2
        # configuration without changing that configuration or its receipts.
        CovariantFieldConfig(
            present_width=self.present_width,
            max_identities=self.max_identities,
            lags=self.lags,
            snapshot_ridge=self.snapshot_ridge,
            correction_ridge=self.correction_ridge,
        )
        for name, value in (
            ("anisotropy_ridge", self.anisotropy_ridge),
            ("anisotropy_support_threshold", self.anisotropy_support_threshold),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float, np.number)):
                raise CovariantFieldError(f"{name} must be numeric")
            numeric = float(value)
            if not np.isfinite(numeric) or numeric < 0.0:
                raise CovariantFieldError(f"{name} must be finite and nonnegative")
            object.__setattr__(self, name, numeric)
        if isinstance(self.min_anisotropic_worlds, bool) or not isinstance(
            self.min_anisotropic_worlds, (int, np.integer)
        ):
            raise CovariantFieldError("min_anisotropic_worlds must be an integer")
        if not 1 <= int(self.min_anisotropic_worlds) <= 1_000_000:
            raise CovariantFieldError("min_anisotropic_worlds is outside 1..1000000")
        object.__setattr__(self, "min_anisotropic_worlds", int(self.min_anisotropic_worlds))

    @property
    def base_config(self) -> CovariantFieldConfig:
        return CovariantFieldConfig(
            present_width=self.present_width,
            max_identities=self.max_identities,
            lags=self.lags,
            snapshot_ridge=self.snapshot_ridge,
            correction_ridge=self.correction_ridge,
        )


class HierarchicalCovariantRecurrentField(RegimeCovariantRecurrentField):
    """V2 covariant coordinates with field-owned anisotropy shrinkage."""

    def __init__(self, config: HierarchicalCovariantFieldConfig) -> None:
        self.hierarchical_config = config
        super().__init__(config.base_config)

    def initial_state(self) -> RegimeCovariantState:
        field = torch.zeros(self.config.shape, dtype=torch.float64, device="cpu")
        flat = field.reshape(-1)
        flat[0] = 314159265.0
        flat[1] = 2.0
        flat[2] = float(self.config.present_width)
        flat[3] = float(self.config.max_identities)
        flat[4] = float(self.config.max_lag)
        flat[5] = float(len(self.config.lags))
        flat[6] = self.config.snapshot_ridge
        flat[7] = self.config.correction_ridge
        flat[16] = self.hierarchical_config.anisotropy_ridge
        flat[17] = self.hierarchical_config.anisotropy_support_threshold
        flat[18] = float(self.hierarchical_config.min_anisotropic_worlds)
        flat[19] = 3.0
        flat[self._layout.lags] = torch.tensor(
            self.config.lags, dtype=torch.float64
        )
        state = RegimeCovariantState(field=field)
        self.validate_state(state)
        return state

    def validate_state(self, state: RegimeCovariantState) -> None:
        super().validate_state(state)
        flat = state.field.detach().numpy().reshape(-1)
        if flat[14] < 0.0 or flat[14] > flat[11]:
            raise CovariantFieldError("anisotropic support count is invalid")
        if flat[15] < 0.0 or not np.isfinite(flat[15]):
            raise CovariantFieldError("anisotropic evidence is invalid")
        expected = (
            self.hierarchical_config.anisotropy_ridge,
            self.hierarchical_config.anisotropy_support_threshold,
            float(self.hierarchical_config.min_anisotropic_worlds),
            3.0,
        )
        if not np.array_equal(flat[16:20], np.asarray(expected, dtype=np.float64)):
            raise CovariantFieldError("hierarchical shrinkage configuration differs")

    def _hierarchical_solve(
        self,
        gram: np.ndarray,
        cross: np.ndarray,
        *,
        anisotropy_penalty: bool,
    ) -> np.ndarray:
        scale = max(1.0, float(np.trace(gram)) / max(1, gram.shape[0]))
        penalties = np.asarray(
            (
                self.hierarchical_config.correction_ridge,
                self.hierarchical_config.anisotropy_ridge
                if anisotropy_penalty
                else 0.0,
            ),
            dtype=np.float64,
        )
        matrix = 0.5 * (gram + gram.T) + scale * np.diag(penalties)
        return np.linalg.solve(matrix, cross)

    @staticmethod
    def _basis(correction: np.ndarray) -> np.ndarray:
        return np.stack(
            (correction[:, 0] + correction[:, 1], correction[:, 0] - correction[:, 1]),
            axis=1,
        )

    def learn_world(
        self,
        state: RegimeCovariantState,
        frames: Iterable[CovariantFrame],
    ) -> RegimeCovariantState:
        """Accumulate shared correction evidence and bounded anisotropic support."""

        successor, flat = self._mutable(state)
        if flat[8] != 1.0:
            raise CovariantFieldError("snapshot baseline must be fitted before learning")
        self._clear_tracks(flat)
        gram = self._view(
            flat,
            self._layout.correction_gram,
            (2, 2),
        )
        cross = flat[self._layout.correction_cross]
        world_gram = np.zeros((2, 2), dtype=np.float64)
        world_cross = np.zeros(2, dtype=np.float64)
        learned = 0
        skipped = 0
        previous_tick = 0
        frame_count = 0
        for raw in frames:
            frame = self._canonical_frame(raw, require_target=True)
            if frame.tick <= previous_tick:
                raise CovariantFieldError("world ticks must be strictly increasing")
            previous_tick = frame.tick
            frame_count += 1
            assert frame.target is not None
            past_position, past_velocity, resolved = self._past_coordinates(
                flat, tick=frame.tick, query_ids=frame.identity_ids
            )
            if np.any(resolved):
                causal, correction, scale = self._covariant_coordinates(
                    frame, past_position, past_velocity
                )
                selected = resolved & (scale > 0.0)
                if np.any(selected):
                    features = self._basis(correction[selected]) / scale[
                        selected, None, None
                    ]
                    residual = (frame.target[selected] - causal[selected]) / scale[
                        selected, None
                    ]
                    local_gram = np.einsum("nci,ndi->cd", features, features)
                    local_cross = np.einsum("nci,ni->c", features, residual)
                    gram += local_gram
                    cross += local_cross
                    world_gram += local_gram
                    world_cross += local_cross
                    learned += int(np.count_nonzero(selected))
                skipped += int(np.count_nonzero(resolved & ~selected))
            self._admit_current(flat, frame)
        if frame_count == 0 or learned == 0:
            raise CovariantFieldError("world does not contain usable covariant history")
        gram[:] = 0.5 * (gram + gram.T)
        world_gram[:] = 0.5 * (world_gram + world_gram.T)
        local_coefficients = self._ridge_solve(
            world_gram,
            world_cross,
            relative_ridge=self.hierarchical_config.correction_ridge,
        )
        isotropic_scale = max(abs(float(local_coefficients[0])), 0.05)
        anisotropic_ratio = abs(float(local_coefficients[1])) / isotropic_scale
        if anisotropic_ratio >= self.hierarchical_config.anisotropy_support_threshold:
            flat[14] += 1.0
        flat[15] += anisotropic_ratio
        flat[10] += float(learned)
        flat[11] += 1.0
        flat[13] += float(skipped)
        self.validate_state(successor)
        return successor

    def forecast_isotropic(
        self,
        state: RegimeCovariantState,
        frames: Iterable[CovariantFrame],
        *,
        break_identity: bool = False,
    ) -> CovariantForecast:
        """Read the shared coefficient while suppressing anisotropic departure."""

        isolated = RegimeCovariantState(field=state.field.clone())
        flat = isolated.field.numpy().reshape(-1)
        flat[14] = 0.0
        return super().forecast_world(
            isolated,
            frames,
            break_identity=break_identity,
        )

    def _basis_coefficients(self, flat: np.ndarray) -> np.ndarray:
        if flat[10] == 0.0:
            return np.zeros(2, dtype=np.float64)
        coefficients = self._hierarchical_solve(
            self._view(flat, self._layout.correction_gram, (2, 2)),
            flat[self._layout.correction_cross],
            anisotropy_penalty=True,
        )
        if flat[14] < float(self.hierarchical_config.min_anisotropic_worlds):
            coefficients[1] = 0.0
        return coefficients

    def _correction_coefficients(self, flat: np.ndarray) -> np.ndarray:
        """Return radial/transverse coefficients expected by the inherited forecast."""

        isotropic, anisotropic = self._basis_coefficients(flat)
        return np.asarray(
            (isotropic + anisotropic, isotropic - anisotropic),
            dtype=np.float64,
        )

    def inspect(self, state: RegimeCovariantState) -> dict[str, object]:
        flat = self._flat(state)
        result = super().inspect(state)
        basis_coefficients = self._basis_coefficients(flat)
        result.update(
            {
                "schema": SCHEMA,
                "anisotropy_ridge": self.hierarchical_config.anisotropy_ridge,
                "anisotropy_support_threshold": self.hierarchical_config.anisotropy_support_threshold,
                "min_anisotropic_worlds": self.hierarchical_config.min_anisotropic_worlds,
                "anisotropic_world_support": int(flat[14]),
                "anisotropic_evidence_sum": float(flat[15]),
                "basis_coefficients": basis_coefficients.tolist(),
                "correction_coefficients": self._correction_coefficients(flat).tolist(),
                "coordinate_contract": (
                    "causal d1 plus hierarchically shrunk isotropic jerk and "
                    "field-released radial/transverse departure"
                ),
                "adaptive_owner": "RegimeCovariantState.field",
            }
        )
        return result


__all__ = [
    "SCHEMA",
    "HierarchicalCovariantFieldConfig",
    "HierarchicalCovariantRecurrentField",
    "RegimeCovariantState",
    "CovariantForecast",
    "CovariantFrame",
]
