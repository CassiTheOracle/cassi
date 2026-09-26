"""Modal field reference for the native CassiQwen hot path.

The production recurrence is a deliberately linearized spectral fast path:
the canonical 2,560 conjugate mode pairs are retained directly, the dense
positive/negative spatial split is replaced by its signed epsilon equivalent,
and the source-free periodic two-fluid operator is evolved exactly per mode.
The Godot dense engine remains the parity/reference oracle; this module freezes
the new native recurrence rather than claiming dense-grid bit identity.
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from l18_field_output_systems import DIMENSION, GRID_N, MODE_COUNT, PHI, canonical_modes


DT = 0.005
OMEGA2 = 20.0
RETAINED_WEIGHT = 0.9
STEPS_PER_LAYER = 4
LAYER_COUNT = 64

class ModalFieldError(ValueError):
    """Invalid modal state, direction, or configuration."""


def _finite_scalar(value: float, label: str) -> float:
    if not isinstance(value, (int, float, np.integer, np.floating)) or not math.isfinite(float(value)):
        raise ModalFieldError(f"{label} must be finite")
    return float(value)


def laplacian_symbol(kx: int, ky: int, kz: int, *, grid_n: int = GRID_N) -> float:
    """Return the exact cube-mode symbol of ``cassi_two_fluid.glsl``."""
    if grid_n <= 0:
        raise ModalFieldError("grid_n must be positive")
    tx = 2.0 * math.pi * int(kx) / grid_n
    ty = 2.0 * math.pi * int(ky) / grid_n
    tz = 2.0 * math.pi * int(kz) / grid_n
    cx, cy, cz = math.cos(tx), math.cos(ty), math.cos(tz)
    axis = (1.0 / 3.0) * ((cx - 1.0) + (cy - 1.0) + (cz - 1.0))
    faces = (2.0 / 3.0) * ((cx * cy - 1.0) + (cy * cz - 1.0) + (cz * cx - 1.0))
    return axis + faces


def one_step_matrix(symbol: float, *, dt: float = DT, omega2: float = OMEGA2, phi: float = PHI) -> np.ndarray:
    """Return one exact shader leapfrog/symplectic-Euler transition."""
    symbol = _finite_scalar(symbol, "Laplacian symbol")
    dt = _finite_scalar(dt, "dt")
    omega2 = _finite_scalar(omega2, "omega2")
    phi = _finite_scalar(phi, "phi")
    if dt <= 0.0 or omega2 < 0.0 or phi <= 0.0:
        raise ModalFieldError("dt and phi must be positive; omega2 must be non-negative")
    ay_y = symbol - omega2
    ay_i = omega2 * phi
    ai_y = omega2
    ai_i = symbol - omega2 * phi
    dt2 = dt * dt
    return np.asarray(
        [
            [1.0 + dt2 * ay_y, dt2 * ay_i, dt, 0.0],
            [dt2 * ai_y, 1.0 + dt2 * ai_i, 0.0, dt],
            [dt * ay_y, dt * ay_i, 1.0, 0.0],
            [dt * ai_y, dt * ai_i, 0.0, 1.0],
        ],
        dtype=np.float64,
    )


def transition_matrices(*, steps: int = STEPS_PER_LAYER) -> np.ndarray:
    """Return one precomputed 4x4 transition for each frozen canonical mode."""
    if not isinstance(steps, int) or isinstance(steps, bool) or steps < 0:
        raise ModalFieldError("steps must be a non-negative integer")
    result = np.empty((MODE_COUNT, 4, 4), dtype=np.float32)
    for index, mode in enumerate(canonical_modes()):
        base = one_step_matrix(laplacian_symbol(mode.kx, mode.ky, mode.kz))
        result[index] = np.linalg.matrix_power(base, steps).astype(np.float32)
    if not np.isfinite(result).all():
        raise ModalFieldError("transition matrix contains non-finite values")
    return np.ascontiguousarray(result)


def normalize_direction(direction: np.ndarray) -> np.ndarray:
    values = np.asarray(direction, dtype=np.float64)
    if values.shape != (DIMENSION,) or not np.isfinite(values).all():
        raise ModalFieldError(f"direction must be finite with shape ({DIMENSION},)")
    norm = float(np.linalg.norm(values))
    if not math.isfinite(norm) or norm <= 0.0:
        raise ModalFieldError("direction must have positive finite norm")
    return np.ascontiguousarray((values / norm).astype(np.float32))


def direction_modes(direction: np.ndarray) -> np.ndarray:
    """Map a normalized 5,120-vector to its canonical complex coefficients."""
    values = normalize_direction(direction)
    return np.ascontiguousarray(values[0::2] - 1j * values[1::2], dtype=np.complex64)


@dataclass
class ModalFieldState:
    """Per-sequence FP32 modal state: EY, EI, velocity-Y, velocity-I."""

    values: np.ndarray
    layer_updates: int = 0

    @classmethod
    def zeros(cls) -> "ModalFieldState":
        return cls(np.zeros((MODE_COUNT, 4), dtype=np.complex64))

    def __post_init__(self) -> None:
        self.values = np.ascontiguousarray(self.values, dtype=np.complex64)
        if self.values.shape != (MODE_COUNT, 4) or not np.isfinite(self.values).all():
            raise ModalFieldError(f"modal state must be finite with shape ({MODE_COUNT}, 4)")
        if not isinstance(self.layer_updates, int) or isinstance(self.layer_updates, bool) or self.layer_updates < 0:
            raise ModalFieldError("layer_updates must be a non-negative integer")

    def deposit(self, direction: np.ndarray, *, retained_weight: float = RETAINED_WEIGHT) -> None:
        retained = _finite_scalar(retained_weight, "retained_weight")
        if not 0.0 <= retained <= 1.0:
            raise ModalFieldError("retained_weight must be in [0, 1]")
        incoming = 1.0 - retained
        modes = direction_modes(direction)
        # The fundamental component of the spatial positive/negative split is
        # EY=d/2 and EI=-d/(2*phi), which preserves epsilon=EY-phi*EI=d.
        self.values[:, 0] = retained * self.values[:, 0] + incoming * (0.5 * modes)
        self.values[:, 1] = retained * self.values[:, 1] - incoming * (0.5 / PHI * modes)
        if not np.isfinite(self.values).all():
            raise ModalFieldError("deposit produced non-finite state")

    def evolve(self, transitions: np.ndarray) -> None:
        matrices = np.asarray(transitions, dtype=np.float32)
        if matrices.shape != (MODE_COUNT, 4, 4) or not np.isfinite(matrices).all():
            raise ModalFieldError(f"transitions must be finite with shape ({MODE_COUNT}, 4, 4)")
        self.values = np.ascontiguousarray(np.einsum("mij,mj->mi", matrices, self.values, optimize=True), dtype=np.complex64)
        if not np.isfinite(self.values).all():
            raise ModalFieldError("field evolution produced non-finite state")
        self.layer_updates += 1

    def update_layer(self, direction: np.ndarray, transitions: np.ndarray, *, retained_weight: float = RETAINED_WEIGHT) -> None:
        self.deposit(direction, retained_weight=retained_weight)
        self.evolve(transitions)

    def update_token(self, layer_directions: Iterable[np.ndarray], transitions: np.ndarray, *, retained_weight: float = RETAINED_WEIGHT) -> None:
        count = 0
        for direction in layer_directions:
            self.update_layer(direction, transitions, retained_weight=retained_weight)
            count += 1
        if count != LAYER_COUNT:
            raise ModalFieldError(f"one token requires exactly {LAYER_COUNT} layer directions, got {count}")

    def decode(self) -> np.ndarray:
        epsilon = self.values[:, 0] - np.float32(PHI) * self.values[:, 1]
        result = np.empty(DIMENSION, dtype=np.float32)
        result[0::2] = epsilon.real
        result[1::2] = -epsilon.imag
        if not np.isfinite(result).all():
            raise ModalFieldError("decoded field contains non-finite values")
        return np.ascontiguousarray(result)

    @property
    def byte_size(self) -> int:
        return int(self.values.nbytes)
